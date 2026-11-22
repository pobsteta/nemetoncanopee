"""Étape `validate` : MAE et biais de la hauteur sur les dalles de test du découpage figé.

Les écarts se calculent sur les cellules où la cible et la prédiction brute existent ;
biais = prédiction − cible (décision 10), en m. Sorties : `validate/rapport.json` (clés
`mae_m`, `biais_m`, `dalles: {id: {n, mae_m, biais_m}}`, décision 8) et `validate/rapport.md`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from nemeton_canopee import decoupage
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_json, ecrire_texte, lire_bande
from nemeton_canopee.erreurs import EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import lire_manifeste
from nemeton_canopee.models import modele_actif

CM_PAR_M = 100.0
DECIMALES = 4


def ecarts(cible: np.ndarray, prediction: np.ndarray, nodata: int) -> np.ndarray:
    """Écarts prédiction − cible (m) sur les cellules où les deux existent."""
    ok = (cible != nodata) & (prediction != nodata)
    return (prediction[ok].astype("int64") - cible[ok].astype("int64")) / CM_PAR_M


def resume(e: np.ndarray) -> dict[str, Any]:
    """n, MAE et biais (m) d'un vecteur d'écarts."""
    if e.size == 0:
        return {"n": 0, "mae_m": float("nan"), "biais_m": float("nan")}
    return {
        "n": int(e.size),
        "mae_m": round(float(np.abs(e).mean()), DECIMALES),
        "biais_m": round(float(e.mean()), DECIMALES),
    }


def rapport_markdown(rapport: dict[str, Any]) -> str:
    """Rapport lisible : versions, découpage, tableau par dalle de test, MAE globale."""
    lignes = [
        "# Rapport de validation — hauteur",
        "",
        f"- Version du modèle : `{rapport['version_modele']}`",
        f"- Version des données : `{rapport['version_donnees']}`",
        f"- Graine : {rapport['graine']}",
        f"- Couche évaluée : {rapport['couche']} ({rapport['traitement']})",
        f"- Dalles d'apprentissage : {', '.join(rapport['dalles_apprentissage'])}",
        f"- Dalles de test : {', '.join(rapport['dalles'])}",
        "",
        "Biais = prédiction − cible. Cellules où la cible et la prédiction existent.",
        "",
        "| Dalle de test | n | MAE (m) | Biais (m) |",
        "|---|---:|---:|---:|",
    ]
    for dalle, b in rapport["dalles"].items():
        lignes.append(f"| {dalle} | {b['n']} | {b['mae_m']:.2f} | {b['biais_m']:.2f} |")
    lignes += [
        f"| **Toutes** | {rapport['n']} | **{rapport['mae_m']:.2f}** | {rapport['biais_m']:.2f} |",
        "",
        f"**MAE** sur les blocs de test : {rapport['mae_m']:.2f} m.",
        "",
    ]
    return "\n".join(lignes)


def executer(conf: Configuration) -> dict[str, Any]:
    """Écrit le rapport de validation ; le renvoie."""
    ch = Chemins(conf.travail)
    version, modele = modele_actif(ch)
    dec = decoupage.lire(conf)
    par_dalle: dict[str, dict[str, Any]] = {}
    tous = []
    for dalle in lire_manifeste(ch, dec.test):
        cible, _, _ = lire_bande(exiger_fichier(ch.cible(dalle.annee, dalle.id), "targets"))
        pred, _, _ = lire_bande(exiger_fichier(ch.brute(dalle.annee, dalle.id), "infer"))
        e = ecarts(cible, pred, conf.nodata)
        par_dalle[dalle.id] = resume(e)
        tous.append(e)
    if not tous:
        raise EntreeManquante("aucune dalle de test dans le manifeste (relancer ingest)")
    global_ = resume(np.concatenate(tous))
    rapport = {
        "mae_m": global_["mae_m"],
        "biais_m": global_["biais_m"],
        "n": global_["n"],
        "dalles": par_dalle,
        "couche": conf.hauteur["couche"],
        "traitement": "brute",
        "version_modele": version,
        "version_donnees": modele["version_donnees"],
        "graine": conf.graine,
        "dalles_apprentissage": dec.apprentissage,
    }
    ecrire_json(ch.rapport_json, rapport)
    ecrire_texte(ch.rapport_md, rapport_markdown(rapport))
    return rapport
