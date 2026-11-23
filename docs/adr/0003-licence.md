# ADR 0003 — licence du code et des cartes

- **Date :** 2026-11-22
- **Statut :** proposée — **question de valeur, à trancher par Pascal**
- **Proposée par :** Claude (orchestrateur)
- **Tranchée par :** Pascal

## La décision en une phrase

À trancher par Pascal. Options préparées ci-dessous, sans recommandation de l'IA sur le
fond : c'est une question de valeur.

## Contexte

Question ouverte du brief (« Licence : quelle licence pour le code et les cartes ? »).
Le dépôt n'a aujourd'hui aucun fichier `LICENSE`. Contraintes connues : les entrées IGN
sont sous Licence Ouverte 2.0 (attribution) ; FORMS-T v1 est sous CC BY 4.0 ; le plugin
`imperatrice` et Surculus sont sous GPL-3.0-or-later. La licence de nemeton n'a pas été
vérifiée.

| Objet | Option 1 | Option 2 | Option 3 |
|---|---|---|---|
| Code | GPL-3.0-or-later (comme le plugin et Surculus) | Apache-2.0 (permissive, brevets) | MIT |
| Cartes | Licence Ouverte 2.0 (comme les sources IGN) | CC BY 4.0 (comme FORMS-T) | ODbL (partage à l'identique) |

Point à vérifier avant de trancher : la compatibilité avec la licence de nemeton, qui
charge ce paquet.

## Le crible FRANCE

| Lettre | Question | Réponse (une ligne) | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|---|
| **F**rugale | La plus simple qui tienne ? | à trancher par Pascal | | |
| **R**esponsable | Qui fait quoi ? | Pascal choisit ; l'orchestrateur ajoute `LICENSE` et les métadonnées STAC | | |
| **A**nticiper | Si l'imprévu arrive ? | Une licence se change difficilement une fois les cartes diffusées | | |
| **N**ovateur | Toutes les idées ? | trois options par objet | | |
| **C**oût | Coût complet ? | inconnu | | |
| **É**cologique | Réutilisation ? | Une licence ouverte rend cartes et code réutilisables par d'autres | | |

## Valeurs sacrifiées

À nommer par Pascal.

## Sources

- Licence Ouverte 2.0 : https://www.etalab.gouv.fr/licence-ouverte-open-licence/
- FORMS-T v1, Zenodo (CC BY 4.0) : https://zenodo.org/records/15489231

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
