"""Chargement et contrôle de la configuration YAML (`conf/chaine.yaml` et ses fichiers liés).

Les chemins d'un fichier YAML sont relatifs au dossier de ce fichier. Rien n'est réglé dans le
code : la chaîne lit ici sa graine, sa grille, ses seuils et ses chemins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nemeton_canopee import grille
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante

VARIABLE_CONF = "CANOPEE_CONF"


def _lire_yaml(chemin: Path) -> dict[str, Any]:
    if not chemin.is_file():
        raise EntreeManquante(f"fichier de configuration absent : {chemin}")
    contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    if not isinstance(contenu, dict):
        raise EntreeManquante(f"configuration illisible (dictionnaire attendu) : {chemin}")
    return contenu


def _relatif(base: Path, valeur: str | os.PathLike) -> Path:
    """Chemin `valeur` résolu par rapport au dossier `base` (inchangé s'il est absolu)."""
    chemin = Path(valeur)
    return chemin if chemin.is_absolute() else (base / chemin).resolve()


def _exiger(d: dict[str, Any], cles: list[str], origine: Path) -> None:
    manquantes = [c for c in cles if c not in d]
    if manquantes:
        raise EntreeManquante(f"clés absentes de {origine} : {', '.join(manquantes)}")


@dataclass(frozen=True)
class Zone:
    """Zone de travail : source des données, dalles, années et fichiers d'entrée."""

    nom: str
    mode: str
    racine: Path
    fichiers: dict[str, str]
    dalles: list[str]
    annees: list[int]
    foret_formations: str
    mnh_unite: str

    def chemin(self, cle: str, **champs: str) -> Path:
        """Chemin d'un fichier d'entrée de la zone (`cle` de `fichiers`, gabarit `{dalle}`)."""
        return self.racine / self.fichiers[cle].format(**champs)


@dataclass(frozen=True)
class Configuration:
    """Configuration complète de la chaîne, chemins résolus."""

    fichier: Path
    travail: Path
    graine: int
    zone: Zone
    modele: dict[str, Any]
    grille: dict[str, Any]
    hauteur: dict[str, Any]
    prepare: dict[str, Any]
    smooth: dict[str, Any]
    cog: dict[str, Any]
    stac: dict[str, Any]

    @property
    def nodata(self) -> int:
        return int(self.hauteur["nodata"])

    @property
    def dossier_schemas(self) -> Path:
        return _relatif(self.fichier.parent, self.stac["schemas"])


def charger_zone(chemin: Path) -> Zone:
    """Lit un fichier de zone (`conf/zones/*.yaml`)."""
    d = _lire_yaml(chemin)
    _exiger(d, ["nom", "source", "fichiers", "dalles", "annees", "mnh_unite"], chemin)
    source = d["source"]
    if source.get("mode") != "local":
        # Seul le mode local (jeu embarqué) existe au jalon 1 : aucun accès réseau.
        raise DonneeRefusee(
            f"mode de source {source.get('mode')!r} refusé dans {chemin} "
            "(règle : seul le mode « local » existe au jalon 1, sans réseau)"
        )
    for dalle in d["dalles"]:
        grille.controler_identifiant(str(dalle))
    return Zone(
        nom=str(d["nom"]),
        mode=source["mode"],
        racine=_relatif(chemin.parent, source["racine"]),
        fichiers=dict(d["fichiers"]),
        dalles=[str(x) for x in d["dalles"]],
        annees=[int(a) for a in d["annees"]],
        foret_formations=str(d.get("foret_formations", "tout")),
        mnh_unite=str(d["mnh_unite"]),
    )


def charger(chemin: str | os.PathLike, travail: str | os.PathLike | None = None) -> Configuration:
    """Charge `conf/chaine.yaml` ; `travail` remplace le dossier de travail s'il est donné."""
    fichier = Path(chemin).resolve()
    d = _lire_yaml(fichier)
    cles = ["travail", "graine", "zone", "modele", "grille", "hauteur", "prepare", "smooth"]
    _exiger(d, [*cles, "cog", "stac"], fichier)
    base = fichier.parent
    return Configuration(
        fichier=fichier,
        travail=Path(travail).resolve() if travail else _relatif(base, d["travail"]),
        graine=int(d["graine"]),
        zone=charger_zone(_relatif(base, d["zone"])),
        modele=_lire_yaml(_relatif(base, d["modele"])),
        grille=dict(d["grille"]),
        hauteur=dict(d["hauteur"]),
        prepare=dict(d["prepare"]),
        smooth=dict(d["smooth"]),
        cog=dict(d["cog"]),
        stac=dict(d["stac"]),
    )
