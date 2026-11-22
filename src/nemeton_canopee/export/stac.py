"""Catalogue STAC de l'export : un catalogue, une collection par couche, un item par
millésime et dalle (`hauteur-2022-0901-6665`), assets `brute` et `lissee` (plan 004, § 6).

Géométrie et bbox en WGS84 ; emprise Lambert-93 dans `proj:code` et `proj:bbox`
(décision 9). Liens et assets relatifs : le catalogue se déplace avec le dossier de travail.
Aucune horodate « maintenant » : la date d'un item est la date de vol de sa dalle.
La validation se fait hors ligne, avec les schémas embarqués dans `conf/stac-schemas/`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pystac
import shapely
from pyproj import Transformer
from pystac.validation import JsonSchemaSTACValidator, RegisteredValidator
from shapely.geometry import box, mapping

from nemeton_canopee import __version__
from nemeton_canopee.conf import Configuration
from nemeton_canopee.erreurs import DonneeRefusee

URI_EXTENSION = "https://stac-extensions.github.io/{nom}/{version}/schema.json"
CODE_MULTIHASH_SHA256 = "1220"  # multihash : sha2-256, 32 octets


@dataclass(frozen=True)
class Couche:
    """Une dalle d'un millésime, avec ses COG par traitement et ses métadonnées."""

    dalle: str
    annee: int
    date_vol: str
    emprise: tuple[int, int, int, int]
    forme: tuple[int, int]
    pas_m: float
    cogs: dict[str, Path]
    tags: dict[str, str]
    mentions: list[str] = field(default_factory=list)


@contextmanager
def validateur_hors_ligne(dossier_schemas: Path) -> Iterator[JsonSchemaSTACValidator]:
    """Validateur pystac dont le cache est rempli par les schémas embarqués (sans réseau)."""
    validateur = JsonSchemaSTACValidator()
    for f in sorted(dossier_schemas.glob("*-v*.json")):
        nom, version = f.stem.rsplit("-", 1)
        uri = URI_EXTENSION.format(nom=nom, version=version)
        validateur.schema_cache[uri] = json.loads(f.read_text(encoding="utf-8"))
    for f in sorted((dossier_schemas / "externes").glob("*.json")):
        schema = json.loads(f.read_text(encoding="utf-8"))
        validateur.schema_cache[schema["$id"]] = schema
    ancien = RegisteredValidator.get_validator()
    RegisteredValidator.set_validator(validateur)
    try:
        yield validateur
    finally:
        RegisteredValidator.set_validator(ancien)


def valider(catalogue: Path, dossier_schemas: Path) -> int:
    """Valide tout le catalogue hors ligne ; renvoie le nombre d'items validés."""
    with validateur_hors_ligne(dossier_schemas):
        try:
            return pystac.Catalog.from_file(str(catalogue)).validate_all(recursive=True) or 0
        except pystac.errors.STACValidationError as e:
            raise DonneeRefusee(f"catalogue STAC invalide : {e}") from e


def _wgs84(emprise: tuple[int, int, int, int], crs: str):
    vers_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    return shapely.transform(
        box(*emprise), lambda xy: np.column_stack(vers_wgs84.transform(xy[:, 0], xy[:, 1]))
    )


def _date(texte: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texte[:10]).replace(tzinfo=dt.UTC)


def _sha256_multihash(chemin: Path) -> str:
    return CODE_MULTIHASH_SHA256 + hashlib.sha256(chemin.read_bytes()).hexdigest()


def item(conf: Configuration, c: Couche, dossier_item: Path) -> pystac.Item:
    """Item STAC d'une dalle et d'un millésime ; hrefs des assets relatifs à `dossier_item`."""
    couche, crs = conf.hauteur["couche"], conf.grille["crs"]
    geom = _wgs84(c.emprise, crs)
    xmin, ymin, xmax, ymax = c.emprise
    debut, _, fin = c.date_vol.partition("/")
    proprietes = {
        "title": f"Hauteur {c.annee}, dalle {c.dalle}",
        "proj:code": crs,
        "proj:bbox": [xmin, ymin, xmax, ymax],
        "proj:shape": list(c.forme),
        "proj:transform": [c.pas_m, 0.0, float(xmin), 0.0, -c.pas_m, float(ymax)],
        "processing:software": {"nemeton-canopee": __version__},
        "processing:lineage": (
            "MNH LiDAR HD et Sentinel-2 L2A de l'année de vol ; modèle "
            f"{c.tags['CANOPEE_VERSION_MODELE']} ; lissage temporel identité au jalon 1"
        ),
        "mentions": c.mentions,
        "canopee:version_modele": c.tags["CANOPEE_VERSION_MODELE"],
        "canopee:version_donnees": c.tags["CANOPEE_VERSION_DONNEES"],
        "canopee:graine": int(c.tags["CANOPEE_GRAINE"]),
        "canopee:date_vol": c.date_vol,
    }
    if fin:
        proprietes["start_datetime"] = _date(debut).isoformat()
        proprietes["end_datetime"] = _date(fin).isoformat()
    it = pystac.Item(
        id=f"{couche}-{c.annee}-{c.dalle}",
        geometry=mapping(geom),
        bbox=list(geom.bounds),
        datetime=None if fin else _date(debut),
        properties=proprietes,
        stac_extensions=list(conf.stac["extensions"]),
    )
    for traitement, cog in sorted(c.cogs.items()):
        it.add_asset(
            traitement,
            pystac.Asset(
                href=Path(os.path.relpath(cog, dossier_item)).as_posix(),
                media_type=pystac.MediaType.COG,
                roles=["data"],
                title=f"Hauteur {traitement} ({conf.hauteur['unite']})",
                extra_fields={
                    "raster:bands": [
                        {
                            "nodata": conf.nodata,
                            "data_type": conf.hauteur["dtype"],
                            "unit": conf.hauteur["unite"],
                            "spatial_resolution": c.pas_m,
                        }
                    ],
                    "file:size": cog.stat().st_size,
                    "file:checksum": _sha256_multihash(cog),
                },
            ),
        )
    return it


def ecrire_catalogue(
    conf: Configuration, couches: Sequence[Couche], dossier: Path, dossier_final: Path
) -> None:
    """Écrit le catalogue dans `dossier` ; les hrefs relatifs visent `dossier_final`.

    `dossier` et `dossier_final` sont au même niveau (écriture atomique par renommage), donc
    les chemins relatifs sont les mêmes depuis l'un ou l'autre.
    """
    couche = conf.hauteur["couche"]
    cat_conf = conf.stac["catalogue"]
    annees = sorted({c.annee for c in couches})
    mentions = sorted({m for c in couches for m in c.mentions})
    catalogue = pystac.Catalog(
        id=cat_conf["id"], title=cat_conf["titre"], description=cat_conf["description"]
    )
    items = []
    for c in sorted(couches, key=lambda c: (c.annee, c.dalle)):
        id_item = f"{couche}-{c.annee}-{c.dalle}"
        items.append(item(conf, c, dossier_final / couche / id_item))
    if not items:
        raise DonneeRefusee("aucune couche à cataloguer")
    emprises = [it.bbox for it in items]
    spatial = [
        min(b[0] for b in emprises),
        min(b[1] for b in emprises),
        max(b[2] for b in emprises),
        max(b[3] for b in emprises),
    ]
    dates = sorted(_date(c.date_vol.split("/")[0]) for c in couches)
    dates_fin = sorted(_date(c.date_vol.split("/")[-1]) for c in couches)
    collection = pystac.Collection(
        id=couche,
        title=f"Hauteur de la canopée ({conf.hauteur['unite']}), millésimes "
        + ", ".join(map(str, annees)),
        description=(
            f"Hauteur de la canopée à {conf.grille['pas_m']} m, Lambert-93, "
            f"{conf.hauteur['dtype']} en {conf.hauteur['unite']}, nodata {conf.nodata}. "
            "Mentions : " + " ; ".join(mentions) + "."
        ),
        extent=pystac.Extent(
            pystac.SpatialExtent([spatial]), pystac.TemporalExtent([[dates[0], dates_fin[-1]]])
        ),
        license=conf.stac["licence"],
    )
    for lien in conf.stac["liens_licence"]:
        collection.add_link(pystac.Link(rel="license", target=lien["href"], title=lien["titre"]))
    for it in items:
        collection.add_item(it)
    catalogue.add_child(collection)
    catalogue.normalize_hrefs(str(dossier))
    catalogue.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
