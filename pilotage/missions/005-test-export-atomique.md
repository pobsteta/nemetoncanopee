# Mission 005 — test d'atomicité de l'export

## Mission

**En une phrase :** Écrire les tests qui vérifient que `export --annees` conserve les COG des autres années et qu'un export interrompu ne laisse ni catalogue incohérent ni dossier partiel, pour fermer la remarque du relecteur sur 004.

## Les trois questions

oui · oui (comportement décrit dans 004-plan.md et le journal) · oui. **Temps de la main :** donner. **Degré :** le chef tranche (par délégation).

## L'Homme

`testeur`, sonnet.

## Harnais

- **Peut :** `tests/test_export_atomique.py`.
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** modifier `src/`, `conf/`, les autres tests.

## Valeur provisoire

aucune. **Dépend de :** aucune (004 fusionnée dans la branche).

## Tests

Les tests passent sur le code actuel ; un test qui échoue révèle un défaut, signalé, pas contourné.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`. **Critère d'arrêt :** 3 allers-retours. **Qui tranche :** Claude (orchestrateur, par délégation de Pascal, journal du 22/11).

## Ma réponse d'abord

_Rempli par Pascal seul._
