"""Étape `targets` : cible de hauteur à 10 m tirée du MNH LiDAR HD.

Chaque cellule de 10 m prend le **maximum** des pixels du MNH qu'elle contient (pixels nodata
exclus) ; les hauteurs négatives sont bornées à 0 ; une cellule sans pixel valide, ou hors
forêt, vaut le nodata (65535). Sortie : uint16 en cm, Lambert-93 (plan 004, § 5).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import rasterio

from nemeton_canopee import grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_raster, lire_bande
from nemeton_canopee.erreurs import DonneeRefusee, exiger_fichier
from nemeton_canopee.ingest import lire_manifeste

FACTEUR_UNITE_CM = {"cm": 1.0, "m": 100.0}


def maximum_par_cellule(mnh_cm: np.ndarray, valide: np.ndarray, facteur: int) -> np.ndarray:
    """Maximum des pixels valides par bloc `facteur` x `facteur` ; -1 si aucun pixel valide."""
    lignes, colonnes = mnh_cm.shape[0] // facteur, mnh_cm.shape[1] // facteur
    valeurs = np.where(valide, mnh_cm, -1.0)
    blocs = valeurs.reshape(lignes, facteur, colonnes, facteur)
    return blocs.max(axis=(1, 3))


def cible_hauteur(
    mnh: np.ndarray,
    nodata_source: float | None,
    unite: str,
    foret: np.ndarray,
    facteur: int,
    nodata: int,
) -> np.ndarray:
    """Cible 10 m (uint16, cm) à partir du MNH source et du masque forêt."""
    if unite not in FACTEUR_UNITE_CM:
        raise DonneeRefusee(f"unité du MNH inconnue : {unite!r} (attendu cm ou m)")
    valeurs = mnh.astype("float64")
    valide = np.isfinite(valeurs)
    if nodata_source is not None:
        valide &= valeurs != nodata_source
    cm = np.round(np.clip(valeurs * FACTEUR_UNITE_CM[unite], 0, nodata - 1))  # borne à 0
    maximum = maximum_par_cellule(cm, valide, facteur)
    cible = np.where((maximum >= 0) & (foret == 1), maximum, nodata)
    return cible.astype("uint16")


def executer(conf: Configuration, dalles: Sequence[str] | None = None) -> None:
    """Écrit la cible de hauteur de chaque dalle du manifeste."""
    ch = Chemins(conf.travail)
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    for dalle in lire_manifeste(ch, dalles):
        foret, _, _ = lire_bande(exiger_fichier(ch.foret(dalle.id), "prepare"))
        chemin_mnh = exiger_fichier(conf.zone.chemin("mnh", dalle=dalle.id), "ingest")
        with rasterio.open(chemin_mnh) as src:
            attendue = tuple(float(v) for v in grille.emprise(dalle.id, taille))
            facteur = pas / src.res[0]
            if tuple(src.bounds) != attendue or facteur != int(facteur):
                raise DonneeRefusee(
                    f"MNH de {dalle.id} hors grille : emprise {tuple(src.bounds)}, pas {src.res} "
                    f"(règle : grille de la dalle {attendue}, pas divisant {pas} m)"
                )
            mnh, nodata_source = src.read(1), src.nodata
            unite_fichier = src.tags().get("unite", conf.zone.mnh_unite)
        unite = conf.zone.mnh_unite
        if unite_fichier != unite:
            raise DonneeRefusee(
                f"MNH de {dalle.id} en {unite_fichier!r}, la zone déclare {unite!r} "
                "(règle : unité du MNH déclarée dans conf/zones)"
            )
        cible = cible_hauteur(mnh, nodata_source, unite, foret, int(facteur), conf.nodata)
        tags = {
            "CANOPEE_COUCHE": conf.hauteur["couche"],
            "CANOPEE_UNITE": conf.hauteur["unite"],
            "CANOPEE_DATE_VOL": dalle.date_vol,
            "regle": "maximum du MNH par cellule de 10 m, hors nodata, forêt seulement",
        }
        ecrire_raster(
            ch.cible(dalle.annee, dalle.id),
            cible,
            grille.transformation(dalle.id, taille, pas),
            conf.grille["crs"],
            nodata=conf.nodata,
            tags=tags,
        )
