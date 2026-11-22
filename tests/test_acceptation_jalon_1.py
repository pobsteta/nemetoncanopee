"""Tests d'acceptation du jalon 1 (mission 003, `docs/spec.md` § 4 critères 1 à 7).

Écrits avant le code (mission 004), d'après le plan validé `pilotage/missions/004-plan.md`
(§ 3 fichiers, § 4 signatures, § 5-6 valeurs et tags, § 8 tests attendus). Aucun import du
code testé au niveau du module : un module absent fait échouer le test, pas la collecte.
Le critère 8 (`.claude/test-command` vert, aucun test sauté) relève de la CI.
"""

import hashlib
import json
import re
import shutil
import socket
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from conftest import (
    CARRE_20M,
    CONF,
    DALLES,
    DONNEES,
    ETAPES,
    RACINE,
    arguments_zonal,
    lancer,
)

NODATA = 65535
VALEUR_MODELE_CM = (
    2626  # médiane 2625,5 cm des cibles d'apprentissage, arrondie demi_haut (plan § 5)
)
ANNEE = 2022
APPRENTISSAGE = ["0901-6665", "0902-6665"]
TEST = ["0939-6654", "0939-6655"]
DATE_VOL = {
    "0901-6665": "2022-07-27",
    "0902-6665": "2022-07-27",
    "0939-6654": "2022-10-17",
    "0939-6655": "2022-10-17",
}  # docs/referentiels.md § 8 et manifeste_dalles.parquet
MENTION = "Contains modified Copernicus Sentinel data 2022"
EXTENSIONS_STAC = {
    "https://stac-extensions.github.io/projection/v2.0.0/schema.json",
    "https://stac-extensions.github.io/raster/v1.1.0/schema.json",
    "https://stac-extensions.github.io/file/v2.1.0/schema.json",
    "https://stac-extensions.github.io/processing/v1.2.0/schema.json",
}  # spec § 2 : versions décidées le 22/11
COLONNES_ZONAL = [
    "id",
    "annee",
    "couche",
    "traitement",
    "unite",
    "moyenne",
    "mediane",
    "p10",
    "p90",
    "part_couverte",
    "incertitude_moyenne",
    "version_modele",
    "version_donnees",
    "date_vol",
    "dalles",
]  # plan § 4


def emprise(dalle: str) -> tuple[int, int, int, int]:
    """(xmin, ymin, xmax, ymax) en m ; l'identifiant est le coin nord-ouest en km."""
    x, y = int(dalle[:4]) * 1000, int(dalle[5:]) * 1000
    return x, y - 1000, x + 1000, y


def cog_path(travail: Path, dalle: str, traitement: str) -> Path:
    return (
        travail
        / "export"
        / "cog"
        / "hauteur"
        / str(ANNEE)
        / f"{dalle}_hauteur_{traitement}_{ANNEE}.tif"
    )


def lire(path: Path):
    with rasterio.open(path) as src:
        return src.read(1), src.profile, src.tags(), src.transform, src.crs, src.nodata


def hash_arbre(racine: Path) -> dict[str, str]:
    return {
        p.relative_to(racine).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(racine.rglob("*"))
        if p.is_file()
    }


def exiger_chaine(chaine) -> None:
    """Un test qui lit les sorties de la chaîne ne prouve rien si la chaîne n'a pas tourné."""
    assert all(chaine.codes.get(e) == 0 for e in ETAPES), (
        f"chaîne incomplète : codes={chaine.codes} erreurs={chaine.erreurs}"
    )


def copie_conf_et_donnees(base: Path, modifier_donnees=None) -> Path:
    """Copie `conf/` et `tests/data/` dans `base`, pointe la zone vers la copie, renvoie la conf.

    Suppose (plan § 2) `conf/zones/jeu_essai.yaml` avec `source: {mode: local, racine: ...}`.
    """
    conf = base / "conf"
    donnees = base / "data"
    shutil.copytree(RACINE / "conf", conf)
    shutil.copytree(DONNEES, donnees)
    zone = conf / "zones" / "jeu_essai.yaml"
    cfg = yaml.safe_load(zone.read_text(encoding="utf-8"))
    cfg["source"]["racine"] = str(donnees)
    zone.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    if modifier_donnees:
        modifier_donnees(donnees)
    return conf / "chaine.yaml"


def lancer_etape(conf: Path, travail: Path, etape: str, *suite: str):
    return lancer(["--conf", str(conf), "--travail", str(travail), etape, *suite])


# --------------------------------------------------------------------------------------
# Instrument : le blocage du réseau fonctionne (sinon « sans réseau » ne prouverait rien)
# --------------------------------------------------------------------------------------


def test_reseau_bloque_par_la_fixture():
    with pytest.raises(AssertionError, match="accès réseau interdit"):
        socket.socket().connect(("127.0.0.1", 9))


# --------------------------------------------------------------------------------------
# 1. Chaîne complète (critère 1)
# --------------------------------------------------------------------------------------


def test_chaine_complete(chaine):
    assert chaine.codes == {e: 0 for e in ETAPES}, f"codes={chaine.codes} erreurs={chaine.erreurs}"
    t = chaine.travail
    attendus = [
        t / "ingest" / "manifeste.parquet",
        t / "ingest" / "scenes.parquet",
        t / "validate" / "rapport.md",
        t / "validate" / "rapport.json",
        t / "export" / "stac" / "catalog.json",
        t / "export" / "stac" / "hauteur" / "collection.json",
        chaine.sortie_zonal,
    ]
    for d in DALLES:
        attendus += [
            t / "prepare" / d / "foret_10m.tif",
            t / "targets" / str(ANNEE) / f"{d}_cible_hauteur.tif",
            t / "infer" / str(ANNEE) / f"{d}_hauteur_brute.tif",
            t / "smooth" / str(ANNEE) / f"{d}_hauteur_lissee.tif",
            cog_path(t, d, "brute"),
            cog_path(t, d, "lissee"),
            t
            / "export"
            / "stac"
            / "hauteur"
            / f"hauteur-{ANNEE}-{d}"
            / f"hauteur-{ANNEE}-{d}.json",
        ]
        scenes = sorted((t / "prepare" / str(ANNEE) / d).glob("s2_*.tif"))
        assert len(scenes) == 3, f"{d} : {len(scenes)} scènes préparées au lieu de 3"
    manquants = [
        str(p.relative_to(t)) if t in p.parents else str(p) for p in attendus if not p.is_file()
    ]
    assert not manquants, f"fichiers absents : {manquants}"
    assert len(list((t / "modeles").glob("*/modele.json"))) == 1


# --------------------------------------------------------------------------------------
# 2. COG de hauteur (critère 2)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("traitement", ["brute", "lissee"])
@pytest.mark.parametrize("dalle", DALLES)
def test_cog_hauteur(chaine, dalle, traitement):
    exiger_chaine(chaine)
    from rio_cogeo.cogeo import cog_validate

    chemin = cog_path(chaine.travail, dalle, traitement)
    valide, erreurs, _ = cog_validate(str(chemin))
    assert valide, erreurs
    donnees, profil, tags, transform, crs, nodata = lire(chemin)
    xmin, _, _, ymax = emprise(dalle)
    assert profil["dtype"] == "uint16"
    assert nodata == NODATA
    assert crs.to_epsg() == 2154
    assert donnees.shape == (100, 100)
    assert (transform.c, transform.f) == (xmin, ymax), "origine ≠ coin nord-ouest de la dalle"
    assert (transform.a, transform.e) == (10.0, -10.0)
    # Tags (plan § 6)
    modele = next((chaine.travail / "modeles").glob("*/modele.json"))
    attendu_modele = "mediane-" + hashlib.sha256(modele.read_bytes()).hexdigest()[:12]
    assert tags["CANOPEE_VERSION_MODELE"] == attendu_modele
    assert modele.parent.name == attendu_modele
    assert re.fullmatch(r"jeu-essai-[0-9a-f]{12}", tags["CANOPEE_VERSION_DONNEES"])
    assert tags["CANOPEE_GRAINE"] == "42"
    assert tags["CANOPEE_VERSION_LOGICIEL"]
    assert tags["CANOPEE_COUCHE"] == "hauteur"
    assert tags["CANOPEE_TRAITEMENT"] == traitement
    assert tags["CANOPEE_DATE_VOL"] == DATE_VOL[dalle]
    assert tags["CANOPEE_UNITE"] == "cm"
    assert MENTION in tags["CANOPEE_MENTIONS"]
    # Valeurs : modèle trivial = 2626 partout où il y a une prédiction
    valides = donnees[donnees != NODATA]
    assert valides.size > 0
    assert set(np.unique(valides).tolist()) == {VALEUR_MODELE_CM}


def test_cog_lissee_identique_a_brute_au_jalon_1(chaine):
    exiger_chaine(chaine)
    for d in DALLES:
        brute = lire(cog_path(chaine.travail, d, "brute"))[0]
        lissee = lire(cog_path(chaine.travail, d, "lissee"))[0]
        assert np.array_equal(brute, lissee), d


# --------------------------------------------------------------------------------------
# 3. STAC validé hors ligne (critère 3)
# --------------------------------------------------------------------------------------


def valider_stac_hors_ligne(catalogue: Path) -> int:
    """Valide tout le catalogue avec pystac contre les schémas de `conf/stac-schemas/` seuls."""
    import pystac
    from pystac.validation import JsonSchemaSTACValidator, RegisteredValidator

    dossier = RACINE / "conf" / "stac-schemas"
    validateur = JsonSchemaSTACValidator()
    for f in dossier.glob("*-v*.json"):
        ext, version = f.stem.rsplit("-", 1)
        uri = f"https://stac-extensions.github.io/{ext}/{version}/schema.json"
        validateur.schema_cache[uri] = json.loads(f.read_text(encoding="utf-8"))
    for f in (dossier / "externes").glob("*.json"):
        schema = json.loads(f.read_text(encoding="utf-8"))
        validateur.schema_cache[schema["$id"]] = schema
    ancien = RegisteredValidator.get_validator()
    RegisteredValidator.set_validator(validateur)
    try:
        return pystac.Catalog.from_file(str(catalogue)).validate_all(recursive=True) or 0
    finally:
        RegisteredValidator.set_validator(ancien)


def test_instrument_validation_stac_hors_ligne(tmp_path):
    """Un item avec les 4 extensions déclarées est validé par l'instrument, sans réseau."""
    import datetime

    import pystac

    item = pystac.Item(
        id="x",
        geometry={
            "type": "Polygon",
            "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
        },
        bbox=[0, 0, 1, 1],
        datetime=datetime.datetime(2022, 7, 27, tzinfo=datetime.UTC),
        properties={"proj:code": "EPSG:2154", "processing:software": {"canopee": "0"}},
    )
    item.stac_extensions = sorted(EXTENSIONS_STAC)
    item.add_asset("a", pystac.Asset(href="a.tif", extra_fields={"file:size": 1}))
    cat = pystac.Catalog(id="c", description="d")
    cat.add_item(item)
    cat.normalize_hrefs(str(tmp_path))
    cat.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
    assert valider_stac_hors_ligne(tmp_path / "catalog.json") == 1


def test_stac_valide_hors_ligne(chaine):
    exiger_chaine(chaine)
    import pystac

    stac = chaine.travail / "export" / "stac"
    assert (
        valider_stac_hors_ligne(stac / "catalog.json") == 4
    )  # validate_all renvoie le nombre d'items
    cat = pystac.Catalog.from_file(str(stac / "catalog.json"))
    collections = list(cat.get_children())
    assert [c.id for c in collections] == ["hauteur"]
    items = sorted(collections[0].get_items(), key=lambda i: i.id)
    assert [i.id for i in items] == [f"hauteur-{ANNEE}-{d}" for d in sorted(DALLES)]
    assert MENTION in collections[0].description
    assert any(link.rel == "license" for link in collections[0].links)
    for item in items:
        dalle = item.id.removeprefix(f"hauteur-{ANNEE}-")
        assert set(item.stac_extensions) == EXTENSIONS_STAC
        assert item.properties["proj:code"] == "EPSG:2154"
        assert any(k.startswith("processing:") for k in item.properties)
        assert MENTION in json.dumps(item.properties["mentions"], ensure_ascii=False)
        assert set(item.assets) == {"brute", "lissee"}
        for traitement, actif in item.assets.items():
            href = Path(actif.get_absolute_href())
            assert href.resolve() == cog_path(chaine.travail, dalle, traitement).resolve()
            assert href.is_file()
            bande = actif.extra_fields["raster:bands"][0]
            assert bande["nodata"] == NODATA
            assert bande["unit"] == "cm"
            assert bande["data_type"] == "uint16"
            fichiers = [k for k in actif.extra_fields if k.startswith("file:")]
            assert fichiers, "extension file déclarée mais aucun champ file:*"
            if "file:size" in actif.extra_fields:
                assert actif.extra_fields["file:size"] == href.stat().st_size
    # liens relatifs (plan § 6) dans les fichiers écrits
    for f in stac.rglob("*.json"):
        for lien in json.loads(f.read_text(encoding="utf-8")).get("links", []):
            if lien["rel"] in {"root", "parent", "child", "item", "collection"}:
                assert not lien["href"].startswith(("/", "http")), (f.name, lien)


# --------------------------------------------------------------------------------------
# 4. Rapport de validation (critère 4)
# --------------------------------------------------------------------------------------


def test_rapport_validation(chaine):
    exiger_chaine(chaine)
    t = chaine.travail
    md = (t / "validate" / "rapport.md").read_text(encoding="utf-8")
    assert "MAE" in md
    for d in TEST:
        assert d in md, f"dalle de test {d} absente du rapport"
    rapport = json.loads((t / "validate" / "rapport.json").read_text(encoding="utf-8"))
    # Recalcul à la main (m) : cellules où cible et prédiction existent ; biais = prédiction - cible
    ecarts, biais = [], []
    assert set(rapport["dalles"]) == set(TEST)
    for d in TEST:
        cible = lire(t / "targets" / str(ANNEE) / f"{d}_cible_hauteur.tif")[0].astype(np.int64)
        pred = lire(t / "infer" / str(ANNEE) / f"{d}_hauteur_brute.tif")[0].astype(np.int64)
        ok = (cible != NODATA) & (pred != NODATA)
        assert ok.sum() > 0
        assert set(np.unique(pred[ok]).tolist()) == {VALEUR_MODELE_CM}
        e = np.abs(cible[ok] - VALEUR_MODELE_CM) / 100.0
        b = (pred[ok] - cible[ok]) / 100.0
        ecarts.append(e)
        biais.append(b)
        bloc = rapport["dalles"][d]
        assert bloc["n"] == int(ok.sum())
        assert bloc["mae_m"] == pytest.approx(e.mean(), abs=0.005)
        assert bloc["biais_m"] == pytest.approx(b.mean(), abs=0.005)
    assert rapport["mae_m"] == pytest.approx(float(np.concatenate(ecarts).mean()), abs=0.005)
    assert rapport["biais_m"] == pytest.approx(float(np.concatenate(biais).mean()), abs=0.005)


# --------------------------------------------------------------------------------------
# 5. Zonal (critère 5)
# --------------------------------------------------------------------------------------


def shapely_transform(geom):
    from pyproj import Transformer
    from shapely.ops import transform

    t = Transformer.from_crs(2154, 4326, always_xy=True)
    return transform(t.transform, geom)


def catalogue_synthetique(dossier: Path, valeurs: np.ndarray) -> Path:
    """Catalogue STAC + raster 3x3 à 10 m, origine (901000, 6665000), écrits à la main."""
    import datetime

    import pystac

    cog = dossier / "hauteur" / "2022" / "0901-6665_hauteur_lissee_2022.tif"
    cog.parent.mkdir(parents=True)
    with rasterio.open(
        cog,
        "w",
        driver="GTiff",
        width=3,
        height=3,
        count=1,
        dtype="uint16",
        crs="EPSG:2154",
        transform=rasterio.transform.from_origin(901000, 6665000, 10, 10),
        nodata=NODATA,
    ) as dst:
        dst.write(valeurs.astype("uint16"), 1)
        dst.update_tags(
            CANOPEE_VERSION_MODELE="mediane-aaaaaaaaaaaa",
            CANOPEE_VERSION_DONNEES="jeu-essai-bbbbbbbbbbbb",
            CANOPEE_GRAINE="42",
            CANOPEE_VERSION_LOGICIEL="0.0.0",
            CANOPEE_COUCHE="hauteur",
            CANOPEE_TRAITEMENT="lissee",
            CANOPEE_DATE_VOL="2022-07-27",
            CANOPEE_UNITE="cm",
            CANOPEE_MENTIONS=MENTION,
        )
    from shapely.geometry import box, mapping

    lambert = (901000, 6664970, 901030, 6665000)
    wgs = shapely_transform(box(*lambert))
    geom = mapping(wgs)
    item = pystac.Item(
        id="hauteur-2022-0901-6665",
        geometry=geom,
        bbox=list(wgs.bounds),
        datetime=datetime.datetime(2022, 7, 27, tzinfo=datetime.UTC),
        properties={"proj:code": "EPSG:2154", "proj:bbox": list(lambert)},
    )
    for nom in ("brute", "lissee"):
        item.add_asset(nom, pystac.Asset(href=str(cog), media_type="image/tiff"))
    coll = pystac.Collection(
        id="hauteur",
        description="essai",
        extent=pystac.Extent(
            pystac.SpatialExtent([list(wgs.bounds)]),
            pystac.TemporalExtent([[None, None]]),
        ),
    )
    coll.add_item(item)
    cat = pystac.Catalog(id="essai", description="essai")
    cat.add_child(coll)
    cat.normalize_hrefs(str(dossier / "stac"))
    cat.save(catalog_type=pystac.CatalogType.ABSOLUTE_PUBLISHED)
    return dossier / "stac" / "catalog.json"


def test_zonal_valeur_main_synthetique(tmp_path):
    """(a) Moyenne pondérée par la fraction couverte, calculée à la main.

    Raster 3x3 (cm), cellules de 10 m, origine (901000, 6665000) :
        100    200    300
        400  65535    600      (65535 = nodata)
        700    800    900
    Polygone x 901000-901015, y 6664980-6665000 : couvre les cellules (0,0) et (1,0) en
    entier (fraction 1), (0,1) et (1,1) pour moitié (0,5). La cellule (1,1) est nodata :
    poids valides 1 + 0,5 + 1 = 2,5 ; somme pondérée 100 + 0,5 x 200 + 400 = 600 ;
    moyenne = 600 / 2,5 = 240 cm. part_couverte = 2,5 x 100 m² / 300 m² = 5/6.
    """
    import geopandas as gpd
    from nemeton_canopee.zonal import statistiques_zonales
    from shapely.geometry import box

    valeurs = np.array([[100, 200, 300], [400, NODATA, 600], [700, 800, 900]])
    cat = catalogue_synthetique(tmp_path, valeurs)
    polys = gpd.GeoDataFrame(
        {"id": [7]}, geometry=[box(901000, 6664980, 901015, 6665000)], crs=2154
    )
    res = statistiques_zonales(polys, [ANNEE], ["hauteur"], cat, champ_id="id")
    assert list(res.columns) == COLONNES_ZONAL
    assert len(res) == 1
    ligne = res.iloc[0]
    assert ligne["id"] == 7
    assert ligne["annee"] == ANNEE
    assert ligne["couche"] == "hauteur"
    assert ligne["traitement"] == "lissee"
    assert ligne["unite"] == "cm"
    assert ligne["moyenne"] == pytest.approx(240.0, abs=1e-6)
    assert ligne["part_couverte"] == pytest.approx(5 / 6, abs=1e-6)
    assert np.isnan(ligne["incertitude_moyenne"])
    assert ligne["version_modele"] == "mediane-aaaaaaaaaaaa"
    assert ligne["version_donnees"] == "jeu-essai-bbbbbbbbbbbb"
    assert "2022-07-27" in str(ligne["date_vol"])
    assert "0901-6665" in str(ligne["dalles"])


def test_zonal_valeur_main_carre_20m(chaine):
    """(b) Carré de 20 m sur 4 cellules de 10 m, toutes prédites : tout vaut 2626 cm."""
    exiger_chaine(chaine)
    import geopandas as gpd
    from nemeton_canopee.zonal import statistiques_zonales
    from shapely.geometry import box

    polys = gpd.GeoDataFrame({"id": [1]}, geometry=[box(*CARRE_20M)], crs=2154)
    cat = chaine.travail / "export" / "stac" / "catalog.json"
    res = statistiques_zonales(polys, [ANNEE], ["hauteur"], cat, champ_id="id")
    assert list(res.columns) == COLONNES_ZONAL
    assert len(res) == 1
    ligne = res.iloc[0]
    assert ligne["moyenne"] == pytest.approx(VALEUR_MODELE_CM, abs=1e-6)
    assert ligne["mediane"] == pytest.approx(VALEUR_MODELE_CM, abs=1e-6)
    assert ligne["p10"] == pytest.approx(VALEUR_MODELE_CM, abs=1e-6)
    assert ligne["p90"] == pytest.approx(VALEUR_MODELE_CM, abs=1e-6)
    assert ligne["part_couverte"] == pytest.approx(1.0, abs=1e-9)
    assert ligne["unite"] == "cm"
    assert ligne["traitement"] == "lissee"
    assert "0901-6665" in str(ligne["dalles"])
    assert "2022-07-27" in str(ligne["date_vol"])
    # même valeur par la commande (CSV écrit par l'étape `zonal` de la chaîne)
    import pandas as pd

    csv = pd.read_csv(chaine.sortie_zonal)
    assert list(csv.columns) == COLONNES_ZONAL
    assert len(csv) == 1
    assert csv.loc[0, "moyenne"] == pytest.approx(VALEUR_MODELE_CM, abs=1e-6)
    assert csv.loc[0, "part_couverte"] == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------------------
# 6. Découpage figé (critère 6)
# --------------------------------------------------------------------------------------


def _touche(a: str, b: str) -> bool:
    """Vrai si les emprises de deux dalles se touchent ou se recouvrent (bord ou coin inclus)."""
    ax0, ay0, ax1, ay1 = emprise(a)
    bx0, by0, bx1, by1 = emprise(b)
    return ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1


def test_decoupage_fige():
    texte = (DONNEES / "decoupage.yaml").read_text(encoding="utf-8")
    assert "PROVISOIRE" not in texte, "découpage gelé le 22/11 : la mention doit être retirée"
    d = yaml.safe_load(texte)
    taille = d["taille_bloc_m"]
    assert taille == 10000
    appr = [e["dalle"] for e in d["apprentissage"]]
    test = [e["dalle"] for e in d["test"]]
    assert sorted(appr) == APPRENTISSAGE
    assert sorted(test) == TEST
    assert len(set(appr) | set(test)) == 4

    def bloc(dalle):
        x0, y0, _, _ = emprise(dalle)
        return (x0 // taille, y0 // taille)

    for e in d["apprentissage"] + d["test"]:
        assert tuple(e["bloc"]) == bloc(e["dalle"]), e
    assert {bloc(x) for x in appr}.isdisjoint({bloc(x) for x in test}), "blocs non distincts"
    for a in appr:
        for t in test:
            assert not _touche(a, t), f"{t} (test) touche {a} (apprentissage)"
    # la mécanique voit bien les contacts par un bord et par un coin
    assert _touche("0901-6665", "0902-6665")  # bord
    assert _touche("0901-6665", "0902-6664")  # coin
    assert not _touche("0901-6665", "0903-6665")


def test_train_refuse_un_decoupage_piege(tmp_path, capsys):
    """Un découpage où une dalle de test touche une dalle d'apprentissage est refusé.

    Suppose que `train` lit `decoupage.yaml` sous la racine des données de la zone (copie).
    """

    def pieger(donnees: Path):
        f = donnees / "decoupage.yaml"
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        d["apprentissage"] = [
            {"dalle": "0901-6665", "bloc": [90, 666]},
            {"dalle": "0939-6654", "bloc": [93, 665]},
        ]
        d["test"] = [
            {"dalle": "0902-6665", "bloc": [90, 666]},  # touche 0901-6665 par un bord
            {"dalle": "0939-6655", "bloc": [93, 665]},  # touche 0939-6654 par un bord
        ]
        f.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")

    conf = copie_conf_et_donnees(tmp_path, pieger)
    travail = tmp_path / "travail"
    for etape in ("ingest", "prepare", "targets"):
        code, erreur = lancer_etape(conf, travail, etape)
        assert code == 0, f"{etape} : {code} {erreur}"
    code, erreur = lancer_etape(conf, travail, "train")
    sortie = capsys.readouterr()
    assert code == 3, f"train doit refuser avec le code 3 : {code} {erreur}"
    assert "découpage" in (sortie.err + sortie.out).lower(), "le message ne nomme pas la règle"
    assert not list((travail / "modeles").glob("*/modele.json"))


# --------------------------------------------------------------------------------------
# 7. Chronométrage (critère 7)
# --------------------------------------------------------------------------------------


def test_chrono_chaine(chaine):
    exiger_chaine(chaine)  # un chrono sur une chaîne interrompue ne mesurerait rien
    assert chaine.duree_s < 600, f"chaîne : {chaine.duree_s:.1f} s (limite 600 s)"


# --------------------------------------------------------------------------------------
# Tests unitaires du plan (§ 8, « Plus »)
# --------------------------------------------------------------------------------------


def test_prepare_refuse_une_scene_hors_annee_de_vol(tmp_path, capsys):
    """Une scène de 2021 pour une dalle volée en 2022 est refusée et jamais préparée."""

    def ajouter_scene_2021(donnees: Path):
        f = donnees / "sentinel2_scenes.csv"
        lignes = f.read_text(encoding="utf-8").splitlines()
        entete, corps = lignes[0], lignes[1:]
        modele = [x for x in corps if x.startswith("0901-6665,S2B_31TFN_20220810")]
        assert len(modele) == 2
        faux = [
            x.replace("S2B_31TFN_20220810_0_L2A", "S2B_31TFN_20210810_0_L2A", 1)
            .replace("2022-08-10T", "2021-08-10T", 1)
            .replace(
                "sentinel2/0901-6665/S2B_31TFN_20210810_0_L2A",
                "sentinel2/0901-6665/S2B_31TFN_20220810_0_L2A",
            )
            for x in modele
        ]
        f.write_text("\n".join([entete, *corps, *faux]) + "\n", encoding="utf-8")

    conf = copie_conf_et_donnees(tmp_path, ajouter_scene_2021)
    travail = tmp_path / "travail"
    codes = []
    messages = ""
    for etape in ("ingest", "prepare"):
        code, _ = lancer_etape(conf, travail, etape, "--dalles", "0901-6665")
        codes.append(code)
        sortie = capsys.readouterr()
        messages += sortie.err + sortie.out
    assert 3 in codes, f"la scène de 2021 n'a pas été refusée avec le code 3 : codes={codes}"
    assert "année de vol" in messages.lower(), "le message ne nomme pas la règle"
    assert not list(travail.glob("prepare/*/0901-6665/s2_S2B_31TFN_20210810*.tif"))
    assert not (travail / "prepare" / "2021").exists()


def test_targets_zero_valide_nodata_conserve_maximum_5x5(tmp_path):
    """Cible 10 m : 0 reste 0 (borne à 0, pas un nodata), 65535 reste 65535, maximum 5x5.

    MNH 2 m synthétique (uint16, cm, nodata 65535) sur 0901-6665, entièrement en forêt.
    La cellule 10 m (i, j) agrège les pixels 2 m [5i:5i+5, 5j:5j+5] (plan § 5).
    """

    def mnh_synthetique(donnees: Path):
        f = donnees / "lidar" / "0901-6665_MNH_2m.tif"
        with rasterio.open(f) as src:
            profil = src.profile
        a = np.full((500, 500), 500, dtype="uint16")
        a[0:5, 0:5] = 0  # cellule (0,0) : tout à 0
        a[0:5, 5:10] = NODATA  # cellule (0,1) : tout nodata
        a[0:5, 10:15] = NODATA  # cellule (0,2) : un seul pixel valide
        a[2, 12] = 300
        a[0:5, 15:20] = 100  # cellule (0,3) : maximum 1234 au milieu
        a[3, 17] = 1234
        a[9, 9] = 7777  # dernier pixel de la cellule (1,1)
        a[10, 10] = 8888  # premier pixel de la cellule (2,2)
        with rasterio.open(f, "w", **profil) as dst:
            dst.write(a, 1)

    conf = copie_conf_et_donnees(tmp_path, mnh_synthetique)
    travail = tmp_path / "travail"
    for etape in ("ingest", "prepare", "targets"):
        code, erreur = lancer_etape(conf, travail, etape, "--dalles", "0901-6665")
        assert code == 0, f"{etape} : {code} {erreur}"
    cible, profil, _, transform, crs, nodata = lire(
        travail / "targets" / str(ANNEE) / "0901-6665_cible_hauteur.tif"
    )
    assert profil["dtype"] == "uint16"
    assert nodata == NODATA
    assert crs.to_epsg() == 2154
    assert (transform.c, transform.f) == (901000.0, 6665000.0)
    assert cible.shape == (100, 100)
    assert cible[0, 0] == 0
    assert cible[0, 1] == NODATA
    assert cible[0, 2] == 300
    assert cible[0, 3] == 1234
    assert cible[1, 1] == 7777
    assert cible[2, 2] == 8888
    assert cible[1, 2] == 500
    assert cible[2, 1] == 500
    assert cible[50, 50] == 500


def test_rejouabilite_deux_passes_fichiers_identiques(chaine, tmp_path):
    exiger_chaine(chaine)
    copie = tmp_path / "travail"
    shutil.copytree(chaine.travail, copie)
    avant = hash_arbre(chaine.travail)
    sortie = tmp_path / "zonal_rejeu.csv"
    for etape in ETAPES:
        suite = arguments_zonal(chaine.polygones, sortie) if etape == "zonal" else []
        code, erreur = lancer(["--conf", str(CONF), "--travail", str(copie), etape, *suite])
        assert code == 0, f"{etape} rejoué : {code} {erreur}"
    apres = hash_arbre(copie)
    # le CSV zonal du rejeu est écrit hors travail, celui de la première passe aussi
    assert apres == avant
    assert sortie.read_bytes() == chaine.sortie_zonal.read_bytes()
