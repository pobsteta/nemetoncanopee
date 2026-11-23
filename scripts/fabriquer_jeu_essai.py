#!/usr/bin/env python
"""Fabrique le jeu d'essai de 4 dalles de 1 km (`tests/data/`), une fois, avec le réseau.

Mission 002. Seul script du dépôt qui accède au réseau : les tests lisent ensuite
`tests/data/` sans réseau. Sources (voir `docs/referentiels.md`) :

- MNH et MNT LiDAR HD : WMS-R IGN (GetMap GeoTIFF float32, 0,5 m), réduits ici ;
- BD Forêt V2 : WFS IGN (polygones, GeoPackage) ;
- date de vol : WFS IGN, couche de métadonnées LiDAR HD ;
- Sentinel-2 L2A : Earth Search (STAC, COG anonymes), année de vol, mai à septembre ;
- références à battre (mission 007) : hauteur FORMS-T v1 de l'année de vol (Zenodo,
  lecture par fenêtre `/vsicurl/`, sans compte).

Usage : python scripts/fabriquer_jeu_essai.py [--sortie tests/data] [--seulement references|ortho]

`--seulement references` n'extrait que les références (lit le manifeste déjà présent pour
l'année de vol, ajoute leurs entrées à `PROVENANCE` sans toucher aux autres fichiers).

`--seulement ortho` (mission 012) ajoute les descripteurs de la BD ORTHO 20 cm à 10 m
(`ortho/{dalle}_ortho_10m.tif`, calculés à la volée, l'ortho n'est pas conservée) sans toucher
aux autres fichiers ; seule `PROVENANCE` reçoit des entrées en plus.

Les paramètres sont regroupés ci-dessous. Les choix marqués PROVISOIRE sont écrits dans
`PROVENANCE` (valeurs à geler avant la fusion de la mission 003).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pyproj
import rasterio
import yaml
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from rasterio.windows import from_bounds
from shapely.geometry import box

# --------------------------------------------------------------------------- paramètres

CONF_DEFAUT = Path(__file__).resolve().parent.parent / "conf" / "jeu_essai.yaml"


def charger_conf(chemin: Path) -> SimpleNamespace:
    """Lit `conf/jeu_essai.yaml` ; chaque clé devient un attribut (conf.dalles, conf.crs...)."""
    return SimpleNamespace(**yaml.safe_load(chemin.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- réseau


def _lire(url: str, donnees: bytes | None = None, entetes: dict | None = None) -> bytes:
    """GET (ou POST) avec trois essais."""
    derniere = None
    for essai in range(3):
        try:
            req = urllib.request.Request(url, donnees, entetes or {})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            derniere = e
            time.sleep(2 * (essai + 1))
    raise RuntimeError(f"échec réseau : {url[:200]} : {derniere}")


def _lire_json(url: str, essais: int = 5) -> dict:
    """GET d'un JSON ; le WFS IGN renvoie par moments une page qui n'en est pas un."""
    for essai in range(essais):
        brut = _lire(url)
        if brut[:1] in (b"{", b"["):
            return json.loads(brut)
        time.sleep(3 * (essai + 1))
    raise RuntimeError(f"réponse non JSON après {essais} essais : {url[:200]}")


def _url(base: str, **params: str) -> str:
    return base + "?" + urllib.parse.urlencode(params, safe=",:()'")


# --------------------------------------------------------------------------- dalles


def emprise(dalle: str) -> tuple[float, float, float, float]:
    """Emprise nominale (xmin, ymin, xmax, ymax) en Lambert-93, de `XXXX-YYYY` (coin NO, km)."""
    x, y = (int(v) for v in dalle.split("-"))
    return (x * 1000.0, y * 1000.0 - 1000.0, x * 1000.0 + 1000.0, y * 1000.0)


def metadonnees_vol(conf: SimpleNamespace, dalle: str) -> dict:
    xmin, ymin, xmax, ymax = emprise(dalle)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    url = _url(
        conf.wfs,
        SERVICE="WFS",
        VERSION="2.0.0",
        REQUEST="GetFeature",
        TYPENAMES=conf.couche_meta,
        OUTPUTFORMAT="application/json",
        COUNT="5",
        CQL_FILTER=f"BBOX(geom,{cx - 1},{cy - 1},{cx + 1},{cy + 1},'{conf.crs}')",
    )
    for f in json.loads(_lire(url))["features"]:
        if f["properties"].get("coordonnees_nw") == dalle:
            p = f["properties"]
            return {
                "date_vol_debut": p["date_debut_acquisition"].rstrip("Z"),
                "date_vol_fin": p["date_fin_acquisition"].rstrip("Z"),
                "mission": p.get("code_mission"),
                "capteur": p.get("capteur"),
                "requete": url,
            }
    raise RuntimeError(f"dalle {dalle} absente des métadonnées LiDAR HD")


# --------------------------------------------------------------------------- LiDAR


def verifier_crs_source(crs_source, crs_attendu: str) -> None:
    """Échoue si le CRS du GetMap n'est pas Lambert-93.

    Le WKT renvoyé par l'IGN n'a pas de code EPSG et son datum est « unnamed » (ellipsoïde
    WGS84 au lieu de GRS80 : écart de 1/f de l'ordre de 1e-6, sans effet à l'échelle du mm
    sur 1 km). L'égalité stricte de pyproj échoue donc ; on tente d'abord l'équivalence
    complète, à défaut on compare projection (Lambert conique conforme 2 parallèles) et
    paramètres un à un.
    """
    voulu = pyproj.CRS.from_user_input(crs_attendu)
    obtenu = pyproj.CRS(crs_source.to_wkt())
    if obtenu.equals(voulu, ignore_axis_order=True):
        return
    attendus = {p.name.lower(): p.value for p in voulu.coordinate_operation.params}
    recus = {p.name.lower(): p.value for p in obtenu.coordinate_operation.params}
    methode = obtenu.coordinate_operation.method_name.lower()
    ok = "lambert" in methode and "conic" in methode and "2sp" in methode.replace(" ", "")
    ok = ok or ("lambert" in methode and "conformal" in methode and "2" in methode)
    ok = ok and attendus.keys() == recus.keys()
    ok = ok and all(abs(attendus[k] - recus[k]) < 1e-6 for k in attendus if k in recus)
    ok = ok and abs(obtenu.ellipsoid.semi_major_metre - voulu.ellipsoid.semi_major_metre) < 1e-3
    ok = ok and abs(obtenu.ellipsoid.inverse_flattening - voulu.ellipsoid.inverse_flattening) < 1e-5
    ok = ok and obtenu.prime_meridian.longitude == voulu.prime_meridian.longitude == 0.0
    ok = ok and [a.direction for a in obtenu.axis_info] == [a.direction for a in voulu.axis_info]
    if not ok:
        raise RuntimeError(f"CRS du GetMap non équivalent à {crs_attendu} : {obtenu.name}")


def telecharger_getmap(conf: SimpleNamespace, couche: str, dalle: str) -> tuple[np.ndarray, str]:
    """GetMap 2000 x 2000 float32 pour une dalle ; renvoie le tableau (nodata -> NaN)."""
    xmin, ymin, xmax, ymax = emprise(dalle)
    d = conf.pas_source_m / 2  # les centres de pixel IGN sont sur des coordonnées entières
    bbox = f"{xmin - d},{ymin + d},{xmax - d},{ymax + d}"
    n = int(round(1000 / conf.pas_source_m))
    url = _url(
        conf.wms,
        SERVICE="WMS",
        VERSION="1.3.0",
        EXCEPTIONS="text/xml",
        REQUEST="GetMap",
        LAYERS=couche,
        FORMAT="image/geotiff",
        STYLES="",
        CRS=conf.crs,
        BBOX=bbox,
        WIDTH=str(n),
        HEIGHT=str(n),
    )
    with rasterio.MemoryFile(_lire(url)) as mf, mf.open() as src:
        assert src.shape == (n, n), src.shape
        verifier_crs_source(src.crs, conf.crs)
        o = src.transform
        assert abs(o.c - (xmin - d)) < 1e-6 and abs(o.f - (ymax + d)) < 1e-6, o
        arr = src.read(1).astype("float32")
        nd = src.nodata
    arr[arr == (nd if nd is not None else conf.nodata_mnt)] = np.nan
    return arr, url


def _blocs(arr: np.ndarray, k: int) -> np.ndarray:
    n = arr.shape[0] // k
    return arr.reshape(n, k, n, k).swapaxes(1, 2).reshape(n, n, k * k)


def reduire(conf: SimpleNamespace, arr: np.ndarray, pas_m: float, methode: str) -> np.ndarray:
    """Réduit par blocs : les cellules ont leurs bords sur les multiples de `pas_m`."""
    k = int(round(pas_m / conf.pas_source_m))
    b = _blocs(arr, k)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmax(b, axis=2) if methode == "max" else np.nanmean(b, axis=2)


def ecrire_raster(
    conf: SimpleNamespace,
    chemin: Path,
    data: np.ndarray,
    dalle: str,
    pas_m: float,
    nodata,
    tags: dict,
):
    xmin, _, _, ymax = emprise(dalle)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        chemin,
        "w",
        driver="GTiff",
        height=data.shape[-2],
        width=data.shape[-1],
        count=data.shape[0] if data.ndim == 3 else 1,
        dtype=data.dtype,
        crs=conf.crs,
        transform=from_origin(xmin, ymax, pas_m, pas_m),
        nodata=nodata,
        predictor=3 if data.dtype.kind == "f" else 2,
        tiled=False,
        **conf.compression,
    ) as dst:
        dst.write(data if data.ndim == 3 else data[None])
        dst.update_tags(**{k: str(v) for k, v in tags.items()})
        if tags.get("bandes"):
            for i, nom in enumerate(tags["bandes"].split(","), start=1):
                dst.set_band_description(i, nom)


def fabriquer_lidar(conf: SimpleNamespace, dalle: str, sortie: Path, prov: dict) -> None:
    mnh, url_mnh = telecharger_getmap(conf, conf.couche_mnh, dalle)
    mnt, url_mnt = telecharger_getmap(conf, conf.couche_mnt, dalle)
    today = date.today().isoformat()

    r = reduire(conf, mnh, conf.mnh_pas_m, "max")
    cm = np.where(np.isnan(r), conf.nodata_hauteur, np.round(np.clip(r, 0, None) * 100)).astype(
        "uint16"
    )
    f = f"lidar/{dalle}_MNH_2m.tif"
    ecrire_raster(
        conf,
        sortie / f,
        cm,
        dalle,
        conf.mnh_pas_m,
        conf.nodata_hauteur,
        {"unite": "cm", "reduction": "PROVISOIRE : maximum des pixels de 0,5 m par cellule de 2 m"},
    )
    prov[f] = {
        "source": "IGN, MNH LiDAR HD (WMS-R GetMap, couche " + conf.couche_mnh + ")",
        "requete": url_mnh,
        "date": today,
        "licence": conf.licence_ign,
        "traitement": (
            "PROVISOIRE : 0,5 m -> 2 m par maximum ; hauteurs négatives bornées à 0 ; "
            "uint16 en cm ; nodata IGN (-9999) -> 65535 (spec § 2)"
        ),
    }

    r = reduire(conf, mnt, conf.mnt_pas_m, "mean")
    r = np.where(np.isnan(r), conf.nodata_mnt, r).astype("float32")
    f = f"lidar/{dalle}_MNT_10m.tif"
    ecrire_raster(
        conf,
        sortie / f,
        r,
        dalle,
        conf.mnt_pas_m,
        conf.nodata_mnt,
        {"unite": "m", "reduction": "PROVISOIRE : moyenne"},
    )
    prov[f] = {
        "source": "IGN, MNT LiDAR HD (WMS-R GetMap, couche " + conf.couche_mnt + ")",
        "requete": url_mnt,
        "date": today,
        "licence": conf.licence_ign,
        "traitement": (
            "PROVISOIRE : 0,5 m -> 10 m par moyenne ; float32, altitude IGN69 en m ; nodata -9999"
        ),
    }


# --------------------------------------------------------------------------- BD Forêt


def fabriquer_foret(
    conf: SimpleNamespace, dalle: str, sortie: Path, prov: dict
) -> dict[str, float]:
    """Écrit le masque forêt ; renvoie la surface (ha) par essence BD Forêt sur la dalle."""
    xmin, ymin, xmax, ymax = emprise(dalle)
    url = _url(
        conf.wfs,
        SERVICE="WFS",
        VERSION="2.0.0",
        REQUEST="GetFeature",
        TYPENAMES=conf.couche_foret,
        OUTPUTFORMAT="application/json",
        SRSNAME=conf.crs,
        CQL_FILTER=f"BBOX(geom,{xmin},{ymin},{xmax},{ymax},'{conf.crs}')",
    )
    gdf = gpd.read_file(io.BytesIO(_lire(url)))
    gdf = gdf.set_crs(conf.crs, allow_override=True)
    gdf["geometry"] = gdf.geometry.intersection(box(xmin, ymin, xmax, ymax))
    gdf = gdf[~gdf.geometry.is_empty][["id", "code_tfv", "tfv", "tfv_g11", "essence", "geometry"]]
    gdf["id"] = gdf["id"].astype(str)
    gdf["dalle"] = dalle
    f = f"foret/{dalle}_bdforet_v2.gpkg"
    (sortie / f).parent.mkdir(parents=True, exist_ok=True)
    (sortie / f).unlink(missing_ok=True)
    gdf.to_file(sortie / f, driver="GPKG", layer="formation_vegetale")
    prov[f] = {
        "source": "IGN, BD Forêt V2 (WFS, couche " + conf.couche_foret + ")",
        "requete": url,
        "date": date.today().isoformat(),
        "licence": conf.licence_ign,
        "traitement": "polygones découpés à l'emprise de la dalle, Lambert-93, attributs conservés",
    }
    return (gdf.groupby("essence").geometry.apply(lambda g: g.area.sum()) / 1e4).to_dict()


# --------------------------------------------------------------------------- Sentinel-2


def annee_vol(m: dict) -> str:
    """Année de vol de la dalle (manifeste) ; début et fin doivent être de la même année."""
    a = m["date_vol_debut"][:4]
    assert a == m["date_vol_fin"][:4], f"vol à cheval sur deux années : {m}"
    return a


def chercher_scenes(conf: SimpleNamespace, dalle: str, annee: str) -> tuple[list[dict], str]:
    poly = gpd.GeoSeries([box(*emprise(dalle))], crs=conf.crs).to_crs(4326).iloc[0]
    corps = {
        "collections": ["sentinel-2-l2a"],
        "intersects": poly.__geo_interface__,
        "datetime": f"{annee}-{conf.s2_fenetre[0]}T00:00:00Z/"
        f"{annee}-{conf.s2_fenetre[1]}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": conf.s2_nuage_scene_max}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        "limit": 100,
    }
    brut = _lire(
        conf.stac + "/search", json.dumps(corps).encode(), {"Content-Type": "application/json"}
    )
    return json.loads(brut)["features"], json.dumps(corps)


def decouper(
    conf: SimpleNamespace,
    item: dict,
    assets: dict,
    dalle: str,
    pas_m: float,
    dtype: str,
    nearest=True,
):
    """Découpe les bandes sur la dalle, grille de `pas_m` m, bords sur les multiples de pas_m."""
    xmin, ymin, xmax, ymax = emprise(dalle)
    n = int(round(1000 / pas_m))
    dst_t = from_origin(xmin, ymax, pas_m, pas_m)
    out = np.zeros((len(assets), n, n), dtype=dtype)
    for i, cle in enumerate(assets.values()):
        with rasterio.open(item["assets"][cle]["href"]) as src:
            reproject(
                rasterio.band(src, 1),
                out[i],
                dst_transform=dst_t,
                dst_crs=conf.crs,
                resampling=Resampling.nearest,
            )
    return out


def fabriquer_sentinel2(
    conf: SimpleNamespace, dalle: str, annee: str, sortie: Path, prov: dict, lignes: list[dict]
) -> None:
    items, corps = chercher_scenes(conf, dalle, annee)
    retenus, mois = 0, set()
    for item in items[: conf.s2_candidats_max]:
        if retenus >= conf.s2_nb_scenes:
            break
        mois_item = item["properties"]["datetime"][:7]
        if mois_item in mois:  # une scène par mois : écarte les doublons de saison
            continue
        scl = decouper(conf, item, {"SCL": "scl"}, dalle, 20.0, "uint8")[0]
        if np.isin(scl, conf.scl_mauvais).mean() > conf.s2_nuage_dalle_max:
            continue
        d20 = decouper(conf, item, conf.s2_bandes_20m, dalle, 20.0, "uint16")
        d10 = decouper(conf, item, conf.s2_bandes_10m, dalle, 10.0, "uint16")
        if (d10 == 0).any() or (d20[:-1] == 0).any():  # dalle mal couverte par la scène
            continue
        d20[-1] = scl  # SCL (uint8) rangée comme dernière bande, valeurs 0 à 11
        p = item["properties"]
        assert p["datetime"][:4] == annee, (item["id"], annee)
        tags = {
            "capteur": p.get("platform", "sentinel-2"),
            "scene": item["id"],
            "datetime": p["datetime"],
            "processing_baseline": p.get("s2:processing_baseline"),
            "nuage_scene_pct": p.get("eo:cloud_cover"),
            "valeurs": conf.s2_valeurs,
            "reechantillonnage": "plus proche voisin, depuis UTM 31N vers EPSG:2154",
        }
        for pas, bandes, d in ((10, conf.s2_bandes_10m, d10), (20, conf.s2_bandes_20m, d20)):
            noms = list(bandes)
            f = f"sentinel2/{dalle}/{item['id']}_{pas}m.tif"
            ecrire_raster(
                conf, sortie / f, d, dalle, float(pas), None, {**tags, "bandes": ",".join(noms)}
            )
            prov[f] = {
                "source": "Copernicus Sentinel-2 L2A via Earth Search (Element84), scène "
                + item["id"],
                "requete": f"POST {conf.stac}/search {corps} ; assets COG "
                + ", ".join(item["assets"][c]["href"] for c in bandes.values()),
                "date": date.today().isoformat(),
                "licence": conf.licence_s2.format(annee=annee),
                "traitement": (
                    f"bandes {','.join(noms)} découpées sur la dalle, grille de {pas} m "
                    "alignée sur le km, plus proche voisin, entiers conservés"
                    + (" ; SCL en dernière bande (uint8 -> uint16)" if pas == 20 else "")
                    + " ; valeurs : "
                    + conf.s2_valeurs
                ),
            }
            lignes.append(
                {
                    "dalle": dalle,
                    "scene": item["id"],
                    "date_scene": p["datetime"],
                    "nuage_scene_pct": p.get("eo:cloud_cover"),
                    "processing_baseline": p.get("s2:processing_baseline"),
                    "resolution_m": pas,
                    "bandes": " ".join(noms),
                    "fichier": f,
                }
            )
        mois.add(mois_item)
        retenus += 1
        print(f"  {dalle} S2 {item['id']} (nuage scène {p.get('eo:cloud_cover'):.1f} %)")
    if retenus == 0:
        raise RuntimeError(f"aucune scène Sentinel-2 exploitable pour {dalle}")


# --------------------------------------------------------------------------- références


def convertir_reference(brut: np.ndarray, nodata_source: int, nodata: int) -> np.ndarray:
    """Hauteur de référence en cm vers la convention du projet : uint16, nodata `nodata`.

    Le nodata source (0 chez FORMS-T) devient `nodata` (65535) : 0 est une hauteur valide chez
    nous. Une valeur négative n'est pas une hauteur : elle devient aussi `nodata`.
    """
    invalide = (brut == nodata_source) | (brut < 0)
    return np.where(invalide, nodata, brut.astype("int64")).astype("uint16")


def fabriquer_reference(
    conf: SimpleNamespace, nom: str, dalle: str, annee: str, sortie: Path, prov: dict
) -> None:
    """Extrait la fenêtre de la dalle dans la référence `nom` (sans rééchantillonnage)."""
    ref = SimpleNamespace(**conf.references[nom])
    url = ref.url.format(annee=annee)
    xmin, ymin, xmax, ymax = emprise(dalle)
    with rasterio.open("/vsicurl/" + url) as src:
        verifier_crs_source(src.crs, conf.crs)
        assert str(src.dtypes[0]) == ref.dtype_source, src.dtypes
        assert src.nodata == ref.nodata_source, src.nodata
        t = src.transform
        assert (t.a, -t.e) == (ref.pas_m, ref.pas_m), t
        fen = from_bounds(xmin, ymin, xmax, ymax, transform=t)
        cols, lignes = fen.col_off, fen.row_off
        # Grille alignée : la fenêtre tombe sur des pixels entiers (aucun rééchantillonnage).
        assert float(cols).is_integer() and float(lignes).is_integer(), fen
        n = int(round(1000 / ref.pas_m))
        assert (fen.width, fen.height) == (n, n), fen
        brut = src.read(1, window=fen)
    cm = convertir_reference(brut, ref.nodata_source, conf.nodata_hauteur)
    f = ref.fichier.format(dalle=dalle, annee=annee)
    ecrire_raster(
        conf,
        sortie / f,
        cm,
        dalle,
        ref.pas_m,
        conf.nodata_hauteur,
        {
            "unite": "cm",
            "reference": nom,
            "source": ref.source.format(annee=annee),
            "url": url,
            "doi": ref.doi,
            "version": ref.version,
            "annee": annee,
            "licence": ref.licence,
            "citation": ref.citation,
            "conversion": (
                f"{ref.dtype_source} {ref.unite_source} -> uint16 cm ; nodata "
                f"{ref.nodata_source} -> {conf.nodata_hauteur} ; aucun rééchantillonnage"
            ),
        },
    )
    prov[f] = {
        "source": ref.source.format(annee=annee) + f", DOI {ref.doi}, {ref.version}",
        "requete": f"/vsicurl/{url} ; fenêtre col {int(cols)}, ligne {int(lignes)}, {n} x {n} px",
        "date": date.today().isoformat(),
        "licence": ref.licence,
        "citation": ref.citation,
        "traitement": (
            f"fenêtre de la dalle lue telle quelle (pas {ref.pas_m:g} m aligné sur le km, aucun "
            f"rééchantillonnage) ; {ref.dtype_source} en {ref.unite_source} -> uint16 en cm ; "
            f"nodata source {ref.nodata_source} -> {conf.nodata_hauteur} (0 est une hauteur "
            "valide dans le projet) ; valeurs négatives -> nodata ; année = année de vol"
        ),
    }


def lire_provenance(sortie: Path) -> dict:
    """Entrées existantes de `PROVENANCE` (vide si le fichier n'existe pas)."""
    chemin = sortie / "PROVENANCE"
    if not chemin.is_file():
        return {}
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))["fichiers"]


def fabriquer_references(conf: SimpleNamespace, sortie: Path, prov: dict, meta: dict) -> None:
    for nom in conf.references:
        for d in conf.dalles:
            print(f"dalle {d} : référence {nom}")
            fabriquer_reference(conf, nom, d, annee_vol(meta[d]), sortie, prov)


def meta_du_manifeste(sortie: Path) -> dict:
    """Dates de vol lues dans le manifeste déjà fabriqué (mode `--seulement references`)."""
    man = gpd.read_parquet(sortie / "manifeste_dalles.parquet")
    return {
        r.id: {"date_vol_debut": r.date_vol_debut, "date_vol_fin": r.date_vol_fin}
        for r in man.itertuples()
    }


# --------------------------------------------------------------------------- BD ORTHO (mission 012)


def telecharger_ortho(
    conf: SimpleNamespace, couche: str, dalle: str
) -> tuple[np.ndarray, list[str]]:
    """GetMap de la BD ORTHO 20 cm sur une dalle : tableau (3, 5000, 5000) uint8 et URL(s).

    `ortho.decoupes` = nombre de requêtes par côté (1 : une seule de 5000 x 5000 px, que le
    serveur accepte ; 2 : quatre quarts si la taille est limitée). Emprise exacte de la dalle,
    sans demi-pixel (les bords de pixel IGN tombent sur la grille de 0,2 m).
    """
    o = SimpleNamespace(**conf.ortho)
    xmin, ymin, xmax, ymax = emprise(dalle)
    n = int(round(1000 / o.pas_m))
    k = int(o.decoupes)
    assert n % k == 0, (n, k)
    m, pas = n // k, 1000.0 / k
    out = np.zeros((3, n, n), dtype="uint8")
    urls = []
    for i in range(k):  # i : ligne (du nord au sud), j : colonne (d'ouest en est)
        for j in range(k):
            x0, y1 = xmin + j * pas, ymax - i * pas
            url = _url(
                conf.wms,
                SERVICE="WMS",
                VERSION="1.3.0",
                EXCEPTIONS="text/xml",
                REQUEST="GetMap",
                LAYERS=couche,
                FORMAT="image/geotiff",
                STYLES="",
                CRS=conf.crs,
                BBOX=f"{x0},{y1 - pas},{x0 + pas},{y1}",
                WIDTH=str(m),
                HEIGHT=str(m),
            )
            with rasterio.MemoryFile(_lire(url)) as mf, mf.open() as src:
                assert src.shape == (m, m) and src.count >= 3, (src.shape, src.count)
                verifier_crs_source(src.crs, conf.crs)
                t = src.transform
                assert abs(t.c - x0) < 1e-6 and abs(t.f - y1) < 1e-6, t
                assert abs(t.a - o.pas_m) < 1e-9 and abs(-t.e - o.pas_m) < 1e-9, t
                out[:, i * m : (i + 1) * m, j * m : (j + 1) * m] = src.read([1, 2, 3])
            urls.append(url)
    return out, urls


def date_ortho(conf: SimpleNamespace, dalle: str) -> dict:
    """Date de prise de vue de la BD ORTHO sur la dalle, d'après le graphe de mosaïquage (WFS IGN).

    Le graphe donne, par polygone (département et campagne `pva`), la date de vol de l'ortho
    publiée. `date` : date du polygone au centre de la dalle (la plus ancienne s'il y en a
    plusieurs) ; `date_min` et `date_max` : dates des polygones qui touchent la dalle.
    """
    o = SimpleNamespace(**conf.ortho)
    xmin, ymin, xmax, ymax = emprise(dalle)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    poly = f"POLYGON(({xmin} {ymin},{xmax} {ymin},{xmax} {ymax},{xmin} {ymax},{xmin} {ymin}))"

    def requete(geom: str) -> tuple[list[dict], str]:
        url = _url(
            conf.wfs,
            SERVICE="WFS",
            VERSION="2.0.0",
            REQUEST="GetFeature",
            TYPENAMES=o.couche_graphe,
            OUTPUTFORMAT="application/json",
            PROPERTYNAME="dep,pva,res,echelle,date_vol",
            CQL_FILTER=f"INTERSECTS(geom,SRID=2154;{geom}) AND echelle={o.echelle_graphe}",
        )
        return [f["properties"] for f in _lire_json(url)["features"]], url

    centre, url = requete(f"POINT({cx} {cy})")
    dans_dalle, _ = requete(poly)
    if not centre or not dans_dalle:
        raise RuntimeError(f"dalle {dalle} absente du graphe de mosaïquage BD ORTHO")

    def dates(ps: list[dict]) -> list[str]:
        return sorted(p["date_vol"].rstrip("Z") for p in ps)

    return {
        "date": dates(centre)[0],
        "date_min": dates(dans_dalle)[0],
        "date_max": dates(dans_dalle)[-1],
        "campagnes": sorted({int(p["pva"]) for p in dans_dalle}),
        "departements": sorted({str(p["dep"]) for p in dans_dalle}),
        "requete": url,
    }


def _par_cellules(x: np.ndarray, k: int) -> np.ndarray:
    """(H, W) -> (H/k, k, W/k, k) : les axes 1 et 3 parcourent les pixels d'une cellule."""
    h, w = x.shape
    return x.reshape(h // k, k, w // k, k)


def descripteurs_ortho(
    rvb: np.ndarray, irc: np.ndarray, o: dict | SimpleNamespace, k: int | None = None
) -> np.ndarray:
    """Descripteurs par cellule de k x k pixels (50 = 10 m) : tableau (bandes, H/k, W/k) float32.

    `rvb` et `irc` : (3, H, W) uint8 (IRC : R = proche infrarouge, G = rouge, B = vert). Pixel
    invalide : blanc pur (255, 255, 255) dans l'une des deux images (hors couverture) ou
    PIR + R = 0. Cellule invalide (moins de `valide_min` de pixels valides) : `nodata`.
    Ordre des bandes : `o.bandes`. Calcul par bandes de lignes de cellules (peu de mémoire).
    """
    o = o if isinstance(o, SimpleNamespace) else SimpleNamespace(**o)
    k = k or int(round(o.cellule_m / o.pas_m))
    _, h, w = rvb.shape
    assert irc.shape == rvb.shape and h % k == 0 and w % k == 0, (rvb.shape, irc.shape, k)
    nh, nw = h // k, w // k
    sortie = np.full((len(o.bandes), nh, nw), o.nodata, dtype="float32")
    lignes = 10  # lignes de cellules par bande
    for c0 in range(0, nh, lignes):
        c1 = min(c0 + lignes, nh)
        p0, p1 = c0 * k, c1 * k
        a, b = max(p0 - 1, 0), min(p1 + 1, h)  # une ligne de plus de chaque côté : gradient exact
        v = rvb[:, a:b].astype("float32")
        i = irc[:, a:b].astype("float32")
        lum = 0.299 * v[0] + 0.587 * v[1] + 0.114 * v[2]
        gy, gx = np.gradient(lum)
        grad = np.hypot(gx, gy)
        valide = ~((rvb[:, a:b] == 255).all(0) | (irc[:, a:b] == 255).all(0))
        pir, rouge = i[0], i[1]
        somme = pir + rouge
        valide &= somme > 0
        ndvi = np.where(valide, (pir - rouge) / np.where(somme > 0, somme, 1), 0).astype("float32")
        c = slice(p0 - a, p1 - a)
        valide, pir, rouge, ndvi, lum, grad = (x[c] for x in (valide, pir, rouge, ndvi, lum, grad))
        n = _par_cellules(valide, k).sum(axis=(1, 3))
        ok = n >= o.valide_min * k * k
        nn = np.maximum(n, 1)

        def moy(x: np.ndarray, valide=valide, nn=nn) -> np.ndarray:
            return _par_cellules(np.where(valide, x, 0), k).sum(axis=(1, 3), dtype="float64") / nn

        def ecart(x: np.ndarray, m: np.ndarray, valide=valide, nn=nn) -> np.ndarray:
            x2 = _par_cellules(np.where(valide, x.astype("float64") ** 2, 0), k)
            return np.sqrt(np.maximum(x2.sum(axis=(1, 3)) / nn - m**2, 0))

        m_r, m_p, m_n, m_l = moy(rouge), moy(pir), moy(ndvi), moy(lum)
        valeurs = {
            "rouge_moy": m_r,
            "rouge_std": ecart(rouge, m_r),
            "pir_moy": m_p,
            "pir_std": ecart(pir, m_p),
            "ndvi_moy": m_n,
            "ndvi_std": ecart(ndvi, m_n),
            "part_non_vegetal": moy((ndvi < o.seuil_ndvi_non_vegetal).astype("float32")),
            "part_ombre": moy((lum < o.seuil_ombre_luminance).astype("float32")),
            "lum_moy": m_l,
            "lum_std": ecart(lum, m_l),
            "gradient_moy": moy(grad),
            "part_valide": n / float(k * k),
        }
        for idx, nom in enumerate(o.bandes):
            bande = valeurs[nom].astype("float32")
            sortie[idx, c0:c1] = np.where(ok | (nom == "part_valide"), bande, o.nodata)
    return sortie


def ecart_jours(date_ortho_iso: str, vol_debut: str, vol_fin: str) -> int:
    """Écart (jours) entre la prise de vue de l'ortho et le milieu du vol LiDAR (ortho - vol)."""
    d = date.fromisoformat(date_ortho_iso[:10])
    a, b = date.fromisoformat(vol_debut[:10]), date.fromisoformat(vol_fin[:10])
    return (d - (a + (b - a) / 2)).days


def fabriquer_ortho(
    conf: SimpleNamespace, dalle: str, sortie: Path, prov: dict, meta: dict
) -> dict:
    """Descripteurs ortho 10 m d'une dalle (l'ortho n'est jamais écrite) ; renvoie un résumé."""
    o = SimpleNamespace(**conf.ortho)
    t0 = time.time()
    rvb, urls_rvb = telecharger_ortho(conf, o.couche_rvb, dalle)
    irc, urls_irc = telecharger_ortho(conf, o.couche_irc, dalle)
    cor = float(np.corrcoef(rvb[0, ::7, ::7].ravel(), irc[1, ::7, ::7].ravel())[0, 1])
    if cor < 0.9:  # le rouge du RVB et celui de l'IRC doivent concorder (même vol, mêmes pixels)
        raise RuntimeError(f"{dalle} : rouge RVB et rouge IRC non concordants (r = {cor:.2f})")
    d = descripteurs_ortho(rvb, irc, o)
    del rvb, irc
    dt = date_ortho(conf, dalle)
    ecart = ecart_jours(dt["date"], meta["date_vol_debut"], meta["date_vol_fin"])
    f = o.fichier.format(dalle=dalle)
    tags = {
        "bandes": ",".join(o.bandes),
        "unite": "rouge, pir, lum, lum_std : compte numérique 0-255 ; ndvi : sans unité ; "
        "part_* : fraction 0-1 ; gradient_moy : compte numérique par pixel de 0,2 m",
        "source": "IGN, BD ORTHO 20 cm RVB et IRC (WMS-R) ; " + conf.licence_ign,
        "couches": f"{o.couche_rvb} ; {o.couche_irc}",
        "date_prise_de_vue": dt["date"],
        "date_prise_de_vue_min": dt["date_min"],
        "date_prise_de_vue_max": dt["date_max"],
        "campagnes_pva": ",".join(map(str, dt["campagnes"])),
        "departements": ",".join(dt["departements"]),
        "source_date": "IGN, graphe de mosaïquage BD ORTHO (WFS " + o.couche_graphe + ")",
        "vol_lidar_debut": meta["date_vol_debut"][:10],
        "vol_lidar_fin": meta["date_vol_fin"][:10],
        "ecart_ortho_vol_lidar_jours": ecart,
        "seuil_ndvi_non_vegetal": o.seuil_ndvi_non_vegetal,
        "seuil_ombre_luminance": o.seuil_ombre_luminance,
        "traitement": "PROVISOIRE : statistiques par cellule de 10 m (50 x 50 px de 0,2 m) ; "
        "ortho non conservée ; seuils provisoires",
    }
    ecrire_raster(conf, sortie / f, d, dalle, o.cellule_m, o.nodata, tags)
    prov[f] = {
        "source": "IGN, BD ORTHO 20 cm RVB et IRC (WMS-R, couches "
        + f"{o.couche_rvb} et {o.couche_irc}) ; date de prise de vue : graphe de mosaïquage "
        + f"(WFS, couche {o.couche_graphe}), {dt['date']} (campagne {dt['campagnes']})",
        "requete": " ; ".join(urls_rvb + urls_irc) + " ; " + dt["requete"],
        "date": date.today().isoformat(),
        "licence": o.licence,
        "traitement": (
            f"PROVISOIRE : calculé à la volée sur l'ortho 0,2 m (non conservée), par cellule de "
            f"{o.cellule_m:g} m : {', '.join(o.bandes)} ; NDVI = (PIR - R) / (PIR + R) ; "
            f"non végétal = NDVI < {o.seuil_ndvi_non_vegetal} ; ombre = luminance < "
            f"{o.seuil_ombre_luminance} ; float32, nodata {o.nodata:g} ; date de prise de vue "
            f"{dt['date']} ({dt['date_min']} à {dt['date_max']}), écart au vol LiDAR "
            f"{ecart:+d} jours (milieu du vol)"
        ),
    }
    return {"dalle": dalle, "date": dt["date"], "ecart_jours": ecart, "duree_s": time.time() - t0}


def bornes_ortho(nom: str) -> tuple[float, float]:
    """Plage attendue d'une bande ortho (contrôle intégré)."""
    if nom.startswith("part_") or nom == "ndvi_std":
        return 0.0, 1.0
    if nom == "ndvi_moy":
        return -1.0, 1.0
    return 0.0, 255.0


def controler_ortho(conf: SimpleNamespace, chemin: Path, dalle: str) -> list[str]:
    """Erreurs d'un fichier ortho 10 m : CRS, emprise, pas, bandes, tags, date, plages."""
    o = SimpleNamespace(**conf.ortho)
    f = chemin.name
    if not chemin.is_file():
        return [f"{f} absent"]
    erreurs = []
    attendu = tuple(float(v) for v in emprise(dalle))
    with rasterio.open(chemin) as src:
        if pyproj.CRS.from_user_input(src.crs.to_wkt()) != pyproj.CRS.from_user_input(conf.crs):
            erreurs.append(f"{f} : CRS {src.crs} différent de {conf.crs}")
        if tuple(round(v, 6) for v in src.bounds) != attendu:
            erreurs.append(f"{f} : emprise {tuple(src.bounds)} != {attendu}")
        if src.res != (o.cellule_m, o.cellule_m):
            erreurs.append(f"{f} : pas {src.res} != {o.cellule_m}")
        tags = src.tags()
        if src.count != len(o.bandes) or tags.get("bandes") != ",".join(o.bandes):
            erreurs.append(f"{f} : bandes {tags.get('bandes')} != {','.join(o.bandes)}")
        if src.dtypes[0] != "float32" or src.nodata != o.nodata:
            erreurs.append(f"{f} : type {src.dtypes[0]} ou nodata {src.nodata} inattendu")
        for cle in ("date_prise_de_vue", "vol_lidar_debut", "ecart_ortho_vol_lidar_jours"):
            if not tags.get(cle):
                erreurs.append(f"{f} : tag {cle} absent")
        try:
            date.fromisoformat(tags.get("date_prise_de_vue", ""))
        except ValueError:
            erreurs.append(f"{f} : date_prise_de_vue {tags.get('date_prise_de_vue')!r} illisible")
        a = src.read()
    if a.shape[0] != len(o.bandes):
        return erreurs
    valide = a[o.bandes.index("part_valide")] >= o.valide_min
    if not valide.any():
        erreurs.append(f"{f} : aucune cellule valide")
        return erreurs
    for i, nom in enumerate(o.bandes):
        v = a[i][valide]
        bas, haut = bornes_ortho(nom)
        if not np.isfinite(v).all() or v.min() < bas - 1e-4 or v.max() > haut + 1e-4:
            erreurs.append(f"{f} : {nom} hors de [{bas}, {haut}] ({v.min():.3f} à {v.max():.3f})")
    return erreurs


# --------------------------------------------------------------------------- manifeste, découpage


def ecrire_manifeste(conf: SimpleNamespace, sortie: Path, meta: dict, prov: dict) -> None:
    lignes = []
    for d in conf.dalles:
        m = meta[d]
        lignes.append(
            {
                "id": d,
                "xmin": emprise(d)[0],
                "ymin": emprise(d)[1],
                "xmax": emprise(d)[2],
                "ymax": emprise(d)[3],
                "date_vol_debut": m["date_vol_debut"],
                "date_vol_fin": m["date_vol_fin"],
                "mission": m["mission"],
                "source": "IGN LiDAR HD, métadonnées WFS " + conf.couche_meta,
                "geometry": box(*emprise(d)),
            }
        )
    gdf = gpd.GeoDataFrame(lignes, crs=conf.crs)
    gdf.to_parquet(sortie / "manifeste_dalles.parquet", index=False, compression="zstd")
    prov["manifeste_dalles.parquet"] = {
        "source": "IGN, métadonnées LiDAR HD (WFS " + conf.couche_meta + ")",
        "requete": " ; ".join(meta[d]["requete"] for d in conf.dalles),
        "date": date.today().isoformat(),
        "licence": conf.licence_ign,
        "traitement": "GeoParquet, EPSG:2154 ; emprise nominale de 1 km déduite de l'identifiant",
    }


def bloc(conf: SimpleNamespace, dalle: str) -> list[int]:
    xmin, ymin, _, _ = emprise(dalle)
    return [int(xmin // conf.taille_bloc_m), int(ymin // conf.taille_bloc_m)]


def dates_paire(conf: SimpleNamespace, paire: str, meta: dict) -> str:
    return " ; ".join(
        sorted(
            {
                f"{meta[d]['date_vol_debut']} -> {meta[d]['date_vol_fin']}"
                for d in conf.paires[paire]
            }
        )
    )


def essences_paire(conf: SimpleNamespace, paire: str, essences: dict) -> str:
    """Essences dominantes de la paire, par surface BD Forêt (les deux plus étendues)."""
    tot: dict[str, float] = {}
    for d in conf.paires[paire]:
        for nom, ha in essences[d].items():
            tot[nom] = tot.get(nom, 0.0) + ha
    haut = sorted(tot.items(), key=lambda kv: -kv[1])[:2]
    return ", ".join(f"{nom} {ha:.0f} ha" for nom, ha in haut)


def justification(conf: SimpleNamespace, meta: dict, essences: dict) -> str:
    appr, test = conf.apprentissage, conf.test
    dist = min(
        box(*emprise(a)).distance(box(*emprise(t)))
        for a in conf.paires[appr]
        for t in conf.paires[test]
    )
    return (
        f"Deux paires de dalles voisines, distantes d'au moins {dist / 1000:.0f} km (un bloc "
        f"fait {conf.taille_bloc_m // 1000} km) : aucune dalle de test ne touche une dalle "
        f"d'apprentissage. Apprentissage = paire {appr}, dalles {', '.join(conf.paires[appr])}, "
        f"vol {dates_paire(conf, appr, meta)}. Test = paire {test}, dalles "
        f"{', '.join(conf.paires[test])}, vol {dates_paire(conf, test, meta)}. "
        f"Essences dominantes (BD Forêt V2, surface sur les dalles) : paire {appr} = "
        f"{essences_paire(conf, appr, essences)} ; paire {test} = "
        f"{essences_paire(conf, test, essences)}. Si elles diffèrent, le test sort du "
        "peuplement d'apprentissage : exigeant mais honnête. Le choix inverse serait aussi "
        "valable ; décision du 22/11 (journal)."
    )


def ecrire_decoupage(
    conf: SimpleNamespace, sortie: Path, prov: dict, meta: dict, essences: dict
) -> None:
    doc = {
        "version": 1,
        "statut": "PROVISOIRE : choix proposé, à confirmer par Pascal ; test à figer au jalon 1",
        "taille_bloc_m": conf.taille_bloc_m,
        "bloc": "indice (xmin // taille_bloc_m, ymin // taille_bloc_m) de l'emprise de la dalle",
        "apprentissage": [
            {"dalle": d, "bloc": bloc(conf, d)} for d in conf.paires[conf.apprentissage]
        ],
        "test": [{"dalle": d, "bloc": bloc(conf, d)} for d in conf.paires[conf.test]],
        "justification": justification(conf, meta, essences),
    }
    (sortie / "decoupage.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    prov["decoupage.yaml"] = {
        "source": "choix du projet (script scripts/fabriquer_jeu_essai.py)",
        "requete": "sans objet (aucun accès réseau)",
        "date": date.today().isoformat(),
        "licence": "Licence Ouverte 2.0 (identifiants de dalles IGN)",
        "traitement": f"paire {conf.apprentissage} = apprentissage, paire {conf.test} = test",
    }


def ecrire_scenes(
    conf: SimpleNamespace, sortie: Path, lignes: list[dict], prov: dict, annees: list[str]
) -> None:
    with (sortie / "sentinel2_scenes.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)
    prov["sentinel2_scenes.csv"] = {
        "source": "Earth Search (Element84), métadonnées STAC des scènes retenues",
        "requete": f"POST {conf.stac}/search",
        "date": date.today().isoformat(),
        "licence": " ; ".join(conf.licence_s2.format(annee=a) for a in annees),
        "traitement": "une ligne par fichier Sentinel-2 : dalle, scène, date, nuage, baseline",
    }


def ecrire_provenance(conf: SimpleNamespace, sortie: Path, prov: dict) -> None:
    entete = (
        "# PROVENANCE du jeu d'essai (mission 002), généré par scripts/fabriquer_jeu_essai.py.\n"
        "# Une entrée par fichier de données : source, requête, date d'accès, licence.\n"
        "# Dates de vol : une seule source (WFS IGN), contrôle croisé TerraLab non fait.\n"
        "# Toute valeur marquée PROVISOIRE est à geler avant la fusion de la mission 003.\n"
    )
    corps = yaml.safe_dump(
        {"fichiers": dict(sorted(prov.items()))}, allow_unicode=True, sort_keys=False, width=100
    )
    (sortie / "PROVENANCE").write_text(entete + corps, encoding="utf-8")


# --------------------------------------------------------------------------- principal


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sortie", type=Path, default=Path("tests/data"))
    ap.add_argument("--conf", type=Path, default=CONF_DEFAUT)
    ap.add_argument(
        "--seulement",
        choices=["references", "ortho"],
        help="n'extraire que les références ou les descripteurs ortho (le reste du jeu doit "
        "déjà exister)",
    )
    args = ap.parse_args()
    conf = charger_conf(args.conf)
    sortie: Path = args.sortie
    sortie.mkdir(parents=True, exist_ok=True)

    if args.seulement == "references":
        prov = lire_provenance(sortie)
        fabriquer_references(conf, sortie, prov, meta_du_manifeste(sortie))
        ecrire_provenance(conf, sortie, prov)
        total = sum(p.stat().st_size for p in sortie.rglob("*") if p.is_file())
        print(f"total : {total / 1e6:.2f} Mo")
        return

    if args.seulement == "ortho":
        prov = lire_provenance(sortie)
        meta = meta_du_manifeste(sortie)
        for d in conf.dalles:
            r = fabriquer_ortho(conf, d, sortie, prov, meta[d])
            print(
                f"dalle {d} : ortho du {r['date']} ({r['ecart_jours']:+d} j), {r['duree_s']:.0f} s"
            )
            erreurs = controler_ortho(conf, sortie / conf.ortho["fichier"].format(dalle=d), d)
            if erreurs:
                raise SystemExit("contrôle en échec : " + " ; ".join(erreurs))
        ecrire_provenance(conf, sortie, prov)
        total = sum(p.stat().st_size for p in sortie.rglob("*") if p.is_file())
        print(f"total : {total / 1e6:.2f} Mo")
        return

    prov: dict = {}
    scenes: list[dict] = []
    meta = {}
    essences = {}
    for d in conf.dalles:
        print(f"dalle {d}")
        meta[d] = metadonnees_vol(conf, d)
        fabriquer_lidar(conf, d, sortie, prov)
        essences[d] = fabriquer_foret(conf, d, sortie, prov)
        fabriquer_sentinel2(conf, d, annee_vol(meta[d]), sortie, prov, scenes)
    fabriquer_references(conf, sortie, prov, meta)
    ecrire_manifeste(conf, sortie, meta, prov)
    ecrire_decoupage(conf, sortie, prov, meta, essences)
    ecrire_scenes(conf, sortie, scenes, prov, sorted({annee_vol(m) for m in meta.values()}))
    ecrire_provenance(conf, sortie, prov)
    total = sum(p.stat().st_size for p in sortie.rglob("*") if p.is_file())
    print(f"total : {total / 1e6:.2f} Mo")


if __name__ == "__main__":
    main()
