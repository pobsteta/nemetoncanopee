"""Modèle A de l'ADR 0004 : petit U-Net sur CPU, scène par scène (mission 010).

- **Entrées** d'une scène (une image par scène, comme FORMS-T) : bandes Sentinel-2 en
  réflectance (DN x `echelle_reflectance`), relief tiré du MNT de la zone (altitude, pente,
  exposition nord et est, voir `descripteurs.relief`) et la bande `clair` (SCL bon) ; chaque
  canal est centré-réduit avec la moyenne et l'écart-type des seules dalles d'ajustement ;
  une valeur absente (nuage, MNT sans donnée, exposition d'une cellule plate) vaut 0 après
  normalisation, le canal `clair` dit au réseau où la scène est lisible.
- **Apprentissage** sur les seules dalles d'apprentissage du découpage figé (une dalle de test
  parmi les entrées est refusée, code 3) : patchs carrés (`apprentissage.patch`) tirés de chaque
  scène avec recouvrement (`pas_patch`), padding miroir si la dalle est plus petite que le
  patch ; augmentation par rotations d'un quart de tour et symétrie, l'exposition (vecteur
  nord, est) tournée avec l'image ; perte L1 masquée (cible valide, forêt, scène claire),
  pondérée au-dessus de `poids_grands_arbres.seuil_cm`.
- **Arrêt anticipé** sur des **dalles de validation** : blocs spatiaux
  (`validation.taille_bloc_m`) tirés (graine) parmi ceux des dalles d'apprentissage ; une
  dalle de validation ne sert ni à l'ajustement ni à la normalisation ; les poids gardés sont
  ceux de la meilleure époque (MAE de validation).
- **Inférence** : chaque scène est prédite sur la dalle entière (padding miroir au multiple
  de 2^(niveaux - 1)) ; hauteur = médiane des scènes claires de la cellule, incertitude =
  p90 - p10 entre ces scènes (percentiles linéaires, cm).
- **Rejouable** : graine de la conf, `torch.use_deterministic_algorithms(True)`, nombre de
  fils fixé dans la conf ; les poids s'écrivent en octets bruts (float32 petit-boutiste, ordre
  du `state_dict`), sans horodate, avec leur sha256 dans `modele.json`.

Tous les paramètres viennent de `conf/modele/unet.yaml`. PyTorch (extra `[ml]`) n'est importé
qu'à l'usage.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import rasterio

from nemeton_canopee import descripteurs, grille
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import Dalle

POIDS = "poids.bin"
RELIEF = ["altitude_m", "pente_deg", "exposition_nord", "exposition_est"]
CLAIR = descripteurs.BANDE_CLAIR
ARRONDIS = {"demi_haut": lambda x: np.floor(x + 0.5)}


def _torch():
    try:
        import torch
    except ImportError as e:  # pragma: no cover - dépend de l'installation
        raise EntreeManquante(
            "torch absent : pip install 'nemeton-canopee[ml]' (modèle unet)"
        ) from e
    return torch


def preparer_torch(conf: Configuration):
    """Torch rejouable : graine, algorithmes déterministes, nombre de fils de la conf."""
    torch = _torch()
    torch.manual_seed(conf.graine)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(conf.modele["torch"]["num_threads"]))
    return torch


# --- Entrées --------------------------------------------------------------------------------


def noms_canaux(params: Mapping[str, Any]) -> list[str]:
    """Bandes, relief, puis `clair` : l'ordre des canaux d'entrée du réseau."""
    return [*params["bandes"], *RELIEF, CLAIR]


@dataclass
class EntreesDalle:
    """Entrées brutes d'une dalle : une pile (canaux, lignes, colonnes) par scène, NaN absents."""

    dalle: str
    scenes: list[np.ndarray]  # float64, canaux de `noms_canaux`
    clair: list[np.ndarray]  # booléen par scène


def entrees_dalle(conf: Configuration, ch: Chemins, dalle: str, annee: int) -> EntreesDalle:
    """Lit les scènes préparées de l'année de vol et le relief de la dalle."""
    params = conf.modele["descripteurs"]
    rel = descripteurs.relief(descripteurs.lire_mnt(conf, dalle), float(conf.grille["pas_m"]))
    relief = np.stack([rel[n] for n in RELIEF])
    piles, clairs = [], []
    for chemin in ch.scenes_preparees(annee, dalle):
        with rasterio.open(chemin) as src:
            pile, noms = src.read(), list(src.descriptions)
        variables = descripteurs.variables_scene(pile, noms, {**params, "indices": {}})
        clair = pile[noms.index(CLAIR)] == 1
        bandes = np.stack([variables[b] for b in params["bandes"]])
        piles.append(np.concatenate([bandes, relief, clair[None].astype("float64")]))
        clairs.append(clair)
    if not piles:
        raise EntreeManquante(f"aucune scène préparée pour {dalle} (relancer prepare)")
    return EntreesDalle(dalle=dalle, scenes=piles, clair=clairs)


def normalisation(entrees: Sequence[EntreesDalle]) -> tuple[list[float], list[float]]:
    """Moyenne et écart-type de chaque canal sur les valeurs présentes des dalles données.

    Accumulé en float64 dans l'ordre des dalles et des scènes : rejouable. Un canal constant
    garde un écart-type de 1.
    """
    somme = carres = compte = None
    for e in entrees:
        for pile in e.scenes:
            present = np.isfinite(pile)
            v = np.where(present, pile, 0.0)
            s, c, n = v.sum(axis=(1, 2)), (v * v).sum(axis=(1, 2)), present.sum(axis=(1, 2))
            somme = s if somme is None else somme + s
            carres = c if carres is None else carres + c
            compte = n if compte is None else compte + n
    if somme is None:
        raise EntreeManquante("aucune scène pour la normalisation (relancer prepare)")
    n = np.maximum(compte, 1)
    moyenne = somme / n
    ecart = np.sqrt(np.maximum(carres / n - moyenne**2, 0.0))
    ecart = np.where(ecart > 0, ecart, 1.0)
    return [float(x) for x in moyenne], [float(x) for x in ecart]


def _borne(conf: Configuration) -> float:
    return float(conf.modele["descripteurs"]["borne_normalisee"])


def normalisation_physique(
    norme: tuple[list[float], list[float]],
    canaux: Sequence[str],
    fixees: Mapping[str, Mapping[str, float]],
) -> tuple[list[float], list[float]]:
    """Remplace la moyenne et l'écart-type statistiques des canaux de `fixees` par un centre et
    une échelle physiques de la conf (l'altitude : une poignée de dalles d'apprentissage n'en
    donne pas la plage)."""
    inconnus = sorted(set(fixees) - set(canaux))
    if inconnus:
        raise DonneeRefusee(f"normalisation_physique : canaux inconnus {inconnus} (conf)")
    moyenne, ecart = list(norme[0]), list(norme[1])
    for nom, p in fixees.items():
        if float(p["echelle"]) <= 0:
            raise DonneeRefusee(f"normalisation_physique de {nom} : échelle <= 0 (conf)")
        i = list(canaux).index(nom)
        moyenne[i], ecart[i] = float(p["centre"]), float(p["echelle"])
    return moyenne, ecart


def normaliser(
    pile: np.ndarray, moyenne: Sequence[float], ecart: Sequence[float], borne: float
) -> np.ndarray:
    """Centre-réduit chaque canal, borné à [-borne, borne] (une dalle hors de la plage
    d'apprentissage, une altitude par exemple, ne fait pas extrapoler le réseau sans limite) ;
    une valeur absente (NaN) vaut 0. Sortie float32."""
    m = np.asarray(moyenne)[:, None, None]
    s = np.asarray(ecart)[:, None, None]
    z = np.clip((pile - m) / s, -borne, borne)
    return np.where(np.isfinite(pile), z, 0.0).astype("float32")


# --- Patchs et augmentation -----------------------------------------------------------------


def debuts(longueur: int, patch: int, pas: int) -> list[int]:
    """Débuts des fenêtres de `patch` cellules couvrant `longueur`, au pas `pas` (recouvrement).

    La dernière fenêtre est calée sur le bord ; si `longueur` < `patch`, une seule fenêtre en 0
    (la dalle est alors complétée par padding miroir).
    """
    if patch < 1 or pas < 1:
        raise DonneeRefusee(f"patch {patch} ou pas {pas} refusé (règle : entiers >= 1)")
    if longueur <= patch:
        return [0]
    d = list(range(0, longueur - patch + 1, pas))
    if d[-1] != longueur - patch:
        d.append(longueur - patch)
    return d


def pad_miroir(a: np.ndarray, lignes: int, colonnes: int) -> np.ndarray:
    """Complète les deux derniers axes jusqu'à (lignes, colonnes) par symétrie (bas, droite)."""
    dl, dc = max(0, lignes - a.shape[-2]), max(0, colonnes - a.shape[-1])
    if dl == 0 and dc == 0:
        return a
    largeur = [(0, 0)] * (a.ndim - 2) + [(0, dl), (0, dc)]
    return np.pad(a, largeur, mode="symmetric")


def tourner_exposition(nord: np.ndarray, est: np.ndarray, k: int, miroir: bool):
    """Exposition après `miroir` (colonnes inversées : l'est devient l'ouest) puis `k` quarts
    de tour de `np.rot90` (sens trigonométrique à l'affichage, lignes du nord au sud).

    Un quart de tour envoie l'est vers le nord : (est, nord) -> (-nord, est).
    """
    if miroir:
        est = -est
    for _ in range(k % 4):
        est, nord = -nord, est
    return nord, est


def augmenter(x, y, w, k: int, miroir: bool, i_nord: int, i_est: int):
    """Applique la même transformation (miroir puis k quarts de tour) à l'entrée, la cible et
    les poids (tenseurs torch, axes spatiaux en dernier) ; l'exposition est tournée avec."""
    torch = _torch()
    if miroir:
        x, y, w = (torch.flip(t, dims=(-1,)) for t in (x, y, w))
    if k % 4:
        x, y, w = (torch.rot90(t, k % 4, dims=(-2, -1)) for t in (x, y, w))
    nord, est = tourner_exposition(x[..., i_nord, :, :], x[..., i_est, :, :], k, miroir)
    x = x.clone()
    x[..., i_nord, :, :], x[..., i_est, :, :] = nord, est
    return x, y, w


def poids(cible_cm: np.ndarray, valide: np.ndarray, regle: Mapping[str, Any]) -> np.ndarray:
    """Poids par cellule : 0 hors `valide`, `poids` au-dessus de `seuil_cm` (strictement), 1."""
    w = np.where(cible_cm > float(regle["seuil_cm"]), float(regle["poids"]), 1.0)
    return np.where(valide, w, 0.0).astype("float32")


# --- Réseau ---------------------------------------------------------------------------------


def construire(n_entrees: int, archi: Mapping[str, Any], cible: tuple[float, float] = (0.0, 1.0)):
    """U-Net à `niveaux` résolutions (base_canaux x 2^i canaux), sortie : hauteur (m).

    La tête prédit la cible centrée-réduite ; `cible` (moyenne, écart-type en m, des cellules
    d'ajustement) est gardé dans le réseau (tampon `cible`, écrit avec les poids) et la sortie
    est remise en mètres.
    """
    torch = _torch()
    nn = torch.nn
    niveaux, base = int(archi["niveaux"]), int(archi["base_canaux"])
    if niveaux < 2:
        raise DonneeRefusee(f"U-Net à {niveaux} niveau refusé (règle : niveaux >= 2)")

    def bloc(entree: int, sortie: int):
        return nn.Sequential(
            nn.Conv2d(entree, sortie, 3, padding=1, bias=False),
            nn.BatchNorm2d(sortie),
            nn.ReLU(inplace=True),
            nn.Conv2d(sortie, sortie, 3, padding=1, bias=False),
            nn.BatchNorm2d(sortie),
            nn.ReLU(inplace=True),
        )

    canaux = [base * 2**i for i in range(niveaux)]

    class UNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.descente = nn.ModuleList(
                [bloc(n_entrees if i == 0 else canaux[i - 1], c) for i, c in enumerate(canaux)]
            )
            haut = range(niveaux - 1)
            self.montee = nn.ModuleList(
                [nn.ConvTranspose2d(canaux[i + 1], canaux[i], 2, stride=2) for i in haut]
            )
            self.fusion = nn.ModuleList([bloc(2 * canaux[i], canaux[i]) for i in haut])
            self.tete = nn.Conv2d(canaux[0], 1, 1)
            self.pool = nn.MaxPool2d(2)
            self.register_buffer("cible", torch.tensor([float(c) for c in cible]))

        def forward(self, x):
            sauts = []
            for i, b in enumerate(self.descente):
                x = b(x if i == 0 else self.pool(x))
                sauts.append(x)
            x = sauts.pop()
            for i in reversed(range(niveaux - 1)):
                x = self.fusion[i](torch.cat([sauts.pop(), self.montee[i](x)], dim=1))
            return self.tete(x)[:, 0] * self.cible[1] + self.cible[0]

    return UNet()


def multiple(archi: Mapping[str, Any]) -> int:
    """Les côtés d'une entrée doivent être multiples de 2^(niveaux - 1)."""
    return 2 ** (int(archi["niveaux"]) - 1)


def poids_en_octets(reseau) -> tuple[bytes, list[dict[str, Any]]]:
    """Tenseurs du `state_dict` en octets bruts petit-boutistes, et leur description."""
    morceaux, description = [], []
    for nom, t in reseau.state_dict().items():
        a = t.detach().cpu().numpy()
        type_ = "<f4" if a.dtype.kind == "f" else "<i8"
        morceaux.append(np.ascontiguousarray(a, dtype=type_).tobytes())
        description.append({"nom": nom, "forme": list(a.shape), "type": type_})
    return b"".join(morceaux), description


def charger_poids(reseau, octets: bytes, description: Sequence[Mapping[str, Any]]) -> None:
    torch = _torch()
    etat, debut = {}, 0
    for d in description:
        n = int(np.prod(d["forme"], dtype="int64")) * np.dtype(d["type"]).itemsize
        a = np.frombuffer(octets[debut : debut + n], dtype=d["type"]).reshape(d["forme"])
        etat[d["nom"]] = torch.from_numpy(a.copy())
        debut += n
    if debut != len(octets):
        raise DonneeRefusee("poids du U-Net : taille du fichier différente de la description")
    reseau.load_state_dict(etat)


# --- Apprentissage --------------------------------------------------------------------------


def choisir_dalles_validation(
    dalles: Sequence[str], conf: Configuration, taille_bloc_m: int, part: float
) -> list[str]:
    """Dalles des blocs (`taille_bloc_m`) tirés (graine) pour la validation ; jamais tous."""
    from nemeton_canopee.models.gbm import choisir_blocs_validation

    taille_dalle = int(conf.grille["taille_dalle_m"])
    blocs = np.array([grille.bloc(d, taille_dalle, taille_bloc_m) for d in dalles])
    tires = choisir_blocs_validation(blocs, part, conf.graine)
    return sorted(d for d, b in zip(dalles, blocs, strict=True) if (int(b[0]), int(b[1])) in tires)


def _lire(chemin) -> np.ndarray:
    with rasterio.open(chemin) as src:
        return src.read(1)


@dataclass
class Exemple:
    """Une scène d'une dalle prête pour le réseau : entrée normalisée, cible (m), poids."""

    x: np.ndarray  # float32 (canaux, lignes, colonnes)
    y: np.ndarray  # float32, m
    w: np.ndarray  # float32, 0 hors cellules valides


def exemples(conf: Configuration, ch: Chemins, e: EntreesDalle, annee: int, norme) -> list:
    reglage = conf.modele["apprentissage"]
    cible = _lire(exiger_fichier(ch.cible(annee, e.dalle), "targets"))
    foret = _lire(exiger_fichier(ch.foret(e.dalle), "prepare"))
    base = (cible != conf.nodata) & (foret == 1)
    y = np.where(base, cible, 0).astype("float32") / 100.0  # cm -> m
    sortie = []
    for pile, clair in zip(e.scenes, e.clair, strict=True):
        w = poids(cible, base & clair, reglage["poids_grands_arbres"])
        sortie.append(Exemple(normaliser(pile, *norme, _borne(conf)), y, w))
    return sortie


def patchs(ex: Sequence[Exemple], patch: int, pas: int) -> list[tuple[int, int, int]]:
    """(exemple, ligne, colonne) de chaque patch qui contient au moins une cellule valide."""
    liste = []
    for i, e in enumerate(ex):
        lignes, colonnes = e.y.shape
        for r in debuts(lignes, patch, pas):
            for c in debuts(colonnes, patch, pas):
                if e.w[r : r + patch, c : c + patch].any():
                    liste.append((i, r, c))
    return liste


def _lot(ex, indices, patch: int):
    torch = _torch()
    xs, ys, ws = [], [], []
    for i, r, c in indices:
        e = ex[i]
        x = pad_miroir(e.x[:, r : r + patch, c : c + patch], patch, patch)
        y = pad_miroir(e.y[r : r + patch, c : c + patch], patch, patch)
        w = np.zeros((patch, patch), dtype="float32")  # le miroir n'est jamais compté
        sous = e.w[r : r + patch, c : c + patch]
        w[: sous.shape[0], : sous.shape[1]] = sous
        xs.append(x), ys.append(y), ws.append(w)
    return (torch.from_numpy(np.stack(a)) for a in (xs, ys, ws))


def normalisation_cible(ex: Sequence[Exemple]) -> tuple[float, float]:
    """Moyenne et écart-type (m) de la cible sur les cellules valides et claires (ajustement)."""
    valeurs = np.concatenate([e.y[e.w > 0].astype("float64") for e in ex])
    if valeurs.size == 0:
        raise EntreeManquante("aucune cellule valide pour l'apprentissage (relancer targets)")
    ecart = float(valeurs.std())
    return float(valeurs.mean()), ecart if ecart > 0 else 1.0


def predire_pile(reseau, x: np.ndarray, archi: Mapping[str, Any]) -> np.ndarray:
    """Hauteur (m, float64) d'une scène entière : padding miroir au multiple, puis recadrage."""
    torch = _torch()
    m = multiple(archi)
    lignes, colonnes = x.shape[-2:]
    pad = pad_miroir(x, -(-lignes // m) * m, -(-colonnes // m) * m)
    with torch.no_grad():
        sortie = reseau(torch.from_numpy(np.ascontiguousarray(pad[None])))[0].numpy()
    return sortie[:lignes, :colonnes].astype("float64")


def mae_validation(reseau, ex: Sequence[Exemple], archi) -> float:
    """MAE (m) non pondérée sur les cellules valides et claires des scènes de validation."""
    reseau.eval()
    somme, n = 0.0, 0
    for e in ex:
        p = predire_pile(reseau, e.x, archi)
        valide = e.w > 0
        somme += float(np.abs(p[valide] - e.y[valide]).sum())
        n += int(valide.sum())
    if n == 0:
        raise EntreeManquante("aucune cellule valide dans les dalles de validation")
    return somme / n


def une_epoque(reseau, optimiseur, ex, liste, reglage, gen, i_expo) -> float:
    """Une passe sur tous les patchs (ordre tiré par `gen`) ; renvoie la perte moyenne."""
    torch = _torch()
    reseau.train()
    patch, lot = int(reglage["patch"]), int(reglage["taille_lot"])
    ordre = torch.randperm(len(liste), generator=gen).tolist()
    total, n = 0.0, 0
    for debut in range(0, len(ordre), lot):
        choisis = [liste[i] for i in ordre[debut : debut + lot]]
        x, y, w = _lot(ex, choisis, patch)
        if reglage.get("augmentation", True):
            ks = torch.randint(0, 4, (len(choisis),), generator=gen).tolist()
            miroirs = torch.randint(0, 2, (len(choisis),), generator=gen).tolist()
            sorties = [
                augmenter(x[j], y[j], w[j], ks[j], bool(miroirs[j]), *i_expo)
                for j in range(len(choisis))
            ]
            x, y, w = (torch.stack(t) for t in zip(*sorties, strict=True))
        if float(w.sum()) == 0:
            continue
        optimiseur.zero_grad()
        perte = (torch.abs(reseau(x) - y) * w).sum() / w.sum()
        perte.backward()
        optimiseur.step()
        total += perte.item() * len(choisis)
        n += len(choisis)
    return total / max(n, 1)


def entrainer(
    conf: Configuration, ch: Chemins, dalles: Sequence[Dalle], dalles_test: Sequence[str]
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Entraîne le U-Net ; renvoie (métadonnées, {fichier: octets des poids})."""
    interdites = sorted({d.id for d in dalles} & set(dalles_test))
    if interdites:
        raise DonneeRefusee(
            f"découpage enfreint : dalles de test {interdites} parmi l'apprentissage"
        )
    torch = preparer_torch(conf)
    reglage, archi = conf.modele["apprentissage"], conf.modele["architecture"]
    from nemeton_canopee.models.gbm import controler_separation

    taille_bloc = int(reglage["validation"]["taille_bloc_m"])
    ids = sorted(d.id for d in dalles)
    valid_ids = choisir_dalles_validation(
        ids, conf, taille_bloc, float(reglage["validation"]["part_blocs"])
    )
    taille_dalle = int(conf.grille["taille_dalle_m"])
    bloc = {d: grille.bloc(d, taille_dalle, taille_bloc) for d in {*ids, *valid_ids}}
    controler_separation(
        {bloc[d] for d in ids if d not in valid_ids},
        {bloc[d] for d in valid_ids},
        valid_ids,
        dalles_test,
    )
    par_id = {d.id: d for d in dalles}
    entrees = {d: entrees_dalle(conf, ch, d, par_id[d].annee) for d in ids}
    ajust_ids = [d for d in ids if d not in valid_ids]
    norme = normalisation_physique(
        normalisation([entrees[d] for d in ajust_ids]),
        noms_canaux(conf.modele["descripteurs"]),
        conf.modele["descripteurs"].get("normalisation_physique") or {},
    )
    ex_a = [x for d in ajust_ids for x in exemples(conf, ch, entrees[d], par_id[d].annee, norme)]
    ex_v = [x for d in valid_ids for x in exemples(conf, ch, entrees[d], par_id[d].annee, norme)]
    patch, pas = int(reglage["patch"]), int(reglage["pas_patch"])
    liste = patchs(ex_a, patch, pas)
    if not liste:
        raise EntreeManquante("aucun patch avec une cellule valide (relancer targets)")
    canaux = noms_canaux(conf.modele["descripteurs"])
    i_expo = (canaux.index("exposition_nord"), canaux.index("exposition_est"))
    reseau = construire(len(canaux), archi, normalisation_cible(ex_a))
    optimiseur = torch.optim.Adam(
        reseau.parameters(),
        lr=float(reglage["taux_apprentissage"]),
        weight_decay=float(reglage.get("decroissance_poids", 0.0)),
    )
    gen = torch.Generator().manual_seed(conf.graine)
    meilleur, etat, historique, attente = float("inf"), None, [], 0
    for epoque in range(int(reglage["epoques_max"])):
        perte = une_epoque(reseau, optimiseur, ex_a, liste, reglage, gen, i_expo)
        mae = mae_validation(reseau, ex_v, archi)
        historique.append({"epoque": epoque + 1, "perte": round(perte, 6), "mae_m": round(mae, 6)})
        if mae < meilleur:
            meilleur, attente = mae, 0
            etat = {k: v.detach().clone() for k, v in reseau.state_dict().items()}
        else:
            attente += 1
            if attente >= int(reglage["arret_anticipe_epoques"]):
                break
    reseau.load_state_dict(etat)
    octets, description = poids_en_octets(reseau)
    meta = {
        "canaux": canaux,
        "normalisation": {"moyenne": norme[0], "ecart_type": norme[1]},
        "normalisation_cible_m": [float(v) for v in reseau.cible.tolist()],
        "tenseurs": description,
        "n_parametres": int(sum(p.numel() for p in reseau.parameters())),
        "fichiers": {POIDS: hashlib.sha256(octets).hexdigest()},
        "arrondi": conf.modele["arrondi"],
        "quantiles": [float(q) for q in conf.modele["inference"]["percentiles"]],
        "validation": {
            "taille_bloc_m": taille_bloc,
            "dalles": valid_ids,
            "dalles_ajustement": ajust_ids,
            "meilleure_mae_m": round(meilleur, 6),
        },
        "historique": historique,
        "n_patchs": len(liste),
        "parametres": conf.modele,
        "version_torch": torch.__version__,
    }
    return meta, {POIDS: octets}


# --- Inférence ------------------------------------------------------------------------------


def arrondir(valeurs_cm: np.ndarray, arrondi: str, nodata: int) -> np.ndarray:
    """Arrondi à l'entier (cm), borné à [0, nodata - 1]."""
    if arrondi not in ARRONDIS:
        raise DonneeRefusee(f"arrondi inconnu : {arrondi!r} (connus : {sorted(ARRONDIS)})")
    return np.clip(ARRONDIS[arrondi](valeurs_cm), 0, nodata - 1)


def _nom_quantile(q: float) -> str:
    return f"q{round(float(q)):02d}"


def charger(conf: Configuration, ch: Chemins, version: str, modele: Mapping[str, Any]):
    """Réseau du modèle `version`, poids vérifiés par leur sha256."""
    preparer_torch(conf)
    chemin = exiger_fichier(ch.modele(version).parent / POIDS, "train")
    octets = chemin.read_bytes()
    if hashlib.sha256(octets).hexdigest() != modele["fichiers"][POIDS]:
        raise DonneeRefusee(f"modèle {version} : {POIDS} modifié (empreinte différente)")
    reseau = construire(len(modele["canaux"]), modele["parametres"]["architecture"])
    charger_poids(reseau, octets, modele["tenseurs"])
    reseau.eval()
    return reseau


def predire(
    conf: Configuration,
    ch: Chemins,
    version: str,
    modele: Mapping[str, Any],
    dalle: Dalle,
    masque: np.ndarray,
) -> dict[str, np.ndarray]:
    """Hauteur (médiane des scènes claires), p10, p90 et incertitude (p90 - p10), uint16 cm."""
    if noms_canaux(conf.modele["descripteurs"]) != list(modele["canaux"]):
        raise DonneeRefusee("canaux différents de ceux de l'entraînement (relancer train)")
    reseau = charger(conf, ch, version, modele)
    archi = modele["parametres"]["architecture"]
    norme = (modele["normalisation"]["moyenne"], modele["normalisation"]["ecart_type"])
    e = entrees_dalle(conf, ch, dalle.id, dalle.annee)
    par_scene = [
        np.where(
            clair,
            predire_pile(reseau, normaliser(pile, *norme, _borne(conf)), archi) * 100.0,
            np.nan,
        )
        for pile, clair in zip(e.scenes, e.clair, strict=True)
    ]
    pile = np.stack(par_scene)
    bas, haut = sorted(modele["quantiles"])
    arrondi, nodata = modele["arrondi"], conf.nodata
    sortie = {}
    for cle, q in (("hauteur", 50.0), (_nom_quantile(bas), bas), (_nom_quantile(haut), haut)):
        valeurs = descripteurs.percentile_nan(pile, q)[masque]
        couche = np.full(masque.shape, nodata, dtype="uint16")
        couche[masque] = arrondir(valeurs, arrondi, nodata).astype("uint16")
        sortie[cle] = couche
    incertitude = np.full(masque.shape, nodata, dtype="uint16")
    hb, hh = sortie[_nom_quantile(bas)], sortie[_nom_quantile(haut)]
    incertitude[masque] = hh[masque] - hb[masque]
    sortie["incertitude"] = incertitude
    return sortie
