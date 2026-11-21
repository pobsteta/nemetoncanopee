# nemetoncanopee

[![CI](https://github.com/pobsteta/nemetoncanopee/actions/workflows/ci.yml/badge.svg)](https://github.com/pobsteta/nemetoncanopee/actions/workflows/ci.yml)
[![Release](https://github.com/pobsteta/nemetoncanopee/actions/workflows/release.yml/badge.svg)](https://github.com/pobsteta/nemetoncanopee/actions/workflows/release.yml)
[![Version](https://img.shields.io/github/v/release/pobsteta/nemetoncanopee?label=version)](https://github.com/pobsteta/nemetoncanopee/releases)
![Couverture](.github/badges/coverage.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Cartes annuelles de **hauteur, volume et biomasse forestière**, fiables à l'échelle du
peuplement, pour alimenter [Nemeton](https://github.com/pobsteta/nemeton). Le projet part de
FORMS-T (LSCE) et l'améliore avec le LiDAR HD, les essences, une cohérence temporelle et
l'ortho IGN à 20 cm.

Le périmètre, les données, l'architecture et les jalons sont décrits dans le
[brief de développement](BRIEF.md).

---

## Installation (développement)

```sh
git clone https://github.com/pobsteta/nemetoncanopee
cd nemetoncanopee
python -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
canopee --version
```

## Tests

Une seule commande lance tout ce que la CI vérifie :

```sh
.claude/test-command
```

| Vérification | Commande |
| --- | --- |
| Règle de décision de release | `.github/scripts/test-release-necessaire.sh` |
| Calcul de la version calendaire | `.github/scripts/test-version-calendaire.sh` |
| Style | `ruff check .` et `ruff format --check .` |
| Tests unitaires et couverture | `pytest --cov=nemeton_canopee` |

## Versions, tags et releases

Tout est automatique, sur le modèle de [marculus](https://github.com/pobsteta/marculus) :

1. **Jamais de push direct sur `main`** : tout passe par une PR, que la CI teste.
2. Au merge, `ci.yml` rejoue les tests sur `main`, construit le paquet et met à jour le
   badge de couverture.
3. Si la CI est verte, `release.yml` décide si une release est nécessaire
   (`.github/scripts/release-necessaire.sh`) : il en faut une dès qu'un fichier du projet a
   changé depuis le dernier tag. Les changements limités à `docs/`, aux `*.md`, au badge
   ou aux tests n'en déclenchent pas.
4. La version est **calendaire** : `vAAAA.MM.N`, où `N` est le compteur de releases du
   mois (UTC) et repart à 1 chaque mois. Exemple : `v2026.11.1`, puis `v2026.11.2`.
5. Le workflow pose un tag annoté sur le commit testé, construit le paquet (sdist + wheel)
   et publie une release GitHub avec ses notes générées.

La version n'est écrite dans aucun fichier : le paquet la lit dans le tag git (`hatch-vcs`).
Il n'y a donc ni fichier de version à modifier, ni tag à poser à la main.
