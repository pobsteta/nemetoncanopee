# Mission 015 — diagnostic sur les seuls blocs d'apprentissage

## Mission

**En une phrase :** Trouver, par validation croisée « un bloc d'apprentissage laissé de côté » sur les 6 blocs d'apprentissage (jamais les blocs de test), quel bloc ajouté en 012 pousse gbm_ortho à surestimer les forêts d'altitude de 10–20 m, et à quel nombre de tours l'apprentissage converge réellement, pour que 016 corrige sur une preuve et non sur le test.

## Les trois questions

oui · oui (mesure 014, script de mesure, échantillon) · oui (4 CPU ; ~45 min par entraînement : réduire par sous-échantillonnage documenté si besoin).

## L'Homme

`analyste`, opus (calculs par script).

## Harnais

- **Peut :** `scripts/diagnostiquer_apprentissage.py`, `tests/test_diagnostiquer_apprentissage.py`, `docs/mesures/2026-11-diagnostic-apprentissage.md` ; calculs dans `/data/mesure_015/`.
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** lire une prédiction ou une cible des blocs de test (chaux_b, joux, altitude_b).

## Tests

Le script refuse (code 3) toute dalle de test ; testé sur des données synthétiques.

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Pascal.

## Ma réponse d'abord

_Rempli par Pascal seul._
