"""Tests de scripts/mesurer_modeles.py (mission 011) sur des données synthétiques, sans réseau."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[1]
NODATA = 65535
REGLAGES = {
    "surface_min_ha": 0.5,
    "part_min": 0.5,
    "cote_hectare": 10,
    "classes_m": [10, 20, 30],
    "tirages": 200,
    "graine": 42,
    "tranche_altitude_m": 200,
    "n_min_ventilation": 1,
}


@pytest.fixture(scope="module")
def mm():
    chemin = RACINE / "scripts" / "mesurer_modeles.py"
    spec = importlib.util.spec_from_file_location("mesurer_modeles", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_masque_commun_exige_tous_les_produits(mm):
    cible = np.array([[100, NODATA], [300, 400]], dtype="uint16")
    a = np.array([[1, 2, 3, 4]], dtype="uint16").reshape(2, 2)
    b = np.array([[1, 2], [NODATA, 4]], dtype="uint16")
    assert mm.masque_commun(cible, {"a": a, "b": b}, NODATA).tolist() == [
        [True, False],
        [False, True],
    ]


def test_etiquettes_hectare(mm):
    lab = mm.etiquettes_hectare((20, 20), 10)
    assert sorted(np.unique(lab)) == [1, 2, 3, 4]
    assert (lab == 1).sum() == 100 and lab[0, 10] == 2 and lab[10, 0] == 3


def test_moyennes_par_unite_et_part_minimale(mm):
    lab = np.array([[1, 1, 2, 2]])
    masque = np.array([[True, True, True, False]])
    v = np.array([[2.0, 4.0, 10.0, 99.0]])
    r = mm.moyennes_par_unite(lab, masque, {"v": v}, part_min=0.5)
    assert r["v"].tolist() == [3.0, 10.0] and r["n"].tolist() == [2, 1]
    r = mm.moyennes_par_unite(lab, masque, {"v": v}, part_min=0.6)
    assert r["v"].tolist() == [3.0]  # unité 2 : 1 cellule sur 2 < 60 %


def test_classes_hauteur(mm):
    assert mm.classes_hauteur(np.array([5, 10, 25, 31]), [10, 20, 30]).tolist() == [0, 1, 2, 3]
    assert mm.noms_classes([10, 20, 30]) == ["< 10 m", "10-20 m", "20-30 m", "> 30 m"]


def test_bootstrap_rejouable_apparie(mm):
    sommes = np.array([[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 8.0]])
    comptes = np.ones(4)
    a = mm.bootstrap_dalles(sommes, comptes, 500, 7)
    b = mm.bootstrap_dalles(sommes, comptes, 500, 7)
    assert np.array_equal(a["ic"], b["ic"])
    assert np.array_equal(a["tirages"][0], a["tirages"][1])  # mêmes tirages pour tous
    lo, hi = a["ic"][0]
    assert lo <= 2.5 <= hi
    assert a["ic"][2][1] - a["ic"][2][0] > a["ic"][0][1] - a["ic"][0][0]  # erreur concentrée


def test_couverture(mm):
    c = np.array([1.0, 2.0, 3.0, 4.0])
    assert mm.couverture(c, c - 0.5, c + 0.5) == 1.0
    assert mm.couverture(c, np.array([1.0, 3, 3, 5]), np.array([1.0, 3, 3, 6])) == 0.5


def _dalle(nom, bloc, decalage_ref_cm, rng):
    cible = rng.integers(500, 4000, size=(20, 20)).astype("uint16")
    cible[0, 0] = NODATA
    parfait = cible.copy()
    ref = np.where(cible == NODATA, NODATA, cible + decalage_ref_cm).astype("uint16")
    trou = parfait.copy()
    trou[19, 19] = NODATA  # une prédiction manquante retire la cellule pour tous
    return {
        "dalle": nom,
        "bloc": bloc,
        "cible": cible,
        "produits": {"parfait": parfait, "trou": trou, "forms_t_v1": ref},
        "bornes": {"parfait": (parfait, parfait)},
        "n_claires": np.where(np.arange(400).reshape(20, 20) % 2 == 0, 1, 3),
        "mnt": np.full((20, 20), 850.0),
    }


def test_mesurer_bout_en_bout(mm):
    rng = np.random.default_rng(0)
    dalles = [_dalle(f"d{i}", "A" if i < 2 else "B", 100 * (i + 1), rng) for i in range(4)]
    lab = np.zeros((20, 20), dtype="int32")
    lab[:10, :] = 1
    lab[10:, :15] = 2
    polys = {d["dalle"]: (lab, ["Sapin, épicéa", "Hêtre"]) for d in dalles}
    res = mm.mesurer(dalles, polys, REGLAGES, NODATA)

    tot = res["principal"]["hectare"]["total"]
    assert tot["n_unites"] == 16 and tot["n_dalles"] == 4
    assert tot["parfait"]["mae_m"] == 0.0 and tot["parfait"]["ic95"] == [0.0, 0.0]
    assert tot["forms_t_v1"]["mae_m"] == pytest.approx(2.5)  # décalages 1, 2, 3, 4 m
    assert tot["parfait"]["ecart_forms_t_ic95"][1] < 0  # parfait bat la référence
    poly = res["principal"]["polygone"]["A"]
    assert poly["n_unites"] == 4 and poly["forms_t_v1"]["mae_m"] == pytest.approx(1.5)

    sec = res["secondaire"]["total"]
    assert sec["n_pixels"] == 4 * (400 - 2)  # cible manquante et trou retirés partout
    assert sec["pixel"]["forms_t_v1"]["biais_m"] == pytest.approx(2.5)
    assert sum(sec["part_classes"].values()) == pytest.approx(1.0)
    inc = sec["incertitude"]["parfait"]
    assert inc["couverture_p10_p90"] == 1.0 and inc["part_incertitude_nulle"] == 1.0
    assert inc["part_une_scene_claire"] == pytest.approx(0.5, abs=0.01)
    assert set(res["causes"]["essence"]) == {"Sapin, épicéa", "Hêtre", "hors polygone"}
    assert list(res["causes"]["altitude"]) == ["800-1000 m"]
    assert "A · 20-30 m" in res["causes"]["bloc_classe"]
    assert "## Critère principal" in mm.markdown(res)
