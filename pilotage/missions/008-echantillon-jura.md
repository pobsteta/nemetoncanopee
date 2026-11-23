# Mission 008 — échantillon du Jura

## Mission

**En une phrase :** Fabriquer, hors dépôt et sans garder le brut, un échantillon d'environ 48 dalles forestières du Jura (39) réparties en blocs, avec cibles 10 m, scènes Sentinel-2 de l'année de vol, masque forêt, polygones BD Forêt et FORMS-T v1, pour mesurer les modèles candidats de l'ADR 0004 sur des blocs indépendants.

## Les trois questions

oui · oui (script de 002, référentiels, FORMS-T en /vsicurl/) · oui (réseau, 4 CPU, 15 Go de RAM, 59 Go libres ; budget 20 Go). **Temps de la main :** donner. **Degré :** le chef tranche (par délégation).

## L'Homme

`dev`, sonnet.

## Harnais

- **Peut :** `scripts/fabriquer_echantillon.py`, `conf/echantillon_jura.yaml`, `conf/zones/echantillon_jura.yaml`, `docs/echantillon_jura.md` (manifeste lisible : dalles, blocs, dates de vol, essences, taille), `tests/test_echantillon.py` (tests sans réseau sur le script, avec de petites données factices) ; données dans `/data/echantillon_jura/` (ignoré par git).
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** garder le MNH 0,5 m brut (agrégé à la volée : maximum à 2 m puis cible 10 m) ; dépasser 20 Go ; choisir des dalles d'une autre année de vol que celle de leurs scènes S2.

## Choix

- Au moins 4 blocs de 4×4 km (16 dalles chacun) ou 3 blocs plus grands, au moins 10 km entre blocs, en forêt majoritaire, couvrant feuillus (Chaux), sapinières à grands arbres (> 30 m, forêt de la Joux ou Risoux, à vérifier par le MNH) et un massif d'altitude ; vols LiDAR HD publiés, même année de vol par bloc si possible.
- Le format de sortie suit celui de `tests/data/` (même arborescence et conventions), pour que `canopee --conf …` puisse lire l'échantillon en `mode: local`.

## Valeur provisoire

Budget 20 Go ; 3 scènes S2 par dalle au plus. **Mesurée par :** `du -s` en fin de fabrication.

## Tests

Script testé sans réseau ; échantillon contrôlé (CRS, alignement, provenance, taille) par un contrôle intégré au script.

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Claude (orchestrateur, par délégation de Pascal : « Fais ce qu'il y a de mieux », journal du 22/11).

## Ma réponse d'abord

_Rempli par Pascal seul._
