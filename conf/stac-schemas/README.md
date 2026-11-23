# Schémas JSON des extensions STAC (validation hors ligne)

Téléchargés le **2026-11-22** par `acquereur` (mission 001), sans modification. Propriétaire : Pascal. Format : JSON Schema draft-07.

| Fichier | Extension | Version | URL source |
|---|---|---|---|
| `projection-v2.0.0.json` | projection | v2.0.0 (celle que pystac 1.16.1 écrit par défaut) | https://stac-extensions.github.io/projection/v2.0.0/schema.json |
| `projection-v2.1.0.json` | projection | v2.1.0 (la plus récente trouvée) | https://stac-extensions.github.io/projection/v2.1.0/schema.json |
| `raster-v1.1.0.json` | raster | v1.1.0 (celle que pystac 1.16.1 écrit par défaut) | https://stac-extensions.github.io/raster/v1.1.0/schema.json |
| `raster-v2.0.0.json` | raster | v2.0.0 (la plus récente trouvée ; non gérée par pystac 1.16.1) | https://stac-extensions.github.io/raster/v2.0.0/schema.json |
| `file-v2.1.0.json` | file | v2.1.0 (la plus récente trouvée, et celle de pystac) | https://stac-extensions.github.io/file/v2.1.0/schema.json |
| `processing-v1.2.0.json` | processing | v1.2.0 | https://stac-extensions.github.io/processing/v1.2.0/schema.json |
| `processing-v1.3.0.json` | processing | v1.3.0 (la plus récente trouvée) | https://stac-extensions.github.io/processing/v1.3.0/schema.json |
| `externes/geometry-geojson.json` | schéma référencé par `projection` | — | https://geojson.org/schema/Geometry.json |
| `externes/projjson-v0.7.json` | schéma référencé par `projection` | v0.7 | https://proj.org/schemas/v0.7/projjson.schema.json (redirigé vers `https://proj.org/en/latest/schemas/v0.7/projjson.schema.json`) |

Versions recherchées en testant les URL `v1.0.0` à `v3.0.0` de chaque extension : seules les versions listées ci-dessus et `projection` v1.0.0/1.1.0/1.2.0, `raster` v1.0.0, `file` v1.0.0/2.0.0, `processing` v1.0.0/1.1.0 répondent 200. Le statut « stable » n'a pas été vérifié sur les dépôts GitHub (accès GitHub non disponible dans cette session) : la mention « la plus récente » veut dire « la plus haute version qui répond 200 » le 22/11/2026.

## Vérification faite

Chaque fichier est du JSON valide et se charge avec `jsonschema` 4.x (`Draft7Validator`) ; les `$ref` externes de `projection` (Geometry GeoJSON et PROJJSON) se résolvent avec les deux fichiers de `externes/` enregistrés dans un `referencing.Registry`. Un item minimal sans l'identifiant de l'extension dans `stac_extensions` est refusé comme attendu (le schéma l'exige).

## À savoir pour la mission 004

- **pystac 1.16.1 embarque déjà** les schémas du cœur STAC 1.1.0 (`item`, `catalog`, `collection`, etc., dans `pystac/validation/jsonschemas/stac-spec`) et le schéma GeoJSON : inutile de les télécharger ici.
- pystac embarque aussi `projection` (v1.0.0 à v2.0.0), `raster` (v1.0.0, v1.1.0) et `file` (v1.0.0, v2.0.0, v2.1.0), dans `pystac/extensions/json-schema/`.
- **pystac 1.16.1 n'a ni module ni schéma `processing`** : un item portant `processing:*` ne sera validé hors ligne que si ce fichier est enregistré (sinon pystac tente le réseau). Les champs `processing:*` s'écrivent alors à la main, sans classe d'extension.
- **`raster` v2.0.0 et `projection` v2.1.0 ne sont pas gérées par pystac 1.16.1** : si le catalogue du projet les déclare dans `stac_extensions`, pystac ira chercher les schémas sur le réseau. Choisir la version déclarée (v1.1.0 / v2.0.0, ou les plus récentes) est une décision de la mission 004, non prise ici.
- Si la validation hors ligne doit résoudre `projjson` depuis ce dossier, il faut enregistrer `externes/projjson-v0.7.json` ; pystac 1.16.1 ne contient pas de copie de PROJJSON (non trouvé dans son paquet).
