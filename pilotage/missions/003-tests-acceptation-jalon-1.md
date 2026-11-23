# Mission 003 — tests d'acceptation du jalon 1

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les tests qui vérifient les huit critères du jalon 1 de `docs/spec.md`, avant le code, pour que « terminé » ait un sens vérifiable.

**Redite par l'agent :** « J'écris, avant le code de 004 et sans lire son implémentation, les tests qui vérifient les critères 1 à 7 du jalon 1 d'après le plan validé, exacts et collectables, rouges tant que 004 n'existe pas. » (testeur, 22/11)

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui : critères de la spec, référentiels (001) | |
| A-t-il les moyens ? | oui une fois le jeu d'essai (002) fusionné | dépend de 002 |

**Temps de la main :** donner.

**Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul, avant de lire le travail de l'agent. L'orchestrateur ne le remplit pas._

## L'Homme

- **Agent :** `testeur`
- **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** le code du pipeline (004).

## Harnais

- **Peut (périmètre) :** `tests/test_*.py` (sauf `tests/test_jeu_essai.py` et `tests/data/`), `tests/conftest.py` ; dans `tests/data/decoupage.yaml`, seulement retirer la mention « PROVISOIRE » (gel décidé le 22/11).
- **Câblé (ne peut pas) :** pas de commit ni de push sur `main`, pas de push forcé, pas de « terminé » sans tests verts (`.claude/test-command`), `pilotage/journal.md` en ajout seul (hooks du plugin `imperatrice`).
- **Ne doit pas (écrit) :** affaiblir un critère de la spec ; marquer un test « skip » pour obtenir du vert.
- **Sources autorisées :** `pilotage/missions/004-plan.md` (interfaces validées), `docs/spec.md` §4, `docs/referentiels.md`, `tests/data/`, ADR 0001.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu (critère → test).

## Valeur provisoire (chiffre, réglage)

aucune (les valeurs viennent de la spec validée).

## Dépend de / rouge attendu jusqu'à

- **Dépend de :** 002 et le plan validé de 004. · **Ordre de fusion :** 003 et 004 groupées (même branche, un commit chacune). · **PR en brouillon jusqu'à :** 004 verte. · **CI rouge attendue :** tous les tests d'acceptation, rouges tant que 004 n'est pas fusionnée (« rouge justifiée »).

## Remarques de relecture (aller-retour 1/3, 22/11)

1. `validate_all` compte 4 items : `== 4`, pas `>= 5` (bloquant).
2. Retirer l'assertion 7 < MAE < 8 ; vérifier les clés exactes de `rapport.json` (décision 8).
3. Catalogue synthétique de zonal (a) : géométrie et bbox en WGS84, Lambert-93 dans `proj:*`.
4. Refus de `train` et de `prepare`/`ingest` : code 3 et motif dans le message (décision 9).
5. Remarque : bloquer aussi GDAL (variables GDAL_HTTP_*/proxy mort).

## Tests

- **Comment saura-t-on que c'est juste :** un test par critère (1 à 8), assertions exactes ; la valeur zonale du critère 5 est calculée à la main et écrite dans le test ; liste de contrôle du testeur passée.

## Terrain

- **Échantillon que Pascal vérifiera :** la statistique zonale d'essai recalculée par lui dans QGIS.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Pascal.
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Point de suivi :** à chaque rendu, dans `/imperatrice:boucle`.
- **Qui tranche :** Pascal.

## Comment saura-t-on que ça marche ?

Les tests sont rouges sur `main`, verts sur la branche de 004, et rien d'autre ne change.
