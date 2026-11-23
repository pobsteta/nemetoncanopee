"""Erreurs attendues de la chaîne, chacune avec son code de retour (plan 004, § 4 et décision 9).

- `EntreeManquante` (code 2) : un fichier d'entrée manque ; le message nomme l'étape à relancer.
- `DonneeRefusee` (code 3) : une donnée viole une règle du projet (découpage invalide, scène hors
  de l'année de vol…) ; le message nomme la règle.
"""


class ErreurCanopee(Exception):
    """Erreur attendue : la commande s'arrête proprement avec `code`."""

    code = 1


class EntreeManquante(ErreurCanopee):
    """Une entrée manque : relancer l'étape qui la produit."""

    code = 2


class DonneeRefusee(ErreurCanopee):
    """Une donnée est refusée parce qu'elle enfreint une règle nommée dans le message."""

    code = 3


def exiger_fichier(chemin, etape: str):
    """Lève `EntreeManquante` si `chemin` n'existe pas, en nommant l'étape à relancer."""
    from pathlib import Path

    chemin = Path(chemin)
    if not chemin.is_file():
        raise EntreeManquante(f"entrée manquante : {chemin} (relancer `canopee {etape}`)")
    return chemin
