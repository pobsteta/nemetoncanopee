# Mission 016 — corriger l'apprentissage de gbm_ortho

## Mission

**En une phrase :** Appliquer à gbm_ortho les corrections que prouve 015 (limite de tours relevée avec arrêt anticipé, et traitement du bloc ou du descripteur qui crée le biais d'altitude : exclusion, pondération ou descripteur, selon la preuve), dans une nouvelle conf, pour la remesure 017.

## Les trois questions

oui · oui après 015 · oui.

## L'Homme

`dev`, opus.

## Harnais

- **Peut :** `conf/modele/gbm_ortho_v2.yaml`, `src/nemeton_canopee/models/gbm.py`, `src/nemeton_canopee/descripteurs/` (si un descripteur est en cause), `conf/zones/echantillon_jura.yaml` et `/data/echantillon_jura/decoupage.yaml` (seulement la liste d'apprentissage, si 015 prouve qu'un bloc doit sortir), `tests/test_modele_gbm.py` (ajouts).
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** toucher aux blocs de test ; changer gbm ni gbm_ortho (les mesures 011 et 014 restent reproductibles).

**Dépend de :** 015.

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Pascal.

## Ma réponse d'abord

_Rempli par Pascal seul._
