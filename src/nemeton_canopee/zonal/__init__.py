"""Statistiques zonales des couches publiées, par polygone, année et couche (plan 004, § 4).

Le calcul est confié à `exactextract` (ADR 0001, A2), comme `exactextractr` côté nemeton :
chaque cellule pèse la fraction de sa surface couverte par le polygone ; les cellules nodata
sont exclues. Si un polygone touche plusieurs dalles, les COG concernés sont d'abord
assemblés en mémoire sur la grille commune (même pas, mêmes bords), puis mesurés d'un bloc.

`part_couverte` = somme des fractions des cellules valides × aire d'une cellule / aire du
polygone. L'unité est celle de la couche (cm pour la hauteur, décision 6).
`incertitude_moyenne` vaut NaN au jalon 1 (pas encore de couche d'incertitude).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pystac
import rasterio
from exactextract import exact_extract
from rasterio.io import MemoryFile
from rasterio.merge import merge
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante

COLONNES = [
    "id",
    "annee",
    "couche",
    "traitement",
    "unite",
    "moyenne",
    "mediane",
    "p10",
    "p90",
    "part_couverte",
    "incertitude_moyenne",
    "version_modele",
    "version_donnees",
    "date_vol",
    "dalles",
]
OPERATIONS = ["mean", "median", "quantile(q=0.1)", "quantile(q=0.9)", "count"]
SEPARATEUR = ";"


@dataclass(frozen=True)
class Tuile:
    """Un COG publié : sa dalle, son emprise et ses tags."""

    dalle: str
    chemin: Path
    emprise: tuple[float, float, float, float]
    pas: tuple[float, float]
    crs: str
    nodata: float
    tags: dict[str, str]


def tuiles_du_catalogue(
    catalogue: str | os.PathLike, couche: str, annee: int, traitement: str
) -> list[Tuile]:
    """COG du catalogue pour une couche, une année (année de la date de l'item) et un traitement."""
    cat = pystac.Catalog.from_file(str(catalogue))
    collection = cat.get_child(couche)
    if collection is None:
        raise EntreeManquante(f"couche {couche!r} absente du catalogue {catalogue}")
    tuiles = []
    for it in sorted(collection.get_items(), key=lambda i: i.id):
        date = it.datetime or it.common_metadata.start_datetime
        if date is None or date.year != annee or traitement not in it.assets:
            continue
        chemin = Path(it.assets[traitement].get_absolute_href())
        with rasterio.open(chemin) as src:
            tuiles.append(
                Tuile(
                    dalle=it.id.removeprefix(f"{couche}-{annee}-"),
                    chemin=chemin,
                    emprise=tuple(src.bounds),
                    pas=src.res,
                    crs=src.crs.to_string(),
                    nodata=src.nodata,
                    tags=src.tags(),
                )
            )
    return tuiles


def _uniques(tuiles: Sequence[Tuile], tag: str) -> str:
    return SEPARATEUR.join(sorted({t.tags.get(tag, "") for t in tuiles}))


def _cale(emprise: Sequence[float], pas: float) -> tuple[float, float, float, float]:
    """Emprise élargie aux bords de cellule les plus proches (grille aux multiples du pas)."""
    xmin, ymin, xmax, ymax = emprise
    return (
        float(np.floor(xmin / pas) * pas),
        float(np.floor(ymin / pas) * pas),
        float(np.ceil(xmax / pas) * pas),
        float(np.ceil(ymax / pas) * pas),
    )


def mesurer(geometrie: BaseGeometry, tuiles: Sequence[Tuile]) -> dict[str, float]:
    """Statistiques exactextract d'une géométrie sur l'assemblage des tuiles qu'elle touche."""
    vides = {"moyenne": np.nan, "mediane": np.nan, "p10": np.nan, "p90": np.nan, "poids": 0.0}
    if not tuiles:
        return vides
    pas = tuiles[0].pas[0]
    if any(t.pas != tuiles[0].pas or t.crs != tuiles[0].crs for t in tuiles):
        raise DonneeRefusee("tuiles de pas ou de projection différents (règle : grille commune)")
    sources = [rasterio.open(t.chemin) for t in tuiles]
    try:
        mosaique, transform = merge(
            sources, bounds=_cale(geometrie.bounds, pas), nodata=tuiles[0].nodata
        )
        profil = sources[0].profile
    finally:
        for s in sources:
            s.close()
    profil.update(
        driver="GTiff", height=mosaique.shape[1], width=mosaique.shape[2], transform=transform
    )
    for cle in ("blockxsize", "blockysize", "tiled", "compress", "interleave", "predictor"):
        profil.pop(cle, None)
    polygone = gpd.GeoDataFrame(geometry=[geometrie], crs=tuiles[0].crs)
    with MemoryFile() as memoire:
        with memoire.open(**profil) as dst:
            dst.write(mosaique)
        with memoire.open() as ds:
            res = exact_extract(ds, polygone, OPERATIONS, output="pandas")
    ligne = res.iloc[0]
    if ligne["count"] == 0:
        return vides
    return {
        "moyenne": float(ligne["mean"]),
        "mediane": float(ligne["median"]),
        "p10": float(ligne["quantile_10"]),
        "p90": float(ligne["quantile_90"]),
        "poids": float(ligne["count"]),
    }


def statistiques_zonales(
    polygones: gpd.GeoDataFrame | str | os.PathLike,
    annees: Sequence[int],
    couches: Sequence[str],
    catalogue: str | os.PathLike,
    champ_id: str = "id",
    traitement: str = "lissee",
) -> pd.DataFrame:
    """Une ligne par polygone, année et couche, aux colonnes de `COLONNES`."""
    if not isinstance(polygones, gpd.GeoDataFrame):
        polygones = gpd.read_file(polygones)
    if polygones.crs is None:
        raise DonneeRefusee(
            "polygones sans CRS refusés (règle : système de coordonnées explicite, "
            "Lambert-93 attendu)"
        )
    if champ_id not in polygones.columns:
        raise EntreeManquante(f"champ {champ_id!r} absent des polygones")
    lignes = []
    for couche in couches:
        for annee in annees:
            tuiles = tuiles_du_catalogue(catalogue, couche, int(annee), traitement)
            if not tuiles:
                raise EntreeManquante(f"aucune couche {couche} {annee} dans le catalogue")
            crs = tuiles[0].crs
            geometries = polygones.to_crs(crs)
            aire_cellule = abs(tuiles[0].pas[0] * tuiles[0].pas[1])
            for ident, geom in zip(polygones[champ_id], geometries.geometry, strict=True):
                touchees = [t for t in tuiles if box(*t.emprise).intersection(geom).area > 0]
                stats = mesurer(geom, touchees)
                lignes.append(
                    {
                        "id": ident,
                        "annee": int(annee),
                        "couche": couche,
                        "traitement": traitement,
                        "unite": _uniques(tuiles, "CANOPEE_UNITE"),
                        "moyenne": stats["moyenne"],
                        "mediane": stats["mediane"],
                        "p10": stats["p10"],
                        "p90": stats["p90"],
                        "part_couverte": stats["poids"] * aire_cellule / geom.area,
                        "incertitude_moyenne": np.nan,
                        "version_modele": _uniques(touchees, "CANOPEE_VERSION_MODELE"),
                        "version_donnees": _uniques(touchees, "CANOPEE_VERSION_DONNEES"),
                        "date_vol": _uniques(touchees, "CANOPEE_DATE_VOL"),
                        "dalles": SEPARATEUR.join(sorted(t.dalle for t in touchees)),
                    }
                )
    return pd.DataFrame(lignes, columns=COLONNES)
