# Échantillon du Jura (missions 008 et 012)

- **Propriétaire :** Pascal · **Fabriqué par :** `dev` (missions 008 et 012) · **Date de fabrication : 22 novembre 2026**
- **Statut :** fabriqué et contrôlé ; découpage apprentissage / test **proposé** (à trancher par l'orchestrateur par délégation, puis Pascal). Mission 012 : descripteurs de la BD ORTHO à 10 m et trois blocs d'apprentissage de plus (144 dalles, 9 blocs) ; les trois blocs de test sont inchangés.
- **Pourquoi :** mesurer les modèles candidats de l'ADR 0004 (LightGBM, petit U-Net CPU) contre FORMS-T v1 sur des blocs indépendants, avant de choisir (mission 011).

L'échantillon n'est **pas dans le dépôt** : il vit dans `/data/echantillon_jura/` (ignoré par git, 167 Mo pour 144 dalles, budget 20 Gio). Seuls le script, les configurations et ce manifeste sont versionnés.

## Fabriquer

```
python scripts/fabriquer_echantillon.py                 # tout, reprenable (un fragment par dalle dans .etat/)
python scripts/fabriquer_jeu_essai.py --seulement ortho # jeu d'essai : ajoute les descripteurs ortho, rien d'autre
python scripts/fabriquer_echantillon.py --controler     # contrôle seul, sans réseau
```

Paramètres : `conf/echantillon_jura.yaml` (blocs, rôles, 4 fils, 3 essais par dalle) qui hérite de `conf/jeu_essai.yaml` (sources, grille, Sentinel-2, FORMS-T). Le script réutilise les fonctions de `scripts/fabriquer_jeu_essai.py`. Durée mesurée le 22/11/2026 (4 CPU) : **8,4 min** pour les 96 premières dalles (mission 008) ; mission 012 : **4,4 min** pour les 48 dalles des trois nouveaux blocs (MNH, MNT, S2, BD Forêt), FORMS-T v1 en 7 s, puis **environ 25 min** de descripteurs ortho pour les 144 dalles (4 fils, 30 à 55 s par dalle dont 2 GetMap de 75 Mo ; le WFS IGN a renvoyé par moments une page qui n'était pas du JSON, d'où les reprises) ; une reprise sur échantillon complet prend 9 s. Journal : `/data/echantillon_jura/fabrication.log`. Seul le MNH agrégé est écrit : le brut de 0,5 m est téléchargé en mémoire dalle par dalle, agrégé (maximum à 2 m, comme le jeu d'essai ; MNT en moyenne à 10 m) et jamais conservé.

Contenu : même arborescence que `tests/data/` (`lidar/`, `foret/`, `sentinel2/`, `references/forms_t_v1/`, `ortho/`, `manifeste_dalles.parquet`, `sentinel2_scenes.csv`, `decoupage.yaml`, `PROVENANCE`) plus `MANIFESTE.md`, `fabrication.log` et `.etat/`. Pour chaque dalle : 3 scènes Sentinel-2 L2A de l'année de vol (fenêtre mai-septembre, scènes réelles de juin, juillet et août ; une par mois, moins de 2 % de pixels nuage, ombre ou neige sur la dalle d'après le SCL ; nuage de scène de 0,0002 à 0,019 %), polygones BD Forêt V2, FORMS-T v1 de l'année de vol (hauteur 10 m, 2022), descripteurs de la BD ORTHO (section suivante).

## Lire avec la chaîne

```
canopee --conf conf/chaine_echantillon_jura.yaml ingest | prepare | targets | train | infer | smooth | validate | export
```

`conf/chaine_echantillon_jura.yaml` reprend les réglages de `conf/chaine.yaml` (un test vérifie qu'ils restent identiques), avec la zone `conf/zones/echantillon_jura.yaml` (mode `local`, 144 dalles, année 2022 ; `fichiers.ortho` déclare `ortho/{dalle}_ortho_10m.tif`, pas encore lu par la chaîne) et le travail dans `/data/echantillon_jura_travail`. Mesuré le 22/11/2026 avec le modèle trivial sur les 96 dalles de la mission 008 : ingest 0,7 s, prepare 4,5 s, targets 1,9 s, train 0,9 s, infer 1,7 s, smooth 1,0 s, validate 1,2 s, export 5,3 s, zonal 1,1 s ; chaîne complète 18 s, 96 items STAC validés. Après la mission 012 (144 dalles, 96 d'apprentissage) : `ingest` 0,8 s, **les huit étapes ingest à export 23 s**, 144 items STAC validés ; MAE du modèle trivial sur les 48 dalles de test (inchangées) : **4,53 m** (4,43 m avec 48 dalles d'apprentissage ; le modèle trivial est une médiane, il bouge avec l'apprentissage). Cette valeur est la référence du modèle trivial, pas un résultat de modèle ; la MAE de FORMS-T v1 sur ces dalles reste 3,35 m.

## Descripteurs de la BD ORTHO à 10 m (mission 012)

**Pourquoi :** la mesure de l'ADR 0004 (`docs/mesures/2026-11-adr-0004.md`, cause n° 1) montre que les peuplements bas et les trouées sont surestimés ; Sentinel-2 à 10 m les lisse. L'ortho de 20 cm les voit. Ici, on ne garde que des statistiques par cellule de 10 m (50 x 50 pixels de 0,2 m), jamais l'ortho elle-même.

**Source et calcul** (`scripts/fabriquer_jeu_essai.py`, fonctions `telecharger_ortho`, `descripteurs_ortho`, `date_ortho` ; paramètres dans `conf/jeu_essai.yaml`, clé `ortho`) :

- WMS-R `data.geopf.fr`, GetMap GeoTIFF 5000 x 5000 px (le serveur accepte jusqu'à 5010 ; l'option `ortho.decoupes: 2` demande quatre quarts si cette limite change) de deux couches, emprise exacte de la dalle : `HR.ORTHOIMAGERY.ORTHOPHOTOS` (RVB) et `ORTHOIMAGERY.ORTHOPHOTOS.IRC` (infrarouge couleur : R = proche infrarouge, G = rouge, B = vert ; vérifié sur la Joux, le rouge du RVB et celui de l'IRC ont une corrélation de 0,994, et le script refuse une dalle où elle passe sous 0,9). Une dalle = 2 x 75 Mo téléchargés, traités en mémoire par bandes de 10 lignes de cellules.
- Pixel invalide : blanc pur (255, 255, 255) dans l'une des deux images (hors couverture) ou PIR + R = 0. Une vraie surface blanche saturée sur les trois bandes serait aussi écartée (rare en forêt). Cellule avec moins de 50 % de pixels valides : nodata (-9999). Sur les 144 dalles, aucune cellule n'est en nodata ; la plus faible part de pixels valides d'une cellule est 0,59 (`part_valide`).
- **12 bandes float32** (noms dans les tags et les descriptions de bande) : `rouge_moy`, `rouge_std`, `pir_moy`, `pir_std` (comptes numériques 0-255 de l'IRC), `ndvi_moy`, `ndvi_std` (NDVI = (PIR - R) / (PIR + R) par pixel, sans unité, puis moyenne et écart-type par cellule), `part_non_vegetal` (part de pixels de 0,2 m avec NDVI < seuil), `part_ombre` (part de pixels avec luminance < seuil), `lum_moy`, `lum_std` (luminance 0,299 R + 0,587 V + 0,114 B du RVB ; l'écart-type est la texture « écart-type local »), `gradient_moy` (texture « énergie de gradient » : moyenne de la norme du gradient de la luminance, en comptes par pixel de 0,2 m ; le gradient est calculé sur toute l'image, il déborde donc d'une cellule à l'autre au bord), `part_valide`.
- **Seuils PROVISOIRES, en conf :** `seuil_ndvi_non_vegetal` = 0,10, `seuil_ombre_luminance` = 48. Choisis en regardant la distribution sur trois dalles (Joux, Chaux, altitude) : NDVI sous 0,10 pour 2 à 10 % des pixels, luminance sous 48 pour 15 à 18 %. Aucune vérité terrain : ce sont des ordres de grandeur, à réexaminer au jalon 3.
- Fichier : `ortho/{dalle}_ortho_10m.tif`, Lambert-93, 100 x 100 cellules, aligné sur le km, deflate ; environ 0,36 Mo par dalle (52 Mo pour 144, 1,4 Mo pour les 4 du jeu d'essai). Tags : `bandes`, `unite`, `couches`, `date_prise_de_vue` (+ `_min`, `_max`), `campagnes_pva`, `departements`, `vol_lidar_debut`, `vol_lidar_fin`, `ecart_ortho_vol_lidar_jours`, seuils, traitement. Entrée de `PROVENANCE` : Licence Ouverte 2.0, requêtes GetMap et WFS complètes.

**Date de prise de vue.** `docs/referentiels.md` § 4 laissait la page de dates non lue. Elle n'est pas nécessaire : le WFS IGN publie le **graphe de mosaïquage** de la BD ORTHO, couche `ORTHOIMAGERY.ORTHOPHOTOS.GRAPHE-MOSAIQUAGE:graphe_bdortho` (champs `dep`, `pva` = campagne, `res`, `echelle`, `date_vol`), un polygone par département et par campagne, avec la date de vol. Le script interroge ce graphe (`echelle = 20`, filtre `INTERSECTS` avec le centre de la dalle puis avec la dalle) ; la date du polygone au centre est la date de la dalle, les dates des polygones qui touchent la dalle donnent `_min` et `_max`. Dans le Jura, le graphe donne trois campagnes : 2013 (50 cm), 2020 (20 cm, 2020-05-21) et 2023 (20 cm, début septembre). Les couches `ORTHOIMAGERY.ORTHOPHOTOS.IRC.2021` et `.2022` sont vides sur la zone ; `HR.ORTHOIMAGERY.ORTHOPHOTOS` et `IRC` (sans année) sont **octet pour octet** les mêmes images que `IRC.2023` et `ORTHOPHOTOS2023` : c'est bien le millésime 2023 qui est lu (GetMap de 500 x 500 px comparés par empreinte).

**Écart avec le vol LiDAR (2022) : l'ortho est postérieure de 10 à 21 mois.** Sur les 144 dalles : prises de vue du 2023-09-03 (82 dalles), 2023-09-04 (40), 2023-09-20 (16, bloc `chenaie_c`), 2023-09-06 (2), 2023-09-07 (3, Doubs) et **2024-08-06 (1 dalle, `0932-6593`, dans l'Ain, département 01)** ; écart au milieu du vol LiDAR de 306 à 644 jours, médiane 332. Les blocs :

| Bloc | Rôle | Ortho (prise de vue) | Écart au vol (jours) | % ombre | % non végétal | NDVI moyen | écart-type de luminance |
|---|---|---|---|---|---|---|---|
| chaux_a | apprentissage | 2023-09-04 | 390 à 404 | 18,0 | 3,1 | 0,33 | 13,3 |
| chaux_b | test | 2023-09-03 à 07 | 388 à 406 | 12,9 | 2,6 | 0,29 | 12,2 |
| sapiniere_a | apprentissage | 2023-09-03 à 04 | 313 à 349 | 16,9 | 17,1 | 0,18 | 16,7 |
| joux | test | 2023-09-03 à 06 | 348 à 374 | 19,0 | 13,0 | 0,22 | 15,4 |
| altitude_a | apprentissage | 2023-09-03 | 312 à 334 | 13,9 | 17,8 | 0,22 | 14,4 |
| altitude_b | test | 2023-09-03 | 311 à 322 | 10,2 | 19,0 | 0,17 | 18,0 |
| chenaie_c | apprentissage | 2023-09-20 | 392 | 13,5 | 13,8 | 0,23 | 13,2 |
| sapiniere_c | apprentissage | 2023-09-04 | 314 | 17,3 | 24,8 | 0,16 | 15,8 |
| altitude_c | apprentissage | 2023-09-03 (15 dalles), 2024-08-06 (1) | 306 à 644 | 14,4 | 33,4 | 0,13 | 17,6 |

(Moyennes des cellules, seuils provisoires.) Conséquences : (1) l'ortho date d'**après** le vol : une coupe, une chute d'arbres ou un recrû entre 2022 et septembre 2023 est vue par l'ortho et pas par le MNH, et inversement ; (2) la règle du projet d'apparier chaque dalle à l'année de son vol ne tient pas pour l'ortho, seule couche de l'échantillon dans ce cas (aucune ortho 2022 sur la zone) : à trancher par Pascal ; (3) la date est écrite par dalle (tag et PROVENANCE), de sorte que le modèle ou une analyse peut s'en servir ; (4) la dalle `0932-6593` a une date d'ortho différente de ses voisines.

**Limite connue des seuils.** Le NDVI est calculé sur des comptes numériques de l'ortho publiée, **non étalonnés** : les teintes varient d'une campagne et d'un département à l'autre (la part de pixels « non végétaux » va de 3 % dans la chênaie de Chaux à 33 % dans `altitude_c`, et vaut 14 % dans `chenaie_c`, ortho du 20 septembre : écart partiellement dû à la radiométrie, pas seulement aux routes et aux clairières). Un seuil absolu est donc fragile d'un bloc à l'autre ; un seuil relatif (par dalle ou par campagne) est une piste, non testée ici.

## Pourquoi ces neuf blocs

Critères (mission 008 ; les trois blocs `_c` de la mission 012 suivent les mêmes) : 4 x 4 dalles dont les 16 portent la même année de vol 2022 (WFS IGN `IGNF_LIDAR-HD_METADONNEE:metadata`, début et fin dans la même année), bloc à 95 % au moins dans le Jura (AdminExpress), BD Forêt V2 sur 73 à 100 % de la surface, MNH publié (au moins 50 % de cellules valides par dalle ; mesuré 100 % sur les 96 dalles), au moins 10 km entre blocs (le plus proche : 10,05 km entre la Joux et `altitude_a`, 10,2 km entre les deux blocs de Chaux). Sur les 1 049 blocs candidats du Jura, la BD Forêt et les hauteurs approchées (GetMap à 16 m) ont servi à choisir trois types de forêt, chacun en deux blocs (un pour apprendre, un pour tester) :

- **chênaie de plaine** (forêt de Chaux, 210-280 m) : `chaux_a` et `chaux_b` ;
- **sapinière à grands arbres** : `joux` (forêt de la Joux, communes de Supt et alentours, 630-870 m, MNH jusqu'à 49,8 m, 8,6 % des cellules de 2 m au-dessus de 30 m), avec `sapiniere_a` en apprentissage (Haut-Jura nord-ouest, 740-1120 m, 7,4 % au-dessus de 30 m) ;
- **forêt d'altitude** (Haut-Jura) : `altitude_b` (970-1290 m, sapin-épicéa à 1 368 ha) en test, `altitude_a` (860-1090 m, mixte, sapin-épicéa, hêtre) en apprentissage.

**Mission 012 : trois blocs d'apprentissage de plus**, un par type, pour donner au modèle d'autres exemplaires de chaque type (un seul par type en apprentissage rendait l'évaluation très exigeante, voir plus bas). Chaque bloc est à 10 km ou plus de **tous** les autres blocs, tests compris, et dans le Jura (au moins 95 % du bloc dans le département 39 d'après AdminExpress). Sélection : sur les dalles du Jura, vol 2022 sur les 16 dalles du bloc (WFS métadonnées), BD Forêt V2 sur au moins 73 % de la surface (rasterisée à 50 m), MNH publié sur toutes les dalles (GetMap à 20 m, au moins 50 % de cellules valides), altitude du MNT (GetMap à 100 m), puis types par essence BD Forêt et altitude ; 353 blocs candidats restaient.

| Bloc | Type | Coin NO (km) | Altitude (MNT 10 m, 5 à 95 %) | Plus proche bloc | Bloc de test le plus proche |
|---|---|---|---|---|---|
| `chenaie_c` | chênaie de plaine, Jura nord-ouest (chênes décidus 915 ha sur 1 342 ha de forêt) | 890-6649 | 212-237 m | 15,0 km (`chaux_a`) | 25,2 km (`chaux_b`) |
| `sapiniere_c` | sapinière-pessière de moyenne montagne, Haut-Jura sud (sapin-épicéa 606 ha, mixte 505 ha, feuillus 299 ha sur 1 413 ha) | 910-6597 | 694-907 m (620-983 m) | 11,2 km (`sapiniere_a`) | 21,9 km (`altitude_b`) |
| `altitude_c` | forêt d'altitude, sapin-épicéa (778 ha sur 1 174 ha) | 929-6596 | 1 121-1 430 m (1 014-1 495 m) | 10,05 km (`altitude_b`) | 10,05 km (`altitude_b`) |

`altitude_c` est le bloc le plus haut de l'échantillon (jusqu'à 1 495 m, au-dessus de `altitude_b`, 970-1 290 m) et à la limite des 10 km de `altitude_b` ; sa hauteur reste du même ordre (99e centile du MNH par dalle de 27 à 33 m, MNH maximal 41,6 m, contre 30 à 33 m pour `altitude_b`). Il ne prouve rien sur les peuplements bas : il ajoute de l'altitude, pas une structure connue pour être basse (la structure fine est à lire sur le MNH, non vérifiée ici). Les blocs ont été choisis sur des critères de forêt et de distance, pas sur un résultat de modèle ; ils sont rangés en apprentissage seulement. `altitude_c` touche l'Ain (la dalle `0932-6593`, voir plus haut).

Écart au brief de la mission : la forêt de la Joux est à x 926-930 km, y 6642-6646 km (Supt, vérifié par AdminExpress), non vers x 915-925 km. Les altitudes sont lues sur le MNT et arrondies (à ±10 m).

## Découpage proposé (`decoupage.yaml`, mission 012 : seuls les blocs d'apprentissage changent)

Test = `chaux_b`, `joux`, `altitude_b` (48 dalles, **identiques** à la mission 008, vérifié sur `decoupage.yaml`) ; apprentissage = `chaux_a`, `sapiniere_a`, `altitude_a` (mission 008) et `chenaie_c`, `sapiniere_c`, `altitude_c` (mission 012), **96 dalles**. Justification : le test est de **chaque type**, appris ailleurs sur un autre bloc, avec un vol de la même année ; le test comporte les plus grands sapins (Joux) et une forêt d'altitude (`altitude_b`, 970-1 290 m ; `altitude_c`, en apprentissage, monte plus haut, à 1 495 m), là où un modèle de hauteur est le plus exigeant (hauteurs de plus de 30 m, relief). Aucune dalle de test ne touche une dalle d'apprentissage ; les blocs de 10 km ne sont pas partagés (le découpage passe le contrôle `nemeton_canopee.decoupage`). Deux blocs par type de forêt en apprentissage depuis la mission 012 (un seul avant : le modèle ne voyait qu'un exemplaire de chaque type). Choix inverse ou 3 blocs de test seulement : à trancher.

## Manifeste (généré par le script, `MANIFESTE.md` ; surfaces BD Forêt à polygones fusionnés)

Taille de l'échantillon : 167 Mo (0.16 Gio), budget 20 Gio.

| Bloc | Rôle | Type de forêt | Coin NO (km) | Vol | Forêt (ha) | Essences BD Forêt | MNH max (m) | Part > 30 m | Scènes S2 |
|---|---|---|---|---|---|---|---|---|---|
| chaux_a | apprentissage | chênaie de plaine (forêt de Chaux), 210-260 m | 894-6668 | 2022-07-27 -> 2022-08-24 | 1577 | Chênes décidus 896 ha, Hêtre 265 ha, Feuillus 252 ha | 38.2 | 2.5% | 48 |
| chaux_b | test | chênaie de plaine (forêt de Chaux), 240-280 m | 908-6674 | 2022-07-28 -> 2022-08-25 | 1595 | Chênes décidus 1203 ha, Feuillus 118 ha, Mixte 105 ha | 36.9 | 1.4% | 48 |
| sapiniere_a | apprentissage | sapinière-hêtraie de moyenne montagne, 740-1120 m | 916-6612 | 2022-09-20 -> 2022-10-25 | 1447 | Sapin, épicéa 903 ha, Mixte 483 ha, NC 34 ha | 48.5 | 7.4% | 48 |
| joux | test | sapinière à grands arbres (forêt de la Joux), 630-870 m | 926-6646 | 2022-08-25 -> 2022-10-17 | 1490 | Sapin, épicéa 1269 ha, Mixte 207 ha, Conifères 11 ha | 49.8 | 8.6% | 48 |
| altitude_a | apprentissage | forêt d'altitude, sapin-épicéa et hêtre, 860-1090 m | 938-6636 | 2022-09-20 -> 2022-10-27 | 1171 | Mixte 563 ha, Sapin, épicéa 320 ha, Hêtre 166 ha | 44.5 | 1.7% | 48 |
| altitude_b | test | forêt d'altitude du Haut-Jura, sapin-épicéa, 970-1290 m | 934-6610 | 2022-10-05 -> 2022-10-27 | 1540 | Sapin, épicéa 1368 ha, Mixte 157 ha, NC 14 ha | 42.9 | 2.2% | 48 |
| chenaie_c | apprentissage | chênaie de plaine (Jura nord-ouest), 210-250 m | 890-6649 | 2022-08-24 -> 2022-08-24 | 1342 | Chênes décidus 915 ha, Feuillus 364 ha, NR 49 ha | 37.2 | 0.9% | 48 |
| sapiniere_c | apprentissage | sapinière-pessière de moyenne montagne (Haut-Jura sud), 620-980 m | 910-6597 | 2022-10-25 -> 2022-10-25 | 1413 | Sapin, épicéa 606 ha, Mixte 505 ha, Feuillus 299 ha | 46.9 | 2.2% | 48 |
| altitude_c | apprentissage | forêt d'altitude, sapin-épicéa, 1010-1500 m | 929-6596 | 2022-10-27 -> 2022-11-07 | 1174 | Sapin, épicéa 778 ha, Mixte 244 ha, Hêtre 79 ha | 41.6 | 1.5% | 48 |

### Bloc chaux_a (apprentissage)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0894-6665 | 2022-07-28 -> 2022-08-24 | 2023-09-04 (+390 j) | 100 | Chênes décidus 58 ha | 34.2 | 28.6 |
| 0894-6666 | 2022-07-28 -> 2022-08-24 | 2023-09-04 (+390 j) | 100 | Chênes décidus 99 ha | 33.8 | 30.4 |
| 0894-6667 | 2022-07-28 -> 2022-08-24 | 2023-09-04 (+390 j) | 100 | Chênes décidus 76 ha | 34.6 | 30.7 |
| 0894-6668 | 2022-07-28 -> 2022-08-24 | 2023-09-04 (+390 j) | 99 | Chênes décidus 92 ha | 34.2 | 30.8 |
| 0895-6665 | 2022-07-28 -> 2022-07-28 | 2023-09-04 (+403 j) | 100 | Chênes décidus 47 ha | 33.5 | 28.9 |
| 0895-6666 | 2022-07-28 -> 2022-07-28 | 2023-09-04 (+403 j) | 100 | Chênes décidus 42 ha | 34.2 | 30.2 |
| 0895-6667 | 2022-07-28 -> 2022-07-28 | 2023-09-04 (+403 j) | 99 | Feuillus 57 ha | 36.5 | 32.2 |
| 0895-6668 | 2022-07-28 -> 2022-07-28 | 2023-09-04 (+403 j) | 99 | Hêtre 71 ha | 38.2 | 33.5 |
| 0896-6665 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 100 | Chênes décidus 58 ha | 32.9 | 28.3 |
| 0896-6666 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 97 | Feuillus 34 ha | 37.5 | 30.8 |
| 0896-6667 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 100 | Hêtre 71 ha | 36.1 | 31.4 |
| 0896-6668 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 100 | Chênes décidus 44 ha | 36.2 | 30.2 |
| 0897-6665 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 98 | Chênes décidus 52 ha | 34.7 | 29.9 |
| 0897-6666 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 92 | Chênes décidus 72 ha | 35.7 | 29.5 |
| 0897-6667 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 97 | Chênes décidus 97 ha | 34.8 | 30.8 |
| 0897-6668 | 2022-07-27 -> 2022-07-28 | 2023-09-04 (+404 j) | 98 | Chênes décidus 75 ha | 34.8 | 30.2 |

### Bloc chaux_b (test)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0908-6671 | 2022-07-28 -> 2022-07-28 | 2023-09-04 (+403 j) | 100 | Chênes décidus 90 ha | 34.9 | 30.3 |
| 0908-6672 | 2022-07-28 -> 2022-07-28 | 2023-09-04 (+403 j) | 100 | Chênes décidus 92 ha | 36.9 | 31.2 |
| 0908-6673 | 2022-07-28 -> 2022-08-25 | 2023-09-04 (+389 j) | 100 | Chênes décidus 97 ha | 35.6 | 30.9 |
| 0908-6674 | 2022-07-28 -> 2022-08-25 | 2023-09-04 (+389 j) | 100 | Chênes décidus 78 ha | 34.3 | 30.5 |
| 0909-6671 | 2022-07-28 -> 2022-07-28 | 2023-09-03 (+402 j) | 100 | Pin autre 36 ha | 35.2 | 31.0 |
| 0909-6672 | 2022-07-28 -> 2022-07-28 | 2023-09-03 (+402 j) | 100 | Chênes décidus 82 ha | 34.7 | 29.6 |
| 0909-6673 | 2022-07-28 -> 2022-08-25 | 2023-09-03 (+388 j) | 100 | Chênes décidus 100 ha | 34.2 | 29.7 |
| 0909-6674 | 2022-07-28 -> 2022-08-25 | 2023-09-03 (+388 j) | 100 | Chênes décidus 100 ha | 32.0 | 28.4 |
| 0910-6671 | 2022-07-28 -> 2022-07-28 | 2023-09-07 (+406 j) | 100 | Chênes décidus 31 ha | 36.8 | 30.3 |
| 0910-6672 | 2022-07-28 -> 2022-07-28 | 2023-09-03 (+402 j) | 100 | Chênes décidus 75 ha | 32.5 | 28.9 |
| 0910-6673 | 2022-07-28 -> 2022-08-25 | 2023-09-03 (+388 j) | 100 | Chênes décidus 88 ha | 33.4 | 29.4 |
| 0910-6674 | 2022-07-28 -> 2022-08-25 | 2023-09-03 (+388 j) | 100 | Chênes décidus 87 ha | 34.1 | 29.2 |
| 0911-6671 | 2022-07-28 -> 2022-07-28 | 2023-09-07 (+406 j) | 100 | Feuillus 57 ha | 35.8 | 31.9 |
| 0911-6672 | 2022-07-28 -> 2022-07-28 | 2023-09-07 (+406 j) | 100 | Chênes décidus 69 ha | 35.0 | 29.0 |
| 0911-6673 | 2022-07-28 -> 2022-08-25 | 2023-09-03 (+388 j) | 98 | Chênes décidus 55 ha | 34.6 | 30.0 |
| 0911-6674 | 2022-07-28 -> 2022-08-25 | 2023-09-03 (+388 j) | 97 | Chênes décidus 85 ha | 32.9 | 29.3 |

### Bloc sapiniere_a (apprentissage)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0916-6609 | 2022-09-20 -> 2022-10-25 | 2023-09-04 (+332 j) | 100 | Mixte 75 ha | 46.4 | 37.4 |
| 0916-6610 | 2022-09-20 -> 2022-10-25 | 2023-09-04 (+332 j) | 100 | Sapin, épicéa 72 ha | 46.2 | 35.9 |
| 0916-6611 | 2022-09-20 -> 2022-09-20 | 2023-09-04 (+349 j) | 98 | Sapin, épicéa 97 ha | 45.0 | 33.2 |
| 0916-6612 | 2022-09-20 -> 2022-09-20 | 2023-09-04 (+349 j) | 16 | Mixte 7 ha | 36.8 | 24.7 |
| 0917-6609 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 100 | Mixte 83 ha | 46.8 | 37.4 |
| 0917-6610 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 100 | Mixte 61 ha | 48.5 | 36.5 |
| 0917-6611 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 89 | Sapin, épicéa 60 ha | 42.5 | 34.0 |
| 0917-6612 | 2022-09-20 -> 2022-09-20 | 2023-09-03 (+348 j) | 67 | NC 33 ha | 43.8 | 32.0 |
| 0918-6609 | 2022-10-25 -> 2022-10-25 | 2023-09-03 (+313 j) | 99 | Sapin, épicéa 70 ha | 46.2 | 37.0 |
| 0918-6610 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 99 | Sapin, épicéa 71 ha | 46.9 | 37.0 |
| 0918-6611 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 100 | Mixte 66 ha | 42.4 | 33.5 |
| 0918-6612 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 100 | Sapin, épicéa 97 ha | 45.6 | 36.5 |
| 0919-6609 | 2022-10-25 -> 2022-10-25 | 2023-09-03 (+313 j) | 88 | Sapin, épicéa 80 ha | 44.3 | 35.0 |
| 0919-6610 | 2022-10-25 -> 2022-10-25 | 2023-09-03 (+313 j) | 92 | Sapin, épicéa 92 ha | 44.9 | 35.6 |
| 0919-6611 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 100 | Sapin, épicéa 74 ha | 47.9 | 34.7 |
| 0919-6612 | 2022-09-20 -> 2022-10-25 | 2023-09-03 (+331 j) | 100 | Sapin, épicéa 56 ha | 47.0 | 34.5 |

### Bloc joux (test)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0926-6643 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 81 | Sapin, épicéa 78 ha | 41.7 | 34.2 |
| 0926-6644 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 78 | Sapin, épicéa 71 ha | 42.4 | 34.9 |
| 0926-6645 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 88 | Sapin, épicéa 65 ha | 45.0 | 34.8 |
| 0926-6646 | 2022-08-25 -> 2022-10-17 | 2023-09-03 (+348 j) | 76 | Sapin, épicéa 68 ha | 42.0 | 32.9 |
| 0927-6643 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 99 | Sapin, épicéa 85 ha | 45.5 | 36.1 |
| 0927-6644 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 97 | Sapin, épicéa 97 ha | 45.2 | 35.7 |
| 0927-6645 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 100 | Sapin, épicéa 95 ha | 40.3 | 34.9 |
| 0927-6646 | 2022-08-25 -> 2022-10-17 | 2023-09-03 (+348 j) | 100 | Sapin, épicéa 100 ha | 38.8 | 31.4 |
| 0928-6643 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 99 | Sapin, épicéa 86 ha | 45.1 | 35.6 |
| 0928-6644 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 98 | Sapin, épicéa 85 ha | 46.7 | 38.1 |
| 0928-6645 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 100 | Sapin, épicéa 95 ha | 45.2 | 36.2 |
| 0928-6646 | 2022-08-25 -> 2022-10-17 | 2023-09-06 (+351 j) | 100 | Sapin, épicéa 68 ha | 43.0 | 34.6 |
| 0929-6643 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 97 | Sapin, épicéa 72 ha | 49.8 | 39.3 |
| 0929-6644 | 2022-08-25 -> 2022-08-25 | 2023-09-03 (+374 j) | 79 | Mixte 40 ha | 45.2 | 37.1 |
| 0929-6645 | 2022-08-25 -> 2022-10-17 | 2023-09-03 (+348 j) | 100 | Sapin, épicéa 74 ha | 44.9 | 34.7 |
| 0929-6646 | 2022-08-25 -> 2022-10-17 | 2023-09-06 (+351 j) | 99 | Sapin, épicéa 94 ha | 44.9 | 36.6 |

### Bloc altitude_a (apprentissage)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0938-6633 | 2022-09-20 -> 2022-10-27 | 2023-09-03 (+330 j) | 60 | Sapin, épicéa 24 ha | 37.1 | 28.6 |
| 0938-6634 | 2022-09-21 -> 2022-10-17 | 2023-09-03 (+334 j) | 60 | Feuillus 27 ha | 33.4 | 26.5 |
| 0938-6635 | 2022-09-21 -> 2022-10-17 | 2023-09-03 (+334 j) | 51 | Feuillus 33 ha | 34.6 | 25.2 |
| 0938-6636 | 2022-09-21 -> 2022-10-17 | 2023-09-03 (+334 j) | 4 | Feuillus 2 ha | 30.1 | 16.7 |
| 0939-6633 | 2022-10-25 -> 2022-10-27 | 2023-09-03 (+312 j) | 100 | Mixte 52 ha | 39.7 | 31.9 |
| 0939-6634 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 88 | Hêtre 73 ha | 37.5 | 28.5 |
| 0939-6635 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 57 | Mixte 17 ha | 37.1 | 28.0 |
| 0939-6636 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 27 | Sapin, épicéa 11 ha | 38.3 | 30.0 |
| 0940-6633 | 2022-10-25 -> 2022-10-27 | 2023-09-03 (+312 j) | 88 | Mixte 60 ha | 42.1 | 33.6 |
| 0940-6634 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 82 | Mixte 32 ha | 39.9 | 32.1 |
| 0940-6635 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 84 | Mixte 41 ha | 36.7 | 28.8 |
| 0940-6636 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 84 | Mixte 47 ha | 40.0 | 31.6 |
| 0941-6633 | 2022-10-25 -> 2022-10-27 | 2023-09-03 (+312 j) | 100 | Mixte 73 ha | 43.7 | 33.6 |
| 0941-6634 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 99 | Mixte 71 ha | 41.5 | 33.0 |
| 0941-6635 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 91 | Mixte 45 ha | 43.0 | 33.2 |
| 0941-6636 | 2022-10-17 -> 2022-10-17 | 2023-09-03 (+321 j) | 95 | Mixte 80 ha | 44.5 | 32.7 |

### Bloc altitude_b (test)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0934-6607 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 98 | Sapin, épicéa 98 ha | 36.7 | 29.6 |
| 0934-6608 | 2022-10-05 -> 2022-10-27 | 2023-09-03 (+322 j) | 99 | Sapin, épicéa 99 ha | 40.2 | 30.6 |
| 0934-6609 | 2022-10-05 -> 2022-10-27 | 2023-09-03 (+322 j) | 98 | Sapin, épicéa 79 ha | 42.9 | 33.0 |
| 0934-6610 | 2022-10-05 -> 2022-10-27 | 2023-09-03 (+322 j) | 78 | Sapin, épicéa 47 ha | 40.6 | 33.3 |
| 0935-6607 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 100 | Sapin, épicéa 100 ha | 42.0 | 31.4 |
| 0935-6608 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 96 | Sapin, épicéa 96 ha | 37.6 | 30.1 |
| 0935-6609 | 2022-10-05 -> 2022-10-27 | 2023-09-03 (+322 j) | 98 | Sapin, épicéa 98 ha | 38.4 | 30.6 |
| 0935-6610 | 2022-10-05 -> 2022-10-27 | 2023-09-03 (+322 j) | 100 | Sapin, épicéa 100 ha | 41.1 | 30.9 |
| 0936-6607 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 99 | Sapin, épicéa 71 ha | 42.8 | 33.5 |
| 0936-6608 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 100 | Sapin, épicéa 100 ha | 41.0 | 31.2 |
| 0936-6609 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 100 | Sapin, épicéa 100 ha | 38.6 | 30.3 |
| 0936-6610 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 100 | Sapin, épicéa 100 ha | 41.0 | 31.5 |
| 0937-6607 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 76 | Mixte 59 ha | 40.6 | 31.0 |
| 0937-6608 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 99 | Sapin, épicéa 78 ha | 42.8 | 32.3 |
| 0937-6609 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 99 | Sapin, épicéa 99 ha | 40.1 | 30.8 |
| 0937-6610 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 100 | Sapin, épicéa 100 ha | 38.8 | 29.6 |

### Bloc chenaie_c (apprentissage)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0890-6646 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 94 | Chênes décidus 72 ha | 35.8 | 29.8 |
| 0890-6647 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 72 | Feuillus 43 ha | 32.8 | 29.3 |
| 0890-6648 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 95 | Chênes décidus 85 ha | 35.4 | 29.0 |
| 0890-6649 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 83 | Feuillus 40 ha | 35.6 | 29.0 |
| 0891-6646 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 67 | Chênes décidus 42 ha | 31.9 | 28.4 |
| 0891-6647 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 89 | Feuillus 77 ha | 34.0 | 29.8 |
| 0891-6648 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 83 | Chênes décidus 73 ha | 34.5 | 28.9 |
| 0891-6649 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 85 | Chênes décidus 77 ha | 33.9 | 29.1 |
| 0892-6646 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 74 | Feuillus 61 ha | 33.5 | 27.9 |
| 0892-6647 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 82 | Chênes décidus 66 ha | 33.9 | 30.5 |
| 0892-6648 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 91 | Chênes décidus 91 ha | 35.5 | 29.9 |
| 0892-6649 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 91 | Chênes décidus 89 ha | 34.5 | 29.5 |
| 0893-6646 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 66 | Feuillus 40 ha | 37.2 | 31.7 |
| 0893-6647 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 100 | Chênes décidus 63 ha | 35.9 | 31.4 |
| 0893-6648 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 99 | Chênes décidus 92 ha | 32.7 | 28.7 |
| 0893-6649 | 2022-08-24 -> 2022-08-24 | 2023-09-20 (+392 j) | 71 | Chênes décidus 59 ha | 32.9 | 29.0 |

### Bloc sapiniere_c (apprentissage)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0910-6594 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 95 | Feuillus 66 ha | 42.9 | 30.8 |
| 0910-6595 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 80 | Feuillus 43 ha | 38.6 | 26.3 |
| 0910-6596 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 97 | Mixte 48 ha | 39.6 | 27.3 |
| 0910-6597 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 97 | Mixte 67 ha | 43.8 | 34.5 |
| 0911-6594 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 99 | Sapin, épicéa 49 ha | 45.6 | 36.4 |
| 0911-6595 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 86 | Sapin, épicéa 36 ha | 46.9 | 32.3 |
| 0911-6596 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 100 | Mixte 90 ha | 42.1 | 29.5 |
| 0911-6597 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 100 | Mixte 78 ha | 42.6 | 32.8 |
| 0912-6594 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 99 | Sapin, épicéa 81 ha | 39.1 | 31.5 |
| 0912-6595 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 100 | Sapin, épicéa 100 ha | 40.4 | 31.7 |
| 0912-6596 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 51 | Sapin, épicéa 37 ha | 42.2 | 30.1 |
| 0912-6597 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 84 | Sapin, épicéa 44 ha | 41.1 | 32.8 |
| 0913-6594 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 90 | Feuillus 52 ha | 40.9 | 31.8 |
| 0913-6595 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 87 | Sapin, épicéa 68 ha | 41.3 | 31.0 |
| 0913-6596 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 78 | Sapin, épicéa 64 ha | 37.9 | 29.5 |
| 0913-6597 | 2022-10-25 -> 2022-10-25 | 2023-09-04 (+314 j) | 71 | Sapin, épicéa 39 ha | 41.4 | 30.7 |

### Bloc altitude_c (apprentissage)

| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) | Essence dominante | MNH max | MNH p99 |
|---|---|---|---|---|---|---|
| 0929-6593 | 2022-10-27 -> 2022-11-07 | 2023-09-03 (+306 j) | 81 | Sapin, épicéa 57 ha | 38.9 | 30.5 |
| 0929-6594 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 20 | Sapin, épicéa 9 ha | 36.2 | 27.1 |
| 0929-6595 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 47 | Sapin, épicéa 25 ha | 37.2 | 30.0 |
| 0929-6596 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 91 | Sapin, épicéa 59 ha | 39.2 | 32.4 |
| 0930-6593 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 75 | Mixte 40 ha | 37.1 | 28.6 |
| 0930-6594 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 78 | Sapin, épicéa 47 ha | 37.2 | 28.7 |
| 0930-6595 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 41 | Sapin, épicéa 29 ha | 37.3 | 29.9 |
| 0930-6596 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 67 | Sapin, épicéa 52 ha | 41.5 | 32.7 |
| 0931-6593 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 71 | Hêtre 30 ha | 37.9 | 29.8 |
| 0931-6594 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 99 | Sapin, épicéa 40 ha | 39.8 | 29.4 |
| 0931-6595 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 96 | Sapin, épicéa 95 ha | 37.8 | 30.6 |
| 0931-6596 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 76 | Sapin, épicéa 68 ha | 41.6 | 32.1 |
| 0932-6593 | 2022-10-27 -> 2022-11-07 | 2024-08-06 (+644 j) | 37 | Hêtre 21 ha | 38.8 | 28.9 |
| 0932-6594 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 96 | Sapin, épicéa 53 ha | 39.6 | 31.2 |
| 0932-6595 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 100 | Sapin, épicéa 86 ha | 39.4 | 30.6 |
| 0932-6596 | 2022-10-27 -> 2022-10-27 | 2023-09-03 (+311 j) | 98 | Sapin, épicéa 98 ha | 40.5 | 32.5 |

## À vérifier ou à savoir

- **Dates de vol** : une seule source (WFS IGN), contrôle croisé TerraLab non fait (comme `docs/referentiels.md` § 9). Les vols des blocs d'altitude et de `sapiniere_a` vont de septembre à fin octobre 2022 alors que les scènes Sentinel-2 vont de juin à août : l'appariement se fait à l'année de vol (règle du projet), pas au mois ; les dalles d'altitude ont un feuillage d'été sur l'image et un MNH d'automne.
- **BD Forêt** : pas de date par polygone ; l'essence peut dater de l'inventaire départemental. Les essences ci-dessus sont celles de la BD Forêt, pas une mesure.
- **MNH maximal** : des valeurs élevées isolées (jusqu'à 81 m sur des GetMap grossiers du Haut-Jura, repérés avant fabrication) peuvent être des artefacts (pylônes, grues, éoliennes) ; le maximum à 2 m les conserve, comme au jeu d'essai. Non vérifié sur le terrain.
- **FORMS-T v1** : lu par fenêtre `/vsicurl/` sur Zenodo, sans compte ; hauteur 2022 pour les 96 dalles (aucune dalle hors 2018-2024).
- **Ortho** : une seule source pour la date (graphe de mosaïquage du WFS IGN, pas de contrôle croisé) ; seuils d'ombre et de non-végétal provisoires, sans vérité terrain ; la date de l'ortho est postérieure au vol LiDAR de 10 à 21 mois (voir la section ci-dessus) ; la dalle `0932-6593` est à l'Ain avec une ortho de 2024. `docs/referentiels.md` § 4 et § 9 (point 7) parlent encore d'une page de dates « non lue » : le graphe de mosaïquage la remplace, à mettre à jour hors de cette mission.
- **Pré-entraînement** : les blocs de test ne doivent pas être vus par un pré-entraînement (Open-Canopy compris) ; non vérifié ici (CLAUDE.md).
