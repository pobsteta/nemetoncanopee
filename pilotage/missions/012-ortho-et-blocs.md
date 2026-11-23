# Mission 012 — texture de l'ortho et blocs d'apprentissage en plus

## Mission

**En une phrase :** Ajouter à l'échantillon du Jura (et au jeu d'essai) des descripteurs à 10 m tirés de la BD ORTHO RVB + IRC à 20 cm (moyenne et écart-type de l'IRC et d'un indice de végétation, part de pixels non végétaux ou d'ombre, texture locale), calculés à la volée sans garder l'ortho, avec sa date de prise de vue, et trois blocs d'apprentissage de plus (un par type de forêt), pour donner au modèle de quoi voir les trouées et les peuplements bas.

## Les trois questions

oui · oui (WMS-R BD ORTHO, `docs/referentiels.md` ; script de 008) · oui (réseau, 59 Go libres, budget 20 Go). **Temps de la main :** donner. **Degré :** le chef tranche.

## L'Homme

`dev`, sonnet.

## Harnais

- **Peut :** `scripts/fabriquer_echantillon.py`, `scripts/fabriquer_jeu_essai.py` (ajout d'une option `--seulement ortho`), `conf/echantillon_jura.yaml`, `conf/jeu_essai.yaml`, `conf/zones/echantillon_jura.yaml`, `conf/zones/jeu_essai.yaml`, `tests/data/` (ajouts, PROVENANCE en ajout seul), `docs/echantillon_jura.md`, `tests/test_echantillon.py`, `tests/test_jeu_essai.py` (ajouts).
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** garder l'ortho brute ; dépasser 20 Mo de jeu d'essai ; toucher aux blocs de test existants (chaux_b, joux, altitude_b) ; choisir un nouveau bloc à moins de 10 km d'un bloc de test.

## Valeur provisoire

Choix des descripteurs ortho et seuils (ombre, non végétal) : provisoires, en conf.

## Tests

Script testé sans réseau ; contrôle intégré (CRS, alignement, provenance, date de l'ortho) ; jeu d'essai toujours < 20 Mo.

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Pascal.

## Ma réponse d'abord

_Rempli par Pascal seul._
