"""Descripteurs par cellule de 10 m pour le modèle LightGBM (mission 009, ADR 0004 option C).

Pour une dalle et son année de vol, à partir des fichiers de `prepare` et de la zone :

- **scène par scène** : bandes Sentinel-2 en réflectance (DN x `echelle_reflectance`) et
  indices normalisés (a - b) / (a + b) ; une cellule nuageuse (bande `clair` à 0) vaut NaN ;
- **entre scènes** : percentiles (p10, médiane, p90 par défaut) de chaque variable, NaN
  ignorés ;
- **voisinages** carrés (3 x 3 = 30 m, 5 x 5 = 50 m) : moyenne et écart-type de la médiane de
  chaque variable, sans déborder de la dalle ;
- **relief** tiré du MNT de la zone (m) : altitude, pente (degrés), exposition donnée par
  ses composantes nord (cos) et est (sin) de l'azimut de la ligne de plus grande pente ;
- **essence** BD Forêt V2 : valeur du champ choisi au centre de la cellule (texte, encodée
  en catégorie par le modèle, avec le vocabulaire des seules dalles d'apprentissage).

Tous les paramètres viennent de `conf/modele/gbm.yaml` (clé `descripteurs`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

from nemeton_canopee import grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier

BANDE_CLAIR = "clair"


@dataclass(frozen=True)
class Descripteurs:
    """Descripteurs numériques (n, lignes, colonnes), leurs noms, l'essence et le masque clair."""

    noms: list[str]
    valeurs: np.ndarray
    essence: np.ndarray  # texte par cellule, "" hors polygone
    clair: np.ndarray  # vrai si au moins une scène est claire


def variables_scene(
    pile: np.ndarray, noms_bandes: Sequence[str], params: Mapping[str, Any]
) -> dict[str, np.ndarray]:
    """Bandes (réflectance) et indices d'une scène ; NaN là où la scène n'est pas claire."""
    if BANDE_CLAIR not in noms_bandes:
        raise EntreeManquante("pile Sentinel-2 sans bande « clair » (relancer prepare)")
    index = {n: i for i, n in enumerate(noms_bandes)}
    clair = pile[index[BANDE_CLAIR]] == 1
    echelle = float(params["echelle_reflectance"])
    absentes = [b for b in params["bandes"] if b not in index]
    if absentes:
        raise EntreeManquante(f"bandes absentes des piles préparées : {absentes} (prepare)")
    reflectance = {
        b: np.where(clair, pile[index[b]].astype("float64") * echelle, np.nan)
        for b in params["bandes"]
    }
    sortie = dict(reflectance)
    for nom, (a, b) in (params.get("indices") or {}).items():
        if a not in reflectance or b not in reflectance:
            raise DonneeRefusee(
                f"indice {nom} : bandes {a}, {b} absentes de descripteurs.bandes (conf)"
            )
        somme = reflectance[a] + reflectance[b]
        with np.errstate(divide="ignore", invalid="ignore"):
            sortie[nom] = np.where(somme != 0, (reflectance[a] - reflectance[b]) / somme, np.nan)
    return sortie


def statistiques_entre_scenes(
    scenes: Sequence[Mapping[str, np.ndarray]], percentiles: Sequence[float]
) -> dict[str, np.ndarray]:
    """Percentiles de chaque variable entre scènes, NaN ignorés : clés `{variable}_p{q}`."""
    if not scenes:
        raise EntreeManquante("aucune scène préparée (relancer prepare)")
    sortie = {}
    for variable in scenes[0]:
        pile = np.stack([s[variable] for s in scenes])
        for q in percentiles:
            sortie[f"{variable}_p{q:g}"] = percentile_nan(pile, float(q))
    return sortie


def percentile_nan(pile: np.ndarray, q: float) -> np.ndarray:
    """Percentile `q` sur l'axe 0, NaN ignorés, interpolation linéaire (`np.nanpercentile`).

    Vectorisé : `np.nanpercentile` boucle cellule par cellule et coûte ~10 s par dalle.
    Une cellule sans aucune valeur vaut NaN.
    """
    trie = np.sort(pile, axis=0)  # NaN en dernier
    n = np.isfinite(pile).sum(axis=0)
    position = q / 100.0 * np.maximum(n - 1, 0)
    bas = np.floor(position).astype("int64")
    haut = np.minimum(bas + 1, np.maximum(n - 1, 0))
    v_bas = np.take_along_axis(trie, bas[None], axis=0)[0]
    v_haut = np.take_along_axis(trie, haut[None], axis=0)[0]
    valeur = v_bas + (v_haut - v_bas) * (position - bas)
    return np.where(n > 0, valeur, np.nan)


def voisinage(valeurs: np.ndarray, cote: int) -> tuple[np.ndarray, np.ndarray]:
    """Moyenne et écart-type (ddof 0) sur une fenêtre carrée de `cote` cellules, NaN ignorés.

    La fenêtre ne déborde pas de la dalle : au bord, seules les cellules de la dalle comptent.
    """
    if cote < 1 or cote % 2 == 0:
        raise DonneeRefusee(f"voisinage de côté {cote} refusé (règle : côté impair, >= 1)")
    r = cote // 2
    present = np.isfinite(valeurs)
    v = np.pad(np.where(present, valeurs, 0.0), r)
    n = np.pad(present.astype("float64"), r)
    fen_v = np.lib.stride_tricks.sliding_window_view(v, (cote, cote))
    fen_n = np.lib.stride_tricks.sliding_window_view(n, (cote, cote))
    compte = fen_n.sum(axis=(2, 3))
    with np.errstate(divide="ignore", invalid="ignore"):
        moyenne = fen_v.sum(axis=(2, 3)) / compte
        ecarts = (fen_v - moyenne[:, :, None, None]) ** 2 * fen_n
        ecart_type = np.sqrt(ecarts.sum(axis=(2, 3)) / compte)
    vide = compte == 0
    return np.where(vide, np.nan, moyenne), np.where(vide, np.nan, ecart_type)


def relief(mnt_m: np.ndarray, pas_m: float) -> dict[str, np.ndarray]:
    """Altitude (m), pente (degrés) et exposition (composantes nord et est de l'azimut).

    L'azimut est celui de la ligne de plus grande pente, vers l'aval, compté depuis le nord
    dans le sens horaire ; une cellule plate a une exposition NaN. Les lignes du raster vont
    du nord au sud.
    """
    d_lignes, d_colonnes = np.gradient(mnt_m, pas_m)
    dz_est, dz_nord = d_colonnes, -d_lignes
    norme = np.hypot(dz_est, dz_nord)
    with np.errstate(divide="ignore", invalid="ignore"):
        nord = np.where(norme > 0, -dz_nord / norme, np.nan)
        est = np.where(norme > 0, -dz_est / norme, np.nan)
    return {
        "altitude_m": mnt_m,
        "pente_deg": np.degrees(np.arctan(norme)),
        "exposition_nord": nord,
        "exposition_est": est,
    }


def lire_mnt(conf: Configuration, dalle: str) -> np.ndarray:
    """MNT de la dalle sur la grille 10 m, en m, NaN hors donnée."""
    cle = conf.modele["descripteurs"]["relief"]["fichier_zone"]
    if cle not in conf.zone.fichiers:
        raise EntreeManquante(
            f"la zone {conf.zone.nom!r} ne déclare pas le fichier {cle!r} (MNT) dans `fichiers` "
            "(règle : chemins des entrées dans conf/zones)"
        )
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    chemin = exiger_fichier(conf.zone.chemin(cle, dalle=dalle), "ingest (MNT absent)")
    with rasterio.open(chemin) as src:
        grille.controler_crs(src.crs, conf.grille["crs"], f"MNT de {dalle}")
        attendue = tuple(float(v) for v in grille.emprise(dalle, taille))
        if tuple(src.bounds) != attendue or src.res != (pas, pas):
            raise DonneeRefusee(
                f"MNT de {dalle} hors grille : emprise {tuple(src.bounds)}, pas {src.res} "
                f"(règle : grille {pas} m de la dalle {attendue})"
            )
        unite = src.tags().get("unite") or conf.zone.mnt_unite
        if unite is None:
            raise DonneeRefusee(
                f"MNT de {dalle} sans unité : ni tag `unite` dans le fichier, ni `mnt_unite` "
                "dans la zone (règle : unité du MNT déclarée, jamais supposée)"
            )
        if unite != "m":
            raise DonneeRefusee(f"MNT de {dalle} en {unite!r} (règle : MNT en mètres)")
        mnt = src.read(1).astype("float64")
        if src.nodata is not None:
            mnt[mnt == src.nodata] = np.nan
    return mnt


def essence_par_cellule(conf: Configuration, dalle: str) -> np.ndarray:
    """Valeur du champ d'essence BD Forêt au centre de chaque cellule ("" hors polygone)."""
    champ = conf.modele["descripteurs"]["essence"]["champ"]
    polygones = gpd.read_file(exiger_fichier(conf.zone.chemin("foret", dalle=dalle), "ingest"))
    if champ not in polygones.columns:
        raise DonneeRefusee(f"champ {champ!r} absent de la BD Forêt de {dalle} (conf essence)")
    polygones = polygones[polygones.geometry.notna()].to_crs(conf.grille["crs"])
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    forme = grille.forme(taille, pas)
    valeurs = polygones[champ].fillna("").astype(str)
    if "id" in polygones.columns:  # ordre stable : les recouvrements donnent toujours le même
        ordre = np.argsort(polygones["id"].astype(str).to_numpy(), kind="stable")
        polygones, valeurs = polygones.iloc[ordre], valeurs.iloc[ordre]
    vocab = sorted(set(valeurs) - {""})
    if not vocab:
        return np.full(forme, "", dtype=object)
    code = {v: i + 1 for i, v in enumerate(vocab)}
    formes = [(g, code[v]) for g, v in zip(polygones.geometry, valeurs, strict=True) if v]
    indices = rasterize(
        formes,
        out_shape=forme,
        transform=grille.transformation(dalle, taille, pas),
        fill=0,
        all_touched=False,  # règle des centres (spec § 2)
        dtype="int32",
    )
    table = np.array(["", *vocab], dtype=object)
    return table[indices]


def calculer(conf: Configuration, ch: Chemins, dalle: str, annee: int) -> Descripteurs:
    """Descripteurs d'une dalle pour son année de vol."""
    params = conf.modele["descripteurs"]
    scenes = []
    clair = None
    for chemin in ch.scenes_preparees(annee, dalle):
        with rasterio.open(chemin) as src:
            pile, noms = src.read(), list(src.descriptions)
        variables = variables_scene(pile, noms, params)
        scenes.append(variables)
        c = pile[noms.index(BANDE_CLAIR)] == 1
        clair = c if clair is None else clair | c
    if clair is None:
        raise EntreeManquante(f"aucune scène préparée pour {dalle} (relancer prepare)")
    percentiles = [float(q) for q in params["percentiles"]]
    stats = statistiques_entre_scenes(scenes, percentiles)
    q_centre = min(percentiles, key=lambda q: abs(q - 50))
    sortie: dict[str, np.ndarray] = dict(stats)
    for variable in scenes[0]:
        centre = stats[f"{variable}_p{q_centre:g}"]
        for cote in params["voisinages"]:
            moyenne, ecart = voisinage(centre, int(cote))
            sortie[f"{variable}_v{cote}_moy"] = moyenne
            sortie[f"{variable}_v{cote}_et"] = ecart
    sortie.update(relief(lire_mnt(conf, dalle), float(conf.grille["pas_m"])))
    noms = list(sortie)
    return Descripteurs(
        noms=noms,
        valeurs=np.stack([sortie[n] for n in noms]),
        essence=essence_par_cellule(conf, dalle),
        clair=clair,
    )
