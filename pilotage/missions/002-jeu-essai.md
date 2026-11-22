# Mission 002 — jeu d'essai de 4 dalles

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire le script versionné qui fabrique, une fois et avec le réseau, le jeu d'essai de 4 dalles de 1 km (moins de 20 Mo, provenance et licence par fichier), pour que toute la chaîne se teste ensuite sans réseau.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui une fois 001 rendue (grille, nomenclature, dates de vol) | dépend de 001 |
| A-t-il les moyens ? | oui : 4 dalles retenues le 22/11 (0901-6665, 0902-6665, 0939-6654, 0939-6655 ; `docs/referentiels.md`), accès IGN et Earth Search vérifiés | |

**Temps de la main :** donner.

**Degré de la main :** le chef tranche (choix des dalles).

## Ma réponse d'abord

_Rempli par Pascal seul, avant de lire le travail de l'agent. L'orchestrateur ne le remplit pas._

## L'Homme

- **Agent :** `dev`
- **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** le pipeline ; les tests d'acceptation (003).

## Harnais

- **Peut (périmètre) :** `scripts/fabriquer_jeu_essai.py`, `tests/test_jeu_essai.py`, la liste `dependencies` de `pyproject.toml` (dépendances de l'ADR 0001, nécessaires à la CI), `tests/data/` (données, `PROVENANCE`, `decoupage.yaml` : 2 dalles d'apprentissage, 2 de test, blocs distincts).
- **Câblé (ne peut pas) :** pas de commit ni de push sur `main`, pas de push forcé, pas de « terminé » sans tests verts (`.claude/test-command`), `pilotage/journal.md` en ajout seul (hooks du plugin `imperatrice`).
- **Ne doit pas (écrit) :** dépasser 20 Mo ; versionner un fichier sans provenance ; écrire dans `/data/`.
- **Sources autorisées :** `docs/referentiels.md` (001) ; IGN géoplateforme (MNH, MNT LiDAR HD, BD ORTHO, BD Forêt V2) ; STAC Copernicus Data Space ou Earth Search (Sentinel-2 L2A, Sentinel-1 GRD).

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu (dalles, scènes retenues, taille totale).

## Valeur provisoire (chiffre, réglage)

- **Valeur provisoire :** budget de 20 Mo (spec) ; réduction du MNH à 2,5 m dans le jeu si le budget l'exige, marquée « provisoire ».
- **Mesurée par :** la taille réelle, mesurée en première tâche. · **Gel :** avant la fusion de 003.

## Dépend de / rouge attendu jusqu'à

- **Dépend de :** 001. · **Ordre de fusion :** 001 → 002. · **PR en brouillon jusqu'à :** fusion de 001. · **CI rouge attendue :** aucune.

## Tests

- **Comment saura-t-on que c'est juste :** un test vérifie la taille totale, la présence de `PROVENANCE` pour chaque fichier, l'EPSG:2154 et l'alignement des dalles sur la grille de 1 km.

## Terrain

- **Échantillon que Pascal vérifiera :** les 4 dalles ouvertes dans QGIS sur l'ortho : sont-ce bien des forêts qu'il connaît ?

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Pascal.
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Point de suivi :** à chaque rendu, dans `/imperatrice:boucle`.
- **Qui tranche :** Pascal.

## Comment saura-t-on que ça marche ?

`pytest` tourne réseau coupé et trouve toutes ses données.
