"""Écriture et validation des COG (rio-cogeo), avec les tags `CANOPEE_*` de la couche."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from rio_cogeo.cogeo import cog_translate, cog_validate
from rio_cogeo.profiles import cog_profiles

from nemeton_canopee.ecriture import atomique
from nemeton_canopee.erreurs import DonneeRefusee


def ecrire_cog(
    source: Path,
    destination: Path,
    *,
    profil: str,
    predictor: int,
    tags: Mapping[str, str],
) -> None:
    """Convertit `source` en COG à `destination` (écriture atomique), puis le valide."""
    options = {**cog_profiles.get(profil), "predictor": predictor}
    with atomique(destination) as tmp:
        cog_translate(
            source,
            tmp,
            options,
            in_memory=True,
            allow_intermediate_compression=True,
            quiet=True,
            additional_cog_metadata=dict(tags),
        )
        valide, erreurs, _ = cog_validate(str(tmp), quiet=True)
        if not valide:
            raise DonneeRefusee(f"COG invalide pour {destination.name} : {erreurs}")
