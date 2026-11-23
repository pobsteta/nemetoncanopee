# Mission 007 — références sur le jeu d'essai et dans le rapport

## Mission

**En une phrase :** Extraire la hauteur 2022 de FORMS-T v1 sur les 4 dalles d'essai et ajouter au rapport de `validate` sa MAE et son biais sur les dalles de test, à côté du modèle du projet, pour que le tableau de référence du jalon 2 existe. (FORMSpoT reporté : licence CC-BY-NC à trancher par Pascal ; décision du 22/11.)

## Les trois questions

oui · oui après 006 · oui. **Temps de la main :** donner (le format du rapport est déjà fixé). **Degré :** le chef tranche (par délégation).

## L'Homme

`dev`, opus.

## Harnais

- **Peut :** `scripts/fabriquer_jeu_essai.py`, `conf/jeu_essai.yaml`, `tests/data/` (références ajoutées, PROVENANCE), `src/nemeton_canopee/validate/`, `src/nemeton_canopee/ingest/`, `conf/zones/jeu_essai.yaml`, `conf/chaine.yaml`, `tests/test_references.py`, `tests/test_jeu_essai.py` (ajouts seulement).
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** dépasser 20 Mo de jeu d'essai ; comparer sans ramener les références à la grille et à l'unité du projet (cm, 10 m, Lambert-93) ; inventer une donnée inaccessible.

## Valeur provisoire

Aucun rééchantillonnage : la hauteur FORMS-T à 10 m s'aligne sur la grille. Nodata FORMS-T 0 → 65535 du projet.

**Dépend de :** 006. **Ordre :** 006 → 007.

## Tests

`rapport.json` gagne `references: {forms_t_v1: {mae_m, biais_m, n}}` ; valeurs recalculées à la main dans le test ; chaîne toujours sans réseau ; test-command vert.

## Terrain

Pascal compare dans QGIS FORMS-T et la cible LiDAR sur une dalle de Levier (écart de moyenne signalé par 006 : 26,4 m contre 17,7 m).

## Qui veille, qui tranche

- **Relecteur :** `relecteur`. **Critère d'arrêt :** 3 allers-retours. **Qui tranche :** Claude (orchestrateur, par délégation de Pascal, journal du 22/11).

## Ma réponse d'abord

_Rempli par Pascal seul._
