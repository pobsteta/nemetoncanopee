"""Étape `smooth` : cohérence temporelle des couches.

Au jalon 1 (décision 3), le lissage est l'**identité** : la couche lissée est la couche brute,
avec le tag `CANOPEE_TRAITEMENT=lissee`. Le seuil de rupture est lu dans la configuration et
écrit dans les métadonnées, sans effet (PROVISOIRE, calage au jalon 5).
"""

from __future__ import annotations

from collections.abc import Sequence

import rasterio

from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_raster
from nemeton_canopee.erreurs import exiger_fichier
from nemeton_canopee.ingest import lire_manifeste


def executer(
    conf: Configuration,
    annees: Sequence[int] | None = None,
    dalles: Sequence[str] | None = None,
) -> None:
    """Écrit la couche lissée de chaque dalle choisie."""
    ch = Chemins(conf.travail)
    seuil = int(conf.smooth["seuil_rupture_cm"])
    for dalle in lire_manifeste(ch, dalles, annees):
        with rasterio.open(exiger_fichier(ch.brute(dalle.annee, dalle.id), "infer")) as src:
            hauteur, transform, crs, nodata = src.read(1), src.transform, src.crs, src.nodata
            tags = src.tags()
        tags.pop("AREA_OR_POINT", None)
        tags.update(CANOPEE_TRAITEMENT="lissee", CANOPEE_SEUIL_RUPTURE_CM=str(seuil))
        ecrire_raster(
            ch.lissee(dalle.annee, dalle.id),
            hauteur,  # identité au jalon 1
            transform,
            crs.to_string(),
            nodata=nodata,
            tags=tags,
        )
