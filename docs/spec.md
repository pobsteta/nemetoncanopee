# Spécification — nemetoncanopee

22 novembre 2026 · rédigée par Claude (orchestrateur) à partir de `docs/brief.md` et des
arbitrages de Pascal du 22 novembre · **statut : validée par Pascal le 22 novembre 2026**, avec les propositions S1 à S4 du `contradicteur` (journal du 22/11)

Le brief reste la source du *pourquoi* ; cette spec dit *quoi* et *comment on saura que
c'est juste*. Un lien plutôt qu'une copie : les tableaux de données, de couches et de
cibles chiffrées sont dans le brief.

## 1. Pour qui, et le parcours

**Utilisateur direct** : nemeton (package R), et à travers lui le gestionnaire qui
analyse une parcelle ou un peuplement.

Parcours visé à la fin du jalon 7 :

1. Dans nemeton, le gestionnaire désigne une parcelle (polygone en Lambert-93) et une
   période.
2. nemeton charge le paquet `nemeton-canopee` et appelle `canopee zonal` (ou la fonction
   Python équivalente) avec le polygone, les années et les couches voulues.
3. Il reçoit, par année et par couche : moyenne, médiane, percentiles 10 et 90, part de
   surface couverte, incertitude moyenne, et les perturbations datées dans la parcelle.
4. Il voit d'où vient chaque chiffre : version du modèle, version des données, date de
   vol LiDAR de la dalle, couche brute ou lissée.

Parcours de l'opérateur (Pascal), étape par étape, une commande par étape, rejouable
dalle par dalle :

```
canopee ingest   --zone conf/zones/pilote.yaml --annees 2018-2025
canopee prepare  --zone …
canopee targets  --zone …            # hauteur LiDAR HD agrégée à 10 m
canopee train    --modele conf/modele/unet.yaml
canopee infer    --annees …
canopee smooth   --annees …
canopee validate                      # rapport de validation
canopee export                        # COG + catalogue STAC
canopee zonal    --polygones parcelles.gpkg --annees … --couches hauteur,volume
```

Chaque étape lit et écrit des fichiers sur disque ; une étape échouée se relance seule.

## 2. Données manipulées

| Donnée | Forme sur disque | Clé | Métadonnées obligatoires |
| --- | --- | --- | --- |
| Manifeste des dalles | GeoParquet ou CSV | identifiant de dalle 1 km (nomenclature IGN) | emprise, source, date d'acquisition, date de vol lue dans les métadonnées de la dalle |
| Entrées Sentinel par dalle et scène | GeoTIFF | dalle, date de scène | capteur, bandes, masque nuages |
| Cibles de hauteur 10 m | GeoTIFF uint16 (cm) | dalle, année de vol | percentiles, masque forêt, exclusion du bâti |
| Couches produites | COG | couche, millésime, dalle | version du modèle, version des données, graine, brute ou lissée |
| Catalogue | STAC (JSON) | collection par couche, item par millésime et dalle | licence, références |
| Configuration | YAML dans `conf/` | — | chaque coefficient avec sa source publiée |

Le jeu d'essai embarqué (`tests/data/`) : 4 dalles de 1 km, extraits Sentinel figés,
MNH et MNT LiDAR HD réduits, masque BD Forêt, sans réseau. Il est **fabriqué par un script
versionné** (un seul accès réseau, au moment de la fabrication), pèse **moins de 20 Mo** au
total, et chaque fichier a sa provenance et sa licence dans un fichier `PROVENANCE` (Licence
Ouverte 2.0 pour l'IGN ; « Contains modified Copernicus Sentinel data [année] » pour
Sentinel).

Conventions de raster : hauteur en uint16 (cm), **nodata = 65535** (0 est une hauteur
valide). Extensions STAC : `projection`, `raster` (unité, nodata), `file`, `processing` ;
leurs schémas JSON sont **embarqués dans le dépôt** pour valider sans réseau.

Décisions du 22/11 (orchestrateur, par délégation ; journal) :

- **Grille** : les cellules de 10 m ont leurs bords sur les multiples de 10 m en
  Lambert-93 (donc sur les bords de dalle au km). Une cellule [x, x+10) × [y, y+10) agrège
  les pixels du MNH à 0,5 m dont le **centre** tombe dedans (les centres IGN sont sur des
  coordonnées entières : décalage de 0,25 m par rapport à l'emprise nominale,
  `docs/referentiels.md`).
- **Hauteurs négatives** du MNH (jusqu'à −0,29 m mesuré) : bornées à 0 avant le passage en
  uint16 ; le nodata IGN (−9999) devient 65535.
- **Versions des extensions STAC** : celles que pystac connaît (projection v2.0.0,
  raster v1.1.0, file v2.1.0), plus processing v1.2.0, enregistrée à partir du schéma
  embarqué.
- **Sentinel-1** : absent du jeu d'essai du jalon 1 (modèle trivial, accès anonyme non
  garanti) ; Sentinel-2 L2A seulement, Earth Search.

## 3. Hors périmètre

- Détection d'arbres individuels, interface web, outre-mer (brief).
- Passerelle R dans ce dépôt : nemeton charge le paquet (arbitrage du 22/11).
- Modèle de volume sur placettes IFN tant qu'aucune convention IGN n'est signée.
- Téléchargement en CI : les tests ne touchent pas le réseau.

## 4. Critères d'acceptation

### Jalon 1 — squelette de bout en bout (premier livrable)

Terminé quand, sur le jeu de 4 dalles, sans réseau, en moins de 10 minutes sur CPU :

1. les commandes `ingest` (en mode lecture du jeu embarqué), `prepare`, `targets`,
   `train` (modèle trivial : hauteur = médiane de la cible du jeu d'apprentissage),
   `infer`, `smooth`, `validate`, `export` et `zonal` s'enchaînent sans erreur ;
2. `export` écrit au moins un COG de hauteur, uint16 en cm, nodata 65535, Lambert-93
   (EPSG:2154), aligné sur la grille des dalles, avec version du modèle, version des
   données et graine dans ses métadonnées ; un validateur de COG (rio-cogeo) le confirme ;
3. `export` écrit un catalogue STAC qui décrit ce COG, validé par `pystac` contre les
   schémas embarqués, sans réseau, avec la mention Copernicus ;
4. `validate` écrit un rapport (Markdown) avec la MAE de hauteur sur les blocs de test ;
5. `zonal` rend, pour un polygone d'essai, une statistique dont la valeur est vérifiée à
   la main dans le test ;
6. le découpage apprentissage/test est figé dans un fichier versionné : 2 dalles
   d'apprentissage et 2 de test, dans des blocs distincts ; un test vérifie la
   *mécanique* (aucune dalle de test ne touche une dalle d'apprentissage, par un bord ou un
   coin). La taille réelle des blocs (10 km) sera justifiée par un corrélogramme sur la
   zone pilote, pas au jalon 1 ;
7. un test chronomètre la chaîne complète et échoue au-delà de 10 minutes ;
8. `.claude/test-command` passe (ruff, pytest, couverture).

### Jalons 2 à 7

Les critères chiffrés sont ceux du brief (« Validation et critères d'acceptation »), avec
les arbitrages du 22/11 : comparaison à FORMS-T v1 et FORMSpoT sur le même jeu de test ;
sans convention IGN, critères IFN agrégés à la sylvoécorégion.

## 5. Besoins en référentiels (à confier à l'`acquereur`)

| Référentiel | Pour | Source attendue |
| --- | --- | --- |
| Nomenclature et grille des dalles LiDAR HD 1 km | grille commune | IGN, géoservices |
| Dates de vol par dalle | appariement temporel | métadonnées des dalles IGN ; carte TerraLab en contrôle |
| Définition du volume (bois fort tige / total) | volume | IGN, inventaire forestier (méthodologie) |
| Infradensité et facteurs d'expansion par essence | biomasse | IPCC 2006 vol. 4 ch. 4 ; CITEPA (OMINEA) |
| Sylvoécorégions | allométrie, validation agrégée | IGN (inventaire forestier) |
| Essences dominantes | variables du volume | BD Forêt V2, IGN |
| Équations allométriques hauteur → volume | volume par défaut | publications IGN/IFN ou littérature, à sourcer |

## 6. Décisions structurantes

Proposées en ADR au crible FRANCE dans `docs/adr/`, critiquées par le `contradicteur`
avant que Pascal tranche :

- ADR 0001 — stack du squelette : **acceptée par Pascal le 22/11** ;
- ADR 0002 — définition du volume et source des coefficients de biomasse ;
- ADR 0003 — licence du code et des cartes (à trancher par Pascal ; question ouverte du brief).

Restent des questions ouvertes du brief, hors ADR : zone pilote, calcul (GPU, stockage),
convention IFN.
