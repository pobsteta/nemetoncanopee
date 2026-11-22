# Échantillon du Jura (mission 008)

- **Propriétaire :** Pascal · **Fabriqué par :** `dev` (mission 008) · **Date de fabrication : 22 novembre 2026**
- **Statut :** fabriqué et contrôlé ; découpage apprentissage / test **proposé** (à trancher par l'orchestrateur par délégation, puis Pascal).
- **Pourquoi :** mesurer les modèles candidats de l'ADR 0004 (LightGBM, petit U-Net CPU) contre FORMS-T v1 sur des blocs indépendants, avant de choisir (mission 011).

L'échantillon n'est **pas dans le dépôt** : il vit dans `/data/echantillon_jura/` (ignoré par git, 76 Mo, budget 20 Gio). Seuls le script, les configurations et ce manifeste sont versionnés.

## Fabriquer

```
python scripts/fabriquer_echantillon.py                 # tout, reprenable (un fragment par dalle dans .etat/)
python scripts/fabriquer_echantillon.py --controler     # contrôle seul, sans réseau
```

Paramètres : `conf/echantillon_jura.yaml` (blocs, rôles, 4 fils, 3 essais par dalle) qui hérite de `conf/jeu_essai.yaml` (sources, grille, Sentinel-2, FORMS-T). Le script réutilise les fonctions de `scripts/fabriquer_jeu_essai.py` (inchangé). Durée mesurée le 22/11/2026 (4 CPU) : **8,4 min** pour 96 dalles ; une reprise sur échantillon complet prend 4 s. Journal : `/data/echantillon_jura/fabrication.log`. Seul le MNH agrégé est écrit : le brut de 0,5 m est téléchargé en mémoire dalle par dalle, agrégé (maximum à 2 m, comme le jeu d'essai ; MNT en moyenne à 10 m) et jamais conservé.

Contenu : même arborescence que `tests/data/` (`lidar/`, `foret/`, `sentinel2/`, `references/forms_t_v1/`, `manifeste_dalles.parquet`, `sentinel2_scenes.csv`, `decoupage.yaml`, `PROVENANCE`) plus `MANIFESTE.md`, `fabrication.log` et `.etat/`. Pour chaque dalle : 3 scènes Sentinel-2 L2A de l'année de vol (fenêtre mai-septembre, scènes réelles de juin, juillet et août ; une par mois, moins de 2 % de pixels nuage, ombre ou neige sur la dalle d'après le SCL ; nuage de scène de 0,0002 à 0,019 %), polygones BD Forêt V2, FORMS-T v1 de l'année de vol (hauteur 10 m, 2022).

## Lire avec la chaîne

```
canopee --conf conf/chaine_echantillon_jura.yaml ingest | prepare | targets | train | infer | smooth | validate | export
```

`conf/chaine_echantillon_jura.yaml` reprend les réglages de `conf/chaine.yaml` (un test vérifie qu'ils restent identiques), avec la zone `conf/zones/echantillon_jura.yaml` (mode `local`, 96 dalles, année 2022) et le travail dans `/data/echantillon_jura_travail`. Mesuré le 22/11/2026 avec le modèle trivial : ingest 0,7 s, prepare 4,5 s, targets 1,9 s, train 0,9 s, infer 1,7 s, smooth 1,0 s, validate 1,2 s, export 5,3 s, zonal 1,1 s ; **chaîne complète 18 s**, 96 items STAC validés. Le modèle trivial donne MAE 4,43 m sur les 48 dalles de test contre 3,35 m pour FORMS-T v1 (même masque, 462 467 cellules) : c'est la référence à battre et le plancher du modèle trivial, pas un résultat de modèle.

## Pourquoi ces six blocs

Critères : 4 x 4 dalles dont les 16 portent la même année de vol 2022 (WFS IGN `IGNF_LIDAR-HD_METADONNEE:metadata`, début et fin dans la même année), bloc à 95 % au moins dans le Jura (AdminExpress), BD Forêt V2 sur 73 à 100 % de la surface, MNH publié (au moins 50 % de cellules valides par dalle ; mesuré 100 % sur les 96 dalles), au moins 10 km entre blocs (le plus proche : 10,0 km entre la Joux et `altitude_a`, 10,2 km entre les deux blocs de Chaux). Sur les 1 049 blocs candidats du Jura, la BD Forêt et les hauteurs approchées (GetMap à 16 m) ont servi à choisir trois types de forêt, chacun en deux blocs (un pour apprendre, un pour tester) :

- **chênaie de plaine** (forêt de Chaux, 210-280 m) : `chaux_a` et `chaux_b` ;
- **sapinière à grands arbres** : `joux` (forêt de la Joux, communes de Supt et alentours, 630-870 m, MNH jusqu'à 49,8 m, 8,6 % des cellules de 2 m au-dessus de 30 m), avec `sapiniere_a` en apprentissage (Haut-Jura nord-ouest, 740-1120 m, 7,4 % au-dessus de 30 m) ;
- **forêt d'altitude** (Haut-Jura) : `altitude_b` (970-1290 m, sapin-épicéa à 1 368 ha) en test, `altitude_a` (860-1090 m, mixte, sapin-épicéa, hêtre) en apprentissage.

Écart au brief de la mission : la forêt de la Joux est à x 926-930 km, y 6642-6646 km (Supt, vérifié par AdminExpress), non vers x 915-925 km. Les altitudes sont lues sur le MNT et arrondies (à ±10 m).

## Découpage proposé (`decoupage.yaml`)

Test = `chaux_b`, `joux`, `altitude_b` (48 dalles) ; apprentissage = `chaux_a`, `sapiniere_a`, `altitude_a` (48 dalles). Justification : le test est de **chaque type**, appris ailleurs sur un autre bloc, avec un vol de la même année ; le test comporte les plus grands sapins (Joux) et la forêt la plus haute, là où un modèle de hauteur est le plus exigeant (hauteurs de plus de 30 m, relief). Aucune dalle de test ne touche une dalle d'apprentissage ; les blocs de 10 km ne sont pas partagés (le découpage passe le contrôle `nemeton_canopee.decoupage`). Un seul bloc par type de forêt en apprentissage : le modèle ne voit qu'un exemplaire de chaque type, ce qui rend l'évaluation exigeante. Choix inverse ou 3 blocs de test seulement : à trancher.

## Manifeste (généré par le script, `MANIFESTE.md` ; surfaces BD Forêt à polygones fusionnés)

Taille de l'échantillon : 76 Mo (0.07 Gio), budget 20 Gio.

| Bloc | Rôle | Type de forêt | Coin NO (km) | Vol | Forêt (ha) | Essences BD Forêt | MNH max (m) | Part > 30 m | Scènes S2 |
|---|---|---|---|---|---|---|---|---|---|
| chaux_a | apprentissage | chênaie de plaine (forêt de Chaux), 210-260 m | 894-6668 | 2022-07-27 -> 2022-08-24 | 1577 | Chênes décidus 896 ha, Hêtre 265 ha, Feuillus 252 ha | 38.2 | 2.5% | 48 |
| chaux_b | test | chênaie de plaine (forêt de Chaux), 240-280 m | 908-6674 | 2022-07-28 -> 2022-08-25 | 1595 | Chênes décidus 1203 ha, Feuillus 118 ha, Mixte 105 ha | 36.9 | 1.4% | 48 |
| sapiniere_a | apprentissage | sapinière-hêtraie de moyenne montagne, 740-1120 m | 916-6612 | 2022-09-20 -> 2022-10-25 | 1447 | Sapin, épicéa 903 ha, Mixte 483 ha, NC 34 ha | 48.5 | 7.4% | 48 |
| joux | test | sapinière à grands arbres (forêt de la Joux), 630-870 m | 926-6646 | 2022-08-25 -> 2022-10-17 | 1490 | Sapin, épicéa 1269 ha, Mixte 207 ha, Conifères 11 ha | 49.8 | 8.6% | 48 |
| altitude_a | apprentissage | forêt d'altitude, sapin-épicéa et hêtre, 860-1090 m | 938-6636 | 2022-09-20 -> 2022-10-27 | 1171 | Mixte 563 ha, Sapin, épicéa 320 ha, Hêtre 166 ha | 44.5 | 1.7% | 48 |
| altitude_b | test | forêt d'altitude du Haut-Jura, sapin-épicéa, 970-1290 m | 934-6610 | 2022-10-05 -> 2022-10-27 | 1540 | Sapin, épicéa 1368 ha, Mixte 157 ha, NC 14 ha | 42.9 | 2.2% | 48 |

### Bloc chaux_a (apprentissage)

| Dalle | Vol (début -> fin) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|
| 0894-6665 | 2022-07-28 -> 2022-08-24 | 100 | Chênes décidus 58 ha | 34.2 | 28.6 |
| 0894-6666 | 2022-07-28 -> 2022-08-24 | 100 | Chênes décidus 99 ha | 33.8 | 30.4 |
| 0894-6667 | 2022-07-28 -> 2022-08-24 | 100 | Chênes décidus 76 ha | 34.6 | 30.7 |
| 0894-6668 | 2022-07-28 -> 2022-08-24 | 99 | Chênes décidus 92 ha | 34.2 | 30.8 |
| 0895-6665 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 47 ha | 33.5 | 28.9 |
| 0895-6666 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 42 ha | 34.2 | 30.2 |
| 0895-6667 | 2022-07-28 -> 2022-07-28 | 99 | Feuillus 57 ha | 36.5 | 32.2 |
| 0895-6668 | 2022-07-28 -> 2022-07-28 | 99 | Hêtre 71 ha | 38.2 | 33.5 |
| 0896-6665 | 2022-07-27 -> 2022-07-28 | 100 | Chênes décidus 58 ha | 32.9 | 28.3 |
| 0896-6666 | 2022-07-27 -> 2022-07-28 | 97 | Feuillus 34 ha | 37.5 | 30.8 |
| 0896-6667 | 2022-07-27 -> 2022-07-28 | 100 | Hêtre 71 ha | 36.1 | 31.4 |
| 0896-6668 | 2022-07-27 -> 2022-07-28 | 100 | Chênes décidus 44 ha | 36.2 | 30.2 |
| 0897-6665 | 2022-07-27 -> 2022-07-28 | 98 | Chênes décidus 52 ha | 34.7 | 29.9 |
| 0897-6666 | 2022-07-27 -> 2022-07-28 | 92 | Chênes décidus 72 ha | 35.7 | 29.5 |
| 0897-6667 | 2022-07-27 -> 2022-07-28 | 97 | Chênes décidus 97 ha | 34.8 | 30.8 |
| 0897-6668 | 2022-07-27 -> 2022-07-28 | 98 | Chênes décidus 75 ha | 34.8 | 30.2 |

### Bloc chaux_b (test)

| Dalle | Vol (début -> fin) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|
| 0908-6671 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 90 ha | 34.9 | 30.3 |
| 0908-6672 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 92 ha | 36.9 | 31.2 |
| 0908-6673 | 2022-07-28 -> 2022-08-25 | 100 | Chênes décidus 97 ha | 35.6 | 30.9 |
| 0908-6674 | 2022-07-28 -> 2022-08-25 | 100 | Chênes décidus 78 ha | 34.3 | 30.5 |
| 0909-6671 | 2022-07-28 -> 2022-07-28 | 100 | Pin autre 36 ha | 35.2 | 31.0 |
| 0909-6672 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 82 ha | 34.7 | 29.6 |
| 0909-6673 | 2022-07-28 -> 2022-08-25 | 100 | Chênes décidus 100 ha | 34.2 | 29.7 |
| 0909-6674 | 2022-07-28 -> 2022-08-25 | 100 | Chênes décidus 100 ha | 32.0 | 28.4 |
| 0910-6671 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 31 ha | 36.8 | 30.3 |
| 0910-6672 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 75 ha | 32.5 | 28.9 |
| 0910-6673 | 2022-07-28 -> 2022-08-25 | 100 | Chênes décidus 88 ha | 33.4 | 29.4 |
| 0910-6674 | 2022-07-28 -> 2022-08-25 | 100 | Chênes décidus 87 ha | 34.1 | 29.2 |
| 0911-6671 | 2022-07-28 -> 2022-07-28 | 100 | Feuillus 57 ha | 35.8 | 31.9 |
| 0911-6672 | 2022-07-28 -> 2022-07-28 | 100 | Chênes décidus 69 ha | 35.0 | 29.0 |
| 0911-6673 | 2022-07-28 -> 2022-08-25 | 98 | Chênes décidus 55 ha | 34.6 | 30.0 |
| 0911-6674 | 2022-07-28 -> 2022-08-25 | 97 | Chênes décidus 85 ha | 32.9 | 29.3 |

### Bloc sapiniere_a (apprentissage)

| Dalle | Vol (début -> fin) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|
| 0916-6609 | 2022-09-20 -> 2022-10-25 | 100 | Mixte 75 ha | 46.4 | 37.4 |
| 0916-6610 | 2022-09-20 -> 2022-10-25 | 100 | Sapin, épicéa 72 ha | 46.2 | 35.9 |
| 0916-6611 | 2022-09-20 -> 2022-09-20 | 98 | Sapin, épicéa 97 ha | 45.0 | 33.2 |
| 0916-6612 | 2022-09-20 -> 2022-09-20 | 16 | Mixte 7 ha | 36.8 | 24.7 |
| 0917-6609 | 2022-09-20 -> 2022-10-25 | 100 | Mixte 83 ha | 46.8 | 37.4 |
| 0917-6610 | 2022-09-20 -> 2022-10-25 | 100 | Mixte 61 ha | 48.5 | 36.5 |
| 0917-6611 | 2022-09-20 -> 2022-10-25 | 89 | Sapin, épicéa 60 ha | 42.5 | 34.0 |
| 0917-6612 | 2022-09-20 -> 2022-09-20 | 67 | NC 33 ha | 43.8 | 32.0 |
| 0918-6609 | 2022-10-25 -> 2022-10-25 | 99 | Sapin, épicéa 70 ha | 46.2 | 37.0 |
| 0918-6610 | 2022-09-20 -> 2022-10-25 | 99 | Sapin, épicéa 71 ha | 46.9 | 37.0 |
| 0918-6611 | 2022-09-20 -> 2022-10-25 | 100 | Mixte 66 ha | 42.4 | 33.5 |
| 0918-6612 | 2022-09-20 -> 2022-10-25 | 100 | Sapin, épicéa 97 ha | 45.6 | 36.5 |
| 0919-6609 | 2022-10-25 -> 2022-10-25 | 88 | Sapin, épicéa 80 ha | 44.3 | 35.0 |
| 0919-6610 | 2022-10-25 -> 2022-10-25 | 92 | Sapin, épicéa 92 ha | 44.9 | 35.6 |
| 0919-6611 | 2022-09-20 -> 2022-10-25 | 100 | Sapin, épicéa 74 ha | 47.9 | 34.7 |
| 0919-6612 | 2022-09-20 -> 2022-10-25 | 100 | Sapin, épicéa 56 ha | 47.0 | 34.5 |

### Bloc joux (test)

| Dalle | Vol (début -> fin) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|
| 0926-6643 | 2022-08-25 -> 2022-08-25 | 81 | Sapin, épicéa 78 ha | 41.7 | 34.2 |
| 0926-6644 | 2022-08-25 -> 2022-08-25 | 78 | Sapin, épicéa 71 ha | 42.4 | 34.9 |
| 0926-6645 | 2022-08-25 -> 2022-08-25 | 88 | Sapin, épicéa 65 ha | 45.0 | 34.8 |
| 0926-6646 | 2022-08-25 -> 2022-10-17 | 76 | Sapin, épicéa 68 ha | 42.0 | 32.9 |
| 0927-6643 | 2022-08-25 -> 2022-08-25 | 99 | Sapin, épicéa 85 ha | 45.5 | 36.1 |
| 0927-6644 | 2022-08-25 -> 2022-08-25 | 97 | Sapin, épicéa 97 ha | 45.2 | 35.7 |
| 0927-6645 | 2022-08-25 -> 2022-08-25 | 100 | Sapin, épicéa 95 ha | 40.3 | 34.9 |
| 0927-6646 | 2022-08-25 -> 2022-10-17 | 100 | Sapin, épicéa 100 ha | 38.8 | 31.4 |
| 0928-6643 | 2022-08-25 -> 2022-08-25 | 99 | Sapin, épicéa 86 ha | 45.1 | 35.6 |
| 0928-6644 | 2022-08-25 -> 2022-08-25 | 98 | Sapin, épicéa 85 ha | 46.7 | 38.1 |
| 0928-6645 | 2022-08-25 -> 2022-08-25 | 100 | Sapin, épicéa 95 ha | 45.2 | 36.2 |
| 0928-6646 | 2022-08-25 -> 2022-10-17 | 100 | Sapin, épicéa 68 ha | 43.0 | 34.6 |
| 0929-6643 | 2022-08-25 -> 2022-08-25 | 97 | Sapin, épicéa 72 ha | 49.8 | 39.3 |
| 0929-6644 | 2022-08-25 -> 2022-08-25 | 79 | Mixte 40 ha | 45.2 | 37.1 |
| 0929-6645 | 2022-08-25 -> 2022-10-17 | 100 | Sapin, épicéa 74 ha | 44.9 | 34.7 |
| 0929-6646 | 2022-08-25 -> 2022-10-17 | 99 | Sapin, épicéa 94 ha | 44.9 | 36.6 |

### Bloc altitude_a (apprentissage)

| Dalle | Vol (début -> fin) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|
| 0938-6633 | 2022-09-20 -> 2022-10-27 | 60 | Sapin, épicéa 24 ha | 37.1 | 28.6 |
| 0938-6634 | 2022-09-21 -> 2022-10-17 | 60 | Feuillus 27 ha | 33.4 | 26.5 |
| 0938-6635 | 2022-09-21 -> 2022-10-17 | 51 | Feuillus 33 ha | 34.6 | 25.2 |
| 0938-6636 | 2022-09-21 -> 2022-10-17 | 4 | Feuillus 2 ha | 30.1 | 16.7 |
| 0939-6633 | 2022-10-25 -> 2022-10-27 | 100 | Mixte 52 ha | 39.7 | 31.9 |
| 0939-6634 | 2022-10-17 -> 2022-10-17 | 88 | Hêtre 73 ha | 37.5 | 28.5 |
| 0939-6635 | 2022-10-17 -> 2022-10-17 | 57 | Mixte 17 ha | 37.1 | 28.0 |
| 0939-6636 | 2022-10-17 -> 2022-10-17 | 27 | Sapin, épicéa 11 ha | 38.3 | 30.0 |
| 0940-6633 | 2022-10-25 -> 2022-10-27 | 88 | Mixte 60 ha | 42.1 | 33.6 |
| 0940-6634 | 2022-10-17 -> 2022-10-17 | 82 | Mixte 32 ha | 39.9 | 32.1 |
| 0940-6635 | 2022-10-17 -> 2022-10-17 | 84 | Mixte 41 ha | 36.7 | 28.8 |
| 0940-6636 | 2022-10-17 -> 2022-10-17 | 84 | Mixte 47 ha | 40.0 | 31.6 |
| 0941-6633 | 2022-10-25 -> 2022-10-27 | 100 | Mixte 73 ha | 43.7 | 33.6 |
| 0941-6634 | 2022-10-17 -> 2022-10-17 | 99 | Mixte 71 ha | 41.5 | 33.0 |
| 0941-6635 | 2022-10-17 -> 2022-10-17 | 91 | Mixte 45 ha | 43.0 | 33.2 |
| 0941-6636 | 2022-10-17 -> 2022-10-17 | 95 | Mixte 80 ha | 44.5 | 32.7 |

### Bloc altitude_b (test)

| Dalle | Vol (début -> fin) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|
| 0934-6607 | 2022-10-27 -> 2022-10-27 | 98 | Sapin, épicéa 98 ha | 36.7 | 29.6 |
| 0934-6608 | 2022-10-05 -> 2022-10-27 | 99 | Sapin, épicéa 99 ha | 40.2 | 30.6 |
| 0934-6609 | 2022-10-05 -> 2022-10-27 | 98 | Sapin, épicéa 79 ha | 42.9 | 33.0 |
| 0934-6610 | 2022-10-05 -> 2022-10-27 | 78 | Sapin, épicéa 47 ha | 40.6 | 33.3 |
| 0935-6607 | 2022-10-27 -> 2022-10-27 | 100 | Sapin, épicéa 100 ha | 42.0 | 31.4 |
| 0935-6608 | 2022-10-27 -> 2022-10-27 | 96 | Sapin, épicéa 96 ha | 37.6 | 30.1 |
| 0935-6609 | 2022-10-05 -> 2022-10-27 | 98 | Sapin, épicéa 98 ha | 38.4 | 30.6 |
| 0935-6610 | 2022-10-05 -> 2022-10-27 | 100 | Sapin, épicéa 100 ha | 41.1 | 30.9 |
| 0936-6607 | 2022-10-27 -> 2022-10-27 | 99 | Sapin, épicéa 71 ha | 42.8 | 33.5 |
| 0936-6608 | 2022-10-27 -> 2022-10-27 | 100 | Sapin, épicéa 100 ha | 41.0 | 31.2 |
| 0936-6609 | 2022-10-27 -> 2022-10-27 | 100 | Sapin, épicéa 100 ha | 38.6 | 30.3 |
| 0936-6610 | 2022-10-27 -> 2022-10-27 | 100 | Sapin, épicéa 100 ha | 41.0 | 31.5 |
| 0937-6607 | 2022-10-27 -> 2022-10-27 | 76 | Mixte 59 ha | 40.6 | 31.0 |
| 0937-6608 | 2022-10-27 -> 2022-10-27 | 99 | Sapin, épicéa 78 ha | 42.8 | 32.3 |
| 0937-6609 | 2022-10-27 -> 2022-10-27 | 99 | Sapin, épicéa 99 ha | 40.1 | 30.8 |
| 0937-6610 | 2022-10-27 -> 2022-10-27 | 100 | Sapin, épicéa 100 ha | 38.8 | 29.6 |

## À vérifier ou à savoir

- **Dates de vol** : une seule source (WFS IGN), contrôle croisé TerraLab non fait (comme `docs/referentiels.md` § 9). Les vols des blocs d'altitude et de `sapiniere_a` vont de septembre à fin octobre 2022 alors que les scènes Sentinel-2 vont de juin à août : l'appariement se fait à l'année de vol (règle du projet), pas au mois ; les dalles d'altitude ont un feuillage d'été sur l'image et un MNH d'automne.
- **BD Forêt** : pas de date par polygone ; l'essence peut dater de l'inventaire départemental. Les essences ci-dessus sont celles de la BD Forêt, pas une mesure.
- **MNH maximal** : des valeurs élevées isolées (jusqu'à 81 m sur des GetMap grossiers du Haut-Jura, repérés avant fabrication) peuvent être des artefacts (pylônes, grues, éoliennes) ; le maximum à 2 m les conserve, comme au jeu d'essai. Non vérifié sur le terrain.
- **FORMS-T v1** : lu par fenêtre `/vsicurl/` sur Zenodo, sans compte ; hauteur 2022 pour les 96 dalles (aucune dalle hors 2018-2024).
- **Pré-entraînement** : les blocs de test ne doivent pas être vus par un pré-entraînement (Open-Canopy compris) ; non vérifié ici (CLAUDE.md).
