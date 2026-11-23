"""Contrôles du jeu d'essai `tests/data/` (mission 002), sans réseau."""

import csv
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
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
        elif nom.startswith("references/forms_t_v1/"):
            assert "CC BY 4.0" in licence, nom
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


# --------------------------------------------------------------------------------------
# Références à battre (mission 007) : hauteur FORMS-T v1 de l'année de vol
# --------------------------------------------------------------------------------------


def references_forms_t() -> list[Path]:
    return sorted(DATA.glob("references/forms_t_v1/*_hauteur_*.tif"))


def test_reference_forms_t_une_par_dalle_annee_de_vol():
    fichiers = references_forms_t()
    assert [p.name[:9] for p in fichiers] == DALLES
    for p in fichiers:
        assert p.stem.endswith(f"_hauteur_{annee_vol_dalle(p.name[:9])}"), p.name


@pytest.mark.parametrize("chemin", references_forms_t(), ids=lambda p: p.name)
def test_reference_forms_t_convention_du_projet(chemin):
    dalle = chemin.name[:9]
    x, y = (int(v) for v in dalle.split("-"))
    with rasterio.open(chemin) as r:
        assert r.crs == CRS.from_epsg(2154)
        assert r.dtypes[0] == "uint16" and r.nodata == 65535
        assert r.res == (10.0, 10.0) and (r.width, r.height) == (100, 100)
        assert (r.bounds.left, r.bounds.top) == (x * 1000, y * 1000)
        a = r.read(1)
        tags = r.tags()
    valides = a[a != 65535]
    assert valides.size > 0 and valides.max() <= 6000  # cm, 0 à 60 m
    assert tags["unite"] == "cm" and tags["reference"] == "forms_t_v1"
    assert tags["url"] == (
        f"https://zenodo.org/api/records/15489231/files/Height_{annee_vol_dalle(dalle)}.tif/content"
    )
    assert "CC BY 4.0" in tags["licence"]
    assert "10.5281/zenodo.15489231" in tags["citation"]
    assert "0 -> 65535" in tags["conversion"]


def test_reference_forms_t_provenance_et_licence():
    prov = yaml.safe_load((DATA / "PROVENANCE").read_text(encoding="utf-8"))["fichiers"]
    for p in references_forms_t():
        e = prov[p.relative_to(DATA).as_posix()]
        assert "zenodo.org/api/records/15489231" in e["requete"]
        assert e["date"] and e["licence"].startswith("CC BY 4.0")
        assert "Schwartz" in e["citation"] and "10.5281/zenodo.15489231" in e["citation"]
        assert "65535" in e["traitement"] and "aucun rééchantillonnage" in e["traitement"]


# --------------------------------------------------------------------------------------
# Descripteurs de la BD ORTHO à 10 m (mission 012) : l'ortho brute n'est pas dans le jeu
# --------------------------------------------------------------------------------------

BANDES_ORTHO = [
    "rouge_moy",
    "rouge_std",
    "pir_moy",
    "pir_std",
    "ndvi_moy",
    "ndvi_std",
    "part_non_vegetal",
    "part_ombre",
    "lum_moy",
    "lum_std",
    "gradient_moy",
    "part_valide",
]


def orthos() -> list[Path]:
    return sorted(DATA.glob("ortho/*_ortho_10m.tif"))


def test_ortho_une_par_dalle_et_pas_d_ortho_brute():
    assert [p.name[:9] for p in orthos()] == DALLES
    for p in orthos():
        with rasterio.open(p) as r:
            assert r.res == (10.0, 10.0) and (r.width, r.height) == (100, 100), p.name  # pas 0,2 m
            assert r.crs == CRS.from_epsg(2154) and r.dtypes[0] == "float32"
            assert r.count == len(BANDES_ORTHO)
    # aucun raster plus fin que 2 m (MNH) : l'ortho de 20 cm n'est pas conservée
    for p in rasters():
        with rasterio.open(p) as r:
            assert r.res[0] >= 2.0, p.name


@pytest.mark.parametrize("chemin", orthos(), ids=lambda p: p.name)
def test_ortho_bandes_tags_et_valeurs(chemin):
    dalle = chemin.name[:9]
    x, y = (int(v) for v in dalle.split("-"))
    with rasterio.open(chemin) as r:
        a, tags, nodata = r.read(), r.tags(), r.nodata
        assert (r.bounds.left, r.bounds.top) == (x * 1000, y * 1000)
        descr = list(r.descriptions)
    assert tags["bandes"].split(",") == BANDES_ORTHO and descr == BANDES_ORTHO
    assert nodata == -9999.0
    v = {nom: a[i] for i, nom in enumerate(BANDES_ORTHO)}
    valide = v["part_valide"] >= 0.5
    assert valide.mean() > 0.9  # le jeu est en forêt, couvert par l'ortho
    for nom, bande in v.items():
        b = bande[valide]
        assert np.isfinite(b).all(), nom
        if nom.startswith("part_"):
            assert 0.0 <= b.min() and b.max() <= 1.0, nom
    assert (v["ndvi_moy"][valide] > -1).all() and (v["ndvi_moy"][valide] < 1).all()
    assert v["pir_moy"][valide].mean() > v["rouge_moy"][valide].mean()  # végétation : PIR > rouge
    assert v["lum_std"][valide].mean() > 0 and v["gradient_moy"][valide].mean() > 0


@pytest.mark.parametrize("chemin", orthos(), ids=lambda p: p.name)
def test_ortho_date_de_prise_de_vue_et_provenance(chemin):
    dalle = chemin.name[:9]
    with rasterio.open(chemin) as r:
        tags = r.tags()
    d = date.fromisoformat(tags["date_prise_de_vue"])
    assert date.fromisoformat(tags["date_prise_de_vue_min"]) <= d
    assert d <= date.fromisoformat(tags["date_prise_de_vue_max"])
    assert 2013 <= d.year <= 2026 and tags["campagnes_pva"]
    man = gpd.read_parquet(DATA / "manifeste_dalles.parquet").set_index("id")
    debut, fin = man.loc[dalle, "date_vol_debut"][:10], man.loc[dalle, "date_vol_fin"][:10]
    assert tags["vol_lidar_debut"] == debut and tags["vol_lidar_fin"] == fin
    milieu = date.fromisoformat(debut) + (date.fromisoformat(fin) - date.fromisoformat(debut)) / 2
    assert int(tags["ecart_ortho_vol_lidar_jours"]) == (d - milieu).days
    assert "IGN" in tags["source"] and "graphe de mosaïquage" in tags["source_date"]
    assert "PROVISOIRE" in tags["traitement"] and float(tags["seuil_ndvi_non_vegetal"]) > 0
    prov = yaml.safe_load((DATA / "PROVENANCE").read_text(encoding="utf-8"))["fichiers"]
    e = prov[chemin.relative_to(DATA).as_posix()]
    assert e["licence"].startswith("Licence Ouverte 2.0") and "BD ORTHO" in e["source"]
    assert tags["date_prise_de_vue"] in e["source"] and tags["date_prise_de_vue"] in e["traitement"]
    assert "non conservée" in e["traitement"] and "HR.ORTHOIMAGERY.ORTHOPHOTOS" in e["requete"]
    assert "ORTHOIMAGERY.ORTHOPHOTOS.IRC" in e["requete"] and "GRAPHE-MOSAIQUAGE" in e["requete"]


def test_ortho_controle_integre_du_script():
    import importlib.util
    from pathlib import Path as P

    racine = P(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "fabriquer_jeu_essai_ortho", racine / "scripts" / "fabriquer_jeu_essai.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    conf = module.charger_conf(racine / "conf" / "jeu_essai.yaml")
    for p in orthos():
        assert module.controler_ortho(conf, p, p.name[:9]) == [], p.name
