"""Tests sans réseau de `scripts/fabriquer_echantillon.py` (mission 008).

Petites données factices : aucun accès à l'IGN, à Earth Search ni à Zenodo. L'échantillon réel
(`/data/echantillon_jura`, hors dépôt) n'est pas lu ici.
"""

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote_plus

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


def ecrire_ortho_factice(base, c, chemin: Path, dalle: str, date: str = "2023-09-03") -> None:
    """Fichier ortho 10 m factice mais conforme (12 bandes float32, tags de date)."""
    o = c.ortho
    a = np.zeros((len(o["bandes"]), 100, 100), dtype="float32")
    for i, nom in enumerate(o["bandes"]):
        a[i] = 0.5 if nom.startswith("part_") else 100.0
    a[o["bandes"].index("part_valide")] = 1.0
    a[o["bandes"].index("ndvi_moy")] = 0.3
    a[o["bandes"].index("ndvi_std")] = 0.05
    tags = {
        "bandes": ",".join(o["bandes"]),
        "date_prise_de_vue": date,
        "vol_lidar_debut": "2022-07-28",
        "ecart_ortho_vol_lidar_jours": 400,
    }
    base.ecrire_raster(c, chemin, a, dalle, o["cellule_m"], o["nodata"], tags)


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
        f = c.ortho["fichier"].format(dalle=d)
        ecrire_ortho_factice(base, c, sortie / f, d)
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
    assert len(lu["apprentissage"]) == 96 and len(lu["test"]) == 48
    decoupe = decoupage.controler(lu, 1000)
    assert set(decoupe.test).isdisjoint(decoupe.apprentissage)
    assert doc["justification"].count("bloc") >= 9
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


# --------------------------------------------------------------------------- mission 012 : blocs


BLOCS_TEST_GELES = {"chaux_b": [908, 6674], "joux": [926, 6646], "altitude_b": [934, 6610]}
BLOCS_MISSION_012 = {
    "chenaie_c": [890, 6649],
    "sapiniere_c": [910, 6597],
    "altitude_c": [929, 6596],
}


def test_blocs_de_test_inchanges_et_trois_blocs_en_plus(script, conf_reelle):
    c = conf_reelle
    test = {b["nom"]: b["nw_km"] for b in c.blocs if b["role"] == "test"}
    assert test == BLOCS_TEST_GELES
    appr = {b["nom"]: b["nw_km"] for b in c.blocs if b["role"] == "apprentissage"}
    for nom, nw in BLOCS_MISSION_012.items():
        assert appr[nom] == nw
    assert len(c.blocs) == 9 and len(c.dalles) == 144
    # chaque bloc nouveau est à 10 km ou plus de TOUS les autres blocs, tests compris
    for nom, nw in BLOCS_MISSION_012.items():
        nouveau = {"nom": nom, "nw_km": nw}
        for b in c.blocs:
            if b["nom"] != nom:
                assert script.distance_blocs_m(c, nouveau, b) >= 10000.0, (nom, b["nom"])
    # même grille de blocs de 10 km : aucun bloc de 10 km partagé entre apprentissage et test
    assert script.controler_blocs(c) == []


def test_zone_declare_les_fichiers_ortho():
    for nom in ("echantillon_jura", "jeu_essai"):
        zone = conf_chaine.charger_zone(RACINE / "conf" / "zones" / f"{nom}.yaml")
        assert zone.fichiers["ortho"] == "ortho/{dalle}_ortho_10m.tif"
        assert (
            zone.chemin("ortho", dalle="0926-6646")
            .as_posix()
            .endswith("ortho/0926-6646_ortho_10m.tif")
        )


# --------------------------------------------------------------------------- mission 012 : ortho


@pytest.fixture(scope="module")
def ortho_conf(conf_reelle):
    return SimpleNamespace(**conf_reelle.ortho)


def test_conf_ortho_seuils_provisoires_et_bandes(ortho_conf):
    o = ortho_conf
    assert len(o.bandes) == len(set(o.bandes)) == 12
    assert 0.0 < o.seuil_ndvi_non_vegetal < 0.5 and 0.0 < o.seuil_ombre_luminance < 128
    assert o.pas_m == 0.2 and o.cellule_m == 10.0 and round(o.cellule_m / o.pas_m) == 50
    assert o.decoupes in (1, 2, 4)
    assert o.couche_rvb != o.couche_irc


def image_factice(n: int = 100):
    """RVB et IRC (3, n, n) uint8 : quatre cellules de 50 x 50 px aux contenus connus."""
    rvb = np.zeros((3, n, n), dtype="uint8")
    irc = np.zeros((3, n, n), dtype="uint8")
    # cellule (0, 0) : végétation uniforme, PIR 200, rouge 50 (NDVI 0,6), RVB (50, 100, 60)
    irc[0, :50, :50], irc[1, :50, :50], irc[2, :50, :50] = 200, 50, 100
    rvb[0, :50, :50], rvb[1, :50, :50], rvb[2, :50, :50] = 50, 100, 60
    # cellule (0, 1) : moitié gauche sol nu (PIR 80, R 100 : NDVI < 0), moitié droite végétation
    irc[0, :50, 50:75], irc[1, :50, 50:75] = 80, 100
    irc[0, :50, 75:], irc[1, :50, 75:] = 200, 50
    rvb[:, :50, 50:] = 90
    # cellule (1, 0) : ombre (luminance 10 ou 30) en bandes verticales de 2 px (texture forte)
    _, xx = np.indices((50, 50))
    bandes = (xx // 2) % 2 == 0
    for b in range(3):
        rvb[b, 50:, :50] = np.where(bandes, 10, 30)
    irc[0, 50:, :50], irc[1, 50:, :50] = 100, 20
    # cellule (1, 1) : hors couverture (blanc pur)
    rvb[:, 50:, 50:] = 255
    irc[:, 50:, 50:] = 255
    return rvb, irc


def test_descripteurs_ortho_valeurs_connues(script, ortho_conf):
    rvb, irc = image_factice()
    o = ortho_conf
    d = script.base.descripteurs_ortho(rvb, irc, o)
    assert d.shape == (12, 2, 2) and d.dtype == np.float32
    b = {nom: d[i] for i, nom in enumerate(o.bandes)}
    # cellule uniforme : moyenne exacte, écart-type nul, NDVI = (200 - 50) / (200 + 50)
    assert b["pir_moy"][0, 0] == pytest.approx(200.0) and b["rouge_moy"][0, 0] == pytest.approx(
        50.0
    )
    assert b["pir_std"][0, 0] == pytest.approx(0.0, abs=1e-3)
    assert b["ndvi_moy"][0, 0] == pytest.approx(0.6, abs=1e-6)
    assert b["lum_moy"][0, 0] == pytest.approx(0.299 * 50 + 0.587 * 100 + 0.114 * 60, abs=1e-3)
    assert b["part_non_vegetal"][0, 0] == 0.0 and b["part_ombre"][0, 0] == 0.0
    assert b["gradient_moy"][0, 0] < 1.0  # seul le bord voisin d'une autre cellule a un gradient
    # cellule mixte : la moitié gauche (25 colonnes sur 50) est du sol nu (NDVI < seuil)
    assert b["part_non_vegetal"][0, 1] == pytest.approx(0.5)
    assert b["pir_std"][0, 1] == pytest.approx(60.0, abs=1e-3)  # moitié 80, moitié 200
    # cellule d'ombre rayée : toute la cellule est sous le seuil, texture forte
    assert b["part_ombre"][1, 0] == 1.0
    assert b["lum_std"][1, 0] == pytest.approx(
        20 * (0.52 * 0.48) ** 0.5, abs=1e-3
    )  # 26 px à 10, 24 à 30
    assert b["gradient_moy"][1, 0] > 2.0  # différence centrée de (30 - 10) / 2 aux bords
    # hors couverture : aucune cellule valide, nodata partout sauf `part_valide` (0)
    assert all(b[nom][1, 1] == o.nodata for nom in o.bandes if nom != "part_valide")
    assert b["part_valide"][1, 1] == 0.0 and b["part_valide"][0, 0] == 1.0


def test_descripteurs_ortho_seuils_en_conf(script, ortho_conf):
    """Les seuils viennent de la conf : un seuil d'ombre plus haut classe plus de pixels."""
    rvb, irc = image_factice()
    bas = script.base.descripteurs_ortho(rvb, irc, {**vars(ortho_conf), "seuil_ombre_luminance": 5})
    haut = script.base.descripteurs_ortho(
        rvb, irc, {**vars(ortho_conf), "seuil_ombre_luminance": 150}
    )
    i = ortho_conf.bandes.index("part_ombre")
    assert bas[i][0, 0] == 0.0 and haut[i][0, 0] == 1.0  # luminance de la cellule (0, 0) : ~ 85
    j = ortho_conf.bandes.index("part_non_vegetal")
    plus_haut = script.base.descripteurs_ortho(
        rvb, irc, {**vars(ortho_conf), "seuil_ndvi_non_vegetal": 0.7}
    )
    assert plus_haut[j][0, 0] == 1.0  # NDVI 0,6 < 0,7


def test_descripteurs_ortho_par_bandes_identique_a_tout_d_un_coup(script, ortho_conf):
    """Le calcul par bandes de 10 lignes de cellules (gradient avec recouvrement) est exact."""
    rng = np.random.default_rng(0)
    rvb = rng.integers(20, 200, (3, 600, 100), dtype=np.uint8)  # 12 lignes de cellules
    irc = rng.integers(20, 200, (3, 600, 100), dtype=np.uint8)
    d = script.base.descripteurs_ortho(rvb, irc, ortho_conf)
    assert d.shape == (12, 12, 2)
    lum = (0.299 * rvb[0] + 0.587 * rvb[1] + 0.114 * rvb[2]).astype("float32")
    gy, gx = np.gradient(lum)
    attendu = np.hypot(gx, gy).reshape(12, 50, 2, 50).mean(axis=(1, 3))
    i = ortho_conf.bandes.index("gradient_moy")
    assert np.allclose(d[i], attendu, atol=1e-3)  # y compris autour de la frontière de bande
    j = ortho_conf.bandes.index("lum_moy")
    assert np.allclose(d[j], lum.reshape(12, 50, 2, 50).mean(axis=(1, 3)), atol=1e-3)


def test_ecart_jours_milieu_du_vol(script):
    e = script.base.ecart_jours
    assert e("2023-09-03", "2022-09-03", "2022-09-03") == 365
    assert (
        e("2023-09-03", "2022-08-25", "2022-10-17") == (date(2023, 9, 3) - date(2022, 9, 20)).days
    )
    assert e("2022-07-01", "2022-07-01", "2022-07-01") == 0


def tiff_ortho_octets(x0: float, y1: float, n: int, valeur: int) -> bytes:
    from rasterio.transform import from_origin

    with rasterio.MemoryFile() as mf:
        with mf.open(
            driver="GTiff",
            height=n,
            width=n,
            count=3,
            dtype="uint8",
            crs="EPSG:2154",
            transform=from_origin(x0, y1, 0.2, 0.2),
        ) as dst:
            dst.write(np.full((3, n, n), valeur, dtype="uint8"))
        return mf.read()


def test_telecharger_ortho_par_quarts_sans_reseau(script, conf_reelle, monkeypatch):
    """Quatre requêtes de 2500 px : chaque quart est posé à sa place (nord-ouest = haut gauche)."""
    import urllib.parse as up

    conf = SimpleNamespace(**{**vars(conf_reelle), "ortho": {**conf_reelle.ortho, "decoupes": 2}})
    appels = []

    def faux_lire(url, donnees=None, entetes=None):
        q = up.parse_qs(up.urlparse(url).query)
        assert q["CRS"] == ["EPSG:2154"] and q["LAYERS"] == ["COUCHE"]
        assert q["WIDTH"] == q["HEIGHT"] == ["2500"]
        x0, y0, x1, y1 = (float(v) for v in q["BBOX"][0].split(","))
        assert (x1 - x0, y1 - y0) == (500.0, 500.0)  # axes x, y (EPSG:2154 en WMS 1.3.0 : x puis y)
        appels.append((x0, y1))
        # valeur = 10 pour le quart nord-ouest, 20 nord-est, 30 sud-ouest, 40 sud-est
        v = 10 * (1 + int(x0 >= 926500) + 2 * int(y1 < 6646000))
        return tiff_ortho_octets(x0, y1, 2500, v)

    monkeypatch.setattr(script.base, "_lire", faux_lire)
    out, urls = script.base.telecharger_ortho(conf, "COUCHE", "0926-6646")
    assert out.shape == (3, 5000, 5000) and len(urls) == 4
    assert sorted(appels) == [
        (926000.0, 6645500.0),
        (926000.0, 6646000.0),
        (926500.0, 6645500.0),
        (926500.0, 6646000.0),
    ]
    assert out[0, 0, 0] == 10 and out[0, 0, -1] == 20  # haut : ouest puis est
    assert out[0, -1, 0] == 30 and out[0, -1, -1] == 40  # bas : ouest puis est


def test_telecharger_ortho_refuse_mauvaise_origine(script, conf_reelle, monkeypatch):
    monkeypatch.setattr(
        script.base, "_lire", lambda *a, **k: tiff_ortho_octets(926100.0, 6646000.0, 5000, 1)
    )
    with pytest.raises(AssertionError):
        script.base.telecharger_ortho(conf_reelle, "COUCHE", "0926-6646")


def test_date_ortho_depuis_le_graphe_sans_reseau(script, conf_reelle, monkeypatch):
    requetes = []

    def faux_lire(url, donnees=None, entetes=None):
        requetes.append(url)
        if "POINT" in url:
            ps = [{"dep": "39", "pva": 2023, "date_vol": "2023-09-03Z"}]
        else:
            ps = [
                {"dep": "25", "pva": 2023, "date_vol": "2023-09-06Z"},
                {"dep": "39", "pva": 2023, "date_vol": "2023-09-03Z"},
            ]
        return json.dumps({"features": [{"properties": p} for p in ps]}).encode()

    monkeypatch.setattr(script.base, "_lire", faux_lire)
    r = script.base.date_ortho(conf_reelle, "0926-6646")
    assert r["date"] == "2023-09-03" and r["date_min"] == "2023-09-03"
    assert r["date_max"] == "2023-09-06" and r["campagnes"] == [2023]
    assert r["departements"] == ["25", "39"]
    q = unquote_plus(requetes[0])
    assert "POINT(926500.0 6645500.0)" in q  # centre de la dalle (x puis y, Lambert-93)
    assert "SRID=2154" in q and "echelle=20" in q
    monkeypatch.setattr(script.base, "_lire", lambda *a, **k: b'{"features": []}')
    with pytest.raises(RuntimeError, match="absente du graphe"):
        script.base.date_ortho(conf_reelle, "0926-6646")


def test_controler_ortho_conforme_puis_defauts(script, conf_reelle, tmp_path):
    base = script.base
    chemin = tmp_path / "0926-6646_ortho_10m.tif"
    ecrire_ortho_factice(base, conf_reelle, chemin, "0926-6646")
    assert base.controler_ortho(conf_reelle, chemin, "0926-6646") == []
    # mauvaise dalle : emprise différente
    assert any("emprise" in e for e in base.controler_ortho(conf_reelle, chemin, "0927-6646"))
    # date illisible
    ecrire_ortho_factice(base, conf_reelle, chemin, "0926-6646", date="septembre 2023")
    assert any("illisible" in e for e in base.controler_ortho(conf_reelle, chemin, "0926-6646"))
    # fichier absent
    assert any(
        "absent" in e for e in base.controler_ortho(conf_reelle, tmp_path / "x.tif", "0926-6646")
    )
    # valeur hors plage (une fraction > 1)
    ecrire_ortho_factice(base, conf_reelle, chemin, "0926-6646")
    with rasterio.open(chemin, "r+") as dst:
        i = conf_reelle.ortho["bandes"].index("part_ombre") + 1
        a = dst.read(i)
        a[3, 3] = 1.7
        dst.write(a, i)
    assert any("part_ombre" in e for e in base.controler_ortho(conf_reelle, chemin, "0926-6646"))
    # mauvais CRS
    ecrire_ortho_factice(base, conf_reelle, chemin, "0926-6646")
    with rasterio.open(chemin) as src:
        data, profil = src.read(), src.profile
    profil.update(crs="EPSG:32631")
    with rasterio.open(chemin, "w", **profil) as dst:
        dst.write(data)
    assert any("CRS" in e for e in base.controler_ortho(conf_reelle, chemin, "0926-6646"))


def test_controle_integre_signale_une_ortho_manquante(script, conf_reelle, tmp_path):
    c = conf_mini(script, conf_reelle)
    sortie = tmp_path / "ech"
    fabriquer_faux_echantillon(script, c, sortie)
    assert script.controler_echantillon(c, sortie) == []
    (sortie / "ortho" / "0900-6600_ortho_10m.tif").unlink()
    erreurs = script.controler_echantillon(c, sortie)
    assert any("ortho_10m.tif absent" in e for e in erreurs)


def test_reprise_ortho_sans_reseau(script, conf_reelle, tmp_path, monkeypatch):
    """Une dalle dont l'ortho et l'entrée de PROVENANCE existent n'est pas refaite."""
    f = conf_reelle.ortho["fichier"].format(dalle="0900-6600")
    (tmp_path / "ortho").mkdir()
    (tmp_path / f).write_bytes(b"x")
    etat = {"dalle": "0900-6600", "meta": {}, "prov_ortho": {f: {"source": "x"}}}

    def interdit(*a, **k):
        raise AssertionError("réseau appelé")

    monkeypatch.setattr(script.base, "fabriquer_ortho", interdit)
    assert script.fabriquer_ortho_dalle(
        conf_reelle, "0900-6600", etat, tmp_path, lambda m: None
    ) == {f: {"source": "x"}}
    (tmp_path / f).unlink()
    with pytest.raises(AssertionError, match="réseau appelé"):
        script.fabriquer_ortho_dalle(conf_reelle, "0900-6600", etat, tmp_path, lambda m: None)


def test_lire_json_reessaie_quand_le_wfs_renvoie_autre_chose(script, monkeypatch):
    """Le WFS IGN renvoie par moments des métriques en texte : on réessaie, puis on échoue net."""
    reponses = [b"# HELP jmx_exporter_build_info", b"<xml/>", b'{"features": []}']
    monkeypatch.setattr(script.base, "_lire", lambda *a, **k: reponses.pop(0))
    monkeypatch.setattr(script.base.time, "sleep", lambda s: None)
    assert script.base._lire_json("https://wfs.test/x") == {"features": []}
    monkeypatch.setattr(script.base, "_lire", lambda *a, **k: b"# HELP")
    with pytest.raises(RuntimeError, match="non JSON"):
        script.base._lire_json("https://wfs.test/x", essais=2)
