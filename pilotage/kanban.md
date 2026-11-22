# Kanban de nemetoncanopee

> Cinq colonnes (fiche n° 8). Chaque carte porte l'Homme (qui), la Mission (quoi, quand,
> combien) et les Moyens (comment, où, avec qui), et renvoie à sa fiche dans
> `pilotage/missions/`. Elle note aussi depuis quel cycle de `/boucle` elle est dans sa
> colonne ; on change ce numéro chaque fois qu'elle change de colonne.
> **Une carte qui ne bouge pas est souvent la mauvaise nouvelle à dire tout de suite.**

**Dernier cycle :** 7 _(augmenté de 1 à la fin de chaque `/boucle`, même quand elle n'a
rien lancé. Une carte est immobile quand dernier cycle − N ≥ 2.)_

_Modèle de carte :_

```
- [NNN-titre](missions/NNN-titre.md) · depuis le cycle N
  - Homme : qui
  - Mission : quoi, quand, combien
  - Moyens : comment, où, avec qui
```

## Bac à sable

## Validé

## Planifié

## Terminé
- [012-ortho-et-blocs](missions/012-ortho-et-blocs.md) · depuis le cycle 7
  - Homme : `dev` · Mission : ortho 10 m et trois blocs · Moyens : réseau, /data/
- [013-gbm-trouees](missions/013-gbm-trouees.md) · depuis le cycle 7
  - Homme : `dev` (opus) · Mission : gbm_ortho · Moyens : 012
- [014-mesure-gbm-ortho](missions/014-mesure-gbm-ortho.md) · depuis le cycle 7
  - Homme : `analyste` · Mission : nouvelle mesure · Moyens : 012, 013
- [008-echantillon-jura](missions/008-echantillon-jura.md) · depuis le cycle 5
  - Homme : `dev` · Mission : échantillon du Jura, 96 dalles · Moyens : réseau, /data/
- [009-modele-gbm](missions/009-modele-gbm.md) · depuis le cycle 5
  - Homme : `dev` (opus) · Mission : modèle LightGBM · Moyens : jeu d'essai
- [010-modele-unet-cpu](missions/010-modele-unet-cpu.md) · depuis le cycle 5
  - Homme : `dev` (opus) · Mission : petit U-Net CPU · Moyens : jeu d'essai
- [011-mesure-adr-0004](missions/011-mesure-adr-0004.md) · depuis le cycle 5
  - Homme : `analyste` · Mission : mesure côte à côte · Moyens : 008-010
- [005-test-export-atomique](missions/005-test-export-atomique.md) · depuis le cycle 3
  - Homme : `testeur` · Mission : atomicité de l'export · Moyens : 004
- [006-references-acces](missions/006-references-acces.md) · depuis le cycle 3
  - Homme : `acquereur` · Mission : accès FORMS-T v1 et FORMSpoT · Moyens : web
- [007-references-evaluation](missions/007-references-evaluation.md) · depuis le cycle 3
  - Homme : `dev` (opus) · Mission : FORMS-T v1 dans le jeu et le rapport · Moyens : 006

- [001-referentiels-jalon-1](missions/001-referentiels-jalon-1.md) · depuis le cycle 2
  - Homme : `acquereur`
  - Mission : référentiels sourcés du jalon 1, premier cycle
  - Moyens : web (IGN, data.gouv.fr, stac-extensions), liste de contrôle
- [002-jeu-essai](missions/002-jeu-essai.md) · depuis le cycle 2
  - Homme : `dev`
  - Mission : script et jeu d'essai de 4 dalles < 20 Mo, premier cycle
  - Moyens : 001, géoplateforme IGN, STAC Sentinel ; dalles à choisir par Pascal
- [003-tests-acceptation-jalon-1](missions/003-tests-acceptation-jalon-1.md) · depuis le cycle 2
  - Homme : `testeur`
  - Mission : un test par critère du jalon 1, deuxième cycle
  - Moyens : spec, 001, 002
- [004-squelette-pipeline](missions/004-squelette-pipeline.md) · depuis le cycle 2
  - Homme : `dev` (opus), plan d'abord
  - Mission : neuf commandes de bout en bout, modèle trivial, deuxième cycle
  - Moyens : brief, spec, ADR 0001, 001, 002, 003


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

- cycle 2 · livraison : jalon 1, squelette de bout en bout (9 commandes canopee, COG de hauteur, catalogue STAC, rapport, statistiques zonales) sur 4 dalles de Chaux et Levier, sans réseau, en ~2 s · pour Pascal, puis nemeton · ce qu'elle apporte : la première chaîne qui produit une carte et une statistique par parcelle (la précédente : aucune) ; modèle trivial, MAE 7,53 m, à battre au jalon 3
- cycle 3 · livraison : tableau de référence du jalon 2 sur le jeu d'essai (FORMS-T v1 : MAE 3,46 m, biais −0,46 m ; modèle trivial : 7,53 m, +0,98 m ; mêmes cellules) et export atomique testé · pour Pascal · ce qu'elle apporte : la cible chiffrée à battre au jalon 3, mesurée sur nos dalles et non plus reprise de l'article
- cycle 5 · mauvaise nouvelle : aucun modèle sans GPU ne bat FORMS-T v1 au peuplement sur le Jura (gbm 2,05 m contre 1,89 m à l'hectare, égalité statistique ; 2,23 contre 1,67 par polygone) · pour Pascal · ce qu'elle nous apprend : gbm est au niveau à l'hectare et meilleur au-dessus de 30 m ; 67 % de son retard vient des peuplements bas et trouées surestimés, une cause précise à traiter ; le U-Net CPU n'est pas la voie
- cycle 7 · mauvaise nouvelle : gbm_ortho ne bat pas FORMS-T v1 au peuplement (par polygone 1,85 contre 1,67 m, égalité ; par hectare 2,11 contre 1,89 m, perd de justesse) · pour Pascal · ce qu'elle nous apprend : l'ortho est le bon levier (−0,29 m par polygone, −33 % de surestimation des peuplements bas sur Joux et Chaux), les blocs ajoutés ont introduit un biais sur l'altitude, l'apprentissage bute sur tours_max ; gbm_ortho bat FORMS-T au-dessus de 30 m et sur Chaux
