"""Modèle unet (mission 010, ADR 0004 option A) : petit U-Net PyTorch sur CPU.

La chaîne complète tourne avec `modele: unet` sur le jeu d'essai, à partir d'une conf dérivée
de `conf/chaine.yaml` dans un dossier temporaire (la conf du dépôt garde le modèle trivial) ;
le modèle y est minuscule (2 époques, 4 canaux de base) pour tenir en moins de 2 minutes CPU.
Torch est requis (extra `[ml]`, inclus dans `[dev]`) : aucun test n'est ignoré sans lui.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest
import rasterio
import torch
import yaml
from conftest import CARRE_20M, CONF, ETAPES, RACINE, arguments_zonal, lancer

from nemeton_canopee import descripteurs
from nemeton_canopee.erreurs import DonneeRefusee
from nemeton_canopee.models import unet

TEST = ["0939-6654", "0939-6655"]
APPRENTISSAGE = ["0901-6665", "0902-6665"]
NODATA = 65535


def conf_unet(dossier: Path) -> Path:
    """Conf dérivée : modèle unet minuscule, zone du jeu d'essai (MNT déclaré), chemins absolus."""
    dossier.mkdir(parents=True, exist_ok=True)
    chaine = yaml.safe_load(CONF.read_text(encoding="utf-8"))
    zone = yaml.safe_load((CONF.parent / chaine["zone"]).read_text(encoding="utf-8"))
    zone["source"]["racine"] = str(RACINE / "tests" / "data")
    (dossier / "zone.yaml").write_text(yaml.safe_dump(zone, allow_unicode=True), "utf-8")
    modele = yaml.safe_load((CONF.parent / "modele" / "unet.yaml").read_text(encoding="utf-8"))
    modele["architecture"]["base_canaux"] = 4
    modele["apprentissage"]["epoques_max"] = 2
    modele["torch"]["num_threads"] = 2
    (dossier / "unet.yaml").write_text(yaml.safe_dump(modele, allow_unicode=True), "utf-8")
    chaine["zone"] = "zone.yaml"
    chaine["modele"] = "unet.yaml"
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
    """Deux passes complètes de la chaîne unet dans deux dossiers distincts, chronométrées."""
    import geopandas as gpd
    from shapely.geometry import box

    base = tmp_path_factory.mktemp("unet")
    polygones = base / "polygones.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[box(*CARRE_20M)], crs="EPSG:2154").to_file(
        polygones, driver="GPKG"
    )
    conf = conf_unet(base / "conf")
    passes = []
    for i in (1, 2):
        travail = base / f"travail{i}"
        debut = time.perf_counter()
        codes = executer(conf, travail, polygones)
        passes.append((travail, codes, time.perf_counter() - debut))
    return conf, passes


def test_chaine_complete_unet_moins_de_2_minutes(deux_passes):
    _, passes = deux_passes
    for travail, codes, duree in passes:
        assert all(c == 0 for c, _ in codes.values()), codes
        assert list(codes) == ETAPES
        assert duree < 120, f"chaîne unet en {duree:.0f} s (règle : < 2 min CPU)"
        (modele,) = (travail / "modeles").glob("unet-*/modele.json")
        contenu = json.loads(modele.read_text(encoding="utf-8"))
        poids = (modele.parent / unet.POIDS).read_bytes()
        assert contenu["fichiers"][unet.POIDS] == __import__("hashlib").sha256(poids).hexdigest()
        assert contenu["dalles_apprentissage"] == APPRENTISSAGE
        assert len(contenu["historique"]) == 2  # 2 époques (conf de test)
        assert str(travail) not in modele.read_text(encoding="utf-8")


def test_rejouable_a_l_octet(deux_passes):
    _, ((t1, _, _), (t2, _, _)) = deux_passes
    fichiers = sorted(
        p.relative_to(t1)
        for p in t1.rglob("*")
        if p.is_file() and p.parts[len(t1.parts)] in {"modeles", "infer", "smooth", "export"}
    )
    assert any(p.name.endswith("incertitude_brute.tif") for p in fichiers)
    assert any(p.name == unet.POIDS for p in fichiers)
    for relatif in fichiers:
        assert (t1 / relatif).read_bytes() == (t2 / relatif).read_bytes(), relatif


def test_incertitude_coherente(deux_passes):
    conf_chemin, ((travail, _, _), _) = deux_passes
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.infer import masque_clair
    from nemeton_canopee.ingest import lire_manifeste
    from nemeton_canopee.models import modele_actif

    conf = charger(conf_chemin, travail)
    ch = Chemins(travail)
    version, modele = modele_actif(ch)
    assert version.startswith("unet-")
    for dalle in lire_manifeste(ch):
        with rasterio.open(ch.brute(dalle.annee, dalle.id)) as src:
            hauteur = src.read(1)
        with rasterio.open(ch.incertitude(dalle.annee, dalle.id)) as src:
            incertitude, tags = src.read(1), src.tags()
            assert src.dtypes[0] == "uint16" and src.nodata == NODATA
        assert tags["CANOPEE_COUCHE"] == "hauteur_incertitude"
        assert tags["CANOPEE_VERSION_MODELE"] == version
        assert np.array_equal(hauteur == NODATA, incertitude == NODATA)
        assert (hauteur != NODATA).sum() > 0
        foret = rasterio.open(ch.foret(dalle.id)).read(1)
        masque = (foret == 1) & masque_clair(ch.scenes_preparees(dalle.annee, dalle.id))
        couches = unet.predire(conf, ch, version, modele, dalle, masque)
        p10, p90, h = couches["q10"][masque], couches["q90"][masque], couches["hauteur"][masque]
        assert np.all(p10 <= h) and np.all(h <= p90)
        assert np.array_equal(couches["hauteur"], hauteur)
        assert np.array_equal(couches["incertitude"][masque], p90 - p10)


def test_mae_rapportee(deux_passes, capsys):
    _, ((travail, _, duree), _) = deux_passes
    rapport = json.loads((travail / "validate" / "rapport.json").read_text(encoding="utf-8"))
    assert sorted(rapport["dalles"]) == TEST
    assert rapport["version_modele"].startswith("unet-")
    assert np.isfinite(rapport["mae_m"]) and rapport["n"] > 0
    with capsys.disabled():
        print(
            f"\n[unet minuscule, 2 époques, jeu d'essai, 2 dalles de test] MAE "
            f"{rapport['mae_m']:.2f} m (n={rapport['n']}) ; chaîne en {duree:.0f} s"
        )


def test_validation_tiree_des_seules_dalles_d_apprentissage(deux_passes):
    _, ((travail, _, _), _) = deux_passes
    (modele,) = (travail / "modeles").glob("unet-*/modele.json")
    validation = json.loads(modele.read_text(encoding="utf-8"))["validation"]
    assert validation["dalles"] and validation["dalles_ajustement"]
    assert set(validation["dalles"]) | set(validation["dalles_ajustement"]) == set(APPRENTISSAGE)
    assert not set(validation["dalles"]) & set(validation["dalles_ajustement"])
    assert not (set(validation["dalles"]) | set(validation["dalles_ajustement"])) & set(TEST)


def test_train_refuse_une_dalle_de_test(tmp_path):
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.ingest import Dalle

    conf = charger(conf_unet(tmp_path / "conf"), tmp_path / "travail")
    dalles = [Dalle("0901-6665", 2022, "2022-10-17", "x"), Dalle("0939-6654", 2022, "x", "x")]
    with pytest.raises(DonneeRefusee, match="dalles de test") as e:
        unet.entrainer(conf, Chemins(tmp_path / "travail"), dalles, TEST)
    assert e.value.code == 3


def test_validation_dans_le_test_refusee_code_3(tmp_path, monkeypatch):
    """Une dalle de validation qui serait de test est refusée (code 3) avant toute lecture."""
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.conf import charger
    from nemeton_canopee.ingest import Dalle

    conf = charger(conf_unet(tmp_path / "conf"), tmp_path / "travail")
    monkeypatch.setattr(unet, "choisir_dalles_validation", lambda *a, **k: ["0939-6654"])
    dalles = [Dalle(d, 2022, "x", "x") for d in APPRENTISSAGE]
    with pytest.raises(DonneeRefusee, match="dalles de test") as e:
        unet.entrainer(conf, Chemins(tmp_path / "travail"), dalles, TEST)
    assert e.value.code == 3


# --- Unités -------------------------------------------------------------------------------


def test_debuts_des_patchs():
    assert unet.debuts(100, 64, 36) == [0, 36]
    assert unet.debuts(100, 64, 20) == [0, 20, 36]  # dernière fenêtre calée sur le bord
    assert unet.debuts(50, 64, 36) == [0]  # dalle plus petite : padding miroir
    with pytest.raises(DonneeRefusee):
        unet.debuts(100, 64, 0)


def test_pad_miroir():
    a = np.arange(6, dtype="float32").reshape(1, 2, 3)
    p = unet.pad_miroir(a, 4, 4)
    assert p.shape == (1, 4, 4)
    assert p[0, 2].tolist() == [3, 4, 5, 5] and p[0, 3].tolist() == [0, 1, 2, 2]


def test_exposition_tournee_avec_l_image():
    """Le relief d'un MNT tourné égale le relief tourné, exposition comprise."""
    rng = np.random.default_rng(0)
    mnt = np.cumsum(rng.random((9, 9)), axis=0) * 3 + np.cumsum(rng.random((9, 9)), axis=1)
    r = descripteurs.relief(mnt, 10.0)
    for miroir in (False, True):
        for k in range(4):
            m = np.flip(mnt, axis=-1) if miroir else mnt
            attendu = descripteurs.relief(np.rot90(m, k), 10.0)
            n, e = r["exposition_nord"], r["exposition_est"]
            if miroir:
                n, e = np.flip(n, axis=-1), np.flip(e, axis=-1)
            n, e = unet.tourner_exposition(np.rot90(n, k), np.rot90(e, k), k, miroir)
            centre = (slice(1, -1), slice(1, -1))  # np.gradient diffère au bord
            assert np.allclose(n[centre], attendu["exposition_nord"][centre]), (k, miroir)
            assert np.allclose(e[centre], attendu["exposition_est"][centre]), (k, miroir)


def test_augmenter_garde_cible_et_poids_alignes():
    x = torch.arange(3 * 4 * 4, dtype=torch.float32).reshape(3, 4, 4)
    y, w = x[0].clone(), x[1].clone()
    ax, ay, aw = unet.augmenter(x, y, w, 1, True, 1, 2)
    assert torch.equal(ax[0], ay)  # le canal 0 a suivi la cible
    assert torch.equal(torch.rot90(torch.flip(x[0], dims=(-1,)), 1, dims=(-2, -1)), ay)


def test_poids_grands_arbres_et_masque():
    cible = np.array([2999, 3000, 3001, 4000])
    valide = np.array([True, True, True, False])
    w = unet.poids(cible, valide, {"seuil_cm": 3000, "poids": 3.0})
    assert w.tolist() == [1.0, 1.0, 3.0, 0.0]


def test_normalisation_ignore_les_absents():
    pile = np.array([[[1.0, 3.0], [np.nan, 5.0]], [[2.0, 2.0], [2.0, 2.0]]])
    e = unet.EntreesDalle("0901-6665", [pile], [np.ones((2, 2), bool)])
    moyenne, ecart = unet.normalisation([e])
    assert moyenne == pytest.approx([3.0, 2.0])
    assert ecart[0] == pytest.approx(np.std([1.0, 3.0, 5.0])) and ecart[1] == 1.0
    n = unet.normaliser(pile, moyenne, ecart, 5.0)
    assert n.dtype == np.float32 and n[0, 1, 0] == 0.0
    loin = unet.normaliser(np.array([[[1e6]], [[-1e6]]]), [0.0, 0.0], [1.0, 1.0], 5.0)
    assert loin.ravel().tolist() == [5.0, -5.0]  # altitude hors plage : bornée


def test_reseau_parametres_et_forme():
    archi = yaml.safe_load((CONF.parent / "modele" / "unet.yaml").read_text("utf-8"))
    reseau = unet.construire(15, archi["architecture"])
    n = sum(p.numel() for p in reseau.parameters())
    assert 500_000 <= n <= 2_000_000, n  # petit U-Net de la mission 010
    reseau.eval()
    x = np.zeros((15, 100, 100), dtype="float32")
    assert unet.predire_pile(reseau, x, {"niveaux": 3}).shape == (100, 100)
    assert unet.predire_pile(reseau, x[:, :98, :99], {"niveaux": 3}).shape == (98, 99)


def test_poids_en_octets_aller_retour():
    torch.manual_seed(0)
    archi = {"niveaux": 2, "base_canaux": 2}
    a, b = unet.construire(3, archi), unet.construire(3, archi)
    octets, description = unet.poids_en_octets(a)
    unet.charger_poids(b, octets, description)
    for (ka, va), (kb, vb) in zip(a.state_dict().items(), b.state_dict().items(), strict=True):
        assert ka == kb and torch.equal(va, vb)
    with pytest.raises(DonneeRefusee):
        unet.charger_poids(b, octets + b"\0", description)


def test_conf_unet_deterministe_et_depot_trivial():
    chaine = yaml.safe_load(CONF.read_text(encoding="utf-8"))
    assert yaml.safe_load((CONF.parent / chaine["modele"]).read_text("utf-8"))["nom"] == "mediane"
    conf = yaml.safe_load((CONF.parent / "modele" / "unet.yaml").read_text("utf-8"))
    assert conf["nom"] == "unet" and conf["apprentissage"]["patch"] == 64
    assert conf["apprentissage"]["poids_grands_arbres"]["seuil_cm"] == 3000
    assert "num_threads" in conf["torch"]


def test_altitude_normalisation_physique():
    norme = ([1.0, 246.8], [1.0, 2.9])  # altitude d'une seule dalle : sigma de 2,9 m
    fixee = {"altitude_m": {"centre": 500.0, "echelle": 500.0}}
    m, e = unet.normalisation_physique(norme, ["B02", "altitude_m"], fixee)
    assert m == [1.0, 500.0] and e == [1.0, 500.0]
    z = unet.normaliser(np.array([[[0.0]], [[810.0]]]), m, e, 5.0)
    assert z[1, 0, 0] == pytest.approx(0.62)  # dalle de test à 810 m : dans la plage
    with pytest.raises(DonneeRefusee):
        unet.normalisation_physique(norme, ["B02", "altitude_m"], {"x": fixee["altitude_m"]})
    conf = yaml.safe_load((CONF.parent / "modele" / "unet.yaml").read_text("utf-8"))
    assert "altitude_m" in conf["descripteurs"]["normalisation_physique"]
