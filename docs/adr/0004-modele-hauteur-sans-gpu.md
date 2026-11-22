# ADR 0004 — modèle de hauteur sans GPU

- **Date :** 2026-11-22
- **Statut :** proposée — à critiquer par le `contradicteur`, puis à trancher par Pascal
- **Proposée par :** Claude (orchestrateur)
- **Tranchée par :** Pascal

## La décision en une phrase

À trancher par Pascal parmi les options ci-dessous. Proposition de l'orchestrateur, revue après la critique du `contradicteur`
(journal du 22/11) : **mesurer d'abord, choisir ensuite**. En première tâche du jalon 3,
sur les mêmes blocs d'une partie du Jura, entraîner l'option C (gradient boosting avec
descripteurs de voisinage) et une époque d'un petit U-Net sur CPU (A) ; comparer MAE
globale, MAE par classe de hauteur (dont > 30 m) et temps de calcul ; garder celle qui bat
FORMS-T v1 (3,46 m, avec intervalle par bootstrap) ; si aucune ne le bat, Pascal décide
de la suite (D, GPU loué, ou cible revue).

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

## Critique du contradicteur (22/11), à prendre en compte

1. La littérature ne donne pas l'avantage au boosting par pixel (Morin et al., MAE 4,3 m ;
   FORMS U-Net 2,94 m, ESSD 2023 ; Potapov et al. 2021, 6,36 m) ; mais ces travaux sont
   supervisés par GEDI, la cible LiDAR HD laisse une chance. D'où la mesure côte à côte.
2. Le coût CPU de A n'est pas mesuré : il l'est en première tâche (~6 000 patchs de 64×64).
3. Hauteurs > 30 m : poids d'échantillon et MAE par classe de hauteur.
4. Validation par blocs pour l'arrêt anticipé et les hyperparamètres ; intervalle de
   confiance par bootstrap sur les dalles pour 3,46 m.
5. Sentinel-1 non accessible anonymement ; incertitude entre scènes perdue par des
   descripteurs annuels (à garder : un modèle par scène, ou quantiles) ; stockage du Jura
   non chiffré (MNH 0,5 m ≈ 80 Go bruts, hypothèse) et non précisé par Pascal.
6. Question de contrôle : MAE au pixel, ou hauteur fiable au peuplement pour Nemeton ?

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
