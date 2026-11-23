# Référentiels du jalon 1

- **Propriétaire :** Pascal · **Rédigé par :** `acquereur` (mission 001) · **Date de consultation de toutes les sources : 22 novembre 2026**
- **Statut :** rendu à relire (`relecteur`, puis Pascal). Aucune valeur n'est reprise de mémoire : chaque URL ci-dessous a été appelée le 22/11/2026 (méthode : `curl` et `urllib` en lecture seule) ; ce qui n'a pas pu l'être est dans le § 9.
- **Question de contrôle :** quelle décision cette donnée va-t-elle éclairer ? → *la grille commune, le manifeste des dalles, le jeu d'essai de 4 dalles (mission 002) et la validation STAC hors ligne (mission 004).*

Rappel : une nomenclature tenue par l'IGN n'est pas recopiée ici (on ne donne que la forme et la manière de l'interroger) ; la liste des dalles disponibles se lit dans la couche WFS (§ 3).

## 1. Grille et nomenclature des dalles LiDAR HD 1 km

Source : couche WFS `IGNF_LIDAR-HD_METADONNEE:metadata` (champs `coordonnees_nw`, `url_mnh`, `url_mnt`, `url_npl`), lue le 22/11/2026 ; fiche data.gouv.fr « MNH LiDAR HD » (`https://www.data.gouv.fr/api/1/datasets/mnh-lidar-hd/`, licence `lov2`, dernière modification 2026-09-30).

| Élément | Valeur observée |
|---|---|
| Projection | Lambert-93, EPSG:2154 (axes Easting, Northing) |
| Dalle | carré de 1 km × 1 km, pas de 0,50 m, 2000 × 2000 pixels |
| Identifiant (champ `coordonnees_nw`) | `XXXX-YYYY` : coin **nord-ouest** de la dalle, en km, 4 chiffres chacun (x = abscisse minimale, y = ordonnée maximale). Exemple : `0901-6665` couvre x de 901 000 à 902 000 m et y de 6 664 000 à 6 665 000 m |
| Nom de fichier MNH | `LHD_FXX_<XXXX>_<YYYY>_MNH_O_0M50_LAMB93_IGN69.tif` (ex. `LHD_FXX_0901_6665_MNH_O_0M50_LAMB93_IGN69.tif`) |
| Nom de fichier MNT / MNS | idem avec `MNT` / `MNS` à la place de `MNH` |
| Nom de fichier nuage de points | `LHD_FXX_<XXXX>_<YYYY>_PTS_LAMB93_IGN69.copc.laz` |
| Type de pixel (GetMap `image/geotiff`) | float32, **nodata = -9999**, mètres (MNH : hauteur au-dessus du sol ; MNT : altitude IGN69) |
| Géoréférencement du GeoTIFF reçu | origine (haut-gauche) = (x_min − 0,25 ; y_max + 0,25), pixel 0,5 m : les **nœuds** (centres de pixel) tombent sur des coordonnées entières, comme l'écrit la fiche data.gouv (« valeurs métriques entières »). Mesuré avec rasterio sur les 8 rasters téléchargés (MNH et MNT des 4 dalles) |

Point à décider (non tranché ici) : l'écart de 0,25 m entre l'emprise nominale de 1 km et l'emprise du raster demande une convention d'alignement explicite pour la grille 10 m (ADR ou spec).

## 2. Accès programmatique au MNH et au MNT

Testé le 22/11/2026, sans authentification.

| Moyen | URL / couche | Résultat |
|---|---|---|
| **WMS-R GetMap (retenu)** | `https://data.geopf.fr/wms-r` · couches `IGNF_LIDAR-HD_MNH_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93` et `IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93` · `FORMAT=image/geotiff` | HTTP 200, 16 000 513 octets, 2000 × 2000 float32, sur les 4 dalles proposées (MNH et MNT) |
| Capabilities WMS-R | `https://data.geopf.fr/wms-r/wms?SERVICE=WMS&REQUEST=GetCapabilities` | 200. Formats GetMap annoncés : `image/jpeg`, `image/png`, `image/tiff`, `image/geotiff`, `image/x-bil;bits=32` |
| WMTS (visuel seulement) | `IGNF_LIDAR-HD_MNH_ELEVATION.ELEVATIONGRIDCOVERAGE.SHADOW` | ombrage, pas de valeur de hauteur : inutilisable comme cible |
| WCS | `https://data.geopf.fr/wcs`, `/wcs/ows`, `/private/wcs`, `/wcs-r` | **404** ; `/wms-r/wcs` répond 400. Pas de WCS public trouvé |
| Téléchargement de dalles | `https://data.geopf.fr/telechargement/capabilities` | 200 mais n'annonce aucun jeu MNH/MNT LiDAR HD (seul `ACCESSIBILITE-PHYSIQUE-FORETS` ressort de la recherche « lidar/mnh/forêt ») ; la fiche data.gouv cite aussi une couche `IGNF_MNH_LIDAR-HD:dalle` : **absente** de la capabilities WFS du 22/11 (requête → 400) |

Requête type pour une dalle (copiée du champ `url_mnh` de la couche de métadonnées, qui est la forme officielle IGN) :

```
https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&EXCEPTIONS=text/xml&REQUEST=GetMap
 &LAYERS=IGNF_LIDAR-HD_MNH_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93&FORMAT=image/geotiff&STYLES=
 &CRS=EPSG:2154&BBOX=900999.75,6664000.25,901999.75,6665000.25&WIDTH=2000&HEIGHT=2000
```

BBOX = (x_min − 0,25 ; y_max − 1000 + 0,25 ; x_min + 1000 − 0,25 ; y_max + 0,25) pour une dalle `XXXX-YYYY` (x_min = XXXX × 1000, y_max = YYYY × 1000). Pour 0,5 m, WIDTH = HEIGHT = 2000. Une emprise plus grande que la dalle n'a pas été testée.

Limites dites : le MNH est un produit **dérivé** (MNS − MNT) ; la fiche data.gouv signale des zones interdites à la captation aérienne (ZICAD) sans données (valeur nodata). Les 8 rasters téléchargés ne contenaient aucun pixel nodata. Le MNH contient de petites valeurs négatives (minimum −0,29 m) : le passage en uint16 (cm) devra les borner (règle à écrire dans la spec, non tranchée ici).

## 3. Date de vol d'une dalle

Source : WFS `https://data.geopf.fr/wfs/ows`, couche `IGNF_LIDAR-HD_METADONNEE:metadata` (une entité par dalle, géométrie polygonale en WGS84 par défaut).

Champs lus (DescribeFeatureType du 22/11/2026) : `capteur`, `url_mnh`, `url_mns`, `url_mnt`, `url_npl`, `code_mission`, `date_edition`, `nombre_points`, `coordonnees_nw`, `moa_acquisition`, `moe_acquisition`, `procede_classement`, `date_fin_acquisition`, `systeme_altimetrique`, `moe_classement_manuel`, `systeme_planimetrique`, `date_debut_acquisition`, `moe_classement_automatique`, `geom`.

- **Date de vol** = `date_debut_acquisition` et `date_fin_acquisition` (type date, rendue avec suffixe `Z`, ex. `2022-07-27Z`). Une dalle peut avoir un début et une fin différents (observé dans la zone de Chaux : `2022-07-27` → `2022-10-17` sur certaines dalles). Le manifeste stockera donc les deux dates.
- `date_edition` est la date de publication de la donnée, **pas** la date de vol (ex. 2025-07-17 pour un vol du 2022-07-27).
- Requête (testée) :
  `https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=IGNF_LIDAR-HD_METADONNEE:metadata&OUTPUTFORMAT=application/json&COUNT=5&CQL_FILTER=BBOX(geom,x1,y1,x2,y2,'EPSG:2154')`
  Un filtre par emprise fonctionne ; un filtre d'égalité sur `coordonnees_nw` a échoué (réponse non JSON) : utiliser l'emprise du centre de la dalle.
- Contrôle croisé prévu (carte TerraLab des dates de vol) : **non fait**, voir § 9.

## 4. BD Forêt V2 et BD ORTHO

| Donnée | Accès testé | Couche | Remarque |
|---|---|---|---|
| BD Forêt V2, vecteur | WFS `https://data.geopf.fr/wfs/ows` (GetFeature, JSON, `srsName=EPSG:2154` accepté) | `LANDCOVER.FORESTINVENTORY.V2:formation_vegetale` | Champs : `id`, `code_tfv`, `tfv`, `tfv_g11`, `essence`, `geom`. Titre de la couche : « BD Forêt v2 (2006-2019) ». Pas de champ de date par polygone : l'essence peut dater de l'inventaire départemental (non vérifié) |
| BD Forêt V2, image | WMS-R `https://data.geopf.fr/wms-r/wms` | `LANDCOVER.FORESTINVENTORY.V2` | GetMap PNG 200 |
| BD ORTHO 20 cm RVB | WMS-R, GetMap PNG 200 | `HR.ORTHOIMAGERY.ORTHOPHOTOS` (la capabilities lui donne le titre « BD ORTHO® IRC 20 cm » mais l'image reçue est identique, octet pour octet en taille, à celle de `ORTHOIMAGERY.ORTHOPHOTOS.BDORTHO` : à vérifier visuellement par la mission 002) | dates de prise de vue : page citée par la capabilities (`https://data.geopf.fr/annexes/ressources/fiches/photographies-aeriennes…`), non lue |
| BD ORTHO 50 cm | WMS-R | `ORTHOIMAGERY.ORTHOPHOTOS.BDORTHO` | 200 |
| BD ORTHO IRC 20 cm | WMS-R | `ORTHOIMAGERY.ORTHOPHOTOS.IRC` | 200 ; couches millésimées `ORTHOIMAGERY.ORTHOPHOTOS.IRC.<année>` (2012 à 2024) |

Exemple WFS BD Forêt sur une dalle : `CQL_FILTER=BBOX(geom,901000,6664000,902000,6665000,'EPSG:2154')`.

## 5. Sentinel-2 L2A et Sentinel-1 : catalogues STAC sans authentification

| Catalogue | Recherche anonyme | Téléchargement anonyme des assets | Observé |
|---|---|---|---|
| **Earth Search (Element84)** `https://earth-search.aws.element84.com/v1` | oui (`POST /search`) | **Sentinel-2 L2A : oui.** Assets en HTTPS public (`https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/…/B04.tif`), COG ; requête `Range` → 206. **Sentinel-1 GRD : oui à l'essai, avec réserve.** Les assets sont en `s3://sentinel-s1-l1c/…` ; en HTTPS (`https://sentinel-s1-l1c.s3.eu-central-1.amazonaws.com/…`) une requête `Range` a reçu 206 (fichier de 700 768 103 octets), alors que la collection déclare `storage:requester_pays = true` | collections présentes : `sentinel-2-l2a`, `sentinel-2-c1-l2a`, `sentinel-2-pre-c1-l2a`, `sentinel-2-l1c`, `sentinel-1-grd` (+ `cop-dem-glo-30/90`, `naip`, `landsat-c2-l2`) |
| **Copernicus Data Space (CDSE)** `https://stac.dataspace.copernicus.eu/v1` | oui (collections `sentinel-2-l2a`, `sentinel-1-grd`) | **non** : l'asset HTTPS `download.dataspace.copernicus.eu/odata/v1/Products(...)/$value` répond **401** (« Token not found ») ; les assets S3 (`s3://eodata/…`) demandent des clés S3 | jeton OIDC ou clés S3 nécessaires |

Détails Earth Search `sentinel-2-l2a`, testés sur l'emprise de la dalle `0901-6665` pour mai à septembre 2022 : 126 scènes (tuiles MGRS 31TFN et 31TGN), 100 renvoyées par page (pagination à suivre), `s2:processing_baseline` valant `04.00` ou `05.11` selon la scène, `earthsearch:boa_offset_applied = true`. Le mélange de lignes de base de traitement est à connaître avant le jeu figé. Ces valeurs sont celles de la requête du 22/11 et peuvent changer si le catalogue est retraité.

Détails Sentinel-1 : collection `sentinel-1-grd`, polarisations VV et VH présentes, 2022-07-30 trouvé sur la zone. Les fichiers GRD pèsent environ 700 Mo : le jeu d'essai devra en découper un extrait.

Choix proposé pour la mission 002 (à confirmer par Pascal) : Earth Search pour Sentinel-2 (téléchargement anonyme sûr) ; pour Sentinel-1, Earth Search tant que l'accès anonyme tient, avec la réserve ci-dessus.

## 6. Mentions de licence

| Source | Mention | Texte de référence |
|---|---|---|
| Données IGN (MNH, MNT, BD Forêt V2, BD ORTHO) | **Licence Ouverte 2.0** (Etalab) ; la fiche data.gouv du MNH la déclare (`license: lov2`). Condition : mentionner la source (au moins le nom du concédant) et la date de dernière mise à jour | `https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf` (lu le 22/11/2026, redirigé vers `static.data.gouv.fr/resources/licence-ouverte-2-0/20260909-072646/etalab-licence-ouverte-v2.0.pdf`), rubrique « Sous réserve de : mentionner la paternité de l'Information » |
| Sentinel-1 et Sentinel-2 | **« Contains modified Copernicus Sentinel data [année] »** quand les données sont adaptées ou modifiées (c'est notre cas) ; « Copernicus Sentinel data [année] » si elles sont diffusées telles quelles. L'année est celle de l'acquisition | « Legal notice on the use of Copernicus Sentinel Data and Service Information », `https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice` (PDF lu le 22/11/2026), qui renvoie à l'article 8 du règlement délégué (UE) n° 1159/2013 et au règlement (UE) n° 377/2014. Le lien affiché par les catalogues, `sentinel.esa.int/...`, ne répondait pas (code 000) : utiliser `sentinels.copernicus.eu` |
| FORMS-T v1 | CC BY 4.0 (indiqué dans le brief ; non rouvert ici) | brief |

Les deux catalogues déclarent `license: proprietary` (Earth Search) ou `other` (CDSE) avec ce même lien : la valeur STAC `license` du catalogue du projet reste à fixer avec l'ADR 0003.

## 7. Convention nodata

Rappel de la spec (§ 2) : hauteur en uint16 en centimètres, **nodata = 65535** (0 est une hauteur valide). À ne pas confondre avec le nodata **−9999** (float32) des rasters sources MNH et MNT reçus de l'IGN (§ 1).

## 8. Proposition de 4 dalles pour le jeu d'essai

Critères : forêt, Bourgogne-Franche-Comté (code région 27), MNH LiDAR HD publié, deux paires de dalles voisines (bord commun), paires distantes de plus de 10 km. Cette liste est une **proposition** : le choix revient à l'orchestrateur par délégation, puis à Pascal sur le terrain.

| Paire | Dalle | Emprise Lambert-93 (m) | Commune (centre) | Date de vol (début → fin) | Mission | Essence dominante BD Forêt V2 (surface sur la dalle) | MNH vérifié |
|---|---|---|---|---|---|---|---|
| A | `0901-6665` | x 901 000–902 000, y 6 664 000–6 665 000 | Santans (39), forêt de Chaux | 2022-07-27 → 2022-07-27 | 22LHD2PI | Chênes décidus 94,9 ha ; pin sylvestre 5,1 ha (forêt fermée sur 100 ha) | oui |
| A | `0902-6665` | x 902 000–903 000, y 6 664 000–6 665 000 | Santans (39) | 2022-07-27 → 2022-07-27 | 22LHD2PI | Chênes décidus 99,3 ha ; mixte 0,7 ha | oui |
| B | `0939-6654` | x 939 000–940 000, y 6 653 000–6 654 000 | Chapelle-d'Huin (25), forêt de Levier | 2022-10-17 → 2022-10-17 | 22LHD2QI | Sapin-épicéa 83,1 ha ; mixte 13,2 ha (forêt fermée sur 97,9 ha) | oui |
| B | `0939-6655` | x 939 000–940 000, y 6 654 000–6 655 000 | Chapelle-d'Huin (25) | 2022-10-17 → 2022-10-17 | 22LHD2QI | Sapin-épicéa 86,4 ha ; forêt fermée sans couvert arboré 9,3 ha | oui |

- **Bords communs** : A partage x = 902 000 m ; B partage y = 6 654 000 m. Distance entre paires : environ 36 km (bord est de A à 903 000 m, bord ouest de B à 939 000 m), très au-delà de 10 km.
- **Vérification de l'existence du MNH** : GetMap MNH et MNT (§ 2) rendu pour chacune des 4 dalles, HTTP 200, 2000 × 2000 float32, EPSG:2154, nodata −9999, aucun pixel nodata. MNH moyen / maximum (m) : 0901-6665 : 19,67 / 33,11 ; 0902-6665 : 16,17 / 33,63 ; 0939-6654 : 17,72 / 48,88 ; 0939-6655 : 14,91 / 46,30. Entité de métadonnées trouvée pour chacune (§ 3), avec `procede_classement = IGN_AUTO_V5`.
- **Même année de vol pour les 4 dalles (2022)** : l'appariement Sentinel se fait sur 2022 (mai à septembre : 126 scènes S2 trouvées sur A). Vol du 27 juillet (A) et du 17 octobre (B) : B est tardif pour un feuillage d'été, mais la dalle est résineuse.
- **Deux peuplements différents** (feuillus de plaine à 240 m, résineux de moyenne montagne à 800 m environ d'après le MNT) : la chaîne ne se teste pas sur un seul régime.
- **Découpage de test** (spec § 4, critère 6) : une paire pour l'apprentissage, l'autre pour le test ; le fichier `decoupage.yaml` revient à la mission 002.

## 9. Ce qui n'a pas pu être vérifié, ou n'est pas accessible

1. **Contrôle croisé des dates de vol** : la carte TerraLab n'a pas été consultée (application cartographique non interrogeable par `curl`). Les dates du § 8 reposent sur **une seule source** (couche WFS IGN). À faire par Pascal ou le `relecteur` avant gel du jeu.
2. **Pas de WCS** et pas de téléchargement de dalle MNH par le service de téléchargement : seul le GetMap WMS-R a été trouvé. Les dalles livrées sont des rendus de ce service (float32, pas la dalle brute éventuelle de l'IGN) ; l'égalité avec la dalle téléchargeable du portail data.gouv n'a pas été contrôlée.
3. **Emprise supérieure à une dalle** pour le GetMap : non testée.
4. **Sentinel-1 anonyme** : le 206 sur `sentinel-s1-l1c` contredit `requester_pays = true` ; à retester avant de s'y appuyer (autre jour, autre réseau).
5. **Date de la BD Forêt V2 par polygone** : non fournie par la couche ; l'écart possible avec le vol 2022 n'est pas mesuré.
6. **Essence dominante** : une seule source (BD Forêt V2). Pas de seconde source indépendante (par exemple l'inventaire forestier) consultée.
7. **Dates de prise de vue de l'ortho** : page de dates citée par la capabilities, non lue.
8. **Définition du volume, biomasse, sylvoécorégions, allométrie** : hors de cette mission (ADR 0002 et missions suivantes).

### Trois points au sol (à vérifier par Pascal)

1. Dalle `0939-6655` : 9,3 ha classés « forêt fermée sans couvert arboré » par la BD Forêt, alors que le MNH y est de 14,9 m en moyenne : coupe récente, ou BD Forêt ancienne ?
2. Dalles `0939-6654` et `0939-6655` : MNH maximal de 48,9 m et 46,3 m sous résineux de moyenne montagne, valeur élevée à confirmer (arbre remarquable, pylône ou artefact du MNS).
3. Dalle `0901-6665` : la BD Forêt compte 5,1 ha de pin sylvestre dans une forêt de chênes de Chaux : plantation réelle ou erreur de classement ?

## 10. Journal d'accès (URL réellement appelées le 22/11/2026)

`https://data.geopf.fr/wms-r/wms?SERVICE=WMS&REQUEST=GetCapabilities` (200) · `https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities` (200) · `https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetCapabilities` (200) · WFS DescribeFeatureType et GetFeature sur `IGNF_LIDAR-HD_METADONNEE:metadata` et `LANDCOVER.FORESTINVENTORY.V2:formation_vegetale` · WMS-R GetMap MNH, MNT, BDORTHO, IRC, BD Forêt · `https://data.geopf.fr/telechargement/capabilities` · `https://www.data.gouv.fr/api/1/datasets/mnh-lidar-hd/` · `https://geo.api.gouv.fr/communes` (commune et département des dalles) · `https://earth-search.aws.element84.com/v1` (collections, search, `sentinel-cogs` et `sentinel-s1-l1c` en Range) · `https://stac.dataspace.copernicus.eu/v1` (collections, search, téléchargement → 401) · notice Copernicus et Licence Ouverte 2.0 (PDF) · `https://stac-extensions.github.io/<extension>/<version>/schema.json` (voir `conf/stac-schemas/README.md`).

## 11. Références à battre : accès à FORMS-T v1 et à FORMSpoT (mission 006)

Consulté le 22/11/2026 par l'`acquereur`, propriétaire Pascal. Pourquoi : permettre au jalon 2 de comparer le modèle du projet à FORMS-T v1 et FORMSpoT sur les 4 dalles d'essai, à périmètre égal. Tous les chiffres « mesuré » viennent de lectures réellement faites le 22/11/2026 ; les dalles sont celles du § 8 (vol 2022, coin NO en km, donc `0939-6654` = x 939 000–940 000, y 6 653 000–6 654 000).

### 11.1 FORMS-T v1 (Zenodo 15489231, DOI 10.5281/zenodo.15489231)

**Source** : `https://zenodo.org/api/records/15489231` (HTTP 200), publié le 2025-06-06 ; article associé DOI 10.1016/j.rse.2025.114959 (non lu : la page éditeur redirige, voir 11.5). **Licence** : `cc-by-4.0` (champ `license.id` de l'API Zenodo, `access_right = open`). Le catalogue STAC indique `license: other` ; la licence Zenodo prévaut, à confirmer par Pascal si usage commercial.

**Fichiers (22 .tif + 1 PNG), un par année 2018–2024** :

| Variable | Fichiers | Taille unitaire | Résolution | Unité (Zenodo) |
|---|---|---|---|---|
| Hauteur | `Height_2018.tif` … `Height_2024.tif` (7) | 6,24 à 6,42 Go (`Height_2022.tif` : 6 284 638 728 o) | 10 m | centimètres |
| Volume (« WVD », wood volume density) | `WVD_2018.tif` … `WVD_2024.tif` (7) | 0,359 à 0,361 Go (`WVD_2022.tif` : 359 591 011 o) | 30 m | m³/ha |
| Biomasse aérienne (« AGBD ») | `AGBD_2018.tif` … `AGBD_2024.tif` (7) | 0,342 à 0,344 Go (`AGBD_2022.tif` : 342 936 872 o) | 30 m | Mg/ha |
| (aperçu) | `Height_map_preview.png` (3 802 285 o) | | | |

Décompte : 7 + 7 + 7 = 21 rasters (les 21 années-variables), plus l'aperçu. Les 21 rasters sont listés dans le JSON de l'API.

**Format (mesuré par `rasterio` 1.5.2 sur `/vsicurl/`)** : GeoTIFF **tuilé 256 × 256, compression deflate, sans vues d'ensemble (`overviews = []`)**, EPSG:2154, **int16, nodata = 0**, échelle 1, décalage 0.
- Hauteur : pas 10 m, 111 000 × 120 000 pixels, emprise x 75 730–1 275 730, y 6 005 080–7 115 080.
- WVD et AGBD : pas 30 m, 40 000 × 40 000 pixels, emprise x 75 730–1 275 730, y 5 915 080–7 115 080.
- Le STAC (11.1 bis) annonce les mêmes valeurs (scale 1, offset 0, nodata 0, int16) et, pour 2022, des statistiques nationales : hauteur moyenne 788,8 cm, max 3 959 ; WVD moyenne 109,1 (min 1, max 799) ; AGBD moyenne 85,0 (min 1, max 381).

**Alignement sur la grille du projet** : l'origine est x = 75 730 m, y = 7 115 080 m. Pour la hauteur à 10 m, les bords de dalle de 1 km tombent sur des pixels entiers (fenêtre 100 × 100 px pour les 4 dalles, décalage de colonne entier). Pour WVD et AGBD à 30 m, **1 km n'est pas un multiple de 30 m et l'origine décale** : la fenêtre vaut 33,33 px, avec un décalage fractionnaire (par exemple colonne 28 775,67 pour `0939-6654`) ; la lecture de 33 × 33 pixels n'est donc pas alignée sur la dalle et il faut rééchantillonner (voir recette).

**Lecture partielle : testée, fonctionne sans compte.**
- `curl -r 0-1023 https://zenodo.org/api/records/15489231/files/Height_2022.tif/content` : **HTTP 206**, `content-range: bytes 0-1023/6284638728`, `accept-ranges: bytes`, 1 024 o en 0,47 s.
- `rasterio.open('/vsicurl/https://zenodo.org/api/records/15489231/files/Height_2022.tif/content')` : ouverture 4,4 s la première fois (1,2 à 1,5 s ensuite) ; lecture de la fenêtre de la dalle `0939-6654` (100 × 100 px) en environ 1 s de plus (total 5,2 s la première fois, 1,8 s la seconde). **Volume transféré mesuré (journal GDAL, 5 requêtes 206)** : 163 840 o pour la hauteur ; 131 072 o pour AGBD (5 requêtes aussi). Soit environ 0,16 Mo contre 6,3 Go pour le fichier entier.
- Les 4 dalles lues sur les 3 variables 2022 (12 lectures, aucune erreur). Moyenne des pixels > 0 :

| Dalle | Hauteur FORMS-T (m) | max (m) | WVD (m³/ha) | AGBD (Mg/ha) | Pixels nodata (WVD) |
|---|---|---|---|---|---|
| `0901-6665` | 25,72 | 30,09 | 267,5 | 216,2 | 0 % |
| `0902-6665` | 20,98 | 29,88 | 206,2 | 171,0 | 0,5 % |
| `0939-6654` | 26,40 | 37,79 | 394,1 | 208,5 | 0,4 % |
| `0939-6655` | 22,98 | 36,89 | 329,3 | 176,3 | 0,6 % |

- **Limite** : Zenodo impose un quota (en-têtes `x-ratelimit-limit: 133`, `retry-after: 60`) ; une lecture par fenêtre est largement dans la limite, mais une boucle sur des centaines de dalles demandera d'attendre ou de passer par le STAC. Zenodo est un point d'accès unique : pour la chaîne de test hors réseau, il faut figer des extraits dans le dépôt.
- **Écart à noter, pas tranché** : la moyenne de hauteur FORMS-T sur la dalle `0939-6654` (26,4 m) est bien supérieure à la moyenne MNH LiDAR HD du § 8 (17,72 m), et celle de `0901-6665` (25,7 m) à 19,67 m. Les deux moyennes ne portent pas sur le même ensemble de pixels (le MNH du § 8 inclut tout pixel, la mienne exclut les 0) et FORMS-T Zenodo (`Height_2022.tif`) n'est pas forcément le même fichier que `Height_mavg_2022.tif` du STAC (voir 11.1 bis). Le jalon 2 devra mesurer l'écart pixel à pixel avant toute conclusion.

**Définition du volume.** Pour FORMS-T v1, **non établie** : l'article RSE (10.1016/j.rse.2025.114959) n'a pas pu être lu (la page éditeur renvoie une redirection, aucun texte intégral accessible). Zenodo dit seulement « Wood volume map at 30 m resolution (WVD files). Units are in cubic meters per hectare » et « FORMS-T Growing Stock Volume ». Pour le prédécesseur FORMS (ESSD 2023, `https://essd.copernicus.org/articles/15/4927/2023/essd-15-4927-2023.html`, Zenodo 7840108) : « the main stem's volume of up to 7 cm diameter », arbres inventoriés à partir de « 7.5 cm DBH », sur/sous écorce non précisé ; biomasse = volume × « 0.59 Mg m−3 » (conifères) et « 0.89 Mg m−3 » (feuillus), soit facteur d'expansion 1,34 / 1,61 × densité 0,44 / 0,55 (CARBOFOR, Loustau 2010) ; R² 0,63 et MAE 30 m³/ha à l'échelle de l'écorégion. **On ne peut pas supposer que FORMS-T v1 reprend cette définition.** Comparaison avec l'ADR 0002 : à instruire par Pascal (comparer avec la définition de `docs/adr/0002-definition-du-volume.md`, non relue ici).

### 11.1 bis FORMS-T via le STAC (second accès)

`https://api.stac.teledetection.fr/collections/forms-t` (200) et `.../items/FORMS-T-2022` (200) : lisibles sans compte. Un item par année (`FORMS-T-2018` … `-2024`), trois actifs `height`, `agbd`, `wvd`. **Les liens de données (`https://s3-data.meso.umontpellier.fr/sm1-gdc-ext/forms-t/...`) répondent 403 sans jeton** (testé : `Height_mavg_2022.tif`, 403 en 224 o). Le jeton s'obtient en ouvrant un compte Data Terra (connexion ORCID) puis `tld apikey register` (bibliothèque `teledetection`) : **compte gratuit requis**, non créé ici, non testé. Le fichier de hauteur du STAC s'appelle `Height_mavg_2022.tif` (« mavg » : probablement moyenne glissante, **non confirmé**) alors que Zenodo livre `Height_2022.tif` : l'identité des deux fichiers n'est pas établie. Contact producteur : Martin Schwartz (LSCE), cité dans les métadonnées de la collection. DOI de la collection STAC : 10.71961/0ts1-zz77.

### 11.2 FORMSpoT (THEIA, DOI 10.71961/F879-K244 ; article RSE 346, 115631 ; Zenodo 22111200)

**Zenodo 22111200 ne contient pas les données** : un seul fichier, `1-s2.0-S0034425726004013-main.pdf` (8 569 179 o), l'article (`cc-by-4.0`, publié le 2026-08-26, DOI 10.1016/j.rse.2026.115631). Aucun raster. **Source des données** : `https://doi.theia.data-terra.org/FORMSpoT/` (200), diffusion par le STAC `https://api.datastore-mtd.theia.data-terra.org/collections/FORMSpoT` (200, lisible sans compte).

**Licence des données : CC-BY-NC 4.0** (« Creative Commons Attribution Non Commercial 4.0 International », page THEIA) : **usage non commercial seulement** ; l'article, lui, est CC-BY. Cette restriction touche l'usage par Nemeton si celui-ci est commercial : à faire trancher par Pascal.

**Contenu** : 11 items, `FORMSpoT-2014` … `FORMSpoT-2024` (liste STAC, 11 identifiants). Actif `height_<année>` = `https://s3-data.meso.umontpellier.fr/sm1-gdc-ext/FORMSpoT/<année>/full_<année>.vrt` (**un VRT, pas un COG unique**). Résolution 1,5 m, EPSG:2154, grille 768 000 × 720 000 px, emprise x 99 000–1 251 000, y 6 046 000–7 126 000, origine (99 000 ; 7 126 000). **uint16, nodata 65 535**, unité **décimètres** (« Units: decimeters (0.1 m) »), échelle 1. Volume annoncé : environ 160 Go par année (notebook THEIA). Statistiques STAC 2022 : moyenne 48,3, max 511. Le titiler public rapporte `overviews: [2,4,…,2048]`, `dtype uint16`, `nodata_value 65535`. Produit complémentaire FORMSpoT-Δ (polygones de perturbation, hors périmètre ici). Pas de biomasse ni de volume : **hauteur seulement**. Précision publiée (article, RSE) : MAE 3,85 m contre l'inventaire forestier, 3,54 m contre les MNH LiDAR (texte de l'article, § 5.1.1).

**Accès par fenêtre : par la voie officielle, un compte est exigé.** Les URL S3 répondent **403 sans jeton** (testé : `full_2022.vrt`, 403). Le notebook THEIA prescrit `tld apikey register` (connexion Data Terra / ORCID). Compte non créé, **lecture officielle non testée**.

**Voie sans compte, testée mais non officielle** : le visualiseur public de THEIA (titiler) lit les fichiers côté serveur et accepte une fenêtre :

`https://wmts.stac.teledetection.fr/cog/bbox/939000,6653000,940000,6654000/667x667.tif?url=https://s3-data.meso.umontpellier.fr/sm1-gdc-ext/FORMSpoT/2022/full_2022.vrt&coord_crs=EPSG:2154&dst_crs=EPSG:2154`

Résultat mesuré : HTTP 200, 1 781 268 o reçus en 1,8 s, GeoTIFF 2 bandes uint16 (hauteur + masque 0/255), EPSG:2154, pas 1,4993 m (667 px pour 1 000 m, car 1 000/1,5 n'est pas entier). Les 4 dalles lues ainsi (hauteur moyenne ; max ; nodata) : `0901-6665` 20,86 m ; 29,2 m ; 0 % · `0902-6665` 17,77 m ; 28,9 m ; 0 % · `0939-6654` 19,16 m ; 36,8 m ; 0 % · `0939-6655` 16,77 m ; 34,6 m ; 0 %. **Fragile** : service de visualisation, sans engagement de disponibilité ni de quota ; les variantes `bbox/...tif?bounds_crs=...` ont renvoyé HTTP 500. À ne pas câbler dans la chaîne ; acceptable pour une mesure ponctuelle du jalon 2.

### 11.3 Recette pour extraire l'année 2022 sur une dalle de 1 km

Dalle exemple `0939-6654` (x 939 000–940 000, y 6 653 000–6 654 000, EPSG:2154).

1. **FORMS-T hauteur 2022 (10 m, anonyme)** : `rasterio.open('/vsicurl/https://zenodo.org/api/records/15489231/files/Height_2022.tif/content')` ; fenêtre `from_bounds(939000, 6653000, 940000, 6654000, transform=src.transform)` ; bande 1 ; int16 en cm ; **0 = nodata** ; résultat 100 × 100 px, déjà alignée sur la dalle (le 10 m divise 1 km et l'origine tombe sur 1 km) ; aucune reprojection. Le jeu du projet est uint16 avec nodata 65 535 : **0 est une hauteur valide chez nous, nodata chez FORMS-T** ; convertir 0 en 65 535 avant comparaison.
2. **FORMS-T volume / biomasse 2022 (30 m, anonyme)** : mêmes appels sur `WVD_2022.tif` et `AGBD_2022.tif` ; fenêtre non alignée (33,33 px) ; lire une fenêtre élargie à l'entier supérieur puis rééchantillonner (moyenne pondérée par la surface, pas le plus proche voisin) sur la grille de la dalle. Unités : m³/ha et Mg/ha ; 0 = nodata.
3. **FORMSpoT hauteur 2022 (1,5 m)** : par compte Data Terra : `tld apikey register`, puis `pystac_client` sur `https://api.stac.teledetection.fr` (écart relevé : le notebook THEIA ouvre `https://api.stac.teledetection.fr`, où `/collections/FORMSpoT` renvoie 404 « Collection formspot does not exist » le 22/11/2026 ; la collection n'a été trouvée que sur `https://api.datastore-mtd.theia.data-terra.org`, à utiliser comme racine STAC) ; asset `height_2022`, `rasterio.open(href)` signé, fenêtre en EPSG:2154. Sans compte : voie titiler ci-dessus (non officielle). Reconvertir décimètres en centimètres (× 10) pour aligner sur l'unité du projet ; 65 535 = nodata dans les deux (identique à la convention du § 7). Passage 1,5 m vers la grille du projet : agrégation (moyenne ou maximum, à décider avec le jalon 2) par bloc, 1 000 / 1,5 n'étant pas entier.
4. **Impossible ou payant** : rien n'est payant. Demande un compte gratuit : l'accès officiel au STAC signé (FORMS-T via S3 et FORMSpoT). Impossible : une définition du volume FORMS-T v1 (article non lu) ; une lecture FORMSpoT signée (non testée) ; une grille FORMSpoT alignée sans rééchantillonnage.

### 11.4 Journal d'accès (URL réellement appelées le 22/11/2026)

`https://zenodo.org/api/records/15489231` (200) · `.../files/Height_2022.tif/content` en Range 0-1023 (206) et par `/vsicurl/` (Height, WVD, AGBD 2022 ; 206 sur chaque bloc) · `https://zenodo.org/api/records/22111200` (200) et son PDF · `https://api.stac.teledetection.fr/` (200), `/collections/forms-t` (200), `/items/FORMS-T-2022` (200), `/sign?href=` (404) · `https://s3-data.meso.umontpellier.fr/sm1-gdc-ext/forms-t/Height_maps/Height_mavg_2022.tif` (403) et `.../FORMSpoT/2022/full_2022.vrt` (403) · `https://doi.theia.data-terra.org/FORMSpoT/` (200) · `https://api.datastore-mtd.theia.data-terra.org/collections/FORMSpoT` et `/items/FORMSpoT-2022` (200) · `https://gist.githubusercontent.com/martinschwartz95/9b7492a861038eec40c26633a96f8a3e/raw` et `.../71bf53926acf779d7081e3256db37d8d/raw` (notebooks) · `https://wmts.stac.teledetection.fr/cog/info` et `/cog/bbox/...` (200, 500 selon variante) · `https://doi.org/10.1016/j.rse.2025.114959` et `.../rse.2026.115631` (redirections vers linkinghub.elsevier.com, contenu non lisible) · `https://essd.copernicus.org/articles/15/4927/2023/essd-15-4927-2023.html`.

### 11.5 Ce qui n'a pas pu être vérifié

1. Définition du volume de FORMS-T v1 (article RSE non lu) ; seule celle de FORMS (ESSD 2023) est citée.
2. Lecture signée (compte Data Terra) de FORMS-T et de FORMSpoT : non testée, aucun compte créé.
3. Identité entre `Height_2022.tif` (Zenodo) et `Height_mavg_2022.tif` (STAC) ; sens de « mavg ».
4. Écart de moyennes de hauteur avec le MNH (11.1) : non élucidé.
5. Version et date de dépôt de FORMS-T : champ `version` absent de Zenodo (`None`) ; date de publication 2025-06-06 ; le STAC indique `published` 2025-12-11 pour l'item 2022.
6. Licence FORMSpoT NC lue sur une seule page (THEIA) ; la licence de l'article (CC-BY) est une autre chose.
