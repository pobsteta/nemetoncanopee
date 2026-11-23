# Mission 013 — LightGBM : descripteurs ortho et peuplements bas

## Mission

**En une phrase :** Brancher les descripteurs de l'ortho (012) dans le modèle LightGBM, en option par la conf, et ajouter ce qui aide à ne plus surestimer les peuplements bas et les trouées (indices de végétation clairsemée, contraste avec le voisinage, éventuellement pondération des hauteurs < 10 m), pour réduire la cause n° 1 de la mesure 011.

## Les trois questions

oui · oui (rapport `docs/mesures/2026-11-adr-0004.md`, ADR 0004) · oui après 012. **Temps de la main :** donner. **Degré :** le chef tranche.

## L'Homme

`dev`, opus.

## Harnais

- **Peut :** `src/nemeton_canopee/descripteurs/`, `src/nemeton_canopee/models/gbm.py`, `src/nemeton_canopee/conf.py` (lecture des fichiers ortho de la zone), `conf/modele/gbm.yaml` (et une variante `gbm_ortho.yaml`), `tests/test_modele_gbm.py` (ajouts).
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** régler quoi que ce soit sur les blocs de test ; casser le gbm actuel (la variante sans ortho reste disponible).

**Dépend de :** 012.

## Tests

Sur le jeu d'essai : chaîne avec `gbm_ortho`, rejouable, sans réseau ; tests des nouveaux descripteurs vérifiés à la main sur une cellule.

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Pascal.

## Ma réponse d'abord

_Rempli par Pascal seul._
