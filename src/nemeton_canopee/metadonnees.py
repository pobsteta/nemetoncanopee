"""Métadonnées écrites dans chaque couche produite (tags GDAL `CANOPEE_*`, plan 004 § 6)."""

from __future__ import annotations

import pandas as pd

from nemeton_canopee import __version__
from nemeton_canopee.conf import Configuration

SEPARATEUR_MENTIONS = " | "


def mentions(conf: Configuration, scenes: pd.DataFrame, dalle: str) -> list[str]:
    """Mentions de licence d'une dalle : Copernicus (années des scènes), puis IGN."""
    annees = sorted({str(d)[:4] for d in scenes.loc[scenes["dalle"] == dalle, "date_scene"]})
    gabarit = conf.stac["mention_copernicus"]
    return [gabarit.format(annee=a) for a in annees] + [conf.stac["mention_ign"]]


def etiquettes(
    conf: Configuration,
    *,
    version_modele: str,
    version_donnees: str,
    traitement: str,
    date_vol: str,
    mentions_dalle: list[str],
) -> dict[str, str]:
    """Tags d'une couche de hauteur : versions, graine, couche, traitement, vol, unité."""
    return {
        "CANOPEE_VERSION_MODELE": version_modele,
        "CANOPEE_VERSION_DONNEES": version_donnees,
        "CANOPEE_GRAINE": str(conf.graine),
        "CANOPEE_VERSION_LOGICIEL": __version__,
        "CANOPEE_COUCHE": conf.hauteur["couche"],
        "CANOPEE_TRAITEMENT": traitement,
        "CANOPEE_DATE_VOL": date_vol,
        "CANOPEE_UNITE": conf.hauteur["unite"],
        "CANOPEE_MENTIONS": SEPARATEUR_MENTIONS.join(mentions_dalle),
    }
