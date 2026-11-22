#!/usr/bin/env python
"""Fabrique le jeu d'essai de 4 dalles de 1 km (`tests/data/`), une fois, avec le réseau.

Mission 002. Seul script du dépôt qui accède au réseau : les tests lisent ensuite
`tests/data/` sans réseau. Sources (voir `docs/referentiels.md`) :

- MNH et MNT LiDAR HD : WMS-R IGN (GetMap GeoTIFF float32, 0,5 m), réduits ici ;
- BD Forêt V2 : WFS IGN (polygones, GeoPackage) ;
- date de vol : WFS IGN, couche de métadonnées LiDAR HD ;
- Sentinel-2 L2A : Earth Search (STAC, COG anonymes), année de vol, mai à septembre.

Usage : python scripts/fabriquer_jeu_essai.py [--sortie tests/data]

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
    args = ap.parse_args()
    conf = charger_conf(args.conf)
    sortie: Path = args.sortie
    sortie.mkdir(parents=True, exist_ok=True)

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
    ecrire_manifeste(conf, sortie, meta, prov)
    ecrire_decoupage(conf, sortie, prov, meta, essences)
    ecrire_scenes(conf, sortie, scenes, prov, sorted({annee_vol(m) for m in meta.values()}))
    ecrire_provenance(conf, sortie, prov)
    total = sum(p.stat().st_size for p in sortie.rglob("*") if p.is_file())
    print(f"total : {total / 1e6:.2f} Mo")


if __name__ == "__main__":
    main()
