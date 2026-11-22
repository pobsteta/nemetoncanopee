# ADR 0002 — définition du volume et coefficients de biomasse

- **Date :** 2026-11-22
- **Statut :** proposée
- **Proposée par :** Claude (orchestrateur), sur critique du `contradicteur`
- **Tranchée par :** Pascal

## La décision en une phrase

Le volume produit est le **volume bois fort tige sur écorce** au sens de l'inventaire
forestier de l'IGN, et la biomasse aérienne s'en déduit par la méthode IPCC 2006
(volume × infradensité × facteur d'expansion), avec les coefficients par essence repris
de l'IGN et du CITEPA, chacun sourcé dans `conf/`.

## Contexte

Le brief ne définit pas le volume ; sans la même définition que FORMS-T v1, la
comparaison « 86 m³/ha » ne tient pas (contradicteur, critique n° 3, retenue le 22/11).
**À vérifier par l'`acquereur` avant que Pascal tranche** : la définition du volume
utilisée par FORMS-T v1 (Schwartz et al., 2025), et les tables exactes d'infradensité et
de facteurs d'expansion publiées par le CITEPA (OMINEA) et l'IGN. Si FORMS-T utilise une
autre définition, la décision suit celle de la référence, ou l'on publie les deux.

Options : (a) bois fort tige (IGN, standard de l'inventaire) ; (b) bois fort total
(tige + branches > 7 cm) ; (c) volume total aérien.

## Le crible FRANCE

| Lettre | Question | Réponse (une ligne) | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|---|
| **F**rugale | La plus simple qui tienne ? | Reprendre la définition de l'inventaire national, sans inventer | Dépend de tables à sourcer | à trancher par Pascal |
| **R**esponsable | Qui fait quoi ? | L'`acquereur` sourcé les tables ; Pascal tranche | — | à trancher par Pascal |
| **A**nticiper | Si l'imprévu arrive ? | Si l'IGN change de méthode, les coefficients changent dans `conf/`, pas dans le code | Versions de coefficients à tracer dans les COG | à trancher par Pascal |
| **N**ovateur | Toutes les idées ? | (a), (b), (c) examinées | — | — |
| **C**oût | Coût complet ? | inconnu | — | — |
| **É**cologique | Réutilisation ? | Mêmes conventions que l'inventaire national et l'inventaire des émissions : comparables par tous | — | à trancher par Pascal |

## Valeurs sacrifiées

À nommer après vérification de la définition de FORMS-T v1.

## Sources

- FAQ IGN « ressources bois carbone » : https://www.ign.fr/publications-de-l-ign/institut/Conferences-ligne/210120_ressources_foret/faq_juign_ressources_bois_carbone.pdf
- Lignes directrices IPCC 2006, vol. 4, chap. 4 : https://www.ipcc-nggip.iges.or.jp/public/2006gl/vol4.html
- Critique du contradicteur, journal du 2026-11-22.

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
