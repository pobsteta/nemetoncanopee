# ADR 0001 — stack du squelette

- **Date :** 2026-11-22
- **Statut :** proposée
- **Proposée par :** Claude (orchestrateur)
- **Tranchée par :** Pascal

## La décision en une phrase

Le squelette (jalon 1) est en Python 3.11+, avec numpy, rasterio, pyproj, shapely,
geopandas, pystac et PyYAML pour seules dépendances obligatoires. PyTorch, Lightning,
LightGBM, dask et odc-stac sont des dépendances optionnelles (`[ml]`, `[cloud]`), ajoutées
au jalon qui en a besoin.

## Contexte

Le brief fixe la stack complète (PyTorch + Lightning, LightGBM, xarray + dask,
pystac-client, odc-stac, Hydra). Le contradicteur juge cette pile lourde pour un
squelette, et Pascal a retenu le 22/11 : PyTorch optionnel, YAML simple au lieu d'Hydra
jusqu'au jalon 3. Il faut fixer les dépendances maintenant, parce que la CI et le jeu
d'essai sans réseau en dépendent.

Options envisagées : (a) toute la stack du brief dès le jalon 1 ; (b) le minimum
ci-dessus, le reste en extras ; (c) R et terra pour tout (écarté : le brief retient
Python, et nemeton charge le paquet).

## Le crible FRANCE

| Lettre | Question | Réponse (une ligne) | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|---|
| **F**rugale | La plus simple qui tienne ? | Option (b) : sept bibliothèques libres, toutes stables | Le modèle trivial du jalon 1 se code en numpy | à trancher par Pascal |
| **R**esponsable | Qui fait quoi ? | Le `dev` code, le `testeur` tient le jeu sans réseau, Pascal tranche les ajouts de dépendance | Chaque nouvel extra repasse par une ADR | à trancher par Pascal |
| **A**nticiper | Si l'imprévu arrive ? | Les extras isolent PyTorch : le cœur reste installable sur un poste sans GPU | Deux chemins d'installation à documenter | à trancher par Pascal |
| **N**ovateur | Toutes les idées ? | (a), (b), (c) examinées ; Hydra réexaminé au jalon 3 | — | — |
| **C**oût | Coût complet ? | CI légère (pas de PyTorch à installer à chaque PR) | inconnu en temps de CI | à trancher par Pascal |
| **É**cologique | Réutilisation ? | Bibliothèques du monde géospatial Python ; GDAL sous rasterio | Dépendance à GDAL (binaires des roues rasterio) | à trancher par Pascal |

## Valeurs sacrifiées

Aucune valeur sacrifiée nommée à ce stade ; le report d'Hydra retarde une configuration
composable (au jalon 3, plus de surcharges à reprendre).

## Sources

- Brief, « Stack technique », et arbitrage n° 6 du 22/11.
- Critique du contradicteur, journal du 2026-11-22.

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
