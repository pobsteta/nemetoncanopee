# Mission 009 — modèle C : LightGBM avec descripteurs de voisinage

## Mission

**En une phrase :** Ajouter à la chaîne un modèle de hauteur LightGBM, entraîné sur CPU à partir de descripteurs par cellule de 10 m (bandes et indices S2 par scène et leurs statistiques saisonnières, voisinages 30 et 50 m, relief, essence BD Forêt), avec poids pour les hauteurs > 30 m, arrêt anticipé validé par blocs, et une incertitude (quantiles 10/90), pour l'option C de l'ADR 0004.

## Les trois questions

oui · oui (ADR 0004 et sa critique, plan 004) · oui (jeu d'essai pour les tests, échantillon 008 pour la mesure). **Temps de la main :** donner. **Degré :** le chef tranche (par délégation).

## L'Homme

`dev`, opus.

## Harnais

- **Peut :** `src/nemeton_canopee/models/gbm.py`, `src/nemeton_canopee/descripteurs/` (nouveau), `src/nemeton_canopee/models/__init__.py` (sélection du modèle par la conf), `src/nemeton_canopee/infer/` (incertitude), `conf/modele/gbm.yaml`, `pyproject.toml` (extra `[ml]` : lightgbm), `tests/test_modele_gbm.py`.
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** casser le modèle trivial ni les tests existants ; utiliser un pixel de test pour l'arrêt anticipé ou les hyperparamètres ; mettre un seuil en dur.

## Valeur provisoire

Hyperparamètres et poids > 30 m : provisoires, réglés sur les blocs d'apprentissage seulement.

**Dépend de :** aucune pour le code (tests sur le jeu d'essai). La mesure se fait en 011.

## Tests

Sur le jeu d'essai : la chaîne tourne avec `modele: gbm`, rejouable (graine), sans réseau ; une couche d'incertitude cohérente (p10 ≤ médiane ≤ p90) ; la MAE du modèle GBM sur les dalles de test est rapportée (aucun seuil exigé sur 4 dalles).

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Claude (orchestrateur, par délégation de Pascal : « Fais ce qu'il y a de mieux », journal du 22/11).

## Ma réponse d'abord

_Rempli par Pascal seul._
