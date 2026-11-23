# Mission 011 — mesure côte à côte (ADR 0004)

## Mission

**En une phrase :** Entraîner C (009) et A (010) sur les blocs d'apprentissage de l'échantillon du Jura (008) et comparer sur les blocs de test, avec FORMS-T v1 et le modèle trivial sur les mêmes cellules, les critères de la spec (MAE au peuplement avec intervalle par bootstrap, MAE au pixel, MAE et biais par classe de hauteur, temps CPU), pour que l'ADR 0004 se tranche sur une mesure.

## Les trois questions

oui · oui (spec, critères du 22/11) · oui après 008, 009, 010.

## L'Homme

`analyste`, opus (calculs par l'orchestrateur ou un `dev` si un script est nécessaire : `scripts/mesurer_modeles.py`).

## Harnais

- **Peut :** `docs/mesures/2026-11-adr-0004.md` (rapport), `scripts/mesurer_modeles.py`.
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** régler quoi que ce soit sur les blocs de test ; conclure sans intervalle.

**Dépend de :** 008, 009, 010.

## Terrain

Pascal regarde dans QGIS les cartes des deux modèles et de FORMS-T sur la forêt de la Joux (grands sapins).

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Claude (orchestrateur, par délégation de Pascal : « Fais ce qu'il y a de mieux », journal du 22/11).

## Ma réponse d'abord

_Rempli par Pascal seul._
