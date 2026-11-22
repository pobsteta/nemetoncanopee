# Équipe de nemetoncanopee

> Produit par l'orchestrateur avec `/imperatrice:mission`, **validé par Pascal** avant
> tout démarrage. Règle de staffing : un agent par mission qui passe les trois
> questions, jamais un agent « par principe ».

- **Statut :** proposée
- **Validée par :** _…_

## Plafond humain

- **PR ouvertes en même temps, au plus :** 3
- **Rythme de relecture de Pascal :** _à fixer par Pascal_

## Délégation

> Ce que Pascal demande à l'orchestrateur de trancher à sa place (skill `methode`,
> « La délégation »). Vide : aucune délégation, Pascal tranche tout.

- **Portée :** _aucune_
- **Jusqu'à :** _…_
- **Réservé à Pascal :** _…_ (toujours, même si rien n'est écrit : sa réponse d'abord ;
  rendre la main ; ce qui touche l'extérieur et ne se défait pas)
- **Inscrite au journal le :** _…_

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
| [002 — jeu d'essai de 4 dalles](missions/002-jeu-essai.md) | `dev` | sonnet | donner | oui · oui (après 001) · **à confirmer : quelles dalles ?** | 1 |
| [003 — tests d'acceptation du jalon 1](missions/003-tests-acceptation-jalon-1.md) | `testeur` | sonnet | donner | oui · oui · oui (après 002) | 2 |
| [004 — squelette du pipeline](missions/004-squelette-pipeline.md) | `dev` | opus | **prendre** (plan validé par Pascal avant le code) | oui · oui · oui (après 002, 003) | 2 |

Ordre : 001 → 002 → (003 + 004, fusion groupée). Au plus 2 PR ouvertes à la fois dans ce
découpage, sous le plafond de 3. Le `relecteur` relit chaque PR avant Pascal.
Non mobilisés au jalon 1 : `contradicteur` (hors critique des ADR), `archiviste`,
`analyste`, `afficheur`.
