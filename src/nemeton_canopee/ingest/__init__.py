"""Étape `ingest` : lit le jeu de la zone et écrit le manifeste des dalles et des scènes.

Au jalon 1, seul le mode `local` existe (jeu embarqué, sans réseau). L'étape contrôle
l'appariement temporel : une scène Sentinel-2 datée hors de l'année de vol de sa dalle est
refusée (code 3), jamais filtrée en silence (plan 004, décision 8).

Sorties : `ingest/manifeste.parquet` (une ligne par dalle, avec l'année et la date de vol et
la version des données) et `ingest/scenes.parquet` (une ligne par fichier de scène).
Relancée sur quelques dalles (`--dalles`), l'étape remplace leurs lignes et garde les autres.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from nemeton_canopee import grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration, Zone
from nemeton_canopee.ecriture import atomique
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier

COLONNES_MANIFESTE = [
    "id",
    "xmin",
    "ymin",
    "xmax",
    "ymax",
    "date_vol_debut",
    "date_vol_fin",
    "date_vol",
    "annee",
    "mission",
    "source",
    "geometry",
    "version_donnees",
]
COLONNES_SCENES = [
    "dalle",
    "annee",
    "scene",
    "date_scene",
    "nuage_scene_pct",
    "processing_baseline",
    "resolution_m",
    "bandes",
    "fichier",
]


@dataclass(frozen=True)
class Dalle:
    """Une dalle du manifeste : identifiant, année et date de vol, version des données."""

    id: str
    annee: int
    date_vol: str
    version_donnees: str


def controler_annees(demandees: set[int], disponibles: set[int]) -> None:
    """Refuse une année demandée (`--annees`) qui n'a aucune dalle (code 3, rien d'écrit)."""
    vides = sorted(set(demandees) - set(disponibles))
    if vides:
        raise DonneeRefusee(
            f"année {', '.join(map(str, vides))} demandée sans aucune dalle volée cette année-là "
            f"(années de vol disponibles : {sorted(int(a) for a in disponibles)} ; règle : une "
            "dalle n'est traitée que pour son année de vol)"
        )


def choisir(disponibles: Sequence[str], demandees: Sequence[str] | None) -> list[str]:
    """Dalles demandées (toutes par défaut) ; identifiant invalide ou hors zone refusé."""
    if not demandees:
        return sorted(disponibles)
    for dalle in demandees:
        grille.controler_identifiant(dalle)
    inconnues = sorted(set(demandees) - set(disponibles))
    if inconnues:
        raise DonneeRefusee(
            f"dalles {', '.join(inconnues)} refusées : hors de la zone {sorted(disponibles)} "
            "(règle : seules les dalles déclarées dans conf/zones sont traitées)"
        )
    return sorted(set(demandees))


def date_de_vol(debut: str, fin: str) -> tuple[str, int]:
    """(date de vol, année de vol) ; un vol à cheval sur deux années est refusé."""
    debut, fin = str(debut)[:10], str(fin)[:10]
    if debut[:4] != fin[:4]:
        raise DonneeRefusee(
            f"vol du {debut} au {fin} sur deux années : année de vol ambiguë "
            "(règle : appariement à l'année de vol)"
        )
    return (debut if debut == fin else f"{debut}/{fin}"), int(debut[:4])


def controler_annee_de_vol(dalle: str, annee: int, scene: str, date_scene: str) -> None:
    """Refuse une scène datée hors de l'année de vol de sa dalle (CLAUDE.md, appariement)."""
    if int(str(date_scene)[:4]) != annee:
        raise DonneeRefusee(
            f"scène {scene} du {str(date_scene)[:10]} refusée pour la dalle {dalle} : "
            f"hors de l'année de vol {annee} (règle : appariement à l'année de vol)"
        )


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def version_donnees(zone: Zone, scenes: pd.DataFrame) -> str:
    """`{nom de zone}-` + 12 caractères du sha256 des fichiers d'entrée de la zone, triés."""
    fichiers = {zone.chemin(cle) for cle in ("manifeste", "scenes", "decoupage")}
    for dalle in zone.dalles:
        fichiers |= {zone.chemin("mnh", dalle=dalle), zone.chemin("foret", dalle=dalle)}
    fichiers |= {zone.racine / f for f in scenes.loc[scenes["dalle"].isin(zone.dalles), "fichier"]}
    lignes = []
    for f in sorted(fichiers):
        exiger_fichier(f, "ingest (jeu de la zone incomplet)")
        lignes.append(f"{f.relative_to(zone.racine).as_posix()}\t{_sha256(f)}\n")
    empreinte = hashlib.sha256("".join(lignes).encode("utf-8")).hexdigest()
    return f"{zone.nom}-{empreinte[:12]}"


def _fusionner(chemin: Path, nouvelles: pd.DataFrame, cle: str, tri: list[str]) -> pd.DataFrame:
    """Remplace dans le fichier existant les lignes des dalles de `nouvelles`, garde les autres."""
    if chemin.is_file():
        anciennes = pd.read_parquet(chemin)
        anciennes = anciennes[~anciennes[cle].isin(nouvelles[cle])]
        nouvelles = pd.concat([anciennes, nouvelles], ignore_index=True)
    return nouvelles.sort_values(tri, kind="stable").reset_index(drop=True)


def _ecrire_parquet(chemin: Path, table: pd.DataFrame) -> None:
    with atomique(chemin) as tmp:
        table.to_parquet(tmp, index=False)


def executer(
    conf: Configuration,
    dalles: Sequence[str] | None = None,
    annees: Sequence[int] | None = None,
) -> list[str]:
    """Écrit le manifeste et les scènes des dalles choisies ; renvoie les dalles ingérées."""
    zone = conf.zone
    choisies = choisir(zone.dalles, dalles)
    annees_voulues = set(annees or zone.annees)

    manifeste = pd.read_parquet(exiger_fichier(zone.chemin("manifeste"), "ingest"))
    manquantes = sorted(set(choisies) - set(manifeste["id"]))
    if manquantes:
        raise EntreeManquante(f"dalles absentes du manifeste de la zone : {manquantes}")
    manifeste = manifeste[manifeste["id"].isin(choisies)].copy()
    vols = [
        date_de_vol(a, b)
        for a, b in zip(manifeste.date_vol_debut, manifeste.date_vol_fin, strict=True)
    ]
    manifeste["date_vol"] = [v[0] for v in vols]
    manifeste["annee"] = [v[1] for v in vols]
    controler_annees(annees_voulues if annees else set(), set(manifeste["annee"]))
    manifeste = manifeste[manifeste["annee"].isin(annees_voulues)]
    if manifeste.empty:
        raise DonneeRefusee(
            f"aucune dalle choisie n'a été volée en {sorted(annees_voulues)} "
            "(règle : une dalle n'est traitée que pour son année de vol)"
        )

    scenes = pd.read_csv(exiger_fichier(zone.chemin("scenes"), "ingest"), dtype=str)
    version = version_donnees(zone, scenes)
    manifeste["version_donnees"] = version
    annee_de = dict(zip(manifeste["id"], manifeste["annee"], strict=True))
    scenes = scenes[scenes["dalle"].isin(annee_de)].copy()
    for ligne in scenes.itertuples():
        controler_annee_de_vol(ligne.dalle, annee_de[ligne.dalle], ligne.scene, ligne.date_scene)
    sans_scene = sorted(set(annee_de) - set(scenes["dalle"]))
    if sans_scene:
        raise EntreeManquante(f"aucune scène Sentinel-2 pour les dalles {sans_scene}")
    scenes["annee"] = scenes["dalle"].map(annee_de).astype("int64")
    scenes["resolution_m"] = scenes["resolution_m"].astype("int64")

    ch = Chemins(conf.travail)
    table = _fusionner(ch.manifeste, manifeste[COLONNES_MANIFESTE], "id", ["id"])
    # La version des données porte sur toute la zone : elle est la même pour chaque dalle.
    table["version_donnees"] = version
    _ecrire_parquet(ch.manifeste, table)
    _ecrire_parquet(
        ch.scenes,
        _fusionner(ch.scenes, scenes[COLONNES_SCENES], "dalle", ["dalle", "scene", "fichier"]),
    )
    return sorted(annee_de)


def lire_manifeste(
    ch: Chemins,
    dalles: Sequence[str] | None = None,
    annees: Sequence[int] | None = None,
) -> list[Dalle]:
    """Dalles du manifeste écrit par `ingest`, filtrées par identifiant et par année."""
    table = pd.read_parquet(exiger_fichier(ch.manifeste, "ingest"))
    if dalles:
        absentes = sorted(set(dalles) - set(table["id"]))
        if absentes:
            raise EntreeManquante(f"dalles absentes du manifeste : {absentes} (relancer ingest)")
        table = table[table["id"].isin(dalles)]
    if annees:
        controler_annees({int(a) for a in annees}, set(table["annee"]))
        table = table[table["annee"].isin([int(a) for a in annees])]
    return [
        Dalle(r.id, int(r.annee), str(r.date_vol), str(r.version_donnees))
        for r in table.sort_values("id").itertuples()
    ]


def lire_scenes(ch: Chemins) -> pd.DataFrame:
    """Table des scènes écrite par `ingest`."""
    return pd.read_parquet(exiger_fichier(ch.scenes, "ingest"))
