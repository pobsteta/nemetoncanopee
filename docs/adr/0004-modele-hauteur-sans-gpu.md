# ADR 0004 — modèle de hauteur sans GPU

- **Date :** 2026-11-22
- **Statut :** proposée — à critiquer par le `contradicteur`, puis à trancher par Pascal
- **Proposée par :** Claude (orchestrateur)
- **Tranchée par :** Pascal

## La décision en une phrase

À trancher par Pascal parmi les options ci-dessous. Proposition de l'orchestrateur :
l'option B (gradient boosting par pixel sur des descripteurs Sentinel annuels et le
relief), entraînée sur CPU, comme modèle du jalon 3 ; le U-Net reste une variante à
essayer si un GPU devient disponible.

## Contexte

Le brief prévoit un U-Net (PyTorch) entraîné sur le Jura, supervisé par le MNH LiDAR HD.
Pascal a précisé le 22/11 : **pas de GPU**. La cible à battre est mesurée : FORMS-T v1,
MAE 3,46 m sur les dalles de test du jeu d'essai (journal, mission 007). Le Jura couvre
environ 5 000 km², dont environ la moitié de forêt (ordre de grandeur, à mesurer).

| Option | Principe | Calcul | Ce qu'on sait |
|---|---|---|---|
| A. U-Net sur CPU | Le modèle du brief, petit (peu de canaux), patchs 10 m | lent (jours à semaines pour le Jura, non mesuré) | référence de l'état de l'art (FORMS-T) |
| B. Gradient boosting par pixel | LightGBM sur des descripteurs annuels par cellule de 10 m : médianes et percentiles saisonniers des bandes S2 et indices, S1 si accessible, altitude, pente, exposition, essence BD Forêt | CPU, minutes à heures | déjà dans la stack (LightGBM, ADR 0001 extra) ; perd le contexte spatial du U-Net |
| C. B + contexte spatial | B, avec des descripteurs de voisinage (moyennes et écarts-types sur 30 et 50 m, textures) | CPU, heures | rattrape une partie du contexte spatial |
| D. GPU loué (cloud) | A sur une machine louée | coût récurrent, dépendance à un tiers | touche l'extérieur et l'argent : décision de Pascal seul |

## Le crible FRANCE (option C, proposée)

| Lettre | Question | Réponse (une ligne) | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|---|
| **F**rugale | La plus simple qui tienne ? | CPU, une bibliothèque déjà prévue, pas de PyTorch | peut-être une MAE moins bonne qu'un U-Net | à trancher par Pascal |
| **R**esponsable | Qui fait quoi ? | `dev` (descripteurs, modèle), `testeur`, `analyste` (erreurs par classe) ; Pascal juge le gain | — | à trancher par Pascal |
| **A**nticiper | Si l'imprévu arrive ? | Si C ne bat pas 3,46 m : U-Net réduit sur CPU (A) ou GPU loué (D), à décider alors | un jalon de plus | à trancher par Pascal |
| **N**ovateur | Toutes les idées ? | A à D examinées ; THREASURE-Net écarté sans GPU | — | — |
| **C**oût | Coût complet ? | aucun matériel ; temps de calcul CPU inconnu (à mesurer en première tâche) | inconnu | à trancher par Pascal |
| **É**cologique | Réutilisation ? | descripteurs réutilisables pour le volume (jalon 4) ; énergie bien moindre qu'un entraînement GPU | — | à trancher par Pascal |

## Valeurs sacrifiées

Proposition : on sacrifie une part possible de justesse (contexte spatial d'un U-Net)
à la frugalité et à la faisabilité sans GPU. À confirmer par Pascal après mesure.

## Valeur provisoire

Temps de calcul et MAE de l'option C : inconnus, mesurés en première tâche du jalon 3 sur
une partie du Jura, avant de geler le choix.

## Sources

- Brief, « Modèle de hauteur » ; arbitrage de Pascal du 22/11 (pas de GPU).
- Journal, mission 007 : FORMS-T v1, MAE 3,46 m sur le jeu d'essai.

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
