"""Étape `export` : COG de hauteur (brute et lissée) et catalogue STAC validé hors ligne.

Sorties : `export/cog/{couche}/{annee}/{dalle}_{couche}_{traitement}_{annee}.tif` et
`export/stac/` (catalogue, collection par couche, item par millésime et dalle).
"""

from __future__ import annotations

from collections.abc import Sequence

import rasterio

from nemeton_canopee import grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import dossier_atomique
from nemeton_canopee.erreurs import exiger_fichier
from nemeton_canopee.export.cog import ecrire_cog
from nemeton_canopee.export.stac import Couche, ecrire_catalogue, valider
from nemeton_canopee.ingest import lire_manifeste, lire_scenes
from nemeton_canopee.metadonnees import mentions

TRAITEMENTS = {"brute": "infer", "lissee": "smooth"}  # traitement -> étape qui le produit


def executer(conf: Configuration, annees: Sequence[int] | None = None) -> int:
    """Écrit les COG des années choisies puis le catalogue ; renvoie le nombre d'items."""
    ch = Chemins(conf.travail)
    couche = conf.hauteur["couche"]
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    scenes = lire_scenes(ch)
    for dalle in lire_manifeste(ch, annees=annees):
        for traitement, etape in TRAITEMENTS.items():
            source = ch.brute if traitement == "brute" else ch.lissee
            chemin = exiger_fichier(source(dalle.annee, dalle.id), etape)
            with rasterio.open(chemin) as src:
                tags = src.tags()
            tags.pop("AREA_OR_POINT", None)
            ecrire_cog(
                chemin,
                ch.cog(couche, dalle.annee, dalle.id, traitement),
                profil=conf.cog["profil"],
                predictor=int(conf.cog["predictor"]),
                tags=tags,
            )

    # Le catalogue décrit toutes les dalles du manifeste dont les COG existent.
    couches = []
    for dalle in lire_manifeste(ch):
        cogs = {t: ch.cog(couche, dalle.annee, dalle.id, t) for t in TRAITEMENTS}
        if not all(p.is_file() for p in cogs.values()):
            continue
        with rasterio.open(cogs["lissee"]) as src:
            tags = src.tags()
        couches.append(
            Couche(
                dalle=dalle.id,
                annee=dalle.annee,
                date_vol=dalle.date_vol,
                emprise=grille.emprise(dalle.id, taille),
                forme=grille.forme(taille, pas),
                pas_m=pas,
                cogs=cogs,
                tags=tags,
                mentions=mentions(conf, scenes, dalle.id),
            )
        )
    with dossier_atomique(ch.stac) as tmp:
        ecrire_catalogue(conf, couches, tmp, ch.stac)
        return valider(tmp / "catalog.json", conf.dossier_schemas)
