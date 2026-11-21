# Brief de développement — nemetoncanopee

21 novembre 2026 · Pascal Obstetar

## Contexte et objectif

nemetoncanopee produit des cartes annuelles de hauteur, de volume et de biomasse forestière, fiables à l'échelle du peuplement, pour alimenter Nemeton.

Le point de départ est [FORMS-T v1](https://zenodo.org/records/15489231) du LSCE : un U-Net entraîné sur Sentinel-1, Sentinel-2 et GEDI, millésimes 2018 à 2024. Ses limites publiées ([Schwartz et al., 2025](https://www.sciencedirect.com/science/article/pii/S0034425725003633)) fixent la cible à battre :

| Variable | Erreur FORMS-T v1 face à l'IFN (MAE) | r² |
| --- | --- | --- |
| Hauteur | 3,07 m | 0,68 |
| Volume sur pied | 86 m³/ha | 0,40 |
| Biomasse aérienne | 65,1 Mg/ha | 0,29 |

La croissance n'y est fiable qu'agrégée à environ 5 km, les grands arbres sont sous-estimés et la montagne est biaisée.

Le projet actionne quatre leviers, par ordre de gain attendu :

1. Remplacer GEDI par le MNH LiDAR HD comme vérité terrain de la hauteur.
2. Ajouter essences, densité de houppiers et station pour le volume et la biomasse.
3. Imposer une cohérence temporelle entre millésimes.
4. Fusionner l'ortho IGN RVB + IRC à 20 cm comme source de structure fine.

## Périmètre et livrables

Le livrable est une chaîne de traitement reproductible qui sort cinq couches par millésime, de 2018 à l'année en cours.

| Couche | Résolution | Unité | Format |
| --- | --- | --- | --- |
| Hauteur de canopée | 10 m (option 2,5 m après fusion ortho) | cm, entier | COG |
| Volume sur pied | 30 m | m³/ha | COG |
| Biomasse aérienne | 30 m | Mg/ha | COG |
| Incertitude par pixel | celle de la couche | même unité | COG |
| Perturbations annuelles (coupe, dépérissement) | 10 m | classe + année | COG |

Livrables associés :

- Un catalogue STAC local décrivant chaque couche et chaque millésime.
- Une fonction de statistiques zonales par parcelle ou peuplement, appelable depuis le package R nemeton.
- Un rapport de validation généré automatiquement à chaque version du modèle.

Zone pilote : un département de Bourgogne-Franche-Comté, puis la région, puis la France métropolitaine. C'est une hypothèse à confirmer.

Hors périmètre de cette version : la détection d'arbres individuels, l'interface web, l'outre-mer.

## Données d'entrée

Sentinel fournit le signal annuel, le LiDAR HD fournit la vérité terrain, l'ortho et les placettes IFN fournissent la structure et le volume.

| Source | Rôle | Résolution | Accès |
| --- | --- | --- | --- |
| Sentinel-2 L2A, mai à septembre | Entrée annuelle du modèle | 10 à 20 m | Catalogue STAC Copernicus |
| Sentinel-1 GRD, VV et VH | Entrée annuelle du modèle | 10 m | Catalogue STAC Copernicus |
| [MNH LiDAR HD](https://www.data.gouv.fr/datasets/mnh-lidar-hd) | Cible d'entraînement de la hauteur | 0,5 m, dalles de 1 km | IGN, ouvert |
| MNT LiDAR HD | Altitude, pente, exposition | 0,5 m | IGN, ouvert |
| BD ORTHO RVB + IRC | Texture, houppiers, type de feuillage | 0,2 m | IGN, ouvert |
| BD Forêt V2 | Masque forêt, essences dominantes | Polygones | IGN, ouvert |
| Placettes IFN | Entraînement et validation du volume | Placette | IGN, coordonnées publiques dégradées |
| GEDI L2A | Validation indépendante de la hauteur | Empreinte de 25 m | NASA, ouvert |
| [FORMS-T v1](https://zenodo.org/records/15489231) | Référence à battre | 10 et 30 m | Zenodo, CC BY 4.0 |
| [Open-Canopy](https://github.com/fajwel/Open-Canopy) | Pré-entraînement et banc d'essai | 1,5 m | Ouvert |

Deux règles s'appliquent à toutes les sources :

- La date d'acquisition est stockée par dalle. Le LiDAR HD et l'ortho ne sont pas annuels, le modèle doit connaître leur âge.
- Chaque dalle LiDAR HD n'est appariée qu'aux images Sentinel de sa propre année de vol.

## Architecture du pipeline

Le pipeline est une suite de sept étapes indépendantes, chacune lancée par une commande et rejouable dalle par dalle.

1. **Ingestion** : téléchargement par emprise et par année, mise en cache locale, manifeste des dalles avec dates d'acquisition.
2. **Préparation** : reprojection en Lambert-93 (EPSG:2154), grille commune alignée sur les dalles LiDAR HD de 1 km, masque nuages, correction du relief pour Sentinel-1.
3. **Cibles** : agrégation du MNH LiDAR HD de 0,5 m vers 10 m (hauteur maximale et percentiles par cellule), masque forêt, exclusion du bâti.
4. **Entraînement hauteur** : modèle Sentinel vers hauteur, découpage spatial apprentissage, validation, test.
5. **Inférence annuelle** : prédiction de chaque millésime sur toute la zone, avec incertitude.
6. **Post-traitement temporel** : détection des perturbations, lissage de la série par pixel.
7. **Volume, biomasse et diffusion** : modèle de volume, conversion en biomasse, écriture COG, catalogue STAC, rapport de validation.

Chaque étape lit et écrit des fichiers sur disque, jamais en mémoire partagée. Une étape échouée se relance sans refaire les précédentes.

## Modèle de hauteur

Le modèle prédit la hauteur à 10 m à partir des images Sentinel d'une année, supervisé par le MNH LiDAR HD de la même année.

- **Entrées** : scènes Sentinel-2 individuelles (10 bandes), Sentinel-1 VV et VH, altitude, pente, exposition. FORMS-T entraîne déjà sur des scènes individuelles pour mieux généraliser entre années ; on garde ce choix.
- **Cible** : hauteur maximale LiDAR HD par cellule de 10 m.
- **Architecture de départ** : U-Net, pour reproduire la référence. Une variante à série temporelle, du type [THREASURE-Net](https://arxiv.org/abs/2512.11524), est testée ensuite.
- **Fonction de perte** : erreur absolue, pondérée pour les hauteurs supérieures à 30 m afin de corriger la sous-estimation des grands arbres.
- **Découpage** : blocs spatiaux de 10 km, jamais de dalles voisines entre apprentissage et test. Le jeu de test est figé dès le premier jalon.
- **Inférence** : médiane des prédictions sur les scènes de mai à septembre ; leur dispersion donne l'incertitude.
- **Branche ortho, en second temps** : un encodeur sur l'ortho RVB + IRC rééchantillonnée à 1 m, fusionné avec la branche Sentinel, l'âge de l'ortho en entrée. Le jeu [PrediTree](https://arxiv.org/abs/2509.01202) sert de point de comparaison.

## Volume et biomasse

Le volume est appris directement sur les placettes IFN, et non déduit de la seule hauteur comme dans FORMS-T v1.

- **Modèle** : gradient boosting (LightGBM) à 30 m, une ligne par placette IFN.
- **Variables explicatives** : hauteur prédite et ses percentiles, essence dominante (BD Forêt), sylvoécorégion, altitude, pente, exposition, taux de couvert et densité de houppiers tirés de l'ortho.
- **Variables LiDAR HD, quand la dalle existe** : percentiles de hauteur, taux de pénétration, étagement. Elles servent à l'apprentissage, puis sont prédites depuis Sentinel pour les autres années.
- **Biomasse** : volume multiplié par l'infradensité et le facteur d'expansion de l'essence. Les coefficients sont dans un fichier de configuration, pas dans le code.
- **Incertitude** : régression quantile, bornes à 10 % et 90 %.
- **Solution de repli** : si les coordonnées exactes des placettes ne sont pas accessibles, allométrie hauteur vers volume par essence et sylvoécorégion.

## Cohérence temporelle et perturbations

Une forêt non perturbée ne perd pas de hauteur d'une année à l'autre : la série de chaque pixel est contrainte en conséquence.

1. **Détecter les ruptures** : une chute de hauteur supérieure à un seuil, confirmée l'année suivante, est classée coupe ou dépérissement et datée.
2. **Lisser par segment** : entre deux ruptures, la série est ajustée par une courbe croissante (régression isotone, pondérée par l'incertitude annuelle).
3. **Ancrer sur le LiDAR HD** : l'année du vol, la série passe par la hauteur mesurée.
4. **Recalculer** volume et biomasse à partir de la hauteur lissée.

Les couches brutes et lissées sont toutes deux conservées. Le seuil de rupture est un paramètre de configuration, à caler sur les zones de coupes connues.

## Validation et critères d'acceptation

Une version est acceptée si elle bat FORMS-T v1 sur le même jeu de test, variable par variable. Les cibles ci-dessous sont des propositions à valider.

| Critère | Référence de comparaison | FORMS-T v1 | Cible proposée |
| --- | --- | --- | --- |
| Hauteur, MAE | Placettes IFN | 3,07 m | 2,5 m ou moins |
| Hauteur, biais au-dessus de 30 m | MNH LiDAR HD, blocs de test | à mesurer | moitié du biais v1 |
| Volume, MAE | Placettes IFN | 86 m³/ha | 70 m³/ha ou moins |
| Biomasse, MAE | Placettes IFN | 65,1 Mg/ha | 55 Mg/ha ou moins |
| Croissance en hauteur, r² | Deux vols LiDAR sur la même zone | 0,60 à 5 km | 0,60 à 1 km |

Règles de validation :

- FORMS-T v1 est réévalué sur le jeu de test du projet, pour comparer à périmètre égal.
- Les erreurs sont ventilées par essence, classe de hauteur, classe de pente et département.
- La validation de la croissance exige une zone couverte par deux vols LiDAR à des dates différentes, à identifier.
- Le rapport est régénéré par une seule commande et versionné avec le modèle.

## Stack technique et structure du dépôt

Le cœur est en Python, avec une passerelle R mince pour le package nemeton.

| Besoin | Choix |
| --- | --- |
| Langage | Python 3.11 ou plus |
| Apprentissage profond | PyTorch + Lightning |
| Volume et biomasse | LightGBM |
| Rasters et vecteurs | rasterio, rioxarray, xarray + dask, geopandas |
| Accès aux catalogues | pystac-client, odc-stac |
| Configuration | Hydra, fichiers YAML |
| Qualité | pytest, ruff, typage vérifié par mypy |
| Sorties | COG + catalogue STAC |
| Passerelle R | fonctions terra lisant les COG, dans nemeton |

```
nemetoncanopee/
  conf/            # YAML : zones, années, modèle, seuils, coefficients
  src/nemeton_canopee/
    ingest/        # sentinel.py, lidar_hd.py, ortho.py, ifn.py
    prepare/       # grille, masques, correction du relief
    targets/       # MNH vers cibles 10 m
    models/        # unet.py, fusion.py, volume.py
    infer/         # prédiction annuelle, incertitude
    temporal/      # ruptures, lissage, ancrage
    validate/      # métriques, rapport
    export/        # COG, STAC
    cli.py         # canopee ingest | prepare | train | infer | smooth | validate | export
  r/               # passerelle nemeton
  tests/           # un jeu de 4 dalles de 1 km embarqué
  docs/adr/        # décisions d'architecture
```

Conventions :

- Lambert-93 partout, grille alignée sur les dalles LiDAR HD.
- Hauteur en centimètres, entier non signé 16 bits, comme FORMS-T v1.
- Aucun chemin ni seuil en dur : tout passe par `conf/`.
- Chaque module a ses tests sur le jeu de 4 dalles ; la chaîne complète s'y exécute en moins de 10 minutes sur CPU.
- Graine aléatoire fixée, version du modèle et des données écrite dans les métadonnées de chaque COG.

## Jalons de développement

Sept jalons, dans cet ordre ; chacun se termine par un critère vérifiable avant de passer au suivant.

1. **Squelette de bout en bout** : les sept étapes tournent sur 4 dalles avec un modèle trivial. Terminé quand `canopee` produit un COG et un rapport.
2. **Référence** : FORMS-T v1 téléchargé et évalué sur le jeu de test figé du département pilote. Terminé quand le tableau de référence est dans le rapport.
3. **Hauteur supervisée LiDAR HD** : U-Net entraîné sur le département pilote. Terminé quand la MAE de hauteur bat la référence.
4. **Volume et biomasse** : modèle sur placettes IFN ou allométrie de repli. Terminé quand les deux MAE battent la référence.
5. **Série temporelle** : inférence 2018 à l'année en cours, ruptures, lissage. Terminé quand la croissance est validée sur une zone à deux vols LiDAR.
6. **Fusion ortho 20 cm** : branche ortho ajoutée, comparaison avec et sans. Conservée seulement si le gain est mesurable.
7. **Passage à la région** : traitement par dalles en parallèle, catalogue STAC, passerelle R. Terminé quand nemeton lit une statistique par parcelle.

Le premier jalon suit l'approche du squelette fonctionnel déjà retenue pour la plateforme Nemeton.

## Risques et questions ouvertes

Quatre questions sont à trancher avant le jalon 2 ; elles changent le dimensionnement.

- [ ] Zone pilote : quel département, et la région Bourgogne-Franche-Comté est-elle bien la cible intermédiaire ?
- [ ] Placettes IFN : un accès aux coordonnées exactes est-il possible par convention avec l'IGN ?
- [ ] Calcul : quel GPU et quel stockage sont disponibles ? Les seules couches de hauteur FORMS-T v1 pèsent environ 6 Go par année pour la France.
- [ ] Licence : quelle licence pour le code et les cartes ?

| Risque | Conséquence | Parade |
| --- | --- | --- |
| Dates de vol LiDAR HD hétérogènes, vols hors feuilles | Cible incohérente avec l'image Sentinel | Appariement par année de vol, filtre sur la saison du vol |
| Radiométrie de l'ortho variable entre départements | Effets de dalle dans les cartes | Normalisation par campagne, jalon 6 optionnel |
| Coordonnées IFN dégradées | Modèle de volume bruité | Allométrie de repli par essence et sylvoécorégion |
| Aucune zone à deux vols LiDAR dans le pilote | Croissance non validable localement | Valider sur une zone hors pilote, par exemple les Vosges comme FORMS-T |
| Surapprentissage au département pilote | Mauvais transfert à la région | Test sur un département jamais vu avant le jalon 7 |

Point à vérifier : la disponibilité des modèles de surface photogrammétriques de l'IGN, qui donneraient une hauteur mesurée à chaque campagne ortho.
