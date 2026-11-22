"""Modèle C de l'ADR 0004 : LightGBM sur les descripteurs par cellule de 10 m (mission 009).

- Apprentissage sur les seules dalles d'apprentissage du découpage figé ; une dalle de test
  parmi les entrées est refusée (code 3).
- Arrêt anticipé sur des **blocs de validation** tirés (graine) parmi les blocs spatiaux des
  dalles d'apprentissage (`apprentissage.validation.taille_bloc_m`) ; un bloc ne sert jamais
  à la fois à l'ajustement et à la validation, et aucune cellule de test n'y entre.
- Poids d'échantillon pour les grandes hauteurs (`apprentissage.poids_grands_arbres`), sur
  le modèle de hauteur ; les quantiles ne sont pondérés que si `quantiles_ponderes` est vrai
  (faux par défaut : un quantile pondéré n'est plus le quantile de la distribution).
- Trois modèles : la hauteur (objectif de la conf, L1 par défaut) et les quantiles 0,1 et 0,9
  pour l'incertitude ; chacun s'écrit en texte LightGBM.
- Rejouable : graine de la conf, `deterministic`, nombre de fils fixé dans la conf.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from nemeton_canopee import descripteurs, grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import Dalle

ESSENCE = "essence"
ARRONDIS = {"demi_haut": lambda x: np.floor(x + 0.5)}


def _lgb():
    try:
        import lightgbm
    except ImportError as e:  # pragma: no cover - dépend de l'installation
        raise EntreeManquante(
            "lightgbm absent : pip install 'nemeton-canopee[ml]' (modèle gbm)"
        ) from e
    return lightgbm


@dataclass
class Table:
    """Cellules d'apprentissage : descripteurs, cible (cm), dalle et bloc de validation."""

    X: np.ndarray
    y: np.ndarray
    dalles: np.ndarray
    blocs: np.ndarray  # (n, 2) indices de bloc (x // taille, y // taille)
    noms: list[str]


def encoder_essence(essence: np.ndarray, vocabulaire: Sequence[str]) -> np.ndarray:
    """Code entier (0, 1, …) de l'essence ; NaN si absente ou hors du vocabulaire appris."""
    code = {v: float(i) for i, v in enumerate(vocabulaire)}
    return np.array([code.get(v, np.nan) for v in essence.ravel()]).reshape(essence.shape)


def blocs_cellules(dalle: str, conf: Configuration, taille_bloc_m: float) -> np.ndarray:
    """Indice de bloc (2, lignes, colonnes) du centre de chaque cellule de la dalle."""
    taille, pas = int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    lignes, colonnes = grille.forme(taille, pas)
    xmin, _, _, ymax = grille.emprise(dalle, taille)
    x = xmin + (np.arange(colonnes) + 0.5) * pas
    y = ymax - (np.arange(lignes) + 0.5) * pas
    xx, yy = np.meshgrid(x, y)
    return np.stack([np.floor(xx / taille_bloc_m), np.floor(yy / taille_bloc_m)]).astype("int64")


def choisir_blocs_validation(blocs: np.ndarray, part: float, graine: int) -> set[tuple[int, int]]:
    """Tire (graine) une part des blocs distincts pour la validation ; au moins 1, jamais tous."""
    uniques = sorted({(int(a), int(b)) for a, b in blocs})
    if len(uniques) < 2:
        raise DonneeRefusee(
            f"{len(uniques)} bloc de validation possible : impossible de valider par blocs "
            "(règle : arrêt anticipé validé par blocs ; réduire "
            "apprentissage.validation.taille_bloc_m)"
        )
    n = min(len(uniques) - 1, max(1, round(part * len(uniques))))
    tires = np.random.default_rng(graine).choice(len(uniques), size=n, replace=False)
    return {uniques[i] for i in sorted(tires)}


def controler_separation(
    blocs_ajustement: set,
    blocs_validation: set,
    dalles_validation: Sequence[str],
    dalles_test: Sequence[str],
) -> None:
    """Refuse (code 3) une validation qui partage un bloc avec l'ajustement ou touche le test."""
    communs = sorted(set(blocs_ajustement) & set(blocs_validation))
    if communs:
        raise DonneeRefusee(
            f"validation refusée : blocs {communs} à la fois en ajustement et en validation "
            "(règle : arrêt anticipé validé par blocs)"
        )
    interdites = sorted(set(dalles_validation) & set(dalles_test))
    if interdites:
        raise DonneeRefusee(
            f"validation refusée : dalles de test {interdites} dans l'arrêt anticipé "
            "(règle : jamais un pixel de test pour l'arrêt anticipé ni les réglages)"
        )


def table_apprentissage(
    conf: Configuration, ch: Chemins, dalles: Sequence[Dalle]
) -> tuple[Table, list[str]]:
    """Table des cellules d'apprentissage et vocabulaire d'essence (dalles d'apprentissage)."""
    taille_bloc = float(conf.modele["apprentissage"]["validation"]["taille_bloc_m"])
    lus = []
    for d in dalles:
        desc = descripteurs.calculer(conf, ch, d.id, d.annee)
        cible = _lire(exiger_fichier(ch.cible(d.annee, d.id), "targets"))
        foret = _lire(exiger_fichier(ch.foret(d.id), "prepare"))
        ok = (cible != conf.nodata) & (foret == 1) & desc.clair
        lus.append((d, desc, cible, ok))
    vocabulaire = sorted({str(v) for _, desc, _, ok in lus for v in desc.essence[ok]} - {""})
    X, y, ids, blocs = [], [], [], []
    noms: list[str] = []
    for d, desc, cible, ok in lus:
        ess = encoder_essence(desc.essence, vocabulaire)
        X.append(np.vstack([desc.valeurs[:, ok], ess[ok][None]]).T)
        y.append(cible[ok].astype("float64"))
        ids.append(np.full(int(ok.sum()), d.id))
        blocs.append(blocs_cellules(d.id, conf, taille_bloc)[:, ok].T)
        noms = [*desc.noms, ESSENCE]
    if not X or sum(len(v) for v in y) == 0:
        raise EntreeManquante("aucune cellule valide pour l'apprentissage (relancer targets)")
    table = Table(
        X=np.vstack(X),
        y=np.concatenate(y),
        dalles=np.concatenate(ids),
        blocs=np.vstack(blocs),
        noms=noms,
    )
    return table, vocabulaire


def _lire(chemin) -> np.ndarray:
    import rasterio

    with rasterio.open(chemin) as src:
        return src.read(1)


def poids(y: np.ndarray, regle: Mapping[str, Any]) -> np.ndarray:
    """Poids d'échantillon : `poids` au-dessus de `seuil_cm` (strictement), 1 ailleurs."""
    return np.where(y > float(regle["seuil_cm"]), float(regle["poids"]), 1.0)


def _params(conf: Configuration, **remplace: Any) -> dict[str, Any]:
    params = dict(conf.modele["lightgbm"])
    params.update(seed=conf.graine, **remplace)
    return params


def _ajuster(
    conf: Configuration,
    table: Table,
    w: np.ndarray,
    ajust: np.ndarray,
    valid: np.ndarray,
    params: dict[str, Any],
) -> tuple[str, int]:
    """Arrêt anticipé sur `valid`, puis (option) refit sur tout ; (texte du modèle, tours)."""
    lgb = _lgb()
    reglage = conf.modele["apprentissage"]

    def jeu(masque: np.ndarray, reference=None):
        return lgb.Dataset(
            table.X[masque],
            table.y[masque],
            weight=w[masque],
            feature_name=table.noms,
            categorical_feature=[ESSENCE],
            reference=reference,
            free_raw_data=False,
            params={"verbosity": -1},
        )

    d_ajust = jeu(ajust)
    d_valid = jeu(valid, d_ajust)
    booster = lgb.train(
        params,
        d_ajust,
        num_boost_round=int(reglage["tours_max"]),
        valid_sets=[d_valid],
        callbacks=[lgb.early_stopping(int(reglage["arret_anticipe_tours"]), verbose=False)],
    )
    tours = int(booster.best_iteration or booster.current_iteration())
    if reglage.get("reentrainer_sur_tout"):
        tout = np.ones(len(table.y), dtype=bool)
        booster = lgb.train(params, jeu(tout), num_boost_round=tours)
    return booster.model_to_string(num_iteration=tours), tours


def entrainer(
    conf: Configuration, ch: Chemins, dalles: Sequence[Dalle], dalles_test: Sequence[str]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Entraîne les trois modèles ; renvoie (métadonnées, {fichier: texte LightGBM})."""
    interdites = sorted({d.id for d in dalles} & set(dalles_test))
    if interdites:
        raise DonneeRefusee(
            f"découpage enfreint : dalles de test {interdites} parmi l'apprentissage"
        )
    reglage = conf.modele["apprentissage"]
    table, vocabulaire = table_apprentissage(conf, ch, dalles)
    blocs_valid = choisir_blocs_validation(
        table.blocs, float(reglage["validation"]["part_blocs"]), conf.graine
    )
    valid = np.array([(int(a), int(b)) in blocs_valid for a, b in table.blocs])
    ajust = ~valid
    controler_separation(
        {(int(a), int(b)) for a, b in table.blocs[ajust]},
        blocs_valid,
        sorted(set(table.dalles[valid])),
        dalles_test,
    )
    w = poids(table.y, reglage["poids_grands_arbres"])
    w_quantiles = w if reglage.get("quantiles_ponderes", False) else np.ones_like(w)
    fichiers: dict[str, str] = {}
    tours: dict[str, int] = {}
    modeles = {"hauteur": (_params(conf), w)}
    for q in reglage["quantiles"]:
        params_q = _params(conf, objective="quantile", alpha=float(q))
        modeles[_nom_quantile(q)] = (params_q, w_quantiles)
    for nom, (params, poids_nom) in modeles.items():
        texte, t = _ajuster(conf, table, poids_nom, ajust, valid, params)
        fichiers[f"{nom}.txt"] = texte
        tours[nom] = t
    meta = {
        "descripteurs": table.noms,
        "vocabulaire_essence": vocabulaire,
        "fichiers": {
            f: hashlib.sha256(t.encode("utf-8")).hexdigest() for f, t in sorted(fichiers.items())
        },
        "tours": tours,
        "quantiles": [float(q) for q in reglage["quantiles"]],
        "arrondi": conf.modele["arrondi"],
        "validation": {
            "taille_bloc_m": float(reglage["validation"]["taille_bloc_m"]),
            "blocs": [list(b) for b in sorted(blocs_valid)],
            "n_ajustement": int(ajust.sum()),
            "n_validation": int(valid.sum()),
        },
        "n_cellules": int(len(table.y)),
        "parametres": conf.modele,
        "version_lightgbm": _lgb().__version__,
    }
    return meta, fichiers


def _nom_quantile(q: float) -> str:
    return f"q{round(float(q) * 100):02d}"


def arrondir(valeurs_cm: np.ndarray, arrondi: str, nodata: int) -> np.ndarray:
    """Arrondi à l'entier (cm), borné à [0, nodata - 1]."""
    if arrondi not in ARRONDIS:
        raise DonneeRefusee(f"arrondi inconnu : {arrondi!r} (connus : {sorted(ARRONDIS)})")
    return np.clip(ARRONDIS[arrondi](valeurs_cm), 0, nodata - 1)


def predire(
    conf: Configuration,
    ch: Chemins,
    version: str,
    modele: Mapping[str, Any],
    dalle: Dalle,
    masque: np.ndarray,
) -> dict[str, np.ndarray]:
    """Hauteur et incertitude (p_haut − p_bas), uint16 cm, nodata hors `masque`."""
    lgb = _lgb()
    dossier = ch.modele(version).parent
    boosters = {}
    for fichier, empreinte in modele["fichiers"].items():
        texte = exiger_fichier(dossier / fichier, "train").read_text(encoding="utf-8")
        if hashlib.sha256(texte.encode("utf-8")).hexdigest() != empreinte:
            raise DonneeRefusee(f"modèle {version} : {fichier} modifié (empreinte différente)")
        boosters[fichier.removesuffix(".txt")] = lgb.Booster(model_str=texte)
    desc = descripteurs.calculer(conf, ch, dalle.id, dalle.annee)
    if [*desc.noms, ESSENCE] != list(modele["descripteurs"]):
        raise DonneeRefusee("descripteurs différents de ceux de l'entraînement (relancer train)")
    ess = encoder_essence(desc.essence, modele["vocabulaire_essence"])
    X = np.vstack([desc.valeurs[:, masque], ess[masque][None]]).T
    nodata = conf.nodata
    sortie = {}
    brutes = {}
    fils = int(conf.modele["lightgbm"]["num_threads"])
    for nom, booster in boosters.items():
        brutes[nom] = booster.predict(X, num_threads=fils) if len(X) else np.empty(0)
    bas, haut = (_nom_quantile(q) for q in sorted(modele["quantiles"]))
    centre = brutes["hauteur"]
    # Quantiles croisés possibles (modèles indépendants) : on borne pour p_bas <= h <= p_haut.
    p_bas = np.minimum(brutes[bas], centre)
    p_haut = np.maximum(brutes[haut], centre)
    arrondi = modele["arrondi"]
    for cle, valeurs in (
        ("hauteur", arrondir(centre, arrondi, nodata)),
        (bas, arrondir(p_bas, arrondi, nodata)),
        (haut, arrondir(p_haut, arrondi, nodata)),
    ):
        couche = np.full(masque.shape, nodata, dtype="uint16")
        couche[masque] = valeurs.astype("uint16")
        sortie[cle] = couche
    incertitude = np.full(masque.shape, nodata, dtype="uint16")
    incertitude[masque] = sortie[haut][masque] - sortie[bas][masque]
    sortie["incertitude"] = incertitude
    return sortie
