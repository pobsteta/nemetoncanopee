"""Mission 005 : atomicité de l'étape `export` (plan 004 : « l'étape remplace ses sorties »).

Chaque test travaille sur une copie du dossier de travail de la chaîne de session : la
fixture `chaine` n'est jamais modifiée.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import rasterio
from conftest import CONF, DALLES, lancer
from test_acceptation_jalon_1 import ANNEE, cog_path, exiger_chaine, hash_arbre

AUTRE_ANNEE = 2021


@pytest.fixture
def travail(chaine, tmp_path):
    exiger_chaine(chaine)
    copie = tmp_path / "travail"
    shutil.copytree(chaine.travail, copie)
    return copie


def exporter(travail: Path, *suite: str):
    return lancer(["--conf", str(CONF), "--travail", str(travail), "export", *suite])


def cogs_autre_annee(travail: Path) -> dict[Path, Path]:
    """Pour chaque COG 2022, son jumeau factice 2021 (copie, donc avec les mêmes tags)."""
    jumeaux = {}
    for dalle in DALLES:
        for traitement in ("brute", "lissee"):
            src = cog_path(travail, dalle, traitement)
            dst = (
                travail
                / "export"
                / "cog"
                / "hauteur"
                / str(AUTRE_ANNEE)
                / f"{dalle}_hauteur_{traitement}_{AUTRE_ANNEE}.tif"
            )
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            jumeaux[src] = dst
    return jumeaux


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hrefs_assets(stac: Path) -> list[tuple[Path, str]]:
    """(fichier item, href) de chaque asset de chaque item du catalogue."""
    sortie = []
    for item in sorted(stac.rglob("*.json")):
        doc = json.loads(item.read_text(encoding="utf-8"))
        if doc.get("type") == "Feature":
            sortie += [(item, a["href"]) for a in doc["assets"].values()]
    return sortie


def dossiers_voisins(travail: Path) -> list[str]:
    return sorted(p.name for p in travail.iterdir() if p.name.startswith(".export"))


# --------------------------------------------------------------------------------------
# 1. --annees conserve les COG des autres années
# --------------------------------------------------------------------------------------


def test_annees_conserve_les_autres_annees_et_reecrit_a_l_identique(travail):
    jumeaux = cogs_autre_annee(travail)
    avant_2021 = {dst: sha(dst) for dst in jumeaux.values()}
    avant_2022 = {src: sha(src) for src in jumeaux}
    assert len(avant_2021) == 8

    code, erreur = exporter(travail, "--annees", str(ANNEE))
    assert (code, erreur) == (0, None)

    for dst, empreinte in avant_2021.items():
        assert dst.is_file(), f"COG {AUTRE_ANNEE} perdu : {dst.name}"
        assert sha(dst) == empreinte
    for src, empreinte in avant_2022.items():
        assert sha(src) == empreinte, f"COG {ANNEE} non identique après réécriture : {src.name}"
    assert dossiers_voisins(travail) == []


def test_annees_catalogue_valide_hors_ligne_et_hrefs_existants(travail):
    from nemeton_canopee.conf import charger
    from nemeton_canopee.export.stac import valider

    cogs_autre_annee(travail)
    code, erreur = exporter(travail, "--annees", str(ANNEE))
    assert (code, erreur) == (0, None)

    stac = travail / "export" / "stac"
    conf = charger(CONF)
    assert valider(stac / "catalog.json", conf.dossier_schemas) == 4

    hrefs = hrefs_assets(stac)
    assert len(hrefs) == 8
    for item, href in hrefs:
        cible = (item.parent / href).resolve()
        assert cible.is_file(), f"href mort : {href}"
        assert cible.is_relative_to((travail / "export").resolve())
        with rasterio.open(cible) as src:
            assert src.tags()["CANOPEE_VERSION_MODELE"]


# --------------------------------------------------------------------------------------
# 2. Interruption : l'export précédent reste intact, aucun dossier partiel ne traîne
# --------------------------------------------------------------------------------------


def _interrompre_au_milieu(monkeypatch, apres: int):
    """Fait échouer `ecrire_cog` à son (apres+1)-ième appel (donc au milieu de l'export)."""
    from nemeton_canopee import export
    from nemeton_canopee.export import cog

    appels = []
    reel = cog.ecrire_cog

    def piege(*args, **kwargs):
        if len(appels) == apres:
            raise OSError("disque plein (simulé)")
        appels.append(args)
        return reel(*args, **kwargs)

    monkeypatch.setattr(export, "ecrire_cog", piege)
    return appels


@pytest.mark.parametrize("annees", [(), ("--annees", str(ANNEE))])
def test_interruption_pendant_l_ecriture_laisse_l_export_intact(travail, monkeypatch, annees):
    cogs_autre_annee(travail)
    avant = hash_arbre(travail / "export")
    assert avant

    appels = _interrompre_au_milieu(monkeypatch, apres=3)
    code, erreur = exporter(travail, *annees)

    assert len(appels) == 3, "l'interruption doit tomber au milieu de l'écriture"
    assert code == "exception"
    assert "disque plein (simulé)" in erreur
    assert hash_arbre(travail / "export") == avant
    assert dossiers_voisins(travail) == []


def test_interruption_pendant_la_validation_laisse_l_export_intact(travail, monkeypatch):
    from nemeton_canopee import export

    avant = hash_arbre(travail / "export")

    def valider_en_echec(*args, **kwargs):
        raise RuntimeError("catalogue invalide (simulé)")

    monkeypatch.setattr(export, "valider", valider_en_echec)
    code, erreur = exporter(travail)

    assert code == "exception"
    assert "catalogue invalide (simulé)" in erreur
    assert hash_arbre(travail / "export") == avant
    assert dossiers_voisins(travail) == []


def test_export_sans_sortie_precedente_interrompu_ne_cree_pas_export(travail, monkeypatch):
    shutil.rmtree(travail / "export")
    _interrompre_au_milieu(monkeypatch, apres=2)

    code, _ = exporter(travail)

    assert code == "exception"
    assert not (travail / "export").exists()
    assert dossiers_voisins(travail) == []


# --------------------------------------------------------------------------------------
# 3. Sans --annees : l'étape remplace ses sorties (comportement voulu, documenté)
# --------------------------------------------------------------------------------------


def test_sans_annees_les_annees_absentes_du_manifeste_sont_supprimees(travail):
    jumeaux = cogs_autre_annee(travail)
    avant_2022 = {src: sha(src) for src in jumeaux}

    code, erreur = exporter(travail)
    assert (code, erreur) == (0, None)

    assert not (travail / "export" / "cog" / "hauteur" / str(AUTRE_ANNEE)).exists()
    for src, empreinte in avant_2022.items():
        assert sha(src) == empreinte
    assert dossiers_voisins(travail) == []
    assert len(hrefs_assets(travail / "export" / "stac")) == 8
