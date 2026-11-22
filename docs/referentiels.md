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
