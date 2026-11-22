"""Étape `infer` : applique le modèle actif sur les cellules de forêt vues sans nuage.

Une cellule est prédite si elle est en forêt et claire (SCL bon) dans au moins une scène
de l'année de vol ; ailleurs elle vaut le nodata. Sortie : couche brute, uint16 en cm.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import rasterio

from nemeton_canopee import grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_raster, lire_bande
from nemeton_canopee.erreurs import EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import lire_manifeste, lire_scenes
from nemeton_canopee.metadonnees import etiquettes, mentions
from nemeton_canopee.models import MODELES, modele_actif


def masque_clair(scenes: Sequence) -> np.ndarray:
    """Vrai là où au moins une scène est claire (dernière bande `clair` des piles)."""
    masque = None
    for chemin in scenes:
        with rasterio.open(chemin) as src:
            clair = src.read(src.count) == 1
        masque = clair if masque is None else (masque | clair)
    if masque is None:
        raise EntreeManquante("aucune scène préparée (relancer prepare)")
    return masque


def executer(
    conf: Configuration,
    annees: Sequence[int] | None = None,
    dalles: Sequence[str] | None = None,
) -> None:
    """Écrit la couche brute de chaque dalle choisie."""
    ch = Chemins(conf.travail)
    version, modele = modele_actif(ch)
    scenes = lire_scenes(ch)
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    for dalle in lire_manifeste(ch, dalles, annees):
        if modele.get("version_donnees") != dalle.version_donnees:
            raise EntreeManquante("modèle entraîné sur d'autres données (relancer train)")
        foret, _, _ = lire_bande(exiger_fichier(ch.foret(dalle.id), "prepare"))
        clair = masque_clair(ch.scenes_preparees(dalle.annee, dalle.id))
        hauteur = MODELES[modele["nom"]].predire(modele, (foret == 1) & clair, conf.nodata)
        tags = etiquettes(
            conf,
            version_modele=version,
            version_donnees=dalle.version_donnees,
            traitement="brute",
            date_vol=dalle.date_vol,
            mentions_dalle=mentions(conf, scenes, dalle.id),
        )
        ecrire_raster(
            ch.brute(dalle.annee, dalle.id),
            hauteur,
            grille.transformation(dalle.id, taille, pas),
            conf.grille["crs"],
            nodata=conf.nodata,
            tags=tags,
        )
