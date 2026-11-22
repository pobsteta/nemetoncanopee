"""Étape `prepare` : piles Sentinel-2 à 10 m et masque forêt, sur la grille de chaque dalle.

- Une pile par scène de l'année de vol : les bandes de `prepare.bandes` (celles à 20 m
  rééchantillonnées au plus proche voisin), plus une bande `clair` (1 si la classe SCL n'est
  pas dans `prepare.scl_mauvais`, 0 sinon). Une scène hors de l'année de vol est refusée.
- Le masque forêt : polygones BD Forêt rastérisés par centre de cellule (1 forêt, 0 sinon).
"""

from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize

from nemeton_canopee import grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_raster
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import controler_annee_de_vol, lire_manifeste, lire_scenes


def _controler_emprise(src: rasterio.DatasetReader, dalle: str, taille_m: int, nom: str) -> None:
    attendue = grille.emprise(dalle, taille_m)
    lue = tuple(round(v, 6) for v in src.bounds)
    if lue != tuple(float(v) for v in attendue) or src.crs.to_epsg() != 2154:
        raise DonneeRefusee(
            f"{nom} hors de la grille de la dalle {dalle} : emprise {lue}, {src.crs} "
            f"(règle : Lambert-93, grille alignée sur la dalle {attendue})"
        )


def pile_scene(conf: Configuration, dalle: str, fichiers: pd.DataFrame) -> np.ndarray:
    """Pile (bandes + `clair`, lignes, colonnes) en uint16 d'une scène, à la grille 10 m."""
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    forme = grille.forme(taille, pas)
    bandes: dict[str, np.ndarray] = {}
    for fichier in fichiers["fichier"]:
        chemin = exiger_fichier(conf.zone.racine / fichier, "ingest (scène absente)")
        with rasterio.open(chemin) as src:
            _controler_emprise(src, dalle, taille, fichier)
            lues = src.read(out_shape=(src.count, *forme), resampling=Resampling.nearest)
            for nom, valeurs in zip(src.descriptions, lues, strict=True):
                bandes[str(nom)] = valeurs
    voulues = [*conf.prepare["bandes"], conf.prepare["bande_scl"]]
    absentes = [b for b in voulues if b not in bandes]
    if absentes:
        raise EntreeManquante(f"bandes absentes pour la dalle {dalle} : {absentes}")
    scl = bandes[conf.prepare["bande_scl"]]
    clair = (~np.isin(scl, conf.prepare["scl_mauvais"])).astype("uint16")
    return np.stack([bandes[b].astype("uint16") for b in conf.prepare["bandes"]] + [clair])


def masque_foret(conf: Configuration, dalle: str) -> np.ndarray:
    """Masque forêt 10 m (uint8) : 1 si le centre de la cellule tombe dans un polygone."""
    if conf.zone.foret_formations != "tout":
        raise DonneeRefusee(
            f"foret_formations={conf.zone.foret_formations!r} : seul « tout » existe au jalon 1"
        )
    polygones = gpd.read_file(exiger_fichier(conf.zone.chemin("foret", dalle=dalle), "ingest"))
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    forme = grille.forme(taille, pas)
    geometries = [g for g in polygones.to_crs(conf.grille["crs"]).geometry if g is not None]
    if not geometries:
        return np.zeros(forme, dtype="uint8")
    return rasterize(
        [(g, 1) for g in geometries],
        out_shape=forme,
        transform=grille.transformation(dalle, taille, pas),
        fill=0,
        all_touched=False,  # règle des centres (spec § 2)
        dtype="uint8",
    )


def executer(conf: Configuration, dalles: Sequence[str] | None = None) -> None:
    """Prépare les scènes et le masque forêt des dalles du manifeste."""
    ch = Chemins(conf.travail)
    scenes = lire_scenes(ch)
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    crs = conf.grille["crs"]
    noms = [*conf.prepare["bandes"], "clair"]
    for dalle in lire_manifeste(ch, dalles):
        transform = grille.transformation(dalle.id, taille, pas)
        a_faire = scenes[scenes["dalle"] == dalle.id]
        for ligne in a_faire.itertuples():
            controler_annee_de_vol(dalle.id, dalle.annee, ligne.scene, ligne.date_scene)
        ecrites = set()
        for scene, fichiers in a_faire.groupby("scene", sort=True):
            chemin = ch.scene_preparee(dalle.annee, dalle.id, str(scene))
            tags = {"scene": scene, "date_scene": fichiers["date_scene"].iloc[0], "dalle": dalle.id}
            pile = pile_scene(conf, dalle.id, fichiers)
            ecrire_raster(chemin, pile, transform, crs, tags=tags, descriptions=noms)
            ecrites.add(chemin)
        # Une étape relancée remplace ses sorties : une scène retirée du manifeste disparaît.
        for perimee in set(ch.scenes_preparees(dalle.annee, dalle.id)) - ecrites:
            perimee.unlink()
        foret = masque_foret(conf, dalle.id)
        tags = {"dalle": dalle.id, "regle": "centre de cellule dans un polygone BD Forêt V2"}
        ecrire_raster(ch.foret(dalle.id), foret, transform, crs, tags=tags)
