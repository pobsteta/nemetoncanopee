"""Étape `export` : COG de hauteur (brute et lissée) et catalogue STAC validé hors ligne.

Sorties : `export/cog/{couche}/{annee}/{dalle}_{couche}_{traitement}_{annee}.tif` et
`export/stac/` (catalogue, collection par couche, item par millésime et dalle).
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

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
    """Écrit les COG des années choisies puis le catalogue ; renvoie le nombre d'items.

    Tout `export/` est écrit dans un dossier temporaire voisin, validé (COG et STAC), puis
    renommé d'un bloc : un export interrompu ou invalide laisse l'export précédent intact.
    Avec `--annees`, les COG des autres années sont repris de l'export précédent.
    """
    ch = Chemins(conf.travail)
    racine_export = ch.stac.parent
    couche = conf.hauteur["couche"]
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    scenes = lire_scenes(ch)
    choisies = lire_manifeste(ch, annees=annees)
    with dossier_atomique(racine_export) as tmp:

        def dans_tmp(chemin: Path) -> Path:
            return tmp / chemin.relative_to(racine_export)

        anciens_cog = racine_export / "cog"
        if annees and anciens_cog.is_dir():
            shutil.copytree(anciens_cog, tmp / "cog")
        for dalle in choisies:
            for traitement, etape in TRAITEMENTS.items():
                source = ch.brute if traitement == "brute" else ch.lissee
                chemin = exiger_fichier(source(dalle.annee, dalle.id), etape)
                with rasterio.open(chemin) as src:
                    tags = src.tags()
                tags.pop("AREA_OR_POINT", None)
                ecrire_cog(
                    chemin,
                    dans_tmp(ch.cog(couche, dalle.annee, dalle.id, traitement)),
                    profil=conf.cog["profil"],
                    predictor=int(conf.cog["predictor"]),
                    tags=tags,
                )

        # Le catalogue décrit toutes les dalles du manifeste dont les COG existent.
        couches = []
        for dalle in lire_manifeste(ch):
            cogs = {t: dans_tmp(ch.cog(couche, dalle.annee, dalle.id, t)) for t in TRAITEMENTS}
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
        # COG et catalogue sont sous la même racine temporaire : les hrefs relatifs calculés
        # ici restent justes une fois le dossier renommé.
        stac = dans_tmp(ch.stac)
        ecrire_catalogue(conf, couches, stac, stac)
        return valider(stac / "catalog.json", conf.dossier_schemas)
