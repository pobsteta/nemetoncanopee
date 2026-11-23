"""Découpage apprentissage / test par blocs spatiaux (CLAUDE.md, « Découpage d'évaluation »).

Le fichier `decoupage.yaml` de la zone est figé (jalon 1). On le relit à chaque usage et on
refuse (code 3) tout découpage où une dalle de test touche une dalle d'apprentissage, par un
bord ou par un coin, ou partage son bloc.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from nemeton_canopee import grille
from nemeton_canopee.conf import Configuration
from nemeton_canopee.erreurs import DonneeRefusee, exiger_fichier

CLES = ["taille_bloc_m", "apprentissage", "test"]
CLES_ENTREE = ["dalle", "bloc"]


@dataclass(frozen=True)
class Decoupage:
    """Dalles d'apprentissage et de test, et taille des blocs (m)."""

    apprentissage: list[str]
    test: list[str]
    taille_bloc_m: int


def controler(d: dict, taille_dalle_m: int) -> Decoupage:
    """Contrôle un découpage lu (dictionnaire YAML) et le renvoie, ou lève `DonneeRefusee`."""
    controler_cles(d)
    taille = int(d["taille_bloc_m"])
    entrees = {"apprentissage": d.get("apprentissage") or [], "test": d.get("test") or []}
    for role, liste in entrees.items():
        for e in liste:
            calcule = grille.bloc(e["dalle"], taille_dalle_m, taille)
            if tuple(e["bloc"]) != calcule:
                raise DonneeRefusee(
                    f"découpage refusé : la dalle {e['dalle']} ({role}) déclare le bloc "
                    f"{tuple(e['bloc'])}, son emprise donne {calcule}"
                )
    appr = sorted(e["dalle"] for e in entrees["apprentissage"])
    test = sorted(e["dalle"] for e in entrees["test"])
    if not appr or not test:
        raise DonneeRefusee("découpage refusé : il faut au moins une dalle de chaque rôle")
    for t in test:
        for a in appr:
            if grille.se_touchent(a, t, taille_dalle_m):
                raise DonneeRefusee(
                    f"découpage refusé : la dalle de test {t} touche la dalle d'apprentissage "
                    f"{a} (règle : jamais de dalles voisines entre apprentissage et test)"
                )
    blocs_appr = {grille.bloc(a, taille_dalle_m, taille) for a in appr}
    communs = blocs_appr & {grille.bloc(t, taille_dalle_m, taille) for t in test}
    if communs:
        raise DonneeRefusee(
            f"découpage refusé : blocs partagés entre apprentissage et test {sorted(communs)} "
            "(règle : blocs spatiaux distincts)"
        )
    return Decoupage(apprentissage=appr, test=test, taille_bloc_m=taille)


def controler_cles(d: object) -> None:
    """Refuse (code 3) un découpage auquel il manque une clé obligatoire."""
    if not isinstance(d, dict):
        raise DonneeRefusee("découpage refusé : decoupage.yaml n'est pas un dictionnaire")
    manquantes = [c for c in CLES if c not in d]
    for role in ("apprentissage", "test"):
        for i, e in enumerate(d.get(role) or []):
            if not isinstance(e, dict):
                manquantes.append(f"{role}[{i}]")
                continue
            manquantes += [f"{role}[{i}].{c}" for c in CLES_ENTREE if c not in e]
    if manquantes:
        raise DonneeRefusee(
            f"découpage refusé : clés absentes de decoupage.yaml : {', '.join(manquantes)} "
            f"(règle : {', '.join(CLES)} obligatoires, chaque entrée avec {', '.join(CLES_ENTREE)})"
        )


def lire(conf: Configuration) -> Decoupage:
    """Lit et contrôle le `decoupage.yaml` de la zone."""
    chemin = exiger_fichier(conf.zone.chemin("decoupage"), "ingest (découpage absent)")
    d = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    return controler(d, int(conf.grille["taille_dalle_m"]))
