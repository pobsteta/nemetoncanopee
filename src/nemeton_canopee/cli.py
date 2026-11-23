"""Commande `canopee` : une sous-commande par étape du pipeline (plan 004, § 4).

    canopee --conf conf/chaine.yaml [--travail DOSSIER] <etape> [options]

`--conf` peut venir de la variable d'environnement `CANOPEE_CONF`. Codes de retour : 0 succès ;
2 entrée manquante (le message nomme l'étape à relancer) ; 3 donnée refusée (le message nomme
la règle).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from nemeton_canopee import __version__
from nemeton_canopee.conf import VARIABLE_CONF, charger
from nemeton_canopee.erreurs import EntreeManquante, ErreurCanopee

ETAPES = ["ingest", "prepare", "targets", "train", "infer", "smooth", "validate", "export", "zonal"]


def _ajouter_dalles(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dalles", nargs="+", metavar="D", help="restreindre à ces dalles")


def _ajouter_annees(p: argparse.ArgumentParser, requis: bool = False) -> None:
    p.add_argument("--annees", nargs="+", type=int, metavar="A", required=requis)


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="canopee",
        description="Cartes annuelles de hauteur, de volume et de biomasse forestière.",
    )
    parseur.add_argument("--version", action="version", version=f"canopee {__version__}")
    parseur.add_argument("--conf", help=f"conf/chaine.yaml (ou variable {VARIABLE_CONF})")
    parseur.add_argument("--travail", help="dossier de travail (remplace celui de la conf)")
    sous = parseur.add_subparsers(dest="etape", metavar="ETAPE")

    p = sous.add_parser("ingest", help="manifeste des dalles et des scènes")
    _ajouter_dalles(p)
    _ajouter_annees(p)
    p = sous.add_parser("prepare", help="piles Sentinel-2 à 10 m et masque forêt")
    _ajouter_dalles(p)
    p = sous.add_parser("targets", help="cible de hauteur LiDAR HD à 10 m")
    _ajouter_dalles(p)
    sous.add_parser("train", help="entraîne le modèle sur les dalles d'apprentissage")
    for nom, aide in (("infer", "couche brute"), ("smooth", "couche lissée")):
        p = sous.add_parser(nom, help=aide)
        _ajouter_annees(p)
        _ajouter_dalles(p)
    sous.add_parser("validate", help="rapport de validation sur les dalles de test")
    p = sous.add_parser("export", help="COG et catalogue STAC")
    _ajouter_annees(p)
    p = sous.add_parser("zonal", help="statistiques zonales par polygone")
    p.add_argument("--polygones", required=True, help="fichier vecteur (GPKG…)")
    p.add_argument("--champ-id", default="id", help="champ identifiant des polygones")
    _ajouter_annees(p, requis=True)
    p.add_argument("--couches", nargs="+", required=True, help="couches (ex. hauteur)")
    p.add_argument("--traitement", default="lissee", choices=["brute", "lissee"])
    p.add_argument("--sortie", help="CSV de sortie (défaut : {travail}/zonal/statistiques.csv)")
    return parseur


def executer_etape(args: argparse.Namespace) -> None:
    """Charge la configuration et lance l'étape demandée."""
    fichier_conf = args.conf or os.environ.get(VARIABLE_CONF)
    if not fichier_conf:
        raise EntreeManquante(f"--conf manquant (ou variable {VARIABLE_CONF})")
    conf = charger(fichier_conf, args.travail)
    etape = args.etape
    if etape == "ingest":
        from nemeton_canopee import ingest

        ingest.executer(conf, args.dalles, args.annees)
    elif etape == "prepare":
        from nemeton_canopee import prepare

        prepare.executer(conf, args.dalles)
    elif etape == "targets":
        from nemeton_canopee import targets

        targets.executer(conf, args.dalles)
    elif etape == "train":
        from nemeton_canopee import models

        print(f"modèle {models.executer(conf)}")
    elif etape == "infer":
        from nemeton_canopee import infer

        infer.executer(conf, args.annees, args.dalles)
    elif etape == "smooth":
        from nemeton_canopee import temporal

        temporal.executer(conf, args.annees, args.dalles)
    elif etape == "validate":
        from nemeton_canopee import validate

        print(f"MAE {validate.executer(conf)['mae_m']:.2f} m")
    elif etape == "export":
        from nemeton_canopee import export

        print(f"{export.executer(conf, args.annees)} items STAC validés")
    else:
        _zonal(conf, args)


def _zonal(conf, args: argparse.Namespace) -> None:
    from pathlib import Path

    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.ecriture import atomique
    from nemeton_canopee.erreurs import exiger_fichier
    from nemeton_canopee.zonal import statistiques_zonales

    ch = Chemins(conf.travail)
    resultat = statistiques_zonales(
        exiger_fichier(args.polygones, "zonal (polygones absents)"),
        args.annees,
        args.couches,
        exiger_fichier(ch.stac / "catalog.json", "export"),
        champ_id=args.champ_id,
        traitement=args.traitement,
    )
    sortie = Path(args.sortie) if args.sortie else ch.zonal
    with atomique(sortie) as tmp:
        resultat.to_csv(tmp, index=False)


def main(argv: Sequence[str] | None = None) -> int:
    parseur = construire_parseur()
    args = parseur.parse_args(argv)
    if args.etape is None:
        parseur.print_help()
        return 0
    try:
        executer_etape(args)
    except ErreurCanopee as e:
        print(f"canopee {args.etape} : {e}", file=sys.stderr)
        return e.code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
