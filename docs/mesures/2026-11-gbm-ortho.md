# Mesure de gbm avec ortho face à FORMS-T (mission 014)

- **Date :** 22 novembre 2026 · **Par :** `analyste` (mission 014) · **Machine :** 4 CPU, 15 Go, sans GPU.
- **En une phrase :** sur les mêmes cellules et les mêmes trois blocs de test que la mesure 011, gbm avec les descripteurs de la BD ORTHO et des trouées (`gbm_ortho`, mission 013) bat-il FORMS-T v1 au peuplement, et quelle part du progrès vient des blocs d'apprentissage en plus, de l'ortho et de l'âge de l'ortho ?
- **Réponse :** **non.** `gbm_ortho` ne bat pas FORMS-T v1 au peuplement. Par polygone, il passe d'une défaite nette à une égalité (écart apparié +0,18 [−0,08 ; +0,41]). À l'hectare, il reste derrière, et l'écart devient significatif (+0,22 [+0,02 ; +0,40]). Le gain par polygone vient de l'ortho ; les blocs en plus n'apportent rien au peuplement et ajoutent un biais positif ; l'âge de l'ortho n'apporte rien de mesurable.

## Ce qui a été mesuré, exactement

- **Données :** échantillon du Jura (`/data/echantillon_jura`, missions 008 et 012), vol LiDAR HD 2022, 3 scènes Sentinel-2 par dalle. Test **inchangé** : `chaux_b`, `joux`, `altitude_b` (48 dalles). Apprentissage : 6 blocs, 96 dalles (`chaux_a`, `sapiniere_a`, `altitude_a`, plus `chenaie_c`, `sapiniere_c`, `altitude_c` de la mission 012), sauf `gbm_011` (3 blocs, 48 dalles).
- **Cinq produits plus FORMS-T v1 :**

| Produit | Descripteurs | Apprentissage | Dossier, conf |
|---|---|---|---|
| `trivial` (pour mémoire) | médiane | 3 blocs | `/data/mesure_011/trivial` (mesure 011) |
| `gbm_011` | `gbm.yaml` | 3 blocs | `/data/mesure_011/gbm` (mesure 011, sorties intactes) |
| `gbm` | `gbm.yaml` | 6 blocs | `/data/mesure_014/gbm`, `conf/modele_gbm_2km.yaml` (copie de celle de 011) |
| `gbm_ortho` | `gbm_ortho.yaml` (S2 + trouées S2 + ortho + âge) | 6 blocs | `/data/mesure_014/gbm_ortho` (entraîné en mission 013, réutilisé) |
| `gbm_ortho_sans_age` | `gbm_ortho.yaml` avec `ortho.age: false` (seule différence) | 6 blocs | `/data/mesure_014/gbm_ortho_sans_age` |

- **Une seule modification de conf** pour tous les gbm, comme en 011 : blocs de validation de 2 km au lieu de 500 m. Les confs dérivées sont dans `/data/mesure_014/conf/` ; `conf/` n'a pas été modifié. Chaîne `ingest` à `smooth` (`/data/mesure_014/lancer_014.py`) ; `validate` et `export` non relancés (7 s en 011, sans effet sur la mesure).
- **Aucun réglage n'a touché les blocs de test.** Hyperparamètres de 009 ; l'ablation de l'âge est décidée avant la mesure (réserve de la relecture 013), pas choisie sur un résultat.
- **Mêmes cellules :** même masque qu'en 011 (cible valide et tous les produits valides) : **462 467 cellules**, **164 polygones** et **4 643 hectares**, identiques à 011. Les MAE de `gbm_011`, `trivial` et FORMS-T sont **identiques au centième** à celles du rapport 011 ; la hauteur rejouée de chaque gbm est identique à l'octet à celle de `infer` (contrôle du script).
- **IC 95 % :** bootstrap sur les dalles de test (1 000 tirages, graine 42, mêmes tirages pour tous les produits). **Nouveau (ajout compatible) :** `--paire A-B` donne l'IC de l'écart apparié entre deux produits quelconques ; c'est lui qui sépare les effets « blocs », « ortho » et « âge ». L'option `--exces` ajoute la section « Excès sur FORMS-T », qui chiffre la cause n° 1 (avant : calcul à la main) ; sans option, la sortie reste celle de 011. (Le tableau en annexe a été produit avant que cette section passe sous option, avec les mêmes chiffres.)
- **Premier passage :** un essai du script sur `trivial`, `gbm_011` et `gbm_ortho` seuls (`/data/mesure_014/essai/`), lancé pendant l'entraînement des deux autres modèles pour vérifier la lecture des sorties de 011 ; ses chiffres sont identiques à ceux de la mesure finale. Sans conséquence.
- **Arrêt anticipé :** les trois modèles 6 blocs s'arrêtent à 1 988 (`gbm_ortho`), 1 997 (`gbm`) et 2 000 tours (`gbm_ortho_sans_age`) sur 2 000 : l'arrêt anticipé ne se déclenche pas, c'est `tours_max` qui borne (réserve 013, confirmée).

## Tableau principal : MAE au peuplement (m) [IC 95 %]

| Critère | gbm_011 | gbm | **gbm_ortho** | sans âge | **FORMS-T v1** | gbm_ortho − FORMS-T |
|---|---|---|---|---|---|---|
| Par polygone (164) | 2,23 [1,93–2,46] | 2,18 [1,88–2,41] | **1,85 [1,64–2,04]** | 1,89 [1,64–2,11] | **1,67 [1,45–1,88]** | +0,18 [−0,08 ; +0,41] |
| Par hectare (4 643) | 2,05 [1,86–2,25] | 2,14 [1,97–2,31] | **2,11 [1,94–2,27]** | 2,09 [1,92–2,25] | **1,89 [1,79–2,01]** | **+0,22 [+0,02 ; +0,40]** |

Écart à FORMS-T des autres : `gbm_011` +0,56 [+0,25 ; +0,81] / +0,16 [−0,07 ; +0,38] ; `gbm` +0,52 [+0,22 ; +0,74] / +0,25 [+0,03 ; +0,43] ; sans âge +0,23 [−0,06 ; +0,46] / +0,20 [−0,01 ; +0,39] (polygone / hectare).

**D'où vient le changement** (écarts appariés, m, négatif = mieux) :

| Effet | Paire | Par polygone | Par hectare |
|---|---|---|---|
| Blocs en plus | gbm − gbm_011 | −0,05 [−0,18 ; +0,07] | +0,09 [−0,09 ; +0,25] |
| Ortho et trouées, sans l'âge | gbm_ortho_sans_age − gbm | **−0,29 [−0,43 ; −0,15]** | −0,05 [−0,15 ; +0,05] |
| Âge de l'ortho | gbm_ortho − gbm_ortho_sans_age | −0,04 [−0,13 ; +0,07] | +0,02 [−0,02 ; +0,07] |
| **Total** | gbm_ortho − gbm_011 | **−0,38 [−0,60 ; −0,13]** | +0,06 [−0,15 ; +0,27] |

L'attribution suit **un seul ordre** (blocs, puis ortho, puis âge) : l'ortho sur 3 blocs n'a pas été entraînée, donc l'interaction blocs × ortho n'est pas mesurée, et l'effet de l'ortho pourrait être autre sur 3 blocs. Par polygone, l'ortho fait **les trois quarts** du gain (−0,29 sur −0,38) ; blocs et âge sont dans le bruit. À l'hectare, aucun effet n'est significatif : le gain de l'ortho est mangé par la perte due aux blocs. (Les trouées S2 sont dans la même paire que l'ortho ; la mission 013 leur attribue moins de 2 % du gain.)

Par bloc de test (gbm_ortho − FORMS-T) :

| Bloc | polygone | hectare |
|---|---|---|
| `chaux_b` | −0,03 [−0,57 ; +0,32] | **−0,34 [−0,62 ; −0,05]** (gbm_ortho gagne) |
| `altitude_b` | **+0,39 [+0,07 ; +0,76]** | **+0,38 [+0,17 ; +0,58]** |
| `joux` | +0,34 [−0,01 ; +0,71] | **+0,64 [+0,41 ; +0,88]** |

## Tableaux secondaires (total des 3 blocs, 462 467 cellules)

| | gbm_011 | gbm | gbm_ortho | sans âge | FORMS-T v1 |
|---|---|---|---|---|---|
| MAE / biais au pixel (m) | 3,55 / +0,31 | 3,51 / +1,31 | 3,42 / +0,85 | 3,42 / +0,95 | **3,35** / −1,17 |
| < 10 m (3,1 %) | 8,23 / +8,11 | 8,06 / +7,90 | 7,04 / +6,78 | 7,03 / +6,79 | **5,77** / +4,24 |
| 10–20 m (12,6 %) | 5,95 / +5,69 | 6,94 / +6,70 | 6,51 / +6,20 | 6,57 / +6,27 | **4,72** / +2,90 |
| 20–30 m (67,9 %) | 2,64 / +0,11 | 2,60 / +1,18 | 2,57 / +0,69 | 2,58 / +0,79 | **2,55** / −1,22 |
| > 30 m (16,4 %) | 4,60 / −4,44 | **3,78** / −3,51 | 3,86 / −3,68 | **3,78** / −3,55 | 5,18 / −5,08 |

| Incertitude p10–p90 | gbm_011 | gbm | gbm_ortho | sans âge |
|---|---|---|---|---|
| Couverture (attendu 80 %) | 67,8 % (Joux 59,4 %) | 71,8 % (Joux 61,6 %) | 70,1 % (Joux **55,9 %**) | 71,1 % (Joux 60,2 %) |
| Largeur moyenne | 9,0 m | 9,1 m | 8,8 m | 8,9 m |

| Temps sur CPU (mur, s ; 1 fil) | gbm_011 (3 blocs) | gbm (6 blocs) | gbm_ortho | sans âge |
|---|---|---|---|---|
| train | 1 099 | 2 405 | 2 522 | 2 586 |
| infer | 344 (96 dalles) | 621 (144 dalles) | 542 | 595 |
| ingest à smooth | 1 450 (24 min) | 3 037 (51 min) | 3 074 (51 min) | 3 193 (53 min) |

`gbm` et `gbm_ortho_sans_age` ont tourné en même temps (1 fil chacun sur 4 CPU), `gbm_ortho` seul (mission 013). Doubler l'apprentissage double à peu près le temps d'entraînement ; l'ortho y ajoute 5 %. Le script de mesure a pris 831 s (quatre gbm rejoués pour p10 et p90).

## La cause n° 1 : de combien l'excès sous 20 m a-t-il baissé ?

Excès = n × (MAE produit − MAE FORMS-T), en milliers de m·cellule, classes < 10 m et 10–20 m.

| Bloc, sous 20 m | gbm_011 | gbm | gbm_ortho | sans âge |
|---|---:|---:|---:|---:|
| `joux` | 75,9 | 73,6 | 58,1 | 61,8 |
| `chaux_b` | 33,5 | 30,9 | 15,0 | 17,3 |
| `altitude_b` | −2,9 | 57,1 | 49,3 | 46,5 |
| **Total** | **106,5** | 161,6 | **122,5** | 125,5 |

- **Au total, il n'a pas baissé : +15 %** (106,5 → 122,5).
- **L'ortho a fait son travail là où la cause avait été vue** : sur la Joux et Chaux, l'excès sous 20 m baisse d'un tiers (109,4 → 73,1, −33 %) ; entre `gbm` et `gbm_ortho`, il baisse de 24 % sur les trois blocs (161,6 → 122,5). Le biais sous 10 m passe de +8,1 à +6,8 m (FORMS-T +4,2).
- **Les blocs en plus ont créé une nouvelle perte sur `altitude_b`** : la classe 10–20 m de ce bloc passe de +4,4 à +7,1 m de biais (excès −4,3 → +54,5), et tout `altitude_b` passe d'un biais de −1,1 à +1,5 m (+1,8 m avec l'ortho). Au total, les blocs en plus font monter le biais de gbm de +0,3 à +1,3 m au pixel.
- L'excès **net** (toutes classes) baisse, lui, de 91,3 à 30,1 : `gbm_ortho` bat FORMS-T de plus en plus au-dessus de 30 m (surtout sur `altitude_b`, −70,7), ce que le critère au peuplement ne récompense pas, puisque le peuplement moyenne les deux erreurs de signe contraire.

## Causes d'erreur restantes (Pareto de l'excès de gbm_ortho sur FORMS-T, au pixel)

Excès brut (groupes où gbm_ortho fait pire) : 150,6 k m·cellule ; gbm_ortho regagne 120,5 ailleurs.

| Cause (bloc · classe) | Excès (k m·cellule) | % | % cumulé |
|---|---:|---:|---:|
| Peuplements bas encore surestimés, Joux et Chaux (`joux` < 10 m 20,8 ; `joux` 10–20 m 37,3 ; `chaux_b` 10–20 m 16,7) | 74,8 | 49,7 | 49,7 |
| Nouvelle surestimation de `altitude_b` 10–20 m après l'ajout des blocs | 50,3 | 33,4 | 83,1 |
| ——— trait ——— | | | |
| Transfert vers la Joux, 20–30 m (biais +1,7 m) | 25,4 | 16,9 | 100 |

1. **Peuplements bas et trouées surestimés (toujours la cause n° 1, 50 %).** L'ortho en a retiré un tiers, pas plus : sous 20 m, le biais reste de +6,2 à +6,8 m (FORMS-T +2,9 à +4,2). Pourquoi (hypothèses, non testées) : le poids × 3 des arbres de plus de 30 m tire toujours vers le haut et la pondération des peuplements bas (déjà en conf, `poids_peuplements_bas`, désactivée) n'a pas été essayée ; l'ortho est postérieure de 11 à 13 mois au vol sur ces deux blocs.
2. **Surestimation de `altitude_b` venue des nouveaux blocs (33 %).** Elle apparaît avec `gbm` (6 blocs) sans ortho, donc elle ne vient pas de l'ortho. Elle touche la tranche 1 200–1 400 m (biais −1,0 → +1,8 m). Pourquoi (hypothèse à vérifier sur les blocs d'apprentissage) : `altitude_c` (1 121–1 430 m, vol fin octobre-novembre, à 10,05 km de `altitude_b`) et `sapiniere_c` apportent des peuplements d'altitude plus hauts à descripteurs égaux, ou une phénologie de fin de saison différente. Ce n'est pas une fuite : aucune dalle de test n'est en apprentissage.
3. **Transfert vers la Joux (17 %).** Inchangé depuis 011 (20–30 m : +1,8 → +1,7 m) ; ni les blocs `_c` ni l'ortho ne l'ont réduit.

À côté, une cause de **Méthode**, non chiffrée : les trois modèles finissent entre 1 988 et 2 000 tours sur 2 000, ils sont peut-être sous-entraînés. Cela se règle sur les blocs de validation (dalles d'apprentissage), pas sur le test.

**L'âge de l'ortho (réserve 013).** Il pèse 2,4 % de l'importance (gain) du modèle de hauteur de `gbm_ortho` (9e descripteur sur 124), et chaque bloc a presque une seule date d'ortho : c'est bien, en pratique, un identifiant de région. Mais l'ablation ne montre **aucun effet mesurable** au peuplement (−0,04 [−0,13 ; +0,07] par polygone, +0,02 [−0,02 ; +0,07] à l'hectare) ni au pixel (3,42 contre 3,42). Seul signe : la couverture p10–p90 sur la Joux baisse avec l'âge (55,9 % contre 60,2 %). Le garder ou l'ôter ne change pas la mesure ; c'est une question de principe (le brief veut que le modèle connaisse l'âge), à trancher par Pascal.

## Pour regarder dans QGIS : les trouées de la Joux

Bloc `joux` (test), 16 dalles : `0926-6643` à `0929-6646` (x de 926 à 929, y de 6643 à 6646 ; coin nord-ouest en km). Pour chaque dalle `{d}` :

- gbm_ortho : `/data/mesure_014/gbm_ortho/infer/2022/{d}_hauteur_brute.tif` (incertitude : `{d}_hauteur_incertitude_brute.tif`) ;
- gbm d'origine : `/data/mesure_011/gbm/infer/2022/{d}_hauteur_brute.tif` (3 blocs) et `/data/mesure_014/gbm/infer/2022/{d}_hauteur_brute.tif` (6 blocs) ;
- FORMS-T v1 : `/data/echantillon_jura/references/forms_t_v1/{d}_hauteur_2022.tif` ;
- cible LiDAR : `/data/mesure_014/gbm_ortho/targets/2022/{d}_cible_hauteur.tif` ;
- ortho résumée à 10 m : `/data/echantillon_jura/ortho/{d}_ortho_10m.tif`.

Toutes les hauteurs sont en cm (uint16, nodata 65535), Lambert-93.

## Ce qui n'a pas été mesuré

- **Variabilité due à l'apprentissage :** une seule graine. Les écarts de 0,05 m entre modèles (blocs, âge) sont du même ordre que ce qu'une autre graine pourrait donner ; seuls les écarts appariés dont l'IC exclut 0 sont lus comme des effets.
- **Séparer ortho et trouées S2 :** ils sont dans la même paire. La mission 013 donne les trouées à moins de 2 % du gain (sur l'apprentissage), non remesuré ici.
- **Pondération des peuplements bas, `tours_max` plus grand :** ce seraient des réglages ; rien n'a été réglé.
- **Ortho de 2020 :** seul le millésime 2023 provisoire a été mesuré (question posée à Pascal, journal 012).
- **`trivial` :** celui de 011 (3 blocs), pour mémoire. Avec 6 blocs il fait 4,53 m au pixel (`docs/echantillon_jura.md`).
- **Mêmes limites qu'en 011 :** 3 blocs de test seulement, 25 polygones sur `altitude_b`, polygones comptés par dalle, couche lissée identique à la brute, FORMS-T entraîné sur des données dont on ne sait pas si elles recouvrent nos blocs.

## Conclusion

- **gbm_ortho ne bat pas FORMS-T v1 au peuplement.**
  - Par polygone : 1,85 [1,64–2,04] contre 1,67 [1,45–1,88], écart +0,18 [−0,08 ; +0,41]. **Égalité statistique** ; c'est un vrai progrès depuis 011 (+0,56, défaite nette).
  - Par hectare : 2,11 [1,94–2,27] contre 1,89 [1,79–2,01], écart **+0,22 [+0,02 ; +0,40]**. **Défaite** de justesse ; en 011, c'était une égalité (+0,16 [−0,07 ; +0,38]). Ce n'est pas une dégradation : face à gbm_011, gbm_ortho fait +0,06 [−0,15 ; +0,27] à l'hectare, sans différence significative ; l'intervalle de l'écart à FORMS-T a seulement franchi zéro.
  - Il bat FORMS-T sur Chaux à l'hectare (−0,34 [−0,62 ; −0,05]) et sur les arbres de plus de 30 m (3,86 contre 5,18 m) ; il perd sur la Joux et sur `altitude_b`.
- **Parts :** par polygone, sur un gain de −0,38 m : **ortho −0,29** (significatif, les trois quarts), blocs en plus −0,05 et âge −0,04 (dans le bruit). À l'hectare, rien de significatif : les blocs en plus (+0,09) annulent l'ortho (−0,05).
- **Cause n° 1 :** l'excès sous 20 m **ne baisse pas au total (+15 %)**. Il baisse d'un tiers sur la Joux et Chaux grâce à l'ortho, mais les nouveaux blocs ont créé une surestimation des peuplements de 10–20 m sur `altitude_b`.
- **Deux ou trois causes sur lesquelles agir :** (1) les peuplements bas encore surestimés (50 %) ; (2) la surestimation d'`altitude_b` apportée par les blocs `_c` (33 %) ; (3) le transfert vers la Joux (17 %). La suite revient à Pascal.

## Annexe : tableaux complets (sortie de `scripts/mesurer_modeles.py`)

Commande :

```
python scripts/mesurer_modeles.py \
  --modele trivial=/data/mesure_011/conf/chaine_trivial.yaml \
  --modele gbm_011=/data/mesure_011/conf/chaine_gbm.yaml \
  --modele gbm=/data/mesure_014/conf/chaine_gbm.yaml \
  --modele gbm_ortho=/data/mesure_014/conf/chaine_gbm_ortho.yaml \
  --modele gbm_ortho_sans_age=/data/mesure_014/conf/chaine_gbm_ortho_sans_age.yaml \
  --quantiles gbm_011 gbm gbm_ortho gbm_ortho_sans_age \
  --paire gbm-gbm_011 --paire gbm_ortho-gbm --paire gbm_ortho_sans_age-gbm \
  --paire gbm_ortho-gbm_ortho_sans_age --paire gbm_ortho-gbm_011 --exces \
  --sortie /data/mesure_014/mesure.json
```

Réglages : surface minimale 0,5 ha ; part minimale 0,5 ; 1 000 tirages ; graine 42 ; classes 10, 20 et 30 m ; tranches d'altitude de 200 m. Durée : 831 s. Sorties : `/data/mesure_014/mesure.json` et `mesure.md`.

### Critère principal : MAE au peuplement (m), IC 95 % bootstrap sur les dalles

#### Par polygone BD Forêt

| Portée | unités | dalles | trivial MAE [IC] | gbm_011 MAE [IC] | gbm MAE [IC] | gbm_ortho MAE [IC] | gbm_ortho_sans_age MAE [IC] | forms_t_v1 MAE [IC] | trivial − FORMS-T [IC] | gbm_011 − FORMS-T [IC] | gbm − FORMS-T [IC] | gbm_ortho − FORMS-T [IC] | gbm_ortho_sans_age − FORMS-T [IC] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| total | 164 | 48 | 3.08 [2.34–3.83] | 2.23 [1.93–2.46] | 2.18 [1.88–2.41] | 1.85 [1.64–2.04] | 1.89 [1.64–2.11] | 1.67 [1.45–1.88] | 1.41 [0.74–2.10] | 0.56 [0.25–0.81] | 0.52 [0.22–0.74] | 0.18 [-0.08–0.41] | 0.23 [-0.06–0.46] |
| altitude_b | 25 | 16 | 2.29 [0.97–3.94] | 1.70 [1.13–2.19] | 1.63 [1.27–1.99] | 1.67 [1.31–2.08] | 1.64 [1.28–2.04] | 1.28 [0.86–1.72] | 1.02 [-0.32–2.89] | 0.42 [-0.36–1.17] | 0.35 [-0.01–0.76] | 0.39 [0.07–0.76] | 0.36 [0.06–0.71] |
| chaux_b | 74 | 16 | 2.30 [1.65–2.90] | 2.37 [1.95–2.70] | 2.31 [1.86–2.65] | 1.77 [1.43–2.01] | 1.80 [1.45–2.08] | 1.79 [1.46–2.20] | 0.51 [-0.13–0.99] | 0.58 [0.02–0.94] | 0.52 [-0.10–0.90] | -0.03 [-0.57–0.32] | 0.01 [-0.55–0.35] |
| joux | 65 | 16 | 4.27 [3.07–5.46] | 2.27 [1.83–2.71] | 2.25 [1.84–2.64] | 2.01 [1.66–2.33] | 2.09 [1.66–2.49] | 1.67 [1.38–1.93] | 2.59 [1.57–3.59] | 0.60 [0.20–0.98] | 0.58 [0.20–0.94] | 0.34 [-0.01–0.71] | 0.42 [0.03–0.82] |

Écarts appariés entre produits, par polygone BD Forêt (m) [IC 95 %] :

| Portée | gbm − gbm_011 | gbm_ortho − gbm | gbm_ortho_sans_age − gbm | gbm_ortho − gbm_ortho_sans_age | gbm_ortho − gbm_011 |
|---|---:|---:|---:|---:|---:|
| total | -0.05 [-0.18–0.07] | -0.33 [-0.50–-0.13] | -0.29 [-0.43–-0.15] | -0.04 [-0.13–0.07] | -0.38 [-0.60–-0.13] |
| altitude_b | -0.07 [-0.69–0.69] | 0.04 [-0.13–0.22] | 0.01 [-0.17–0.18] | 0.03 [-0.01–0.08] | -0.02 [-0.74–0.84] |
| chaux_b | -0.06 [-0.17–0.02] | -0.55 [-0.86–-0.09] | -0.51 [-0.75–-0.23] | -0.04 [-0.18–0.17] | -0.61 [-0.93–-0.21] |
| joux | -0.02 [-0.13–0.07] | -0.23 [-0.41–-0.06] | -0.16 [-0.30–-0.01] | -0.08 [-0.21–0.08] | -0.26 [-0.51–-0.02] |

#### Par cellule de 1 ha

| Portée | unités | dalles | trivial MAE [IC] | gbm_011 MAE [IC] | gbm MAE [IC] | gbm_ortho MAE [IC] | gbm_ortho_sans_age MAE [IC] | forms_t_v1 MAE [IC] | trivial − FORMS-T [IC] | gbm_011 − FORMS-T [IC] | gbm − FORMS-T [IC] | gbm_ortho − FORMS-T [IC] | gbm_ortho_sans_age − FORMS-T [IC] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| total | 4643 | 48 | 2.92 [2.47–3.43] | 2.05 [1.86–2.25] | 2.14 [1.97–2.31] | 2.11 [1.94–2.27] | 2.09 [1.92–2.25] | 1.89 [1.79–2.01] | 1.03 [0.55–1.54] | 0.16 [-0.07–0.38] | 0.25 [0.03–0.43] | 0.22 [0.02–0.40] | 0.20 [-0.01–0.39] |
| altitude_b | 1544 | 16 | 2.23 [1.86–2.71] | 1.80 [1.53–2.15] | 2.04 [1.79–2.26] | 2.16 [1.90–2.39] | 2.12 [1.87–2.37] | 1.77 [1.59–1.99] | 0.45 [0.05–0.99] | 0.03 [-0.33–0.48] | 0.27 [0.05–0.47] | 0.38 [0.17–0.58] | 0.35 [0.13–0.55] |
| chaux_b | 1595 | 16 | 1.90 [1.56–2.24] | 1.81 [1.58–2.07] | 1.80 [1.53–2.11] | 1.69 [1.48–1.90] | 1.66 [1.47–1.86] | 2.02 [1.83–2.20] | -0.13 [-0.58–0.33] | -0.22 [-0.55–0.15] | -0.22 [-0.58–0.18] | -0.34 [-0.62–-0.05] | -0.36 [-0.63–-0.07] |
| joux | 1504 | 16 | 4.72 [4.01–5.50] | 2.57 [2.37–2.82] | 2.60 [2.38–2.86] | 2.51 [2.32–2.74] | 2.51 [2.29–2.78] | 1.88 [1.71–2.04] | 2.84 [2.20–3.56] | 0.70 [0.48–0.94] | 0.72 [0.50–0.98] | 0.64 [0.41–0.88] | 0.64 [0.38–0.91] |

Écarts appariés entre produits, par cellule de 1 ha (m) [IC 95 %] :

| Portée | gbm − gbm_011 | gbm_ortho − gbm | gbm_ortho_sans_age − gbm | gbm_ortho − gbm_ortho_sans_age | gbm_ortho − gbm_011 |
|---|---:|---:|---:|---:|---:|
| total | 0.09 [-0.09–0.25] | -0.03 [-0.14–0.09] | -0.05 [-0.15–0.05] | 0.02 [-0.02–0.07] | 0.06 [-0.15–0.27] |
| altitude_b | 0.24 [-0.26–0.66] | 0.12 [-0.00–0.23] | 0.09 [-0.02–0.18] | 0.03 [-0.02–0.08] | 0.36 [-0.21–0.82] |
| chaux_b | -0.00 [-0.07–0.06] | -0.12 [-0.37–0.15] | -0.14 [-0.33–0.05] | 0.02 [-0.06–0.12] | -0.12 [-0.33–0.11] |
| joux | 0.03 [-0.01–0.07] | -0.09 [-0.20–0.05] | -0.09 [-0.24–0.08] | 0.00 [-0.07–0.09] | -0.06 [-0.17–0.08] |

### Au pixel : MAE / biais (m)

| Portée | n | trivial | gbm_011 | gbm | gbm_ortho | gbm_ortho_sans_age | forms_t_v1 |
|---|---:|---|---|---|---|---|---|
| total | 462467 | 4.43 / 0.42 | 3.55 / 0.31 | 3.51 / 1.31 | 3.42 / 0.85 | 3.42 / 0.95 | 3.35 / -1.17 |
| altitude_b | 154023 | 4.23 / 0.72 | 3.80 / -1.13 | 3.68 / 1.52 | 3.59 / 1.77 | 3.58 / 1.73 | 3.75 / -1.09 |
| chaux_b | 159450 | 2.77 / 0.27 | 2.68 / 0.77 | 2.68 / 1.00 | 2.60 / -0.27 | 2.61 / -0.03 | 2.67 / -1.81 |
| joux | 148994 | 6.41 / 0.26 | 4.23 / 1.32 | 4.22 / 1.43 | 4.11 / 1.10 | 4.12 / 1.20 | 3.68 / -0.56 |

### Par classe de hauteur cible : MAE / biais (m), total

| Classe | part | trivial | gbm_011 | gbm | gbm_ortho | gbm_ortho_sans_age | forms_t_v1 |
|---|---:|---|---|---|---|---|---|
| < 10 m | 3.1% | 20.36 / 20.36 | 8.23 / 8.11 | 8.06 / 7.90 | 7.04 / 6.78 | 7.03 / 6.79 | 5.77 / 4.24 |
| 10-20 m | 12.6% | 8.84 / 8.84 | 5.95 / 5.69 | 6.94 / 6.70 | 6.51 / 6.20 | 6.57 / 6.27 | 4.72 / 2.90 |
| 20-30 m | 67.9% | 2.13 / -0.12 | 2.64 / 0.11 | 2.60 / 1.18 | 2.57 / 0.69 | 2.58 / 0.79 | 2.55 / -1.22 |
| > 30 m | 16.4% | 7.56 / -7.56 | 4.60 / -4.44 | 3.78 / -3.51 | 3.86 / -3.68 | 3.78 / -3.55 | 5.18 / -5.08 |

### Incertitude p10-p90

| Modèle | Portée | couverture | part nulle | largeur moy. (m) | part 1 scène claire | part nulle si ≥ 2 scènes |
|---|---|---:|---:|---:|---:|---:|
| gbm_011 | total | 67.8% | 0.0% | 9.03 | 0.0% | 0.0% |
| gbm | total | 71.8% | 0.0% | 9.06 | 0.0% | 0.0% |
| gbm_ortho | total | 70.1% | 0.0% | 8.80 | 0.0% | 0.0% |
| gbm_ortho_sans_age | total | 71.1% | 0.0% | 8.94 | 0.0% | 0.0% |
| gbm_011 | altitude_b | 68.3% | 0.0% | 10.40 | 0.0% | 0.0% |
| gbm | altitude_b | 73.0% | 0.0% | 9.76 | 0.0% | 0.0% |
| gbm_ortho | altitude_b | 75.3% | 0.0% | 9.67 | 0.0% | 0.0% |
| gbm_ortho_sans_age | altitude_b | 74.5% | 0.0% | 9.51 | 0.0% | 0.0% |
| gbm_011 | chaux_b | 75.1% | 0.0% | 7.74 | 0.0% | 0.0% |
| gbm | chaux_b | 80.2% | 0.0% | 8.27 | 0.0% | 0.0% |
| gbm_ortho | chaux_b | 78.2% | 0.0% | 8.19 | 0.0% | 0.0% |
| gbm_ortho_sans_age | chaux_b | 77.9% | 0.0% | 8.34 | 0.0% | 0.0% |
| gbm_011 | joux | 59.4% | 0.0% | 8.99 | 0.0% | 0.0% |
| gbm | joux | 61.6% | 0.0% | 9.18 | 0.0% | 0.0% |
| gbm_ortho | joux | 55.9% | 0.0% | 8.53 | 0.0% | 0.0% |
| gbm_ortho_sans_age | joux | 60.2% | 0.0% | 8.98 | 0.0% | 0.0% |

### Causes : Bloc × classe, MAE / biais au pixel (m)

| Groupe | n | h moy. (m) | trivial | gbm_011 | gbm | gbm_ortho | gbm_ortho_sans_age | forms_t_v1 |
|---|---:|---:|---|---|---|---|---|---|
| altitude_b · < 10 m | 3051 | 3.78 | 21.57 / 21.57 | 8.32 / 8.19 | 8.70 / 8.52 | 7.52 / 7.22 | 7.44 / 7.13 | 7.85 / 7.40 |
| altitude_b · 10-20 m | 22726 | 17.01 | 8.34 / 8.34 | 4.71 / 4.39 | 7.30 / 7.14 | 7.11 / 6.96 | 7.00 / 6.84 | 4.90 / 4.17 |
| altitude_b · 20-30 m | 105372 | 25.24 | 2.28 / 0.11 | 2.99 / -1.54 | 2.73 / 1.23 | 2.78 / 1.54 | 2.78 / 1.51 | 2.80 / -1.32 |
| altitude_b · > 30 m | 22874 | 32.19 | 6.84 / -6.84 | 6.00 / -5.95 | 3.80 / -3.64 | 3.33 / -3.06 | 3.33 / -3.06 | 6.42 / -6.39 |
| chaux_b · < 10 m | 2054 | 5.53 | 19.82 / 19.82 | 8.68 / 8.63 | 7.60 / 7.45 | 6.06 / 5.59 | 6.24 / 5.91 | 6.88 / 4.62 |
| chaux_b · 10-20 m | 10233 | 16.43 | 8.92 / 8.92 | 6.67 / 6.39 | 6.63 / 6.20 | 5.39 / 4.55 | 5.58 / 4.86 | 3.76 / 1.20 |
| chaux_b · 20-30 m | 138720 | 25.64 | 1.88 / -0.29 | 2.22 / 0.52 | 2.26 / 0.80 | 2.25 / -0.47 | 2.24 / -0.23 | 2.36 / -1.91 |
| chaux_b · > 30 m | 8443 | 31.10 | 5.75 / -5.75 | 3.95 / -3.91 | 3.58 / -3.53 | 4.20 / -4.19 | 4.13 / -4.11 | 5.43 / -5.43 |
| joux · < 10 m | 9149 | 5.27 | 20.08 / 20.08 | 8.09 / 7.96 | 7.94 / 7.79 | 7.10 / 6.90 | 7.08 / 6.87 | 4.83 / 3.10 |
| joux · 10-20 m | 25285 | 16.09 | 9.26 / 9.26 | 6.78 / 6.57 | 6.74 / 6.50 | 6.43 / 6.18 | 6.58 / 6.34 | 4.95 / 2.46 |
| joux · 20-30 m | 69837 | 25.48 | 2.39 / -0.13 | 2.95 / 1.81 | 3.08 / 1.88 | 2.91 / 1.70 | 2.95 / 1.73 | 2.55 / 0.30 |
| joux · > 30 m | 44723 | 33.62 | 8.27 / -8.27 | 4.00 / -3.77 | 3.81 / -3.45 | 4.07 / -3.91 | 3.95 / -3.69 | 4.50 / -4.35 |

### Causes : Essence BD Forêt, MAE / biais au pixel (m)

| Groupe | n | h moy. (m) | trivial | gbm_011 | gbm | gbm_ortho | gbm_ortho_sans_age | forms_t_v1 |
|---|---:|---:|---|---|---|---|---|---|
| Chênes décidus | 120242 | 25.34 | 2.55 / 0.01 | 2.42 / 0.45 | 2.41 / 0.75 | 2.42 / -0.36 | 2.39 / -0.21 | 2.64 / -1.98 |
| Conifères | 3789 | 21.10 | 5.86 / 4.25 | 3.81 / 3.04 | 3.58 / 2.46 | 3.40 / 1.00 | 3.33 / 1.22 | 3.05 / -1.67 |
| Douglas | 1082 | 27.68 | 3.22 / -2.33 | 2.98 / -0.41 | 2.92 / 0.73 | 2.78 / -1.47 | 2.81 / -1.04 | 3.14 / -2.52 |
| Feuillus | 11035 | 22.97 | 3.57 / 2.38 | 3.19 / 2.26 | 3.32 / 2.37 | 2.76 / 0.70 | 2.96 / 1.19 | 2.61 / -1.35 |
| Hêtre | 6763 | 26.49 | 3.25 / -1.14 | 2.72 / -0.50 | 2.58 / -0.13 | 3.07 / -1.75 | 3.10 / -1.52 | 2.86 / -1.80 |
| Mixte | 46319 | 24.78 | 4.13 / 0.57 | 4.07 / -0.08 | 3.61 / 0.53 | 3.40 / 0.16 | 3.51 / 0.56 | 3.36 / -0.28 |
| NC | 1434 | 1.66 | 23.69 / 23.69 | 4.85 / 4.52 | 3.99 / 3.61 | 2.57 / 2.04 | 2.54 / 1.96 | 2.07 / 0.99 |
| NR | 1051 | 11.80 | 13.63 / 13.55 | 4.97 / 4.18 | 4.33 / 3.19 | 3.92 / 2.46 | 3.96 / 2.61 | 3.52 / -2.16 |
| Pin autre | 3927 | 24.68 | 2.92 / 0.67 | 4.04 / 3.59 | 4.60 / 4.35 | 2.92 / 1.83 | 3.25 / 2.34 | 3.12 / -1.68 |
| Pin sylvestre | 1740 | 22.40 | 4.20 / 2.95 | 4.74 / -0.50 | 5.07 / -0.71 | 6.33 / -3.04 | 5.49 / -1.56 | 2.32 / -0.44 |
| Sapin, épicéa | 264741 | 25.06 | 5.27 / 0.29 | 3.98 / 0.14 | 3.99 / 1.63 | 3.91 / 1.60 | 3.89 / 1.59 | 3.74 / -0.92 |

### Causes : Tranche d'altitude (MNT), MAE / biais au pixel (m)

| Groupe | n | h moy. (m) | trivial | gbm_011 | gbm | gbm_ortho | gbm_ortho_sans_age | forms_t_v1 |
|---|---:|---:|---|---|---|---|---|---|
| 200-400 m | 159450 | 25.08 | 2.77 / 0.27 | 2.68 / 0.77 | 2.68 / 1.00 | 2.60 / -0.27 | 2.61 / -0.03 | 2.67 / -1.81 |
| 600-800 m | 135005 | 25.01 | 6.33 / 0.34 | 4.19 / 1.40 | 4.18 / 1.52 | 4.08 / 1.23 | 4.09 / 1.30 | 3.66 / -0.66 |
| 800-1000 m | 14767 | 25.83 | 7.13 / -0.48 | 4.59 / 0.55 | 4.54 / 0.52 | 4.42 / -0.16 | 4.39 / 0.27 | 3.93 / 0.35 |
| 1000-1200 m | 24463 | 24.38 | 5.44 / 0.97 | 4.36 / -1.59 | 3.75 / 0.24 | 3.55 / 0.38 | 3.55 / 0.39 | 3.93 / -1.47 |
| 1200-1400 m | 128782 | 24.68 | 4.00 / 0.67 | 3.69 / -1.05 | 3.66 / 1.77 | 3.60 / 2.03 | 3.58 / 1.99 | 3.71 / -1.02 |

### Excès sur FORMS-T : n × (MAE produit − MAE FORMS-T), k m·cellule

| Groupe | trivial | gbm_011 | gbm | gbm_ortho | gbm_ortho_sans_age |
|---|---:|---:|---:|---:|---:|
| altitude_b · < 10 m | 41.9 | 1.4 | 2.6 | -1.0 | -1.2 |
| altitude_b · 10-20 m | 78.2 | -4.3 | 54.5 | 50.3 | 47.7 |
| altitude_b · 20-30 m | -54.7 | 20.4 | -7.6 | -2.3 | -2.2 |
| altitude_b · > 30 m | 9.8 | -9.4 | -59.9 | -70.7 | -70.6 |
| chaux_b · < 10 m | 26.6 | 3.7 | 1.5 | -1.7 | -1.3 |
| chaux_b · 10-20 m | 52.9 | 29.8 | 29.4 | 16.7 | 18.6 |
| chaux_b · 20-30 m | -65.8 | -19.3 | -13.7 | -15.2 | -15.7 |
| chaux_b · > 30 m | 2.7 | -12.5 | -15.6 | -10.4 | -11.0 |
| joux · < 10 m | 139.6 | 29.8 | 28.5 | 20.8 | 20.6 |
| joux · 10-20 m | 108.9 | 46.1 | 45.1 | 37.3 | 41.2 |
| joux · 20-30 m | -11.2 | 27.7 | 37.3 | 25.4 | 28.2 |
| joux · > 30 m | 168.7 | -22.1 | -30.7 | -19.3 | -24.5 |
| **sous 20 m** | 448.0 | 106.5 | 161.6 | 122.5 | 125.5 |
| **total net** | 497.5 | 91.3 | 71.3 | 30.1 | 29.8 |
| **brut (positifs)** | 629.1 | 158.9 | 198.8 | 150.6 | 156.3 |
