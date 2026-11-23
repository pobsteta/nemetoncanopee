# Mission 010 — option A : petit U-Net sur CPU

## Mission

**En une phrase :** Ajouter à la chaîne un petit U-Net (PyTorch CPU, extra `[ml]`) entraîné par patchs de 64×64 cellules sur les scènes S2 et le relief, perte L1 pondérée au-dessus de 30 m, médiane des scènes en inférence et dispersion comme incertitude, pour mesurer l'option A de l'ADR 0004 face à C.

## Les trois questions

oui · oui (brief « Modèle de hauteur », ADR 0004) · oui. **Temps de la main :** donner. **Degré :** le chef tranche (par délégation).

## L'Homme

`dev`, opus.

## Harnais

- **Peut :** `src/nemeton_canopee/models/unet.py`, `conf/modele/unet.yaml`, `pyproject.toml` (extra `[ml]` : torch CPU), `tests/test_modele_unet.py` ; `src/nemeton_canopee/models/__init__.py` et `infer/` seulement pour brancher le modèle.
- **Câblé :** pas de commit ni de push sur `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** exiger un GPU ; casser les autres modèles ; laisser la CI installer torch si ce n'est pas nécessaire (tests du U-Net ignorés proprement si l'extra n'est pas installé est INTERDIT : la CI installe l'extra, ou les tests utilisent un modèle minuscule).

**Dépend de :** 009 (même point de branchement `models/__init__.py`, `infer/`). **Ordre :** 009 → 010.

## Tests

Sur le jeu d'essai : entraînement de 1 époque en moins de 2 minutes CPU, chaîne complète avec `modele: unet`, rejouable (graine, déterminisme torch), incertitude cohérente.

## Qui veille, qui tranche

**Relecteur :** `relecteur` (3 allers-retours). **Qui tranche :** Claude (orchestrateur, par délégation de Pascal : « Fais ce qu'il y a de mieux », journal du 22/11).

## Ma réponse d'abord

_Rempli par Pascal seul._
