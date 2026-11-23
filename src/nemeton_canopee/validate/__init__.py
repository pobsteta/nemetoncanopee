"""Étape `validate` : MAE et biais de la hauteur sur les dalles de test du découpage figé.

Les écarts se calculent sur les cellules où la cible et la prédiction brute existent ;
biais = prédiction − cible (décision 10), en m. Sorties : `validate/rapport.json` (clés
`mae_m`, `biais_m`, `dalles: {id: {n, mae_m, biais_m}}`, décision 8) et `validate/rapport.md`.

Références à battre (mission 007) : chaque référence déclarée par `ingest` est comparée à la
cible sur un masque commun, les cellules de test où la cible, la prédiction du projet et la
référence existent toutes ; biais = référence − cible. Le projet est recalculé sur ce même
masque (`projet_meme_masque`), pour que la comparaison porte sur les mêmes cellules. Clé :
`references: {nom: {mae_m, biais_m, n, dalles, projet_meme_masque, fichiers}}`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from nemeton_canopee import decoupage
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_json, ecrire_texte, lire_bande
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import lire_manifeste, lire_references
from nemeton_canopee.models import modele_actif

CM_PAR_M = 100.0
DECIMALES = 4


def ecarts(cible: np.ndarray, prediction: np.ndarray, nodata: int) -> np.ndarray:
    """Écarts prédiction − cible (m) sur les cellules où les deux existent."""
    ok = (cible != nodata) & (prediction != nodata)
    return (prediction[ok].astype("int64") - cible[ok].astype("int64")) / CM_PAR_M


def ecarts_communs(
    cible: np.ndarray, prediction: np.ndarray, reference: np.ndarray, nodata: int
) -> tuple[np.ndarray, np.ndarray]:
    """(référence − cible, prédiction − cible), en m, sur le masque commun aux trois rasters."""
    ok = (cible != nodata) & (prediction != nodata) & (reference != nodata)
    c = cible[ok].astype("int64")
    return (
        (reference[ok].astype("int64") - c) / CM_PAR_M,
        (prediction[ok].astype("int64") - c) / CM_PAR_M,
    )


def controler_grille(profil_ref: dict, profil_cible: dict, fichier: str, crs: str) -> None:
    """Refuse (code 3) une référence qui n'est pas sur la grille de la cible (CRS, pas, emprise)."""
    from rasterio.crs import CRS

    if profil_ref.get("crs") is None or profil_ref["crs"] != CRS.from_user_input(crs):
        raise DonneeRefusee(
            f"référence {fichier} refusée : CRS {profil_ref.get('crs')} au lieu de {crs} "
            "(règle : comparer sur la grille du projet)"
        )
    meme = (profil_ref["width"], profil_ref["height"]) == (
        profil_cible["width"],
        profil_cible["height"],
    ) and profil_ref["transform"].almost_equals(profil_cible["transform"])
    if not meme:
        raise DonneeRefusee(
            f"référence {fichier} refusée : grille différente de la cible "
            "(règle : comparer sur la grille du projet, 10 m alignée sur le km)"
        )


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
        *references_markdown(rapport),
    ]
    return "\n".join(lignes)


def references_markdown(rapport: dict[str, Any]) -> list[str]:
    """Tableau projet contre références, sur le même masque, global puis par dalle."""
    refs = rapport.get("references") or {}
    if not refs:
        return []
    lignes = [
        "## Références à battre",
        "",
        "Biais = produit − cible. Masque commun : cellules de test où la cible, la prédiction "
        "du projet et la référence existent toutes.",
        "",
        "| Produit | n | MAE (m) | Biais (m) |",
        "|---|---:|---:|---:|",
    ]
    for r in refs.values():
        p = r["projet_meme_masque"]
        lignes += [
            f"| projet, même masque que {r['libelle']} | {p['n']} | {p['mae_m']:.2f} "
            f"| {p['biais_m']:.2f} |",
            f"| {r['libelle']} | {r['n']} | {r['mae_m']:.2f} | {r['biais_m']:.2f} |",
        ]
    lignes += [
        "",
        "| Dalle de test | Produit | n | MAE (m) | Biais (m) |",
        "|---|---|---:|---:|---:|",
    ]
    for r in refs.values():
        for dalle, b in r["dalles"].items():
            p = r["projet_meme_masque"]["dalles"][dalle]
            lignes += [
                f"| {dalle} | projet | {p['n']} | {p['mae_m']:.2f} | {p['biais_m']:.2f} |",
                f"| {dalle} | {r['libelle']} | {b['n']} | {b['mae_m']:.2f} | {b['biais_m']:.2f} |",
            ]
    return [*lignes, ""]


def comparer_references(
    conf: Configuration, ch: Chemins, dalles: list, rasters: dict[str, tuple]
) -> dict[str, Any]:
    """MAE et biais de chaque référence et du projet sur leur masque commun (mission 007)."""
    table = lire_references(ch)
    sortie: dict[str, Any] = {}
    for nom in sorted(table["nom"].unique()):
        lignes = table[table["nom"] == nom].set_index("dalle")
        par_ref: dict[str, Any] = {}
        par_projet: dict[str, Any] = {}
        fichiers: dict[str, str] = {}
        tous_ref, tous_projet = [], []
        for dalle in dalles:
            if dalle.id not in lignes.index:
                raise EntreeManquante(f"référence {nom} absente pour la dalle {dalle.id}")
            ligne = lignes.loc[dalle.id]
            fichier = str(ligne["fichier"])
            ref, profil_ref, _ = lire_bande(exiger_fichier(conf.zone.racine / fichier, "ingest"))
            cible, profil_cible, pred = rasters[dalle.id]
            controler_grille(profil_ref, profil_cible, fichier, conf.grille["crs"])
            e_ref, e_projet = ecarts_communs(cible, pred, ref, conf.nodata)
            par_ref[dalle.id] = resume(e_ref)
            par_projet[dalle.id] = resume(e_projet)
            fichiers[fichier] = str(ligne["sha256"])
            tous_ref.append(e_ref)
            tous_projet.append(e_projet)
        global_ref = resume(np.concatenate(tous_ref))
        global_projet = resume(np.concatenate(tous_projet))
        sortie[str(nom)] = {
            "libelle": str(lignes["libelle"].iloc[0]),
            "unite": str(lignes["unite"].iloc[0]),
            "mae_m": global_ref["mae_m"],
            "biais_m": global_ref["biais_m"],
            "n": global_ref["n"],
            "dalles": par_ref,
            "projet_meme_masque": {**global_projet, "dalles": par_projet},
            "fichiers": fichiers,
        }
    return sortie


def executer(conf: Configuration) -> dict[str, Any]:
    """Écrit le rapport de validation ; le renvoie."""
    ch = Chemins(conf.travail)
    version, modele = modele_actif(ch)
    dec = decoupage.lire(conf)
    par_dalle: dict[str, dict[str, Any]] = {}
    tous = []
    dalles = lire_manifeste(ch, dec.test)
    rasters: dict[str, tuple] = {}
    for dalle in dalles:
        cible, profil, _ = lire_bande(exiger_fichier(ch.cible(dalle.annee, dalle.id), "targets"))
        pred, _, _ = lire_bande(exiger_fichier(ch.brute(dalle.annee, dalle.id), "infer"))
        rasters[dalle.id] = (cible, profil, pred)
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
        "references": comparer_references(conf, ch, dalles, rasters),
    }
    ecrire_json(ch.rapport_json, rapport)
    ecrire_texte(ch.rapport_md, rapport_markdown(rapport))
    return rapport
