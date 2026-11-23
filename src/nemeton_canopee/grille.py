"""Grille commune : dalles LiDAR HD de 1 km et cellules de 10 m en Lambert-93.

L'identifiant d'une dalle `XXXX-YYYY` est son coin nord-ouest en km (`docs/referentiels.md`
§ 1) : `0901-6665` couvre x de 901 000 à 902 000 m et y de 6 664 000 à 6 665 000 m. Les
cellules ont leurs bords sur les multiples du pas (spec § 2).
"""

from __future__ import annotations

import re

from rasterio.crs import CRS
from rasterio.transform import Affine

from nemeton_canopee.erreurs import DonneeRefusee

MOTIF_DALLE = re.compile(r"^(\d{4})-(\d{4})$")


def controler_identifiant(dalle: str) -> re.Match:
    """Refuse (code 3) un identifiant qui n'a pas la forme IGN `XXXX-YYYY`."""
    m = MOTIF_DALLE.match(str(dalle))
    if not m:
        raise DonneeRefusee(
            f"identifiant de dalle invalide : {dalle!r} (règle : nomenclature IGN XXXX-YYYY, "
            "coin nord-ouest en km)"
        )
    return m


def emprise(dalle: str, taille_m: int) -> tuple[int, int, int, int]:
    """(xmin, ymin, xmax, ymax) de la dalle, en m Lambert-93."""
    m = controler_identifiant(dalle)
    x, y = int(m.group(1)) * 1000, int(m.group(2)) * 1000
    return x, y - taille_m, x + taille_m, y


def transformation(dalle: str, taille_m: int, pas_m: float) -> Affine:
    """Transformation affine de la grille de la dalle au pas donné (origine nord-ouest)."""
    xmin, _, _, ymax = emprise(dalle, taille_m)
    return Affine(pas_m, 0.0, float(xmin), 0.0, -pas_m, float(ymax))


def forme(taille_m: int, pas_m: float) -> tuple[int, int]:
    """(lignes, colonnes) d'une dalle au pas donné."""
    n = taille_m / pas_m
    if n != int(n):
        raise ValueError(f"le pas {pas_m} m ne divise pas la dalle de {taille_m} m")
    return int(n), int(n)


def bloc(dalle: str, taille_dalle_m: int, taille_bloc_m: int) -> tuple[int, int]:
    """Indice du bloc spatial de la dalle : (xmin // taille, ymin // taille)."""
    xmin, ymin, _, _ = emprise(dalle, taille_dalle_m)
    return xmin // taille_bloc_m, ymin // taille_bloc_m


def se_touchent(a: str, b: str, taille_m: int) -> bool:
    """Vrai si deux dalles se recouvrent ou se touchent, par un bord ou par un coin."""
    ax0, ay0, ax1, ay1 = emprise(a, taille_m)
    bx0, by0, bx1, by1 = emprise(b, taille_m)
    return ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1


def controler_crs(lu: CRS | None, attendu: str, nom: str) -> None:
    """Refuse (code 3) une donnée dont la projection n'est pas celle de la conf (`grille.crs`)."""
    if lu is None or CRS.from_user_input(lu) != CRS.from_user_input(attendu):
        raise DonneeRefusee(
            f"{nom} en CRS {lu} refusé (règle : CRS de la grille {attendu}, conf grille.crs)"
        )
