# Mission 001 — référentiels du jalon 1

## Mission

**En une phrase (quoi, et pourquoi) :** Réunir, sourcés, les référentiels dont le squelette a besoin (grille et nomenclature des dalles LiDAR HD, lecture de la date de vol, schémas des extensions STAC, mentions de licence) et proposer 4 dalles de 1 km pour le jeu d'essai, pour que personne n'invente un code ou un format.

**Redite par l'agent :** « Réunir, avec leur source et leur date de consultation, les référentiels du jalon 1 et proposer 4 dalles d'essai en BFC, pour que les missions 002 à 004 n'inventent ni code ni format. » (acquereur, 22/11)

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui : sources nommées ci-dessous, liste de contrôle de l'acquéreur | |
| A-t-il les moyens ? | oui : accès web (IGN géoplateforme, data.gouv.fr, stac-extensions) vérifié le 22/11 | |

**Temps de la main :** donner — travail documentaire, relu avant usage.

**Degré de la main :** le chef tranche (les conventions engagent la justesse des données).

## Ma réponse d'abord

_Rempli par Pascal seul, avant de lire le travail de l'agent. L'orchestrateur ne le remplit pas._

## L'Homme

- **Agent :** `acquereur`
- **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** écrire du code ; choisir la zone pilote (il propose seulement 4 dalles d'essai, en forêt, en Bourgogne-Franche-Comté, avec MNH LiDAR HD publié : deux paires de dalles voisines, les deux paires à plus de 10 km l'une de l'autre ; l'orchestrateur tranche par délégation) ; trancher la définition du volume (ADR 0002).

## Harnais

- **Peut (périmètre) :** `docs/referentiels.md` ; `conf/stac-schemas/` (schémas JSON des extensions `projection`, `raster`, `file`, `processing`, à la version citée).
- **Câblé (ne peut pas) :** pas de commit ni de push sur `main`, pas de push forcé, pas de « terminé » sans tests verts (`.claude/test-command`), `pilotage/journal.md` en ajout seul (hooks du plugin `imperatrice`).
- **Ne doit pas (écrit) :** inventer une nomenclature ; citer une valeur sans source, page et date de consultation.
- **Sources autorisées :** IGN (géoplateforme, fiches LiDAR HD MNH/MNT, BD Forêt V2), data.gouv.fr, carte TerraLab des dates de vol (contrôle seulement), stac-extensions.github.io, Règlement délégué UE 1159/2013 (mention Copernicus), Licence Ouverte 2.0. `docs/brief.md`, `docs/spec.md`, `CLAUDE.md`.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu (sources consultées, ce qui manque).

## Valeur provisoire (chiffre, réglage)

- **Valeur provisoire :** nodata = 65535 (spec, validée) ; aucune autre.
- **Mesurée par :** — · **Gel :** —

## Dépend de / rouge attendu jusqu'à

aucune.

## Tests

- **Comment saura-t-on que c'est juste :** chaque entrée a source, emplacement, version, date ; les schémas embarqués se chargent avec `jsonschema` ; liste de contrôle passée.

## Terrain

- **Échantillon que Pascal vérifiera :** le nom d'une dalle LiDAR HD qu'il connaît, et sa date de vol, comparés au référentiel.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Pascal.
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Point de suivi :** à chaque rendu, dans `/imperatrice:boucle`.
- **Qui tranche :** Pascal.

## Comment saura-t-on que ça marche ?

Les missions 002 à 004 n'ont rien à chercher ailleurs que dans `docs/referentiels.md`.
