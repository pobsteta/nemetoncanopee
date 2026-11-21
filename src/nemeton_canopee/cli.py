"""Commande `canopee` : point d'entrée du pipeline (les étapes arrivent avec le jalon 1)."""

import argparse
from collections.abc import Sequence

from nemeton_canopee import __version__


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="canopee",
        description="Cartes annuelles de hauteur, de volume et de biomasse forestière.",
    )
    parseur.add_argument("--version", action="version", version=f"canopee {__version__}")
    return parseur


def main(argv: Sequence[str] | None = None) -> int:
    parseur = construire_parseur()
    parseur.parse_args(argv)
    parseur.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
