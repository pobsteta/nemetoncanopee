# Kanban de nemetoncanopee

> Cinq colonnes (fiche n° 8). Chaque carte porte l'Homme (qui), la Mission (quoi, quand,
> combien) et les Moyens (comment, où, avec qui), et renvoie à sa fiche dans
> `pilotage/missions/`. Elle note aussi depuis quel cycle de `/boucle` elle est dans sa
> colonne ; on change ce numéro chaque fois qu'elle change de colonne.
> **Une carte qui ne bouge pas est souvent la mauvaise nouvelle à dire tout de suite.**

**Dernier cycle :** 0 _(augmenté de 1 à la fin de chaque `/boucle`, même quand elle n'a
rien lancé. Une carte est immobile quand dernier cycle − N ≥ 2.)_

_Modèle de carte :_

```
- [NNN-titre](missions/NNN-titre.md) · depuis le cycle N
  - Homme : qui
  - Mission : quoi, quand, combien
  - Moyens : comment, où, avec qui
```

## Bac à sable

- [001-referentiels-jalon-1](missions/001-referentiels-jalon-1.md) · depuis le cycle 0
  - Homme : `acquereur`
  - Mission : référentiels sourcés du jalon 1, premier cycle
  - Moyens : web (IGN, data.gouv.fr, stac-extensions), liste de contrôle
- [002-jeu-essai](missions/002-jeu-essai.md) · depuis le cycle 0
  - Homme : `dev`
  - Mission : script et jeu d'essai de 4 dalles < 20 Mo, premier cycle
  - Moyens : 001, géoplateforme IGN, STAC Sentinel ; dalles à choisir par Pascal
- [003-tests-acceptation-jalon-1](missions/003-tests-acceptation-jalon-1.md) · depuis le cycle 0
  - Homme : `testeur`
  - Mission : un test par critère du jalon 1, deuxième cycle
  - Moyens : spec, 001, 002
- [004-squelette-pipeline](missions/004-squelette-pipeline.md) · depuis le cycle 0
  - Homme : `dev` (opus), plan d'abord
  - Mission : neuf commandes de bout en bout, modèle trivial, deuxième cycle
  - Moyens : brief, spec, ADR 0001, 001, 002, 003

## Validé

## Planifié

## Terminé

## Abandonné

_Avec la raison, en une ligne._

## Livraisons

_Une ligne par cycle, ajoutée sous la précédente à la fin de chaque `/boucle`, et une
par `/bilan` : la livraison que Pascal a retenue, pour qui, et ce qu'elle apporte de plus
que la précédente du même rythme. On lance petit (fiche n° 12) : la plus petite version
qui rend déjà un service réel, un MVP, essayée tout de suite sur le terrain. Un cycle sans livraison neuve livre sa mauvaise
nouvelle, car
« une mauvaise nouvelle est une livraison sur laquelle on apprend » (Pascal) : on
l'inscrit avec ce qu'elle nous apprend._

```
- cycle N · livraison · pour qui · ce qu'elle apporte de plus que la précédente
- cycle N · mauvaise nouvelle : … · pour qui · ce qu'elle nous apprend
- bilan du AAAA-MM-JJ · livraison · pour qui · ce qu'elle apporte de plus que la précédente
- bilan du AAAA-MM-JJ · mauvaise nouvelle : … · pour qui · ce qu'elle nous apprend
```
