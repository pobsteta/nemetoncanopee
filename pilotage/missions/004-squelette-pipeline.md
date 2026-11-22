# Mission 004 — squelette du pipeline

## Mission

**En une phrase (quoi, et pourquoi) :** Faire tourner les neuf commandes `canopee` de bout en bout sur le jeu d'essai avec un modèle trivial, pour prouver la chaîne (fichiers, grille, COG, STAC, rapport, zonal) avant tout vrai modèle.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui : brief (architecture), spec, ADR 0001, référentiels (001) | |
| A-t-il les moyens ? | oui : jeu d'essai (002), tests (003) | |

**Temps de la main :** **prendre** — la mission fixe l'arborescence, le format de `conf/` et l'organisation des fichiers sur disque, qui engagent la durée. L'agent rend d'abord un plan ; Pascal le valide avant tout code.

**Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul, avant de lire le travail de l'agent. L'orchestrateur ne le remplit pas._

## L'Homme

- **Agent :** `dev`
- **Modèle :** opus (architecture)
- **Ce qui ne lui est pas demandé :** un vrai modèle de hauteur (jalon 3) ; volume et biomasse (jalon 4).

## Harnais

- **Peut (périmètre) :** `src/nemeton_canopee/`, `conf/`, `pyproject.toml`, `README.md` (section commandes).
- **Câblé (ne peut pas) :** pas de commit ni de push sur `main`, pas de push forcé, pas de « terminé » sans tests verts (`.claude/test-command`), `pilotage/journal.md` en ajout seul (hooks du plugin `imperatrice`).
- **Ne doit pas (écrit) :** écrire un chemin ou un seuil en dur ; toucher `tests/` (003) ; accéder au réseau dans les tests.
- **Sources autorisées :** `docs/brief.md`, `docs/spec.md`, `docs/adr/0001-stack-du-squelette.md`, `docs/referentiels.md`, `tests/`.

## Journal

- **Ce que l'agent inscrit :** une ligne pour le plan, une par rendu.

## Valeur provisoire (chiffre, réglage)

- **Valeur provisoire :** modèle trivial (hauteur = médiane de la cible d'apprentissage) ; seuil de rupture de `smooth` mis en configuration, marqué « provisoire ».
- **Mesurée par :** calage sur des coupes connues, jalon 5. · **Gel :** jalon 5.

## Dépend de / rouge attendu jusqu'à

- **Dépend de :** 001, 002, 003 (branche partie de 003). · **Ordre de fusion :** 003 et 004 groupées. · **PR en brouillon jusqu'à :** plan validé par Pascal. · **CI rouge attendue :** aucune à la sortie du brouillon.

## Tests

- **Comment saura-t-on que c'est juste :** les tests de 003 passent, `.claude/test-command` vert, chaîne en moins de 10 minutes.

## Terrain

- **Échantillon que Pascal vérifiera :** le COG de hauteur ouvert dans QGIS sur l'ortho, et la statistique d'une parcelle.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Pascal.
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Point de suivi :** à chaque rendu, dans `/imperatrice:boucle`.
- **Qui tranche :** Pascal.

## Comment saura-t-on que ça marche ?

`canopee` produit un COG, un catalogue STAC et un rapport sur les 4 dalles, réseau coupé.
