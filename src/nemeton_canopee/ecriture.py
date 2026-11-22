"""Écriture atomique et rejouable des fichiers de travail.

Chaque fichier est d'abord écrit sous un nom temporaire dans son dossier, puis renommé
(`os.replace`) : une étape interrompue ne laisse jamais un fichier à moitié écrit. Aucune
horodate n'est écrite : deux passes donnent des fichiers identiques à l'octet.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.transform import Affine


@contextmanager
def atomique(chemin: Path) -> Iterator[Path]:
    """Donne un chemin temporaire à remplir ; il remplace `chemin` à la sortie sans erreur."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(f".{chemin.stem}.partiel{chemin.suffix}")
    try:
        yield temporaire
        os.replace(temporaire, chemin)
    finally:
        if temporaire.exists():
            temporaire.unlink()


@contextmanager
def dossier_atomique(chemin: Path) -> Iterator[Path]:
    """Comme `atomique`, pour un dossier : le nouveau dossier remplace l'ancien en bloc."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(f".{chemin.name}-partiel")
    ancien = chemin.with_name(f".{chemin.name}-ancien")
    for d in (temporaire, ancien):
        shutil.rmtree(d, ignore_errors=True)
    temporaire.mkdir()
    try:
        yield temporaire
        if chemin.exists():
            os.replace(chemin, ancien)
        os.replace(temporaire, chemin)
    finally:
        shutil.rmtree(temporaire, ignore_errors=True)
        shutil.rmtree(ancien, ignore_errors=True)


def ecrire_texte(chemin: Path, texte: str) -> None:
    with atomique(chemin) as tmp:
        tmp.write_text(texte, encoding="utf-8")


def ecrire_json(chemin: Path, donnees: Any) -> None:
    """JSON indenté, clés dans l'ordre donné, fin de ligne finale."""
    ecrire_texte(chemin, json.dumps(donnees, ensure_ascii=False, indent=2) + "\n")


def ecrire_raster(
    chemin: Path,
    bandes: np.ndarray,
    transform: Affine,
    crs: str,
    *,
    nodata: float | None = None,
    compression: str = "deflate",
    tags: Mapping[str, str] | None = None,
    descriptions: list[str] | None = None,
) -> None:
    """GeoTIFF tuilé et compressé ; `bandes` est en 2D (une bande) ou en 3D (bandes, l, c)."""
    if bandes.ndim == 2:
        bandes = bandes[np.newaxis]
    profil = {
        "driver": "GTiff",
        "count": bandes.shape[0],
        "height": bandes.shape[1],
        "width": bandes.shape[2],
        "dtype": bandes.dtype.name,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": compression,
    }
    with atomique(chemin) as tmp:
        with rasterio.open(tmp, "w", **profil) as dst:
            dst.write(bandes)
            if tags:
                dst.update_tags(**{k: str(v) for k, v in sorted(tags.items())})
            for i, nom in enumerate(descriptions or [], start=1):
                dst.set_band_description(i, nom)


def lire_bande(chemin: Path) -> tuple[np.ndarray, dict[str, Any], dict[str, str]]:
    """(bande 1, profil, tags) d'un raster."""
    with rasterio.open(chemin) as src:
        return src.read(1), dict(src.profile), src.tags()
