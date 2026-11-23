"""Fixtures communes des tests d'acceptation du jalon 1 (mission 003).

- `reseau_bloque` : tout `socket.connect` lève (spec § 4, critère 1 : sans réseau).
- `chaine` : exécute une fois par session les 9 commandes `canopee` sur le jeu de 4 dalles,
  dans un dossier temporaire, et chronomètre (critère 7). Elle ne lève jamais : un échec de
  la chaîne est enregistré et fait échouer les tests qui s'appuient dessus, pas la collecte.
"""

import socket
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
CONF = RACINE / "conf" / "chaine.yaml"
DONNEES = RACINE / "tests" / "data"
DALLES = ["0901-6665", "0902-6665", "0939-6654", "0939-6655"]
ETAPES = ["ingest", "prepare", "targets", "train", "infer", "smooth", "validate", "export", "zonal"]
# Carré de 20 m (cellules 10 m alignées) au milieu de 0901-6665 : forêt, MNH valide, SCL « bon »
# dans les 3 scènes (vérifié sur le jeu d'essai le 2026-11-22).
CARRE_20M = (901500.0, 6664500.0, 901520.0, 6664520.0)


class ReseauBloque(AssertionError):
    pass


def _connect_interdit(self, *args, **kwargs):
    raise ReseauBloque("accès réseau interdit pendant les tests (spec § 4, critère 1)")


PROXY_MORT = "http://127.0.0.1:9"


def bloquer_gdal(mp) -> None:
    """GDAL/curl ne sort plus : proxy mort ; les lectures de fichiers locaux restent possibles."""
    for var in ("GDAL_HTTP_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        mp.setenv(var, PROXY_MORT)
    mp.setenv("NO_PROXY", "")
    mp.setenv("no_proxy", "")
    mp.setenv("CPL_CURL_VERBOSE", "NO")
    mp.setenv("GDAL_HTTP_CONNECTTIMEOUT", "1")
    mp.setenv("GDAL_HTTP_MAX_RETRY", "0")
    mp.setenv("GDAL_HTTP_TIMEOUT", "2")


@pytest.fixture(autouse=True)
def reseau_bloque(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _connect_interdit)
    bloquer_gdal(monkeypatch)


@dataclass
class Chaine:
    travail: Path
    polygones: Path
    sortie_zonal: Path
    codes: dict = field(default_factory=dict)
    erreurs: dict = field(default_factory=dict)
    duree_s: float = 0.0

    def args(self, etape: str, *suite: str) -> list[str]:
        return ["--conf", str(CONF), "--travail", str(self.travail), etape, *suite]


def arguments_zonal(polygones: Path, sortie: Path) -> list[str]:
    return [
        "--polygones",
        str(polygones),
        "--champ-id",
        "id",
        "--annees",
        "2022",
        "--couches",
        "hauteur",
        "--sortie",
        str(sortie),
    ]


def lancer(argv: list[str]) -> tuple[int | str, str | None]:
    """Appelle `nemeton_canopee.cli.main(argv)` ; renvoie (code, erreur ou None)."""
    try:
        from nemeton_canopee.cli import main

        code = main(argv)
        return (0 if code is None else code), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), f"SystemExit({e.code})"
    except Exception as e:
        return "exception", f"{type(e).__name__}: {e}"


def executer_chaine(travail: Path, polygones: Path, sortie: Path) -> Chaine:
    ch = Chaine(travail=travail, polygones=polygones, sortie_zonal=sortie)
    debut = time.perf_counter()
    for etape in ETAPES:
        suite = arguments_zonal(polygones, sortie) if etape == "zonal" else []
        code, erreur = lancer(ch.args(etape, *suite))
        ch.codes[etape] = code
        if erreur:
            ch.erreurs[etape] = erreur
        if code != 0:
            break
    ch.duree_s = time.perf_counter() - debut
    return ch


@pytest.fixture(scope="session")
def chaine(tmp_path_factory):
    import geopandas as gpd
    from shapely.geometry import box

    base = tmp_path_factory.mktemp("chaine")
    polygones = base / "polygones_essai.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[box(*CARRE_20M)], crs="EPSG:2154").to_file(
        polygones, driver="GPKG"
    )
    mp = pytest.MonkeyPatch()
    mp.setattr(socket.socket, "connect", _connect_interdit)
    bloquer_gdal(mp)
    try:
        return executer_chaine(base / "travail", polygones, base / "zonal_essai.csv")
    finally:
        mp.undo()
