# Mission 004 — plan (main prise)

> Rendu par le `dev` le 2026-11-22, sans code. **Validé par Claude (orchestrateur, par
> délégation de Pascal) le 2026-11-22**, avec les décisions en fin de fichier.

**Redite :** brancher les neuf commandes `canopee`, d'`ingest` à `zonal`, en étapes qui
passent par des fichiers et se rejouent dalle par dalle, et les faire tourner sur les 4
dalles embarquées avec un modèle trivial (la médiane), sans réseau et en moins de
10 minutes, pour prouver grille 10 m, COG, STAC, rapport et zonal avant le vrai modèle.

## 1. Modules (`src/nemeton_canopee/`)

| Module | Rôle |
|---|---|
| `conf.py` | charge et contrôle les YAML ; chemins relatifs au fichier de conf |
| `grille.py` | identifiant de dalle → emprise ; transformation 10 m (bords multiples de 10 m) |
| `chemins.py` | le seul nom de chaque fichier de travail (§3) |
| `ingest/` | lit le jeu embarqué (`mode: local`) ; manifeste des dalles et des scènes, version des données |
| `prepare/` | scènes de l'année de vol seulement (refus sinon) ; pile de 10 bandes à 10 m ; masques nuage (SCL) et forêt |
| `targets/` | MNH → 10 m (maximum), uint16 cm, forêt seulement, nodata 65535 |
| `models/` | `trivial.py` : médiane des cibles d'apprentissage ; refuse une dalle de test |
| `infer/` | applique le modèle sur les pixels de forêt sans nuage ; couche brute |
| `temporal/` | `smooth` : identité au jalon 1 |
| `validate/` | MAE et biais sur les dalles de test ; rapport Markdown et JSON |
| `export/` | `cog.py` (rio-cogeo), `stac.py` (pystac, validation hors ligne) |
| `zonal/` | `statistiques_zonales()` avec exactextract |
| `cli.py` | une sous-commande par étape |

## 2. `conf/`

- `conf/chaine.yaml` : `travail`, `graine: 42`, `zone`, `modele`,
  `smooth.seuil_rupture_cm: 500  # PROVISOIRE, calage au jalon 5`, `cog`, `stac`
  (licence `other` en attendant l'ADR 0003, mentions).
- `conf/zones/jeu_essai.yaml` : `source: {mode: local, racine: ../../tests/data}`, dalles,
  découpage, `annees: [2022]`, `foret_formations: tout` (provisoire).
- `conf/modele/trivial.yaml` : `nom: mediane`, `arrondi: demi_haut`.
- CLI : `canopee --conf conf/chaine.yaml <etape> …` (`--conf` obligatoire, ou `CANOPEE_CONF`) ;
  `--travail` remplace le dossier de travail.

## 3. Fichiers sur disque (`{travail}/`)

```
ingest/manifeste.parquet
ingest/scenes.parquet
prepare/{annee}/{dalle}/s2_{scene}.tif
prepare/{dalle}/foret_10m.tif
targets/{annee}/{dalle}_cible_hauteur.tif
modeles/{version_modele}/modele.json
infer/{annee}/{dalle}_hauteur_brute.tif
smooth/{annee}/{dalle}_hauteur_lissee.tif
validate/rapport.md, validate/rapport.json
export/cog/hauteur/{annee}/{dalle}_hauteur_{brute|lissee}_{annee}.tif
export/stac/catalog.json, hauteur/collection.json, hauteur/{item}/{item}.json
zonal/statistiques.csv
```

Écriture atomique ; une étape relancée remplace ses sorties à l'identique ; `--dalles`
restreint aux dalles nommées.

## 4. Signatures

```
canopee --conf C ingest   [--dalles D…] [--annees 2022]
canopee --conf C prepare  [--dalles D…]
canopee --conf C targets  [--dalles D…]
canopee --conf C train
canopee --conf C infer    [--annees A…] [--dalles D…]
canopee --conf C smooth   [--annees A…] [--dalles D…]
canopee --conf C validate
canopee --conf C export   [--annees A…]
canopee --conf C zonal    --polygones F.gpkg [--champ-id id] --annees A… --couches hauteur [--sortie F.csv]
```

Retour : 0 succès ; 2 entrée manquante, avec l'étape à relancer.

```python
statistiques_zonales(polygones: GeoDataFrame | PathLike, annees: Sequence[int],
                     couches: Sequence[str], catalogue: PathLike, champ_id="id",
                     traitement="lissee") -> pandas.DataFrame
```

Colonnes : `id, annee, couche, traitement, unite, moyenne, mediane, p10, p90,
part_couverte, incertitude_moyenne, version_modele, version_donnees, date_vol, dalles`.
Pondération par fraction couverte (exactextract) ; unité de la couche (cm) ;
`part_couverte` = somme des fractions valides × 100 m² / aire ; `incertitude_moyenne` NaN
au jalon 1.

## 5. Calculs

- Grille 100×100 par dalle ; cible = maximum de 5×5 pixels du MNH à 2 m (conforme à la
  règle des centres, le MNH 2 m étant calé sur l'emprise nominale) ; nodata exclu ;
  cellule toute nodata = 65535.
- Masque forêt : tous les polygones BD Forêt, rastérisés par centre de cellule.
- Modèle : médiane des cellules valides des dalles A, mesurée 2625,5 cm → **2626 cm** ;
  graine enregistrée.
- `smooth` : identité, tag `CANOPEE_TRAITEMENT=lissee`, seuil lu et écrit sans effet.
- Rapport : versions, découpage, tableau par dalle de test (n, MAE m, biais m), MAE
  globale (ordre de grandeur attendu ~7,5 m, pas une assertion).
- `version_donnees` = `jeu-essai-` + 12 car. du sha256 des entrées triées ;
  `version_modele` = `mediane-` + 12 car. du sha256 de `modele.json`.

## 6. COG et STAC

- COG : `cog_translate` deflate + predictor 2, uint16, nodata 65535, EPSG:2154 ; tags
  `CANOPEE_VERSION_MODELE`, `CANOPEE_VERSION_DONNEES`, `CANOPEE_GRAINE`,
  `CANOPEE_VERSION_LOGICIEL`, `CANOPEE_COUCHE`, `CANOPEE_TRAITEMENT`, `CANOPEE_DATE_VOL`,
  `CANOPEE_UNITE=cm`, `CANOPEE_MENTIONS` ; `cog_validate` dans l'étape.
- STAC : catalogue, collection `hauteur`, un item par millésime et dalle
  (`hauteur-2022-0901-6665`), assets `brute` et `lissee`, liens relatifs ; extensions
  projection v2.0.0, raster v1.1.0, file v2.1.0, processing v1.2.0 ; validation par
  `JsonSchemaSTACValidator` au `schema_cache` rempli depuis `conf/stac-schemas/` ;
  mention Copernicus (année tirée des scènes) dans la description, une propriété
  `mentions` des items et le tag du COG ; liens de licence.

## 7. Moins de 10 minutes, sans réseau

Jeu de 3,1 Mo, numpy par blocs ; chaîne estimée < 30 s ; `ingest` local sans import
réseau ; schémas STAC locaux.

## 8. Tests d'acceptation (mission 003)

| N° | Test | Vérifie |
|---|---|---|
| 1 | `test_chaine_complete` | 9 commandes → 0, dans l'ordre, sur `tmp_path`, sockets bloqués ; chaque fichier du §3 existe |
| 2 | `test_cog_hauteur` | `cog_validate` ; uint16, nodata 65535, EPSG:2154 ; origine = (xmin, ymax) de la dalle, pas 10 m ; tags de version et graine ; une valeur valide = 2626 |
| 3 | `test_stac_valide_hors_ligne` | `validate_all` sans réseau ; 4 extensions aux versions décidées ; item → COG ; mention Copernicus 2022 |
| 4 | `test_rapport_validation` | `rapport.md` contient « MAE » et les 2 dalles de test ; MAE de `rapport.json` recalculée à la main |
| 5 | `test_zonal_valeur_main` | (a) COG synthétique 3×3, moyenne pondérée calculée à la main ; (b) carré de 20 m dans 0901-6665 → moyenne = médiane = 2626, `part_couverte` = 1 |
| 6 | `test_decoupage_fige` | 2 + 2 dalles, blocs distincts ; aucune emprise de test ne touche une d'apprentissage (bord ou coin) ; `train` refuse un découpage piégé |
| 7 | `test_chrono_chaine` | chaîne < 600 s |
| 8 | CI | `.claude/test-command` vert, aucun test sauté |

Plus : refus d'une scène hors année de vol ; borne à 0 des hauteurs négatives ; 65535
conservé ; rejouabilité (deux passes → fichiers identiques).

## Décisions de l'orchestrateur (par délégation), 2026-11-22

1. Mention Copernicus dans le STAC : comme proposé (description, propriété `mentions`, liens de licence).
2. Licence STAC `other` : gardée en attente de l'ADR 0003, réservée à Pascal.
3. `smooth` en identité au jalon 1 : oui ; le lissage isotone vient au jalon 5.
4. Masque forêt : tous les polygones BD Forêt (provisoire) ; « forêt fermée sans couvert arboré » à réexaminer au jalon 3.
5. `decoupage.yaml` : **figé maintenant** (mention « PROVISOIRE » retirée), par la mission 003.
6. Unité de `zonal` : le cm, comme la couche ; nemeton convertit s'il le souhaite.
7. Épingler exactextract à la version testée.
8. Réserves du testeur (003), tranchées le 22/11 : `rapport.json` a pour clés `mae_m` (MAE poolée sur toutes les cellules de test, en m), `biais_m`, et `dalles: {id: {n, mae_m, biais_m}}` ; une scène hors de l'année de vol fait échouer `ingest` ou `prepare` avec un code non nul (pas de filtrage silencieux) ; aucune horodate « maintenant » dans les sorties (dates STAC = date de vol / dates des scènes), pour la rejouabilité à l'octet.
9. Décisions du 22/11 après relecture de 003 : code de retour **3** pour une donnée refusée (découpage invalide, scène hors de l'année de vol), avec un message qui nomme la règle ; 2 reste réservé à l'entrée manquante. Géométries et bbox STAC en WGS84 (EPSG:4326), l'emprise Lambert-93 dans `proj:code`/`proj:bbox`. Aucun chemin absolu vers le dossier de travail dans les sorties (rejouabilité).
10. Biais = prédiction − cible, en m (convention usuelle : un biais négatif dit une sous-estimation, comme celle des grands arbres dans FORMS-T).
11. Après relecture de 004 (22/11) : une année demandée sans aucune dalle (`--annees`), un identifiant de dalle invalide, une clé absente de `decoupage.yaml`, un `mode` de source autre que `local`, un MNH dont le CRS n'est pas Lambert-93 et un GeoPackage de `zonal` sans CRS sont des **données refusées : code 3**, message qui nomme la règle, rien d'écrit. Le CRS se lit dans la conf (`grille.crs`), jamais en dur. Le texte de `processing:lineage` vient de la conf.
12. Vol à cheval sur deux années (date de début et de fin d'acquisition d'années différentes) : donnée refusée au jalon 1, code 3, message « année de vol » ; une règle d'appariement viendra au jalon 3 si le cas se présente. Plusieurs modèles : `train` remplace le modèle actif (écart 4 du dev, accepté), un seul modèle existe donc à la fois ; pas de test supplémentaire.
