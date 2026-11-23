"""Modèle trivial du jalon 1 : la hauteur prédite est la médiane des cibles d'apprentissage.

Il ne sert qu'à prouver la chaîne. Il refuse toute dalle de test parmi ses entrées.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante

ARRONDIS = {"demi_haut": lambda x: math.floor(x + 0.5)}


def entrainer(
    cibles: Mapping[str, np.ndarray],
    dalles_test: Sequence[str],
    nodata: int,
    arrondi: str,
) -> dict[str, Any]:
    """Médiane des cellules valides des cibles d'apprentissage, arrondie à l'entier (cm)."""
    interdites = sorted(set(cibles) & set(dalles_test))
    if interdites:
        raise DonneeRefusee(
            f"découpage enfreint : dalles de test {interdites} parmi l'apprentissage"
        )
    if arrondi not in ARRONDIS:
        raise DonneeRefusee(f"arrondi inconnu : {arrondi!r} (connus : {sorted(ARRONDIS)})")
    valeurs = [c[c != nodata] for _, c in sorted(cibles.items())]
    tout = np.concatenate(valeurs) if valeurs else np.array([])
    if tout.size == 0:
        raise EntreeManquante("aucune cellule valide pour l'apprentissage (relancer targets)")
    mediane = float(np.median(tout))
    return {
        "valeur_cm": int(ARRONDIS[arrondi](mediane)),
        "mediane_cm": mediane,
        "arrondi": arrondi,
        "n_cellules": int(tout.size),
    }


def predire(modele: Mapping[str, Any], masque: np.ndarray, nodata: int) -> np.ndarray:
    """Hauteur (uint16, cm) : la valeur du modèle là où `masque` est vrai, nodata ailleurs."""
    return np.where(masque, int(modele["valeur_cm"]), nodata).astype("uint16")
