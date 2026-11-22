"""Données refusées (décision 11 du plan 004) : code 3, message qui nomme la règle, rien d'écrit.

Complète `test_acceptation_jalon_1.py` ; mission 003, reprise du 22/11.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import yaml
from conftest import CARRE_20M, CONF, DALLES, arguments_zonal
from shapely.geometry import box
from test_acceptation_jalon_1 import (
    ANNEE,
    copie_conf_et_donnees,
    emprise,
    exiger_chaine,
    lancer_etape,
)


def sortie_lue(capsys) -> str:
    s = capsys.readouterr()
    return (s.err + s.out).lower()


def modifier_yaml(chemin: Path, modif) -> None:
    d = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    modif(d)
    chemin.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")


def test_ingest_annee_sans_dalle_refusee_et_manifeste_intact(tmp_path, capsys):
    travail = tmp_path / "travail"
    assert lancer_etape(CONF, travail, "ingest")[0] == 0
    manifeste = travail / "ingest" / "manifeste.parquet"
    scenes = travail / "ingest" / "scenes.parquet"
    avant = (manifeste.read_bytes(), scenes.read_bytes())
    capsys.readouterr()
    code, erreur = lancer_etape(CONF, travail, "ingest", "--annees", "2023")
    assert code == 3, f"{code} {erreur}"
    assert "2023" in sortie_lue(capsys)
    assert (manifeste.read_bytes(), scenes.read_bytes()) == avant


def test_dalle_invalide_refusee_rien_ecrit(tmp_path, capsys):
    travail = tmp_path / "travail"
    code, erreur = lancer_etape(CONF, travail, "ingest", "--dalles", "9999-9999")
    assert code == 3, f"{code} {erreur}"
    assert "9999-9999" in sortie_lue(capsys)
    assert not (travail / "ingest").exists()


def test_cle_absente_de_decoupage_refusee(tmp_path, capsys):
    def retirer_cle(donnees: Path):
        f = donnees / "decoupage.yaml"
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        del d["test"]
        f.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")

    conf = copie_conf_et_donnees(tmp_path, retirer_cle)
    travail = tmp_path / "travail"
    codes = {}
    for etape in ("ingest", "prepare", "targets", "train"):
        codes[etape], _ = lancer_etape(conf, travail, etape)
        if codes[etape] != 0:
            break
    assert 3 in codes.values(), f"aucun refus (code 3) : {codes}"
    assert set(codes.values()) <= {0, 3}, codes
    assert "découpage" in sortie_lue(capsys), "le message ne nomme pas la règle"
    assert not list((travail / "modeles").glob("*/modele.json"))


def test_source_mode_distant_refusee(tmp_path, capsys):
    conf = copie_conf_et_donnees(tmp_path)
    modifier_yaml(
        conf.parent / "zones" / "jeu_essai.yaml", lambda d: d["source"].update(mode="distant")
    )
    travail = tmp_path / "travail"
    code, erreur = lancer_etape(conf, travail, "ingest")
    assert code == 3, f"{code} {erreur}"
    assert "distant" in sortie_lue(capsys)
    assert not (travail / "ingest").exists()


def test_zonal_geopackage_sans_crs_refuse(chaine, tmp_path, capsys):
    exiger_chaine(chaine)
    gpkg = tmp_path / "sans_crs.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[box(*CARRE_20M)], crs=None).to_file(gpkg, driver="GPKG")
    sortie = tmp_path / "zonal.csv"
    code, erreur = lancer_etape(CONF, chaine.travail, "zonal", *arguments_zonal(gpkg, sortie))
    assert code == 3, f"{code} {erreur}"
    assert "crs" in sortie_lue(capsys)
    assert not sortie.exists()


def test_mnh_dans_un_autre_crs_refuse_a_targets(tmp_path, capsys):
    def reetiqueter(donnees: Path):
        with rasterio.open(donnees / "lidar" / "0901-6665_MNH_2m.tif", "r+") as dst:
            dst.crs = rasterio.crs.CRS.from_epsg(32631)

    conf = copie_conf_et_donnees(tmp_path, reetiqueter)
    travail = tmp_path / "travail"
    for etape in ("ingest", "prepare"):
        code, erreur = lancer_etape(conf, travail, etape)
        assert code == 0, f"{etape} : {code} {erreur}"
    capsys.readouterr()
    code, erreur = lancer_etape(conf, travail, "targets")
    assert code == 3, f"{code} {erreur}"
    assert "crs" in sortie_lue(capsys)
    assert not list((travail / "targets").glob("*/0901-6665_cible_hauteur.tif"))


def test_stac_geometrie_wgs84_et_proj_bbox_lambert93(chaine):
    exiger_chaine(chaine)
    stac = chaine.travail / "export" / "stac" / "hauteur"
    for d in DALLES:
        item = json.loads(
            (stac / f"hauteur-{ANNEE}-{d}" / f"hauteur-{ANNEE}-{d}.json").read_text(
                encoding="utf-8"
            )
        )
        lon_min, lat_min, lon_max, lat_max = item["bbox"]
        assert 5 < lon_min < lon_max < 7 and 46 < lat_min < lat_max < 48, item["bbox"]
        for lon, lat in item["geometry"]["coordinates"][0]:
            assert 5 < lon < 7 and 46 < lat < 48, (lon, lat)
        assert item["properties"]["proj:code"] == "EPSG:2154"
        assert item["properties"]["proj:bbox"] == list(emprise(d))
        assert np.isclose(
            item["geometry"]["coordinates"][0][0][0], item["geometry"]["coordinates"][0][-1][0]
        )


def test_vol_a_cheval_sur_deux_annees_refuse(tmp_path, capsys):
    def chevaucher(donnees: Path):
        f = donnees / "manifeste_dalles.parquet"
        man = gpd.read_parquet(f)
        man.loc[man["id"] == "0901-6665", "date_vol_debut"] = "2021-12-30"
        man.loc[man["id"] == "0901-6665", "date_vol_fin"] = "2022-01-02"
        man.to_parquet(f)

    conf = copie_conf_et_donnees(tmp_path, chevaucher)
    travail = tmp_path / "travail"
    code, erreur = lancer_etape(conf, travail, "ingest")
    assert code == 3, f"{code} {erreur}"
    assert "année de vol" in sortie_lue(capsys)
    assert not (travail / "ingest").exists()
