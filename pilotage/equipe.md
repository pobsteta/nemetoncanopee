# Équipe de nemetoncanopee

> Produit par l'orchestrateur avec `/imperatrice:mission`, **validé par Pascal** avant
> tout démarrage. Règle de staffing : un agent par mission qui passe les trois
> questions, jamais un agent « par principe ».

- **Statut :** validée
- **Validée par :** Claude (orchestrateur, par délégation), 2026-11-22

## Plafond humain

- **PR ouvertes en même temps, au plus :** 3
- **Rythme de relecture de Pascal :** _à fixer par Pascal_

## Délégation

> Ce que Pascal demande à l'orchestrateur de trancher à sa place (skill `methode`,
> « La délégation »). Vide : aucune délégation, Pascal tranche tout.

- **Demande de Pascal, mot pour mot :** « Peux-tu coder jusqu'à la fin sans que j'ai a intervenir ? » (22 novembre 2026)
- **Portée :** « tout » : porte n° 2 (cette équipe), choix des 4 dalles du jeu d'essai,
  plans des missions en « prendre », verdicts de relecture, arbitrages techniques du jalon 1.
- **Jusqu'à :** la fin du jalon 1 (portée la plus étroite, faute de précision : les jalons
  2 à 7 demandent du calcul et des décisions que ce dépôt n'a pas encore).
- **Réservé à Pascal :** rien de plus n'a été dit. Toujours réservé : sa réponse d'abord
  (les rubriques des fiches restent vides) ; rendre la main ; ce qui touche l'extérieur et
  ne se défait pas (fusion dans `main`, qui peut publier une release ; demande de convention
  à l'IGN) ; les questions de valeur hors du brief (licences, ADR 0003 ; choix de la
  biomasse, ADR 0002).
- **Inscrite au journal le :** 2026-11-22 · terminée le 2026-11-22 (fin du jalon 1) · **renouvelée le 2026-11-22** sur « Continue » de Pascal, jusqu'à la fin du jalon 2 sur le jeu d'essai ; zone pilote et moyens de calcul réservés à Pascal

## Le vivier (catalogue, pas une équipe)

| Agent | A / plan | Modèle | Écrit du code ? |
|---|---|---|---|
| `contradicteur` | Abstraction · Polos | opus | non |
| `acquereur` | Acquisition · Ponos | sonnet | non (référentiels et données) |
| `archiviste` | Archivage · Pontos | sonnet | non (docs) |
| `analyste` | Analyse · Ponos | sonnet | non |
| `afficheur` | Affichage · Ponos | sonnet | oui (interface) |
| `dev` | réalisation · Ponos | sonnet | oui |
| `testeur` | réalisation · Ponos | sonnet | oui (tests) |
| `relecteur` | contrôle · C3 | opus | non (lecture seule) |

## Missions

| Mission | Agent | Modèle | Temps de la main | Les 3 questions | Cycle |
|---|---|---|---|---|---|
| [001 — référentiels du jalon 1](missions/001-referentiels-jalon-1.md) | `acquereur` | sonnet | donner | oui · oui · oui | 1 |
| [002 — jeu d'essai de 4 dalles](missions/002-jeu-essai.md) | `dev` | sonnet | donner | oui · oui · oui | 1 |
| [003 — tests d'acceptation du jalon 1](missions/003-tests-acceptation-jalon-1.md) | `testeur` | sonnet | donner | oui · oui · oui (après 002) | 2 |
| [004 — squelette du pipeline](missions/004-squelette-pipeline.md) | `dev` | opus | **prendre** (plan validé par Pascal avant le code) | oui · oui · oui (après 002, 003) | 2 |

Ordre : 001 → 002 → (003 + 004, fusion groupée). Au plus 2 PR ouvertes à la fois dans ce
découpage, sous le plafond de 3. Le `relecteur` relit chaque PR avant Pascal.
Non mobilisés au jalon 1 : `contradicteur` (hors critique des ADR), `archiviste`,
`analyste`, `afficheur`.
| [005 — test d'atomicité de l'export](missions/005-test-export-atomique.md) | `testeur` | sonnet | donner | oui · oui · oui | 3 |
| [006 — accès aux références FORMS-T v1 et FORMSpoT](missions/006-references-acces.md) | `acquereur` | sonnet | donner | oui · oui · oui | 3 |
| [007 — références sur le jeu d'essai et dans le rapport](missions/007-references-evaluation.md) | `dev` | opus | donner | oui · oui (après 006) · oui | 3 |
