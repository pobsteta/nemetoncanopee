"""Tests sans réseau de `scripts/fabriquer_echantillon.py` (mission 008).

Petites données factices : aucun accès à l'IGN, à Earth Search ni à Zenodo. L'échantillon réel
(`/data/echantillon_jura`, hors dépôt) n'est pas lu ici.
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import yaml
from shapely.geometry import box

from nemeton_canopee import conf as conf_chaine
from nemeton_canopee import decoupage

RACINE = Path(__file__).resolve().parents[1]
NODATA = 65535


@pytest.fixture(scope="module")
def script():
    chemin = RACINE / "scripts" / "fabriquer_echantillon.py"
    spec = importlib.util.spec_from_file_location("fabriquer_echantillon", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def conf_reelle(script):
    return script.charger_conf(RACINE / "conf" / "echantillon_jura.yaml")


# --------------------------------------------------------------------------- blocs et conf


def test_dalles_du_bloc_ordre_et_position(script):
    ds = script.dalles_du_bloc([926, 6646])
    assert len(ds) == len(set(ds)) == 16
    assert "0926-6646" in ds  # coin nord-ouest du bloc
    assert "0929-6643" in ds  # coin sud-est
    assert "0930-6646" not in ds and "0926-6642" not in ds
    # x puis y : 0929-6643 couvre x 929-930 km, y 6642-6643 km (ordre et système explicites)
    xmin, ymin, xmax, ymax = script.base.emprise("0929-6643")
    assert (xmin, ymin, xmax, ymax) == (929000.0, 6642000.0, 930000.0, 6643000.0)


def test_conf_reelle_blocs_valides(script, conf_reelle):
    c = conf_reelle
    assert len(c.blocs) >= 4
    assert len(c.dalles) == len(set(c.dalles)) == 16 * len(c.blocs)
    assert script.controler_blocs(c) == []
    roles = {b["role"] for b in c.blocs}
    assert roles == {"apprentissage", "test"}
    # hérité du jeu d'essai : mêmes sources et même grille
    assert c.crs == "EPSG:2154" and c.mnh_pas_m == 2.0 and c.nodata_hauteur == NODATA
    assert c.s2_nb_scenes == 3 and c.s2_nuage_dalle_max == 0.02


def test_zone_et_conf_chaine_alignees_sur_les_blocs(conf_reelle):
    zone = conf_chaine.charger_zone(RACINE / "conf" / "zones" / "echantillon_jura.yaml")
    assert sorted(zone.dalles) == conf_reelle.dalles
    assert zone.mode == "local" and zone.annees == [2022]
    assert [r["nom"] for r in zone.references] == ["forms_t_v1"]
    chaine = conf_chaine.charger(RACINE / "conf" / "chaine_echantillon_jura.yaml")
    assert chaine.zone.nom == "echantillon-jura"
    # mêmes réglages que la chaîne principale (seuls la zone et le travail changent)
    brut = lambda f: yaml.safe_load(f.read_text(encoding="utf-8"))  # noqa: E731
    a = brut(RACINE / "conf" / "chaine.yaml")
    b = brut(RACINE / "conf" / "chaine_echantillon_jura.yaml")
    assert a.keys() == b.keys()
    for cle in a.keys() - {"zone", "travail"}:
        assert a[cle] == b[cle], cle


def test_distance_et_refus_de_blocs_trop_proches(script, conf_reelle):
    c = SimpleNamespace(**vars(conf_reelle))
    a, b = {"nom": "a", "nw_km": [0, 100]}, {"nom": "b", "nw_km": [14, 100]}
    assert script.distance_blocs_m(c, a, b) == 10000.0  # 14 - (0 + 4) km
    diag = {"nom": "c", "nw_km": [14, 90]}  # écart de 10 km en x, 6 km en y
    assert script.distance_blocs_m(c, a, diag) == pytest.approx((10000**2 + 6000**2) ** 0.5)
    c.blocs = [
        {**a, "role": "apprentissage"},
        {"nom": "b", "nw_km": [13, 100], "role": "test"},  # 9 km seulement
    ]
    assert any("< minimum" in e for e in script.controler_blocs(c))
    c.blocs = [{**a, "role": "apprentissage"}, {"nom": "a", "nw_km": [30, 100], "role": "test"}]
    assert any("double" in e for e in script.controler_blocs(c))
    c.blocs = [{**a, "role": "apprentissage"}, {**b, "role": "apprentissage"}]
    assert any(
        "au moins un bloc d'apprentissage et un bloc de test" in e
        for e in script.controler_blocs(c)
    )
    c.blocs = [{**a, "role": "validation"}, {**b, "role": "test"}]
    assert any("inconnu" in e for e in script.controler_blocs(c))


# --------------------------------------------------------------------------- petites fonctions


def test_controler_mnh_publie(script):
    assert script.controler_mnh_publie(0.99, 0.5) == 0.99
    with pytest.raises(RuntimeError, match="MNH publié"):
        script.controler_mnh_publie(0.2, 0.5)


def ecrire_mnh_factice(chemin: Path, cm: np.ndarray) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    from rasterio.transform import from_origin

    with rasterio.open(
        chemin,
        "w",
        driver="GTiff",
        height=cm.shape[0],
        width=cm.shape[1],
        count=1,
        dtype="uint16",
        crs="EPSG:2154",
        transform=from_origin(926000.0, 6646000.0, 2.0, 2.0),
        nodata=NODATA,
    ) as dst:
        dst.write(cm, 1)


def test_statistiques_mnh(script, tmp_path):
    cm = np.full((10, 10), 1500, dtype="uint16")  # 15 m
    cm[0, :5] = 4200  # 5 cellules de 42 m
    cm[9, :] = NODATA  # 10 cellules sans donnée
    cm[5, 5] = 0  # 0 cm : une hauteur valide
    chemin = tmp_path / "mnh.tif"
    ecrire_mnh_factice(chemin, cm)
    s = script.statistiques_mnh(chemin, 30.0)
    assert s["max_m"] == 42.0
    assert s["valide"] == 0.9
    assert s["part_sup_seuil"] == pytest.approx(5 / 90, abs=1e-4)
    assert s["moyenne_m"] == pytest.approx((5 * 42 + 84 * 15 + 0) / 90, abs=0.1)
    ecrire_mnh_factice(tmp_path / "vide.tif", np.full((4, 4), NODATA, dtype="uint16"))
    vide = script.statistiques_mnh(tmp_path / "vide.tif")
    assert vide["max_m"] is None and vide["valide"] == 0.0


def test_meme_annee(script):
    m = {"date_vol_debut": "2022-07-27", "date_vol_fin": "2022-10-17"}
    assert script.meme_annee({"a": m, "b": m}) == "2022"
    autre = {"date_vol_debut": "2023-05-01", "date_vol_fin": "2023-05-02"}
    with pytest.raises(RuntimeError, match="plusieurs années"):
        script.meme_annee({"a": m, "b": autre})
    a_cheval = {"date_vol_debut": "2022-12-30", "date_vol_fin": "2023-01-02"}
    with pytest.raises(AssertionError, match="deux années"):
        script.meme_annee({"a": a_cheval})


def test_avec_reprises(script):
    messages, appels = [], []

    def instable():
        appels.append(1)
        if len(appels) < 3:
            raise ConnectionError("coupé")
        return "ok"

    assert script.avec_reprises(instable, 3, messages.append, "x", pause=0) == "ok"
    assert len(appels) == 3 and sum("ECHEC" in m for m in messages) == 2

    def mort():
        raise TimeoutError("trop long")

    with pytest.raises(TimeoutError):
        script.avec_reprises(mort, 2, messages.append, "y", pause=0)


def test_journal_horodate_et_sur_entre_fils(script, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    j = script.Journal(tmp_path / "sous" / "fabrication.log", echo=False)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda i: j(f"ligne {i}"), range(40)))
    lignes = (tmp_path / "sous" / "fabrication.log").read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 40
    assert all(ligne[4] == "-" and "T" in ligne[:19] for ligne in lignes)


def test_reprise_d_une_dalle_sans_reseau(script, tmp_path, monkeypatch):
    """Un fragment complet est relu sans appeler le réseau ; un fichier manquant refait la dalle."""
    (tmp_path / "lidar").mkdir()
    (tmp_path / "lidar" / "0900-6600_MNH_2m.tif").write_bytes(b"x")
    etat = {"dalle": "0900-6600", "prov": {"lidar/0900-6600_MNH_2m.tif": {}}, "annee": "2022"}
    frag = script.chemin_fragment(tmp_path, "0900-6600")
    frag.parent.mkdir()
    frag.write_text(json.dumps(etat), encoding="utf-8")

    def interdit(*a, **k):
        raise AssertionError("réseau appelé")

    monkeypatch.setattr(script.base, "metadonnees_vol", interdit)
    messages = []
    assert script.fabriquer_dalle(SimpleNamespace(), "0900-6600", tmp_path, messages.append) == etat
    assert "reprise" in messages[0]
    (tmp_path / "lidar" / "0900-6600_MNH_2m.tif").unlink()
    with pytest.raises(AssertionError, match="réseau appelé"):
        script.fabriquer_dalle(SimpleNamespace(), "0900-6600", tmp_path, messages.append)


# --------------------------------------------------------------------------- échantillon factice


def conf_mini(script, conf_reelle):
    """Deux blocs d'une seule dalle, loin l'un de l'autre."""
    c = SimpleNamespace(**vars(conf_reelle))
    c.taille_bloc_dalles = 1
    c.blocs = [
        {"nom": "a", "role": "apprentissage", "nw_km": [900, 6600], "type": "chênaie"},
        {"nom": "b", "role": "test", "nw_km": [926, 6646], "type": "sapinière"},
    ]
    c.dalles = script.dalles_de_la_conf(c)
    return c


def etats_factices(c, annee="2022"):
    etats = {}
    for d in c.dalles:
        etats[d] = {
            "dalle": d,
            "annee": annee,
            "meta": {
                "date_vol_debut": f"{annee}-07-27",
                "date_vol_fin": f"{annee}-08-25",
                "mission": "22LHD2PI",
                "capteur": "x",
                "requete": f"https://wfs.test/{d}",
            },
            "essences": {"Chênes décidus": 80.0, "Mixte": 15.0},
            "foret_ha": 95.0,
            "stats": {"max_m": 38.5, "p99_m": 27.0, "moyenne_m": 18.0, "part_sup_seuil": 0.01},
            "scenes": [{}, {}, {}, {}, {}, {}],
        }
    return etats


def fabriquer_faux_echantillon(script, c, sortie: Path, annee_scene="2022"):
    """Écrit un petit échantillon complet (mêmes noms et conventions que le vrai)."""
    base = script.base
    prov, lignes = {}, []
    meta = {}
    for d in c.dalles:
        meta[d] = etats_factices(c)[d]["meta"]
        for nom, pas, tag in (("MNH_2m", 2.0, "uint16"), ("MNT_10m", 10.0, "float32")):
            n = int(1000 / pas)
            data = np.full((n, n), 1500 if tag == "uint16" else 300.0, dtype=tag)
            f = f"lidar/{d}_{nom}.tif"
            base.ecrire_raster(
                c, sortie / f, data, d, pas, NODATA if tag == "uint16" else -9999.0, {}
            )
            prov[f] = {}
        f = f"foret/{d}_bdforet_v2.gpkg"
        (sortie / f).parent.mkdir(parents=True, exist_ok=True)
        gpd.GeoDataFrame(
            {"essence": ["Mixte"]}, geometry=[box(*base.emprise(d))], crs=c.crs
        ).to_file(sortie / f, driver="GPKG")
        prov[f] = {}
        for pas, bandes in ((10, "B02"), (20, "B05")):
            f = f"sentinel2/{d}/S2A_TEST_{annee_scene}0710_{pas}m.tif"
            n = int(1000 / pas)
            base.ecrire_raster(
                c, sortie / f, np.ones((1, n, n), "uint16"), d, float(pas), None, {"bandes": bandes}
            )
            prov[f] = {}
            lignes.append(
                {
                    "dalle": d,
                    "scene": f"S2A_TEST_{annee_scene}0710",
                    "date_scene": f"{annee_scene}-07-10T10:00:00Z",
                    "nuage_scene_pct": 0.1,
                    "processing_baseline": "04.00",
                    "resolution_m": pas,
                    "bandes": bandes,
                    "fichier": f,
                }
            )
        f = c.references["forms_t_v1"]["fichier"].format(dalle=d, annee="2022")
        base.ecrire_raster(c, sortie / f, np.full((100, 100), 1500, "uint16"), d, 10.0, NODATA, {})
        prov[f] = {}
    base.ecrire_manifeste(c, sortie, meta, prov)
    base.ecrire_scenes(c, sortie, lignes, prov, ["2022"])
    script.ecrire_decoupage(c, sortie, etats_factices(c), prov)
    for e in prov.values():
        e.setdefault("source", "test")
        e.setdefault("requete", "test")
        e.setdefault("date", "2026-11-22")
        e.setdefault("licence", "Licence Ouverte 2.0")
    script.ecrire_provenance(sortie, prov)


def test_decoupage_valide_par_la_chaine(script, conf_reelle, tmp_path):
    """Le `decoupage.yaml` écrit est accepté par le contrôle de la chaîne (blocs distincts)."""
    prov: dict = {}
    c = conf_reelle
    doc = script.ecrire_decoupage(c, tmp_path, etats_factices(c), prov)
    lu = yaml.safe_load((tmp_path / "decoupage.yaml").read_text(encoding="utf-8"))
    assert lu["taille_bloc_m"] == 10000
    assert len(lu["apprentissage"]) == 48 and len(lu["test"]) == 48
    decoupe = decoupage.controler(lu, 1000)
    assert set(decoupe.test).isdisjoint(decoupe.apprentissage)
    assert doc["justification"].count("bloc") >= 6
    assert "decoupage.yaml" in prov
    # chaque dalle porte son bloc de 10 km, calculé par la grille (x puis y)
    e = next(e for e in lu["test"] if e["dalle"] == "0926-6646")
    assert e["bloc"] == [92, 664] and e["bloc_echantillon"] == "joux"


def test_rapport_markdown_et_resume(script, conf_reelle):
    etats = etats_factices(conf_reelle)
    r = script.resume_bloc(conf_reelle, conf_reelle.blocs[0], etats)
    assert r["annee"] == "2022" and r["foret_ha"] == 16 * 95
    assert r["essences"][0] == ("Chênes décidus", 16 * 80)
    assert r["mnh_max_m"] == 38.5 and r["scenes"] == 16 * 3
    md = script.rapport_markdown(conf_reelle, etats, 123_000_000)
    assert "123 Mo" in md
    for b in conf_reelle.blocs:
        assert f"### Bloc {b['nom']}" in md
    assert md.count("| 0926-6646 |") == 1


def test_controle_integre_conforme_puis_defauts(script, conf_reelle, tmp_path):
    c = conf_mini(script, conf_reelle)
    sortie = tmp_path / "ech"
    fabriquer_faux_echantillon(script, c, sortie)
    assert script.controler_echantillon(c, sortie) == []

    # fichier non listé dans PROVENANCE
    (sortie / "lidar" / "intrus.tif").write_bytes(b"x")
    assert any("PROVENANCE" in e for e in script.controler_echantillon(c, sortie))
    (sortie / "lidar" / "intrus.tif").unlink()

    # taille au-dessus du budget
    petit = SimpleNamespace(**{**vars(c), "budget_octets": 10})
    assert any("budget" in e for e in script.controler_echantillon(petit, sortie))

    # fichier manquant
    cible = sortie / "lidar" / "0900-6600_MNT_10m.tif"
    contenu = cible.read_bytes()
    cible.unlink()
    assert any("absent" in e for e in script.controler_echantillon(c, sortie))
    cible.write_bytes(contenu)

    # emprise décalée (raster d'une autre dalle)
    autre = sortie / "lidar" / "0926-6646_MNH_2m.tif"
    cible_mnh = sortie / "lidar" / "0900-6600_MNH_2m.tif"
    sauve = cible_mnh.read_bytes()
    cible_mnh.write_bytes(autre.read_bytes())
    assert any("emprise" in e for e in script.controler_echantillon(c, sortie))
    cible_mnh.write_bytes(sauve)
    assert script.controler_echantillon(c, sortie) == []


def test_controle_refuse_scene_hors_annee_de_vol(script, conf_reelle, tmp_path):
    c = conf_mini(script, conf_reelle)
    sortie = tmp_path / "ech"
    fabriquer_faux_echantillon(script, c, sortie, annee_scene="2021")
    erreurs = script.controler_echantillon(c, sortie)
    assert any("hors de l'année de vol 2022" in e for e in erreurs)


def test_controle_refuse_mauvais_crs(script, conf_reelle, tmp_path):
    c = conf_mini(script, conf_reelle)
    sortie = tmp_path / "ech"
    fabriquer_faux_echantillon(script, c, sortie)
    chemin = sortie / "lidar" / "0900-6600_MNT_10m.tif"
    with rasterio.open(chemin) as src:
        data, profil = src.read(1), src.profile
    profil.update(crs="EPSG:32631")
    with rasterio.open(chemin, "w", **profil) as dst:
        dst.write(data, 1)
    assert any("CRS" in e for e in script.controler_echantillon(c, sortie))


def test_surfaces_foret_polygones_fusionnes(script, tmp_path):
    """Deux polygones qui se recouvrent ne comptent qu'une fois : une dalle fait 100 ha au plus."""
    g = gpd.GeoDataFrame(
        {"essence": ["Mixte", "Mixte", "Hêtre"]},
        geometry=[box(0, 0, 1000, 1000), box(0, 0, 1000, 1000), box(0, 0, 500, 1000)],
        crs="EPSG:2154",
    )
    chemin = tmp_path / "f.gpkg"
    g.to_file(chemin, driver="GPKG")
    ess, tot = script.surfaces_foret(chemin)
    assert ess == {"Mixte": 100.0, "Hêtre": 50.0}
    assert tot == 100.0
    vide = tmp_path / "v.gpkg"
    g.iloc[:0].to_file(vide, driver="GPKG")
    assert script.surfaces_foret(vide) == ({}, 0.0)
