"""Références à battre dans le rapport de `validate` (mission 007), sans réseau.

FORMS-T v1 (hauteur 2022, extraite dans `tests/data/references/`) est comparée à la cible LiDAR
sur les dalles de test, sur le masque commun cible ∧ prédiction ∧ référence ; le projet est
recalculé sur ce même masque. Biais = produit − cible, en m.
"""

import hashlib
import importlib.util
import json

import numpy as np
import pandas as pd
import pytest
import yaml
from conftest import RACINE
from rasterio.transform import from_origin
from test_acceptation_jalon_1 import (
    ANNEE,
    DONNEES,
    NODATA,
    TEST,
    copie_conf_et_donnees,
    exiger_chaine,
    lancer_etape,
    lire,
)

NOM = "forms_t_v1"


def reference(dalle: str) -> np.ndarray:
    return lire(DONNEES / "references" / NOM / f"{dalle}_hauteur_{ANNEE}.tif")[0]


def recalcul(chaine) -> dict:
    """MAE et biais (m) recalculés à la main depuis les fichiers, par dalle et poolés."""
    t = chaine.travail
    out = {"ref": {}, "projet": {}}
    tous_ref, tous_projet = [], []
    for d in TEST:
        cible = lire(t / "targets" / str(ANNEE) / f"{d}_cible_hauteur.tif")[0].astype(np.int64)
        pred = lire(t / "infer" / str(ANNEE) / f"{d}_hauteur_brute.tif")[0].astype(np.int64)
        ref = reference(d).astype(np.int64)
        ok = (cible != NODATA) & (pred != NODATA) & (ref != NODATA)
        assert ok.sum() > 0, d
        e_ref = (ref[ok] - cible[ok]) / 100.0
        e_projet = (pred[ok] - cible[ok]) / 100.0
        out["ref"][d] = (int(ok.sum()), np.abs(e_ref).mean(), e_ref.mean())
        out["projet"][d] = (int(ok.sum()), np.abs(e_projet).mean(), e_projet.mean())
        tous_ref.append(e_ref)
        tous_projet.append(e_projet)
    r, p = np.concatenate(tous_ref), np.concatenate(tous_projet)
    out["ref"]["tout"] = (r.size, np.abs(r).mean(), r.mean())
    out["projet"]["tout"] = (p.size, np.abs(p).mean(), p.mean())
    return out


def verifier(bloc: dict, attendu: tuple) -> None:
    n, mae, biais = attendu
    assert bloc["n"] == n
    assert bloc["mae_m"] == pytest.approx(mae, abs=1e-4)
    assert bloc["biais_m"] == pytest.approx(biais, abs=1e-4)


def test_rapport_json_references_recalculees_a_la_main(chaine):
    exiger_chaine(chaine)
    rapport = json.loads((chaine.travail / "validate" / "rapport.json").read_text("utf-8"))
    assert set(rapport["references"]) == {NOM}
    ref = rapport["references"][NOM]
    attendu = recalcul(chaine)
    verifier(ref, attendu["ref"]["tout"])
    verifier(ref["projet_meme_masque"], attendu["projet"]["tout"])
    assert set(ref["dalles"]) == set(ref["projet_meme_masque"]["dalles"]) == set(TEST)
    for d in TEST:
        verifier(ref["dalles"][d], attendu["ref"][d])
        verifier(ref["projet_meme_masque"]["dalles"][d], attendu["projet"][d])
    # même masque : autant de cellules des deux côtés
    assert ref["n"] == ref["projet_meme_masque"]["n"]
    assert ref["unite"] == "cm"
    # traçabilité : empreinte de chaque fichier de référence, chemin relatif (pas d'absolu)
    for fichier, sha in ref["fichiers"].items():
        assert not fichier.startswith("/")
        assert sha == hashlib.sha256((DONNEES / fichier).read_bytes()).hexdigest()


def test_rapport_md_tableau_projet_contre_forms_t(chaine):
    exiger_chaine(chaine)
    md = (chaine.travail / "validate" / "rapport.md").read_text(encoding="utf-8")
    rapport = json.loads((chaine.travail / "validate" / "rapport.json").read_text("utf-8"))
    ref = rapport["references"][NOM]
    p = ref["projet_meme_masque"]
    assert "## Références à battre" in md
    assert f"| FORMS-T v1 | {ref['n']} | {ref['mae_m']:.2f} | {ref['biais_m']:.2f} |" in md
    assert (
        f"| projet, même masque que FORMS-T v1 | {p['n']} | {p['mae_m']:.2f} | {p['biais_m']:.2f} |"
    ) in md
    assert "Biais = produit − cible" in md


def test_ingest_declare_les_references(chaine):
    exiger_chaine(chaine)
    table = pd.read_parquet(chaine.travail / "ingest" / "references.parquet")
    assert sorted(table["dalle"]) == sorted(["0901-6665", "0902-6665", "0939-6654", "0939-6655"])
    assert set(table["nom"]) == {NOM} and set(table["unite"]) == {"cm"}
    assert set(table["annee"]) == {ANNEE}
    for ligne in table.itertuples():
        assert ligne.fichier == f"references/{NOM}/{ligne.dalle}_hauteur_{ANNEE}.tif"
        assert ligne.sha256 == hashlib.sha256((DONNEES / ligne.fichier).read_bytes()).hexdigest()


def test_reference_dans_une_autre_unite_refusee(tmp_path, capsys):
    conf = copie_conf_et_donnees(tmp_path)
    zone = conf.parent / "zones" / "jeu_essai.yaml"
    d = yaml.safe_load(zone.read_text(encoding="utf-8"))
    d["references"][0]["unite"] = "dm"
    zone.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    code, erreur = lancer_etape(conf, tmp_path / "travail", "ingest")
    assert code == 3, f"{code} {erreur}"
    s = capsys.readouterr()
    assert "unité" in (s.err + s.out)


def test_reference_absente_code_2(tmp_path):
    def retirer(donnees):
        (donnees / "references" / NOM / f"0939-6654_hauteur_{ANNEE}.tif").unlink()

    conf = copie_conf_et_donnees(tmp_path, retirer)
    code, erreur = lancer_etape(conf, tmp_path / "travail", "ingest")
    assert code == 2, f"{code} {erreur}"
    assert not (tmp_path / "travail" / "ingest" / "references.parquet").exists()


def test_reference_hors_grille_refusee():
    from rasterio.crs import CRS

    from nemeton_canopee.erreurs import DonneeRefusee
    from nemeton_canopee.validate import controler_grille

    cible = {
        "crs": CRS.from_epsg(2154),
        "width": 100,
        "height": 100,
        "transform": from_origin(939000, 6654000, 10, 10),
    }
    controler_grille(dict(cible), cible, "ref.tif", "EPSG:2154")
    decalee = {**cible, "transform": from_origin(939005, 6654000, 10, 10)}
    with pytest.raises(DonneeRefusee, match="grille"):
        controler_grille(decalee, cible, "ref.tif", "EPSG:2154")
    autre_crs = {**cible, "crs": CRS.from_epsg(32631)}
    with pytest.raises(DonneeRefusee, match="CRS"):
        controler_grille(autre_crs, cible, "ref.tif", "EPSG:2154")


def test_ecarts_communs_masque_et_signe():
    from nemeton_canopee.validate import ecarts_communs

    cible = np.array([1000, 2000, NODATA, 0, 500], dtype="uint16")
    pred = np.array([1100, NODATA, 1000, 100, 500], dtype="uint16")
    ref = np.array([900, 2500, 1000, 50, NODATA], dtype="uint16")
    e_ref, e_projet = ecarts_communs(cible, pred, ref, NODATA)
    # cellules 0 et 3 seulement (la 1, la 2 et la 4 ont un nodata) ; 0 cm est une hauteur valide
    assert e_ref.tolist() == [-1.0, 0.5]
    assert e_projet.tolist() == [1.0, 1.0]


def charger_script():
    chemin = RACINE / "scripts" / "fabriquer_jeu_essai.py"
    spec = importlib.util.spec_from_file_location("fabriquer_jeu_essai", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_conversion_forms_t_vers_convention_du_projet():
    script = charger_script()
    brut = np.array([0, 1, 2640, 3779, -5, 32767], dtype="int16")
    cm = script.convertir_reference(brut, 0, NODATA)
    assert cm.dtype == np.uint16
    assert cm.tolist() == [NODATA, 1, 2640, 3779, NODATA, 32767]
