"""Le seul nom de chaque fichier de travail (plan 004, § 3).

Toute étape passe par ces fonctions : aucun nom de fichier n'est construit ailleurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chemins:
    """Arborescence du dossier de travail `racine`."""

    racine: Path

    # ingest
    @property
    def manifeste(self) -> Path:
        return self.racine / "ingest" / "manifeste.parquet"

    @property
    def scenes(self) -> Path:
        return self.racine / "ingest" / "scenes.parquet"

    @property
    def references(self) -> Path:
        return self.racine / "ingest" / "references.parquet"

    # prepare
    def scene_preparee(self, annee: int, dalle: str, scene: str) -> Path:
        return self.racine / "prepare" / str(annee) / dalle / f"s2_{scene}.tif"

    def scenes_preparees(self, annee: int, dalle: str) -> list[Path]:
        return sorted((self.racine / "prepare" / str(annee) / dalle).glob("s2_*.tif"))

    def foret(self, dalle: str) -> Path:
        return self.racine / "prepare" / dalle / "foret_10m.tif"

    # targets
    def cible(self, annee: int, dalle: str) -> Path:
        return self.racine / "targets" / str(annee) / f"{dalle}_cible_hauteur.tif"

    # train
    @property
    def modeles(self) -> Path:
        return self.racine / "modeles"

    def modele(self, version: str) -> Path:
        return self.modeles / version / "modele.json"

    # infer, smooth
    def brute(self, annee: int, dalle: str) -> Path:
        return self.racine / "infer" / str(annee) / f"{dalle}_hauteur_brute.tif"

    def incertitude(self, annee: int, dalle: str) -> Path:
        """Couche brute d'incertitude du modèle gbm (p90 - p10, cm), mission 009."""
        return self.racine / "infer" / str(annee) / f"{dalle}_hauteur_incertitude_brute.tif"

    def lissee(self, annee: int, dalle: str) -> Path:
        return self.racine / "smooth" / str(annee) / f"{dalle}_hauteur_lissee.tif"

    # validate
    @property
    def rapport_md(self) -> Path:
        return self.racine / "validate" / "rapport.md"

    @property
    def rapport_json(self) -> Path:
        return self.racine / "validate" / "rapport.json"

    # export
    def cog(self, couche: str, annee: int, dalle: str, traitement: str) -> Path:
        nom = f"{dalle}_{couche}_{traitement}_{annee}.tif"
        return self.racine / "export" / "cog" / couche / str(annee) / nom

    @property
    def stac(self) -> Path:
        return self.racine / "export" / "stac"

    # zonal
    @property
    def zonal(self) -> Path:
        return self.racine / "zonal" / "statistiques.csv"
