"""Provenance des seuils « trouées » de conf/modele/gbm_ortho.yaml (mission 013).

Sur 16 dalles d'**apprentissage** de l'échantillon du Jura (jamais une dalle de test : le
script le refuse), cellules de forêt à cible valide et NDVI médian défini, il affiche par
classe de hauteur cible :
- la médiane du NDVI, de B08 (PIR), B11 et B12 (SWIR), médianes entre scènes de l'année ;
- la part des cellules dont le NDVI médian est sous le seuil (0,75 par défaut).

Sans réseau. Entrée : une conf de chaîne sur l'échantillon dont le dossier de travail contient
les sorties de `prepare` et `targets` (par exemple /data/mesure_014/conf/chaine_gbm_ortho.yaml,
ou toute conf de conf/chaine_echantillon_jura.yaml après `canopee ingest prepare targets`).

    python scripts/justifier_trouees.py --conf /data/mesure_014/conf/chaine_gbm_ortho.yaml
"""

from __future__ import annotations

import argparse

import numpy as np
import rasterio

from nemeton_canopee import decoupage, descripteurs
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import charger
from nemeton_canopee.ingest import lire_manifeste

# Une dalle sur trois des 48 dalles d'apprentissage des blocs chaux_a, sapiniere_a et
# altitude_a (ordre du manifeste), celles lues le 22/11/2026 pour régler gbm_ortho.yaml.
DALLES = [
    "0894-6665", "0894-6668", "0895-6667", "0896-6666", "0897-6665", "0897-6668",
    "0916-6611", "0917-6610", "0918-6609", "0918-6612", "0919-6611",
    "0938-6634", "0939-6633", "0939-6636", "0940-6635", "0941-6634",
]  # fmt: skip
CLASSES_M = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 30), (30, 60)]
VARIABLES = ["NDVI", "B08", "B11", "B12"]


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--conf", required=True)
    a.add_argument("--seuil", type=float, default=0.75)
    args = a.parse_args()
    conf = charger(args.conf)
    ch = Chemins(conf.travail)
    dec = decoupage.lire(conf)
    interdites = sorted(set(DALLES) - set(dec.apprentissage))
    if interdites:
        raise SystemExit(f"dalles hors apprentissage refusées : {interdites}")
    params = conf.modele["descripteurs"]
    valeurs, hauteurs = [], []
    for d in lire_manifeste(ch, DALLES):
        scenes = []
        for chemin in ch.scenes_preparees(d.annee, d.id):
            with rasterio.open(chemin) as src:
                pile, noms = src.read(), list(src.descriptions)
            scenes.append(descripteurs.variables_scene(pile, noms, params))
        stats = descripteurs.statistiques_entre_scenes(scenes, [50])
        with rasterio.open(ch.cible(d.annee, d.id)) as src:
            cible = src.read(1)
        with rasterio.open(ch.foret(d.id)) as src:
            foret = src.read(1)
        ok = (cible != conf.nodata) & (foret == 1) & np.isfinite(stats["NDVI_p50"])
        valeurs.append(np.stack([stats[f"{v}_p50"][ok] for v in VARIABLES], axis=1))
        hauteurs.append(cible[ok] / 100.0)
    v, h = np.concatenate(valeurs), np.concatenate(hauteurs)
    print(f"{len(DALLES)} dalles d'apprentissage, {len(h)} cellules")
    print("classe (m)\tpart\t" + "\t".join(f"{x} méd." for x in VARIABLES) + "\tNDVI < seuil")
    for bas, haut in CLASSES_M:
        m = (h >= bas) & (h < haut)
        med = np.median(v[m], axis=0)
        sous = (v[m, 0] < args.seuil).mean()
        print(
            f"{bas}-{haut}\t{m.mean():.3f}\t"
            + "\t".join(f"{x:.3f}" for x in med)
            + f"\t{100 * sous:.1f} %"
        )


if __name__ == "__main__":
    main()
