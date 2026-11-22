"""Modèle gbm (mission 009, ADR 0004 option C) : LightGBM sur descripteurs par cellule de 10 m.

La chaîne complète tourne avec `modele: gbm` sur le jeu d'essai, à partir d'une conf dérivée
de `conf/chaine.yaml` dans un dossier temporaire (la conf du dépôt garde le modèle trivial).
La zone dérivée déclare le MNT (`fichiers.mnt`) pour les descripteurs de relief.
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm  # noqa: F401  (extra dev : échec franc si absent, jamais de skip)
import numpy as np
import pytest
import rasterio
import yaml
from conftest import CONF, DALLES, ETAPES, RACINE, arguments_zonal, lancer

from nemeton_canopee import descripteurs
from nemeton_canopee.erreurs import DonneeRefusee
from nemeton_canopee.models import gbm

TEST = ["0939-6654", "0939-6655"]
APPRENTISSAGE = ["0901-6665", "0902-6665"]
NODATA = 65535


def conf_gbm(dossier: Path, modele: str = "gbm.yaml") -> Path:
    """Conf dérivée : modèle gbm (ou sa variante `modele`), zone du jeu d'essai avec le MNT
    déclaré, chemins absolus."""
    dossier.mkdir(parents=True, exist_ok=True)
    chaine = yaml.safe_load(CONF.read_text(encoding="utf-8"))
    zone = yaml.safe_load((CONF.parent / chaine["zone"]).read_text(encoding="utf-8"))
    zone["source"]["racine"] = str(RACINE / "tests" / "data")
    assert zone["fichiers"]["mnt"] == "lidar/{dalle}_MNT_10m.tif"  # déclaré dans le dépôt
    (dossier / "zone.yaml").write_text(yaml.safe_dump(zone, allow_unicode=True), "utf-8")
    chaine["zone"] = "zone.yaml"
    chaine["modele"] = str(CONF.parent / "modele" / modele)
    chaine["stac"]["schemas"] = str(CONF.parent / chaine["stac"]["schemas"])
    chemin = dossier / "chaine.yaml"
    chemin.write_text(yaml.safe_dump(chaine, allow_unicode=True), encoding="utf-8")
    return chemin


def executer(conf: Path, travail: Path, polygones: Path) -> dict:
    codes = {}
    for etape in ETAPES:
        suite = arguments_zonal(polygones, travail / "zonal.csv") if etape == "zonal" else []
        code, erreur = lancer(["--conf", str(conf), "--travail", str(travail), etape, *suite])
        codes[etape] = (code, erreur)
        if code != 0:
            break
    return codes


@pytest.fixture(scope="module")
def deux_passes(tmp_path_factory):
    """Deux passes complètes de la chaîne gbm dans deux dossiers distincts."""
    import geopandas as gpd
    from conftest import CARRE_20M
    from shapely.geometry import box

    base = tmp_path_factory.mktemp("gbm")
    polygones = base / "polygones.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[box(*CARRE_20M)], crs="EPSG:2154").to_file(
        polygones, driver="GPKG"
    )
    conf = conf_gbm(base / "conf")
    passes = []
    for i in (1, 2):
        travail = base / f"travail{i}"
        passes.append((travail, executer(conf, travail, polygones)))
    return conf, passes


def test_chaine_complete_gbm(deux_passes):
    _, passes = deux_passes
    for travail, codes in passes:
        assert all(c == 0 for c, _ in codes.values()), codes
        assert list(codes) == ETAPES
        (modele,) = (travail / "modeles").glob("gbm-*/modele.json")
        contenu = json.loads(modele.read_text(encoding="utf-8"))
        for fichier in ("hauteur.txt", "q10.txt", "q90.txt"):
            texte = (modele.parent / fichier).read_text(encoding="utf-8")
            assert texte.startswith("tree"), fichier  # format texte LightGBM
            assert fichier in contenu["fichiers"]
        assert contenu["dalles_apprentissage"] == APPRENTISSAGE
        assert str(travail) not in modele.read_text(encoding="utf-8")


def test_rejouable_a_l_octet(deux_passes):
    _, ((t1, _), (t2, _)) = deux_passes
    fichiers = sorted(
        p.relative_to(t1)
        for p in t1.rglob("*")
        if p.is_file() and p.parts[len(t1.parts)] in {"modeles", "infer", "smooth", "export"}
    )
    assert any(p.name.endswith("incertitude_brute.tif") for p in fichiers)
    assert any(p.suffix == ".txt" for p in fichiers)
    for relatif in fichiers:
        assert (t1 / relatif).read_bytes() == (t2 / relatif).read_bytes(), relatif


def test_incertitude_coherente(deux_passes):
    conf_chemin, ((travail, _), _) = deux_passes
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.ingest import lire_manifeste
    from nemeton_canopee.models import modele_actif

    conf = charger(conf_chemin, travail)
    ch = Chemins(travail)
    version, modele = modele_actif(ch)
    for dalle in lire_manifeste(ch):
        with rasterio.open(ch.brute(dalle.annee, dalle.id)) as src:
            hauteur = src.read(1)
        with rasterio.open(ch.incertitude(dalle.annee, dalle.id)) as src:
            incertitude, tags = src.read(1), src.tags()
            assert src.dtypes[0] == "uint16" and src.nodata == NODATA
        assert tags["CANOPEE_COUCHE"] == "hauteur_incertitude"
        assert tags["CANOPEE_UNITE"] == "cm"
        assert tags["CANOPEE_VERSION_MODELE"] == version
        assert np.array_equal(hauteur == NODATA, incertitude == NODATA)
        assert (hauteur != NODATA).sum() > 0
        foret = rasterio.open(ch.foret(dalle.id)).read(1)
        from nemeton_canopee.infer import masque_clair

        masque = (foret == 1) & masque_clair(ch.scenes_preparees(dalle.annee, dalle.id))
        couches = gbm.predire(conf, ch, version, modele, dalle, masque)
        p10, p90 = couches["q10"][masque], couches["q90"][masque]
        h = couches["hauteur"][masque]
        assert np.all(p10 <= h) and np.all(h <= p90)
        assert np.array_equal(couches["hauteur"], hauteur)
        assert np.array_equal(couches["incertitude"][masque], (p90 - p10))


def test_mae_rapportee(deux_passes, capsys):
    _, ((travail, _), _) = deux_passes
    rapport = json.loads((travail / "validate" / "rapport.json").read_text(encoding="utf-8"))
    assert sorted(rapport["dalles"]) == TEST
    assert rapport["version_modele"].startswith("gbm-")
    assert np.isfinite(rapport["mae_m"]) and rapport["n"] > 0
    ref = rapport["references"]["forms_t_v1"]
    with capsys.disabled():
        print(
            f"\n[gbm, jeu d'essai, 2 dalles de test] MAE {rapport['mae_m']:.2f} m "
            f"(n={rapport['n']}) ; même masque que FORMS-T : projet "
            f"{ref['projet_meme_masque']['mae_m']:.2f} m, FORMS-T {ref['mae_m']:.2f} m"
        )


# --- Séparation apprentissage / arrêt anticipé / test -------------------------------------


def test_bloc_en_ajustement_et_validation_refuse():
    with pytest.raises(DonneeRefusee, match="à la fois en ajustement et en validation"):
        gbm.controler_separation({(1, 1), (1, 2)}, {(1, 2)}, ["0901-6665"], TEST)


def test_dalle_de_test_dans_l_arret_anticipe_refusee():
    with pytest.raises(DonneeRefusee, match="dalles de test"):
        gbm.controler_separation({(1, 1)}, {(1, 2)}, ["0939-6654"], TEST)


def test_separation_acceptee():
    gbm.controler_separation({(1, 1)}, {(1, 2)}, APPRENTISSAGE, TEST)


def test_blocs_validation_tires_parmi_l_apprentissage():
    blocs = np.array([[0, 0], [0, 1], [1, 0], [1, 1], [0, 0]])
    tires = gbm.choisir_blocs_validation(blocs, 0.25, 42)
    assert len(tires) == 1 and tires <= {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert tires == gbm.choisir_blocs_validation(blocs, 0.25, 42)  # graine
    with pytest.raises(DonneeRefusee, match="valider par blocs"):
        gbm.choisir_blocs_validation(np.array([[3, 3], [3, 3]]), 0.25, 42)


def test_train_refuse_une_dalle_de_test(tmp_path):
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.ingest import Dalle

    conf = charger(conf_gbm(tmp_path / "conf"), tmp_path / "travail")
    dalles = [Dalle("0939-6654", 2022, "2022-10-17", "x")]
    with pytest.raises(DonneeRefusee, match="dalles de test"):
        gbm.entrainer(conf, Chemins(tmp_path / "travail"), dalles, TEST)


def test_validation_sans_pixel_de_test(deux_passes):
    """Les blocs d'arrêt anticipé enregistrés tombent tous dans les dalles d'apprentissage."""
    _, ((travail, _), _) = deux_passes
    (modele,) = (travail / "modeles").glob("gbm-*/modele.json")
    validation = json.loads(modele.read_text(encoding="utf-8"))["validation"]
    taille = validation["taille_bloc_m"]
    assert validation["blocs"] and validation["n_validation"] > 0
    for bx, by in validation["blocs"]:
        x, y = bx * taille, by * taille
        dalles = {f"{int(x // 1000):04d}-{int(y // 1000) + 1:04d}"}
        assert dalles <= set(APPRENTISSAGE), (bx, by)


def test_poids_grands_arbres():
    w = gbm.poids(np.array([2999.0, 3000.0, 3001.0]), {"seuil_cm": 3000, "poids": 3.0})
    assert w.tolist() == [1.0, 1.0, 3.0]


def test_essence_inconnue_manquante():
    ess = np.array([["Chênes décidus", "Sapin, épicéa"], ["", "Pin sylvestre"]], dtype=object)
    codes = gbm.encoder_essence(ess, ["Chênes décidus", "Pin sylvestre"])
    assert codes[0, 0] == 0 and codes[1, 1] == 1
    assert np.isnan(codes[0, 1]) and np.isnan(codes[1, 0])


# --- Descripteurs ---------------------------------------------------------------------------


def test_variables_scene_nuage_et_indices():
    pile = np.array(
        [
            [[1000, 1000]],  # B04
            [[3000, 3000]],  # B08
            [[1, 0]],  # clair
        ],
        dtype="uint16",
    )
    params = {"echelle_reflectance": 0.0001, "bandes": ["B04", "B08"], "indices": {}}
    params["indices"] = {"NDVI": ["B08", "B04"]}
    v = descripteurs.variables_scene(pile, ["B04", "B08", "clair"], params)
    assert v["B04"][0, 0] == pytest.approx(0.1) and np.isnan(v["B04"][0, 1])
    assert v["NDVI"][0, 0] == pytest.approx(0.5) and np.isnan(v["NDVI"][0, 1])


def test_statistiques_entre_scenes_ignorent_les_nuages():
    scenes = [{"x": np.array([[1.0, np.nan]])}, {"x": np.array([[3.0, np.nan]])}]
    s = descripteurs.statistiques_entre_scenes(scenes, [10, 50, 90])
    assert s["x_p50"][0, 0] == pytest.approx(2.0)
    assert s["x_p10"][0, 0] == pytest.approx(1.2) and s["x_p90"][0, 0] == pytest.approx(2.8)
    assert np.isnan(s["x_p50"][0, 1])


def test_voisinage_a_la_main():
    v = np.arange(9, dtype="float64").reshape(3, 3)
    v[0, 0] = np.nan
    moyenne, ecart = descripteurs.voisinage(v, 3)
    assert moyenne[1, 1] == pytest.approx(np.nanmean(v))
    assert ecart[1, 1] == pytest.approx(np.nanstd(v))
    assert moyenne[0, 0] == pytest.approx(np.mean([1, 3, 4]))  # coin : pas de débord
    with pytest.raises(DonneeRefusee):
        descripteurs.voisinage(v, 2)


def test_relief_pente_et_exposition():
    # Altitude qui monte de 1 m par 10 m vers le nord (lignes du nord au sud) : versant sud.
    mnt = np.repeat(np.arange(5, 0, -1, dtype="float64")[:, None], 4, axis=1)
    r = descripteurs.relief(mnt, 10.0)
    assert r["pente_deg"][2, 2] == pytest.approx(np.degrees(np.arctan(0.1)))
    assert r["exposition_nord"][2, 2] == pytest.approx(-1.0)
    assert r["exposition_est"][2, 2] == pytest.approx(0.0)
    plat = descripteurs.relief(np.zeros((3, 3)), 10.0)
    assert np.isnan(plat["exposition_nord"]).all() and (plat["pente_deg"] == 0).all()


def test_zone_sans_mnt_refusee(tmp_path):
    from nemeton_canopee.conf import charger
    from nemeton_canopee.erreurs import EntreeManquante

    chemin = conf_gbm(tmp_path / "conf")
    zone = yaml.safe_load((chemin.parent / "zone.yaml").read_text(encoding="utf-8"))
    del zone["fichiers"]["mnt"]
    (chemin.parent / "zone.yaml").write_text(yaml.safe_dump(zone, allow_unicode=True), "utf-8")
    with pytest.raises(EntreeManquante, match="MNT"):
        descripteurs.lire_mnt(charger(chemin, tmp_path / "t"), DALLES[0])


def test_conf_du_depot_garde_le_modele_trivial():
    chaine = yaml.safe_load(CONF.read_text(encoding="utf-8"))
    modele = yaml.safe_load((CONF.parent / chaine["modele"]).read_text(encoding="utf-8"))
    assert modele["nom"] == "mediane"
    gbm_conf = yaml.safe_load((CONF.parent / "modele" / "gbm.yaml").read_text("utf-8"))
    assert gbm_conf["lightgbm"]["deterministic"] is True
    assert "num_threads" in gbm_conf["lightgbm"]


def test_percentile_nan_egal_a_numpy():
    import warnings

    rng = np.random.default_rng(0)
    pile = rng.random((4, 20, 20))
    pile[rng.random(pile.shape) < 0.4] = np.nan
    pile[:, 0, 0] = np.nan  # cellule nuageuse dans toutes les scènes
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for q in (10, 50, 90):
            attendu = np.nanpercentile(pile, q, axis=0)
            assert np.allclose(descripteurs.percentile_nan(pile, q), attendu, equal_nan=True)


def _zone_et_mnt_sans_tag(tmp_path, mnt_unite):
    """Conf dérivée dont le MNT de la 1re dalle n'a pas de tag `unite`."""
    chemin = conf_gbm(tmp_path / "conf")
    zone_f = chemin.parent / "zone.yaml"
    zone = yaml.safe_load(zone_f.read_text(encoding="utf-8"))
    racine = tmp_path / "donnees"
    (racine / "lidar").mkdir(parents=True)
    source = RACINE / "tests" / "data" / "lidar" / f"{DALLES[0]}_MNT_10m.tif"
    with rasterio.open(source) as src:
        profil, valeurs = src.profile, src.read()
    with rasterio.open(racine / "lidar" / source.name, "w", **profil) as dst:
        dst.write(valeurs)
    zone["fichiers"]["mnt"] = str(racine / "lidar" / "{dalle}_MNT_10m.tif")
    zone.pop("mnt_unite", None)
    if mnt_unite:
        zone["mnt_unite"] = mnt_unite
    zone_f.write_text(yaml.safe_dump(zone, allow_unicode=True), "utf-8")
    from nemeton_canopee.conf import charger

    return charger(chemin, tmp_path / "t")


def test_mnt_sans_unite_refuse(tmp_path):
    conf = _zone_et_mnt_sans_tag(tmp_path, None)
    with pytest.raises(DonneeRefusee, match="sans unité"):
        descripteurs.lire_mnt(conf, DALLES[0])


def test_mnt_sans_tag_unite_declaree_par_la_zone(tmp_path):
    conf = _zone_et_mnt_sans_tag(tmp_path, "m")
    assert np.isfinite(descripteurs.lire_mnt(conf, DALLES[0])).any()


def test_quantiles_non_ponderes_par_defaut():
    gbm_conf = yaml.safe_load((CONF.parent / "modele" / "gbm.yaml").read_text("utf-8"))
    assert gbm_conf["apprentissage"]["quantiles_ponderes"] is False


def test_zone_porte_mnt_et_unite():
    from nemeton_canopee.conf import charger_zone

    zone = charger_zone(CONF.parent / "zones" / "jeu_essai.yaml")
    assert zone.mnt_unite == "m"
    assert zone.chemin("mnt", dalle=DALLES[0]).is_file()


# --- Mission 013 : non-régression de gbm, descripteurs trouées et ortho, variante gbm_ortho --

# Non-régression de gbm (conf/modele/gbm.yaml, sans option 013). Le modèle LightGBM et ses
# prédictions ne sont pas portables à l'octet d'une machine à l'autre (CI Python 3.11 / local
# 3.13) : on fige donc ce que gbm reçoit. (a) Noms des descripteurs, dans l'ordre, tels qu'écrits
# dans modele.json AVANT la mission 013 (version gbm-469e8cdf93e9, 22/11/2026), sans « essence ».
DESCRIPTEURS_GBM = [
    "B02_p10",
    "B02_p50",
    "B02_p90",
    "B03_p10",
    "B03_p50",
    "B03_p90",
    "B04_p10",
    "B04_p50",
    "B04_p90",
    "B05_p10",
    "B05_p50",
    "B05_p90",
    "B06_p10",
    "B06_p50",
    "B06_p90",
    "B07_p10",
    "B07_p50",
    "B07_p90",
    "B08_p10",
    "B08_p50",
    "B08_p90",
    "B8A_p10",
    "B8A_p50",
    "B8A_p90",
    "B11_p10",
    "B11_p50",
    "B11_p90",
    "B12_p10",
    "B12_p50",
    "B12_p90",
    "NDVI_p10",
    "NDVI_p50",
    "NDVI_p90",
    "NDRE_p10",
    "NDRE_p50",
    "NDRE_p90",
    "NBR_p10",
    "NBR_p50",
    "NBR_p90",
    "NDMI_p10",
    "NDMI_p50",
    "NDMI_p90",
    "B02_v3_moy",
    "B02_v3_et",
    "B02_v5_moy",
    "B02_v5_et",
    "B03_v3_moy",
    "B03_v3_et",
    "B03_v5_moy",
    "B03_v5_et",
    "B04_v3_moy",
    "B04_v3_et",
    "B04_v5_moy",
    "B04_v5_et",
    "B05_v3_moy",
    "B05_v3_et",
    "B05_v5_moy",
    "B05_v5_et",
    "B06_v3_moy",
    "B06_v3_et",
    "B06_v5_moy",
    "B06_v5_et",
    "B07_v3_moy",
    "B07_v3_et",
    "B07_v5_moy",
    "B07_v5_et",
    "B08_v3_moy",
    "B08_v3_et",
    "B08_v5_moy",
    "B08_v5_et",
    "B8A_v3_moy",
    "B8A_v3_et",
    "B8A_v5_moy",
    "B8A_v5_et",
    "B11_v3_moy",
    "B11_v3_et",
    "B11_v5_moy",
    "B11_v5_et",
    "B12_v3_moy",
    "B12_v3_et",
    "B12_v5_moy",
    "B12_v5_et",
    "NDVI_v3_moy",
    "NDVI_v3_et",
    "NDVI_v5_moy",
    "NDVI_v5_et",
    "NDRE_v3_moy",
    "NDRE_v3_et",
    "NDRE_v5_moy",
    "NDRE_v5_et",
    "NBR_v3_moy",
    "NBR_v3_et",
    "NBR_v5_moy",
    "NBR_v5_et",
    "NDMI_v3_moy",
    "NDMI_v3_et",
    "NDMI_v5_moy",
    "NDMI_v5_et",
    "altitude_m",
    "pente_deg",
    "exposition_nord",
    "exposition_est",
]
# (b) sha256 de la matrice des descripteurs de 0901-6665 arrondie à 1e-4 (NaN -> -9999), du
# masque clair et de l'essence ; identique sous Python 3.11 (numpy 2.4) et 3.13 (numpy 2.5).
EMPREINTE_DESCRIPTEURS_GBM = "3be55ff83e1073a38d762bb5271787f78003b0b7a503a4daa636c7f08bcfde75"
NOUVEAUX_TROUEES = [
    "NDVI_contraste_v5",
    "B08_contraste_v5",
    "B11_contraste_v5",
    "NDVI_min_v3",
    "NDVI_part_bas_v5",
]


def empreinte_descripteurs(desc) -> str:
    """sha256 des descripteurs arrondis à 1e-4 (NaN -> -9999, -0 -> 0), masque et essence."""
    import hashlib

    v = np.round(desc.valeurs.astype("float64"), 4) + 0.0
    v = np.where(np.isfinite(v), v, -9999.0)
    h = hashlib.sha256(v.astype("<f8").tobytes())
    h.update(np.ascontiguousarray(desc.clair, dtype="uint8").tobytes())
    h.update("\n".join(str(e) for e in desc.essence.ravel()).encode("utf-8"))
    return h.hexdigest()


def test_gbm_descripteurs_inchanges_depuis_avant_013(deux_passes):
    """gbm.yaml n'utilise ni ortho ni trouées : mêmes noms qu'avant 013, mêmes valeurs à 1e-4."""
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.ingest import lire_manifeste

    conf_chemin, ((travail, _), _) = deux_passes
    (modele,) = (travail / "modeles").glob("gbm-*/modele.json")
    noms = json.loads(modele.read_text(encoding="utf-8"))["descripteurs"]
    assert noms == [*DESCRIPTEURS_GBM, gbm.ESSENCE]
    conf, ch = charger(conf_chemin, travail), Chemins(travail)
    (dalle,) = [d for d in lire_manifeste(ch) if d.id == "0901-6665"]
    desc = descripteurs.calculer(conf, ch, dalle.id, dalle.annee, dalle.date_vol)
    assert desc.noms == DESCRIPTEURS_GBM
    assert not [n for n in desc.noms if n.startswith("ortho") or n in NOUVEAUX_TROUEES]
    assert empreinte_descripteurs(desc) == EMPREINTE_DESCRIPTEURS_GBM


def test_gbm_yaml_sans_option_013_et_variante_identique_sinon():
    gbm_conf = yaml.safe_load((CONF.parent / "modele" / "gbm.yaml").read_text("utf-8"))
    assert "trouees" not in gbm_conf["descripteurs"] and "ortho" not in gbm_conf["descripteurs"]
    assert "poids_peuplements_bas" not in gbm_conf["apprentissage"]
    ortho = yaml.safe_load((CONF.parent / "modele" / "gbm_ortho.yaml").read_text("utf-8"))
    assert ortho["apprentissage"]["poids_peuplements_bas"]["actif"] is False
    assert ortho["descripteurs"]["ortho"]["age"] is True
    del ortho["descripteurs"]["trouees"], ortho["descripteurs"]["ortho"]
    del ortho["apprentissage"]["poids_peuplements_bas"]
    assert ortho == gbm_conf  # mêmes hyperparamètres, même validation, rien réglé ailleurs


def test_poids_peuplements_bas():
    y = np.array([999.0, 1000.0, 3001.0])
    assert gbm.poids_bas(y, None).tolist() == [1.0, 1.0, 1.0]
    assert gbm.poids_bas(y, {"actif": False, "seuil_cm": 1000, "poids": 2.0}).tolist() == [1.0] * 3
    regle = {"actif": True, "seuil_cm": 1000, "poids": 2.0}
    assert gbm.poids_bas(y, regle).tolist() == [2.0, 1.0, 1.0]


def test_trouees_a_la_main():
    x = np.full((5, 5), 0.9)
    x[2, 2] = 0.4  # trouée au centre
    x[0, 0] = np.nan  # cellule nuageuse
    params = {
        "contraste": {"variables": ["NDVI"], "cote": 5},
        "minimum": [{"variable": "NDVI", "cote": 3}],
        "part_basse": [{"variable": "NDVI", "cote": 5, "seuil": 0.75}],
    }
    t = descripteurs.trouees({"NDVI": x}, params)
    assert list(t) == ["NDVI_contraste_v5", "NDVI_min_v3", "NDVI_part_bas_v5"]
    # Centre : 24 cellules valides, 23 à 0,9 et 1 à 0,4 -> moyenne 21,1 / 24.
    assert t["NDVI_contraste_v5"][2, 2] == pytest.approx(0.4 - 21.1 / 24)
    assert t["NDVI_min_v3"][1, 1] == pytest.approx(0.4)
    assert t["NDVI_min_v3"][0, 0] == pytest.approx(0.9)  # coin : NaN ignoré, pas de débord
    assert t["NDVI_min_v3"][0, 4] == pytest.approx(0.9)
    assert t["NDVI_part_bas_v5"][2, 2] == pytest.approx(1 / 24)
    assert t["NDVI_part_bas_v5"][0, 4] == pytest.approx(1 / 9)  # coin : fenêtre de 3 x 3
    vide = descripteurs.trouees({"NDVI": np.full((2, 2), np.nan)}, params)
    assert all(np.isnan(v).all() for v in vide.values())
    with pytest.raises(DonneeRefusee, match="absente"):
        descripteurs.trouees({"B04": x}, params)


def test_age_ortho_a_la_main():
    # 2022-07-27 -> 2023-07-27 : 365 j, puis 31 j (-> 27/08) et 8 j (-> 04/09) : 404 j.
    assert descripteurs.age_ortho_jours("2023-09-04", "2022-07-27") == 404
    # Vol du 20/09 au 25/10/2022 : 35 j, milieu le 07/10 ; -> 07/10/2023 : 365 j, moins 34 j.
    assert descripteurs.age_ortho_jours("2023-09-03", "2022-09-20/2022-10-25") == 331
    assert descripteurs.age_ortho_jours("2022-07-01", "2022-07-27") == -26  # ortho antérieure


@pytest.fixture(scope="module")
def deux_passes_ortho(tmp_path_factory):
    """Deux passes complètes de la chaîne avec la variante gbm_ortho."""
    import geopandas as gpd
    from conftest import CARRE_20M
    from shapely.geometry import box

    base = tmp_path_factory.mktemp("gbm_ortho")
    polygones = base / "polygones.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[box(*CARRE_20M)], crs="EPSG:2154").to_file(
        polygones, driver="GPKG"
    )
    conf = conf_gbm(base / "conf", "gbm_ortho.yaml")
    passes = []
    for i in (1, 2):
        travail = base / f"travail{i}"
        passes.append((travail, executer(conf, travail, polygones)))
    return conf, passes


def test_chaine_complete_gbm_ortho(deux_passes_ortho, capsys):
    _, passes = deux_passes_ortho
    for travail, codes in passes:
        assert all(c == 0 for c, _ in codes.values()), codes
        assert list(codes) == ETAPES
        (modele,) = (travail / "modeles").glob("gbm-*/modele.json")
        noms = json.loads(modele.read_text(encoding="utf-8"))["descripteurs"]
        for nom in [*NOUVEAUX_TROUEES, "ortho_part_non_vegetal", "ortho_lum_std_v3_moy"]:
            assert nom in noms
        assert descripteurs.AGE_ORTHO in noms
        assert noms[-1] == gbm.ESSENCE
    rapport = json.loads((passes[0][0] / "validate" / "rapport.json").read_text("utf-8"))
    with capsys.disabled():
        print(f"\n[gbm_ortho, jeu d'essai, 2 dalles de test] MAE {rapport['mae_m']:.2f} m")


def test_gbm_ortho_rejouable_a_l_octet(deux_passes_ortho):
    _, ((t1, _), (t2, _)) = deux_passes_ortho
    fichiers = sorted(
        p.relative_to(t1)
        for p in t1.rglob("*")
        if p.is_file() and p.parts[len(t1.parts)] in {"modeles", "infer", "smooth", "export"}
    )
    assert any(p.suffix == ".txt" for p in fichiers)
    for relatif in fichiers:
        assert (t1 / relatif).read_bytes() == (t2 / relatif).read_bytes(), relatif


def test_descripteurs_gbm_ortho_sur_une_cellule(deux_passes_ortho):
    """Cellule (50, 50) de 0901-6665 : ortho, voisinage 3 x 3, âge et trouées refaits à la main."""
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.ingest import lire_manifeste

    conf_chemin, ((travail, _), _) = deux_passes_ortho
    conf, ch = charger(conf_chemin, travail), Chemins(travail)
    (dalle,) = [d for d in lire_manifeste(ch) if d.id == "0901-6665"]
    assert dalle.date_vol == "2022-07-27"
    desc = descripteurs.calculer(conf, ch, dalle.id, dalle.annee, dalle.date_vol)
    v = dict(zip(desc.noms, desc.valeurs, strict=True))
    i, j = 50, 50
    fichier = RACINE / "tests" / "data" / "ortho" / "0901-6665_ortho_10m.tif"
    with rasterio.open(fichier) as src:
        noms = list(src.descriptions)
        nv = src.read(noms.index("part_non_vegetal") + 1).astype("float64")
        gradient = src.read(noms.index("gradient_moy") + 1).astype("float64")
        assert src.tags()["date_prise_de_vue"] == "2023-09-04"
    assert (nv[i - 1 : i + 2, j - 1 : j + 2] != -9999).all()
    assert v["ortho_part_non_vegetal"][i, j] == nv[i, j]
    assert v["ortho_gradient_moy"][i, j] == gradient[i, j]
    attendu = sum(nv[a, b] for a in (i - 1, i, i + 1) for b in (j - 1, j, j + 1)) / 9
    assert v["ortho_part_non_vegetal_v3_moy"][i, j] == pytest.approx(attendu)
    assert (v[descripteurs.AGE_ORTHO] == 404).all()  # 2023-09-04 - 2022-07-27
    ndvi = v["NDVI_p50"]
    fenetre = ndvi[i - 2 : i + 3, j - 2 : j + 3]
    assert np.isfinite(fenetre).all()
    assert v["NDVI_contraste_v5"][i, j] == pytest.approx(ndvi[i, j] - fenetre.mean())
    assert v["NDVI_min_v3"][i, j] == ndvi[i - 1 : i + 2, j - 1 : j + 2].min()
    assert v["NDVI_part_bas_v5"][i, j] == pytest.approx((fenetre < 0.75).sum() / 25)
    b11 = v["B11_p50"]
    assert v["B11_contraste_v5"][i, j] == pytest.approx(
        b11[i, j] - b11[i - 2 : i + 3, j - 2 : j + 3].mean()
    )


def _conf_ortho_copiee(tmp_path, tags: dict):
    """Conf gbm_ortho dont la zone lit une copie de l'ortho de la 1re dalle, tags modifiés."""
    from nemeton_canopee.conf import charger

    chemin = conf_gbm(tmp_path / "conf", "gbm_ortho.yaml")
    zone_f = chemin.parent / "zone.yaml"
    zone = yaml.safe_load(zone_f.read_text(encoding="utf-8"))
    (tmp_path / "ortho").mkdir()
    source = RACINE / "tests" / "data" / "ortho" / f"{DALLES[0]}_ortho_10m.tif"
    with rasterio.open(source) as src:
        profil, valeurs = src.profile, src.read()
        noms, anciens = src.descriptions, src.tags()
    with rasterio.open(tmp_path / "ortho" / source.name, "w", **profil) as dst:
        dst.write(valeurs)
        dst.descriptions = noms
        dst.update_tags(**{k: v for k, v in {**anciens, **tags}.items() if v is not None})
    zone["fichiers"]["ortho"] = str(tmp_path / "ortho" / "{dalle}_ortho_10m.tif")
    zone_f.write_text(yaml.safe_dump(zone, allow_unicode=True), "utf-8")
    return charger(chemin, tmp_path / "t")


def test_ortho_age_contredit_par_le_fichier_refuse(tmp_path):
    conf = _conf_ortho_copiee(tmp_path, {"ecart_ortho_vol_lidar_jours": "400"})
    with pytest.raises(DonneeRefusee, match="écart au vol"):
        descripteurs.descripteurs_ortho(conf, DALLES[0], "2022-07-27")
    assert (
        descripteurs.descripteurs_ortho(conf, DALLES[0], "2022-07-31")["ortho_age_jours"] == 400
    ).all()


def test_ortho_sans_date_refusee(tmp_path):
    conf = _conf_ortho_copiee(tmp_path, {"date_prise_de_vue": ""})
    with pytest.raises(DonneeRefusee, match="âge inconnu"):
        descripteurs.descripteurs_ortho(conf, DALLES[0], "2022-07-27")


def test_zone_sans_ortho_refusee(tmp_path):
    from nemeton_canopee.conf import charger
    from nemeton_canopee.erreurs import EntreeManquante

    chemin = conf_gbm(tmp_path / "conf", "gbm_ortho.yaml")
    zone = yaml.safe_load((chemin.parent / "zone.yaml").read_text(encoding="utf-8"))
    del zone["fichiers"]["ortho"]
    (chemin.parent / "zone.yaml").write_text(yaml.safe_dump(zone, allow_unicode=True), "utf-8")
    with pytest.raises(EntreeManquante, match="ortho"):
        descripteurs.lire_ortho(charger(chemin, tmp_path / "t"), DALLES[0])
