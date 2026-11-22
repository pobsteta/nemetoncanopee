"""Contrôles du jeu d'essai `tests/data/` (mission 002), sans réseau."""

import csv
from pathlib import Path

import geopandas as gpd
import pytest
import rasterio
import yaml
from rasterio.crs import CRS

DATA = Path(__file__).parent / "data"
BUDGET_OCTETS = 20 * 1024 * 1024  # spec § 2 : moins de 20 Mo
DALLES = ["0901-6665", "0902-6665", "0939-6654", "0939-6655"]


def fichiers_donnees() -> list[str]:
    return sorted(
        p.relative_to(DATA).as_posix()
        for p in DATA.rglob("*")
        if p.is_file() and p.name != "PROVENANCE"
    )


def annee_vol_dalle(dalle: str) -> str:
    man = gpd.read_parquet(DATA / "manifeste_dalles.parquet").set_index("id")
    return man.loc[dalle, "date_vol_debut"][:4]


def rasters() -> list[Path]:
    return sorted(DATA.rglob("*.tif"))


def test_taille_totale_sous_le_budget():
    total = sum(p.stat().st_size for p in DATA.rglob("*") if p.is_file())
    assert 0 < total < BUDGET_OCTETS, f"{total} octets"


def test_provenance_pour_chaque_fichier():
    prov = yaml.safe_load((DATA / "PROVENANCE").read_text(encoding="utf-8"))["fichiers"]
    fichiers = fichiers_donnees()
    assert fichiers
    assert sorted(prov) == fichiers, "PROVENANCE et fichiers de données diffèrent"
    for nom, e in prov.items():
        for cle in ("source", "requete", "date", "licence"):
            assert e.get(cle), f"{nom} : champ {cle} vide"
        licence = e["licence"]
        if nom.startswith("sentinel2/"):
            annee = annee_vol_dalle(nom.split("/")[1])
            assert f"Contains modified Copernicus Sentinel data {annee}" in licence, nom
        elif nom == "sentinel2_scenes.csv":
            assert "Contains modified Copernicus Sentinel data" in licence, nom
        else:
            assert "Licence Ouverte 2.0" in licence, nom
        if nom.startswith("sentinel2/"):
            assert "DN x 0,0001" in e["traitement"] and "-0,1" not in e["traitement"], nom


def test_quatre_dalles_par_type():
    for motif in ("lidar/*_MNH_2m.tif", "lidar/*_MNT_10m.tif", "foret/*.gpkg"):
        assert len(list(DATA.glob(motif))) == 4, motif
    for d in DALLES:
        assert len(list((DATA / "sentinel2" / d).glob("*_10m.tif"))) >= 1, d


@pytest.mark.parametrize("chemin", rasters(), ids=lambda p: p.relative_to(DATA).as_posix())
def test_raster_en_lambert93_aligne_sur_le_km(chemin):
    with rasterio.open(chemin) as r:
        assert r.crs == CRS.from_epsg(2154)
        b = r.bounds
        for v in (b.left, b.bottom, b.right, b.top):
            assert v % 1000 == 0, f"{v} hors grille de 1 km"
        assert (b.right - b.left, b.top - b.bottom) == (1000, 1000)
        assert abs(r.res[0] - r.res[1]) < 1e-9 and 1000 % r.res[0] == 0
        assert r.width * r.res[0] == 1000


def test_raster_hauteur_convention():
    for chemin in DATA.glob("lidar/*_MNH_2m.tif"):
        with rasterio.open(chemin) as r:
            assert r.dtypes[0] == "uint16" and r.nodata == 65535
            a = r.read(1)
            valides = a[a != 65535]
            assert valides.size > 0 and valides.max() <= 6000, chemin.name  # 0 à 60 m


def test_foret_en_lambert93_dans_la_dalle():
    for chemin in DATA.glob("foret/*.gpkg"):
        dalle = chemin.name[:9]
        x, y = (int(v) for v in dalle.split("-"))
        g = gpd.read_file(chemin)
        assert g.crs.to_epsg() == 2154 and len(g) > 0
        minx, miny, maxx, maxy = g.total_bounds
        assert minx >= x * 1000 and maxx <= x * 1000 + 1000
        assert miny >= y * 1000 - 1000 and maxy <= y * 1000


def test_manifeste_et_decoupage_coherents():
    man = gpd.read_parquet(DATA / "manifeste_dalles.parquet")
    dec = yaml.safe_load((DATA / "decoupage.yaml").read_text(encoding="utf-8"))
    assert man.crs.to_epsg() == 2154
    assert sorted(man["id"]) == DALLES
    appr = [e["dalle"] for e in dec["apprentissage"]]
    test = [e["dalle"] for e in dec["test"]]
    assert len(appr) == len(test) == 2
    assert sorted(appr + test) == sorted(man["id"]), "une dalle manque ou est en double"
    # emprise du manifeste = emprise déduite de l'identifiant (coin nord-ouest, en km)
    for _, ligne in man.iterrows():
        x, y = (int(v) for v in ligne["id"].split("-"))
        assert (ligne.xmin, ligne.ymin, ligne.xmax, ligne.ymax) == (
            x * 1000,
            y * 1000 - 1000,
            x * 1000 + 1000,
            y * 1000,
        )
        assert ligne.geometry.bounds == (ligne.xmin, ligne.ymin, ligne.xmax, ligne.ymax)
        assert ligne.date_vol_debut <= ligne.date_vol_fin
        assert ligne.date_vol_debut.startswith("2022")
    # blocs de 10 km distincts entre apprentissage et test, et conformes aux emprises
    t = dec["taille_bloc_m"]
    blocs = {e["dalle"]: tuple(e["bloc"]) for e in dec["apprentissage"] + dec["test"]}
    for _, ligne in man.iterrows():
        assert blocs[ligne["id"]] == (int(ligne.xmin // t), int(ligne.ymin // t))
    assert not {blocs[d] for d in appr} & {blocs[d] for d in test}
    # aucune dalle de test ne touche une dalle d'apprentissage (bord ou coin)
    geo = man.set_index("id").geometry
    for a in appr:
        for b in test:
            assert not geo[a].intersects(geo[b]), (a, b)


def test_annee_des_scenes_sentinel2_egale_annee_de_vol():
    man = gpd.read_parquet(DATA / "manifeste_dalles.parquet").set_index("id")
    with (DATA / "sentinel2_scenes.csv").open(encoding="utf-8") as fh:
        lignes = list(csv.DictReader(fh))
    assert lignes
    for ligne in lignes:
        annee = man.loc[ligne["dalle"], "date_vol_debut"][:4]
        assert ligne["date_scene"][:4] == annee, ligne["scene"]
        assert annee == man.loc[ligne["dalle"], "date_vol_fin"][:4]
        assert (DATA / ligne["fichier"]).is_file()
