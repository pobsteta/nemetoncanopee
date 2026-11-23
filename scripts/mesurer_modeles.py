"""Mesure côte à côte des modèles de hauteur contre FORMS-T v1 (mission 011, ADR 0004).

    python scripts/mesurer_modeles.py \
        --modele trivial=/data/mesure_011/conf/chaine_trivial.yaml \
        --modele gbm=/data/mesure_011/conf/chaine_gbm.yaml \
        --modele unet=/data/mesure_011/conf/chaine_unet.yaml \
        --sortie /data/mesure_011/mesure.json

Chaque `--modele` nomme une configuration de chaîne dont le dossier de travail a déjà passé
`targets` et `infer`. Le script ne règle rien et n'écrit rien dans ces dossiers : il lit les
cibles, les couches brutes et FORMS-T v1 des dalles de test du découpage figé, et compare
tous les produits sur les MÊMES cellules : cible valide (donc forêt, la cible est masquée
par la BD Forêt) et toutes les prédictions valides, FORMS-T compris.

Critère principal (spec, « Critères du modèle de hauteur ») : MAE au peuplement, c'est-à-dire
MAE des moyennes par polygone BD Forêt (polygones fusionnés par identifiant dans la dalle, de
surface >= `--surface-min-ha`) et MAE des moyennes par cellule de 1 ha (10 x 10 cellules de
10 m). Une unité n'est gardée que si au moins `--part-min` de ses cellules sont communes.
Intervalle à 95 % par bootstrap sur les dalles (tirage avec remise des dalles de test, mêmes
tirages pour tous les produits, graine fixe) ; on donne aussi l'intervalle de l'écart apparié
modèle − FORMS-T, plus puissant que la comparaison de deux intervalles.

Critères secondaires : MAE et biais au pixel ; par classe de hauteur cible ; couverture de
l'intervalle p10-p90 et part des cellules à incertitude nulle (modèles qui en donnent) ;
ventilations par bloc, essence BD Forêt et tranche d'altitude pour chercher les causes.
Biais = produit − cible, en m.

Mission 014 (ajouts compatibles) : `--paire A-B` donne l'intervalle de l'écart apparié entre
deux produits quelconques (mêmes tirages), par exemple gbm_ortho − gbm pour séparer les effets ;
`--exces` ajoute la section « Excès sur FORMS-T », qui chiffre, par bloc x classe,
n x (MAE produit − MAE FORMS-T) en milliers de m·cellule (Pareto de la cause n° 1 de la mesure 011).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

CM_PAR_M = 100.0
REFERENCE = "forms_t_v1"


# --- Calculs purs (testés sur des données synthétiques) -------------------------------------


def masque_commun(cible: np.ndarray, produits: Mapping[str, np.ndarray], nodata: int) -> np.ndarray:
    """Cellules où la cible et tous les produits existent."""
    ok = cible != nodata
    for p in produits.values():
        ok &= p != nodata
    return ok


def etiquettes_hectare(forme: tuple[int, int], cote: int) -> np.ndarray:
    """Numéro (à partir de 1) de la cellule de `cote` x `cote` pixels contenant chaque pixel."""
    lignes, colonnes = np.indices(forme)
    par_ligne = -(-forme[1] // cote)
    return (lignes // cote) * par_ligne + (colonnes // cote) + 1


def moyennes_par_unite(
    etiquettes: np.ndarray,
    masque: np.ndarray,
    couches: Mapping[str, np.ndarray],
    part_min: float,
) -> dict[str, np.ndarray]:
    """Moyenne de chaque couche par unité (étiquette > 0) sur les cellules du masque.

    Une unité est gardée si la part de ses cellules dans le masque atteint `part_min`.
    Renvoie {couche: moyennes des unités gardées}, plus `n` (cellules par unité).
    """
    lab = etiquettes.ravel()
    m = masque.ravel() & (lab > 0)
    taille = np.bincount(lab[lab > 0], minlength=lab.max() + 1)
    n = np.bincount(lab[m], minlength=taille.size)
    garde = (taille > 0) & (n > 0) & (n >= part_min * np.maximum(taille, 1))
    sortie = {"n": n[garde]}
    for nom, c in couches.items():
        s = np.bincount(lab[m], weights=c.ravel()[m].astype("float64"), minlength=taille.size)
        sortie[nom] = s[garde] / n[garde]
    return sortie


def mae_biais(e: np.ndarray) -> dict[str, Any]:
    """n, MAE et biais d'un vecteur d'écarts (m)."""
    if e.size == 0:
        return {"n": 0, "mae_m": None, "biais_m": None}
    return {"n": int(e.size), "mae_m": float(np.abs(e).mean()), "biais_m": float(e.mean())}


def classes_hauteur(cible_m: np.ndarray, bornes: Sequence[float]) -> np.ndarray:
    """Indice de classe de hauteur (0 : < bornes[0], ..., len(bornes) : >= dernière borne)."""
    return np.digitize(cible_m, bornes, right=False)


def noms_classes(bornes: Sequence[float]) -> list[str]:
    b = [f"{x:g}" for x in bornes]
    return [f"< {b[0]} m", *[f"{a}-{c} m" for a, c in zip(b, b[1:], strict=False)], f"> {b[-1]} m"]


def bootstrap_dalles(
    sommes: np.ndarray, comptes: np.ndarray, tirages: int, graine: int, niveau: float = 0.95
) -> dict[str, Any]:
    """Intervalle par bootstrap sur les dalles d'une MAE poolée.

    `sommes` : (produits, dalles) sommes des écarts absolus des unités de chaque dalle ;
    `comptes` : (dalles,) nombre d'unités par dalle. Mêmes tirages pour tous les produits.
    Renvoie les MAE tirées (produits, tirages) et les bornes (produits, 2).
    """
    rng = np.random.default_rng(graine)
    k = comptes.size
    idx = rng.integers(0, k, size=(tirages, k))
    tot = comptes[idx].sum(axis=1)
    tot = np.where(tot == 0, np.nan, tot)
    maes = np.stack([s[idx].sum(axis=1) / tot for s in sommes])
    a = (1 - niveau) / 2 * 100
    bornes = np.nanpercentile(maes, [a, 100 - a], axis=1).T
    return {"tirages": maes, "ic": bornes}


def couverture(cible: np.ndarray, bas: np.ndarray, haut: np.ndarray) -> float:
    """Part des cibles comprises dans [bas, haut] (bornes incluses)."""
    if cible.size == 0:
        return float("nan")
    return float(((cible >= bas) & (cible <= haut)).mean())


def exces_sur_reference(
    bloc_classe: Mapping[str, Mapping[str, Any]], produit: str, reference: str = REFERENCE
) -> dict[str, float]:
    """Excès d'erreur du produit sur la référence par groupe : n x (MAE produit − MAE
    référence), en m·cellule (positif : le produit fait pire). Groupes vides ignorés."""
    sortie = {}
    for g, v in bloc_classe.items():
        a, r = v[produit], v[reference]
        if a["n"]:
            sortie[g] = a["n"] * (a["mae_m"] - r["mae_m"])
    return sortie


def exces_sous(exces: Mapping[str, float], classes: Sequence[str]) -> float:
    """Somme des excès des groupes « bloc · classe » dont la classe est dans `classes`."""
    return float(sum(v for g, v in exces.items() if g.split(" · ", 1)[1] in classes))


# --- Lecture des données -------------------------------------------------------------------


def _lire(chemin: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(chemin) as src:
        return src.read(1)


def polygones_dalle(conf, dalle: str, forme, surface_min_m2: float) -> tuple[np.ndarray, list]:
    """Étiquettes (1..k) des polygones BD Forêt de la dalle, fusionnés par identifiant, et leur
    essence ; seuls les polygones d'au moins `surface_min_m2` dans la dalle sont gardés."""
    import geopandas as gpd
    from rasterio.features import rasterize

    from nemeton_canopee import grille

    g = gpd.read_file(conf.zone.chemin("foret", dalle=dalle))
    g = g.dissolve(by="id", aggfunc="first").reset_index()
    g = g[g.geometry.area >= surface_min_m2].reset_index(drop=True)
    transform = grille.transformation(
        dalle, int(conf.grille["taille_dalle_m"]), float(conf.grille["pas_m"])
    )
    if g.empty:
        return np.zeros(forme, dtype="int32"), []
    formes = ((geom, i + 1) for i, geom in enumerate(g.geometry))
    lab = rasterize(formes, out_shape=forme, transform=transform, fill=0, dtype="int32")
    return lab, list(g["essence"].fillna("NC"))


def lire_test(confs: Mapping[str, Any], quantiles: Sequence[str]) -> list[dict[str, Any]]:
    """Par dalle de test : cible, produits, quantiles (p10, p90), scènes claires, MNT, forêt."""
    from nemeton_canopee import decoupage
    from nemeton_canopee.chemins import Chemins
    from nemeton_canopee.infer import masque_clair
    from nemeton_canopee.ingest import lire_manifeste
    from nemeton_canopee.models import modele_actif, predire

    conf0 = next(iter(confs.values()))
    dec = decoupage.lire(conf0)
    import yaml

    brut = yaml.safe_load(conf0.zone.chemin("decoupage").read_text(encoding="utf-8"))
    bloc_de = {e["dalle"]: e.get("bloc_echantillon", "?") for e in brut["test"]}
    dalles = lire_manifeste(Chemins(conf0.travail), dec.test)
    actifs = {nom: modele_actif(Chemins(c.travail)) for nom, c in confs.items()}
    sortie = []
    for d in dalles:
        ch0 = Chemins(conf0.travail)
        cible = _lire(ch0.cible(d.annee, d.id))
        produits, bornes = {}, {}
        for nom, c in confs.items():
            ch = Chemins(c.travail)
            if not np.array_equal(_lire(ch.cible(d.annee, d.id)), cible):
                raise SystemExit(f"cibles différentes entre modèles pour {d.id}")
            produits[nom] = _lire(ch.brute(d.annee, d.id))
            if nom in quantiles:
                foret = _lire(ch.foret(d.id))
                masque = (foret == 1) & masque_clair(ch.scenes_preparees(d.annee, d.id))
                version, modele = actifs[nom]
                couches = predire(c, ch, version, modele, d, masque)
                if not np.array_equal(couches["hauteur"], produits[nom]):
                    raise SystemExit(f"{nom} {d.id} : prédiction rejouée différente de infer")
                bas, haut = sorted(k for k in couches if k.startswith("q"))
                bornes[nom] = (couches[bas], couches[haut])
        ref = conf0.zone.references[0] if conf0.zone.references else None
        chemin_ref = conf0.zone.racine / ref["chemin"].format(dalle=d.id, annee=d.annee)
        produits[REFERENCE] = _lire(chemin_ref)
        scenes = ch0.scenes_preparees(d.annee, d.id)
        n_claires = sum((_lire_bande_claire(s) == 1).astype("int16") for s in scenes)
        sortie.append(
            {
                "dalle": d.id,
                "bloc": bloc_de.get(d.id, "?"),
                "cible": cible,
                "produits": produits,
                "bornes": bornes,
                "n_claires": n_claires,
                "mnt": _lire(conf0.zone.chemin("mnt", dalle=d.id)).astype("float64"),
            }
        )
    return sortie


def _lire_bande_claire(chemin: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(chemin) as src:
        return src.read(src.count)


# --- Mesure --------------------------------------------------------------------------------


def mesurer(
    dalles: Sequence[dict[str, Any]],
    polygones: Mapping[str, tuple[np.ndarray, list]],
    reglages: Mapping[str, Any],
    nodata: int,
) -> dict[str, Any]:
    """Toutes les mesures, par bloc de test et au total. `polygones` : {dalle: (étiquettes,
    essences)}. Les dalles portent cible, produits, bornes, n_claires, mnt (voir lire_test)."""
    noms = list(dalles[0]["produits"])
    blocs = sorted({d["bloc"] for d in dalles})
    bornes_h = reglages["classes_m"]
    unites = {"polygone": [], "hectare": []}
    pixels = []
    for d in dalles:
        ok = masque_commun(d["cible"], d["produits"], nodata)
        couches = {"cible": d["cible"] / CM_PAR_M}
        couches |= {n: p / CM_PAR_M for n, p in d["produits"].items()}
        lab_poly, essences = polygones[d["dalle"]]
        for unite, lab in (
            ("polygone", lab_poly),
            ("hectare", etiquettes_hectare(d["cible"].shape, reglages["cote_hectare"])),
        ):
            moy = moyennes_par_unite(lab, ok, couches, reglages["part_min"])
            unites[unite].append((d["dalle"], d["bloc"], moy))
        ess = np.array(["hors polygone", *essences], dtype=object)[lab_poly]
        pix = {
            "dalle": d["dalle"],
            "bloc": d["bloc"],
            "cible": couches["cible"][ok],
            "ecarts": {n: couches[n][ok] - couches["cible"][ok] for n in noms},
            "essence": ess[ok],
            "altitude": d["mnt"][ok],
            "n_claires": d["n_claires"][ok],
            "bornes": {
                n: (b[0][ok] / CM_PAR_M, b[1][ok] / CM_PAR_M) for n, b in d["bornes"].items()
            },
        }
        pixels.append(pix)

    resultat: dict[str, Any] = {"produits": noms, "blocs": blocs, "reglages": dict(reglages)}
    portees = {"total": None, **{b: b for b in blocs}}
    resultat["principal"] = {}
    for unite, liste in unites.items():
        resultat["principal"][unite] = {}
        for portee, b in portees.items():
            sel = [(dl, moy) for dl, bl, moy in liste if b is None or bl == b]
            sommes = np.array(
                [[np.abs(m[n] - m["cible"]).sum() for _, m in sel] for n in noms], dtype="float64"
            )
            comptes = np.array([m["cible"].size for _, m in sel], dtype="float64")
            boot = bootstrap_dalles(sommes, comptes, reglages["tirages"], reglages["graine"])
            i_ref = noms.index(REFERENCE)
            diff = boot["tirages"] - boot["tirages"][i_ref]
            ic_diff = np.nanpercentile(diff, [2.5, 97.5], axis=1).T
            ligne = {"n_unites": int(comptes.sum()), "n_dalles": len(sel)}
            for i, n in enumerate(noms):
                e = np.concatenate([m[n] - m["cible"] for _, m in sel])
                ligne[n] = {
                    **mae_biais(e),
                    "ic95": [float(x) for x in boot["ic"][i]],
                    "ecart_forms_t_ic95": [float(x) for x in ic_diff[i]],
                }
            for a, b in reglages.get("paires", []):
                d_ab = boot["tirages"][noms.index(a)] - boot["tirages"][noms.index(b)]
                ligne.setdefault("paires", {})[f"{a} − {b}"] = {
                    "ecart_m": ligne[a]["mae_m"] - ligne[b]["mae_m"],
                    "ic95": [float(x) for x in np.nanpercentile(d_ab, [2.5, 97.5])],
                }
            resultat["principal"][unite][portee] = ligne

    noms_c = noms_classes(bornes_h)
    resultat["secondaire"] = {}
    for portee, b in portees.items():
        sel = [p for p in pixels if b is None or p["bloc"] == b]
        cible = np.concatenate([p["cible"] for p in sel])
        cls = classes_hauteur(cible, bornes_h)
        r: dict[str, Any] = {"n_pixels": int(cible.size), "pixel": {}, "classes": {}}
        for n in noms:
            e = np.concatenate([p["ecarts"][n] for p in sel])
            r["pixel"][n] = mae_biais(e)
            r["classes"][n] = {noms_c[k]: mae_biais(e[cls == k]) for k in range(len(noms_c))}
        r["part_classes"] = {noms_c[k]: float((cls == k).mean()) for k in range(len(noms_c))}
        r["incertitude"] = {}
        for n in sel[0]["bornes"]:
            bas = np.concatenate([p["bornes"][n][0] for p in sel])
            haut = np.concatenate([p["bornes"][n][1] for p in sel])
            claires = np.concatenate([p["n_claires"] for p in sel])
            nulle = haut == bas
            r["incertitude"][n] = {
                "couverture_p10_p90": couverture(cible, bas, haut),
                "part_incertitude_nulle": float(nulle.mean()),
                "largeur_moyenne_m": float((haut - bas).mean()),
                "part_une_scene_claire": float((claires == 1).mean()),
                "part_nulle_si_plusieurs_scenes": float(nulle[claires > 1].mean())
                if (claires > 1).any()
                else None,
            }
        resultat["secondaire"][portee] = r

    resultat["causes"] = ventilations(pixels, noms, reglages)
    return resultat


def ventilations(pixels, noms, reglages) -> dict[str, Any]:
    """MAE et biais au pixel par bloc x classe, par essence, par tranche d'altitude."""
    cible = np.concatenate([p["cible"] for p in pixels])
    bloc = np.concatenate([np.full(p["cible"].size, p["bloc"], dtype=object) for p in pixels])
    ess = np.concatenate([p["essence"] for p in pixels])
    alt = np.concatenate([p["altitude"] for p in pixels])
    ecarts = {n: np.concatenate([p["ecarts"][n] for p in pixels]) for n in noms}
    pas = reglages["tranche_altitude_m"]
    tranche = (np.floor(alt / pas) * pas).astype(int)
    cls = classes_hauteur(cible, reglages["classes_m"])
    noms_c = noms_classes(reglages["classes_m"])
    sortie: dict[str, Any] = {"bloc_classe": {}, "essence": {}, "altitude": {}}
    for b in sorted(set(bloc)):
        for k, nc in enumerate(noms_c):
            m = (bloc == b) & (cls == k)
            sortie["bloc_classe"][f"{b} · {nc}"] = {
                "hauteur_moyenne_m": float(cible[m].mean()) if m.any() else None,
                **{n: mae_biais(ecarts[n][m]) for n in noms},
            }
    for e in sorted(set(ess)):
        m = ess == e
        if m.sum() >= reglages["n_min_ventilation"]:
            sortie["essence"][e] = {
                "hauteur_moyenne_m": float(cible[m].mean()),
                **{n: mae_biais(ecarts[n][m]) for n in noms},
            }
    for t in sorted(set(tranche)):
        m = tranche == t
        if m.sum() >= reglages["n_min_ventilation"]:
            sortie["altitude"][f"{t}-{t + pas} m"] = {
                "hauteur_moyenne_m": float(cible[m].mean()),
                **{n: mae_biais(ecarts[n][m]) for n in noms},
            }
    return sortie


# --- Rendu ---------------------------------------------------------------------------------


def _f(x, d=2) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def markdown(res: Mapping[str, Any], exces: bool = False) -> str:
    """Tableaux du rapport (principal, secondaires, causes ; excès sur FORMS-T si `exces`)."""
    noms = res["produits"]
    out = ["## Critère principal : MAE au peuplement (m), IC 95 % bootstrap sur les dalles", ""]
    for unite, lib in (("polygone", "polygone BD Forêt"), ("hectare", "cellule de 1 ha")):
        out += [
            f"### Par {lib}",
            "",
            "| Portée | unités | dalles | "
            + " | ".join(f"{n} MAE [IC]" for n in noms)
            + " | "
            + " | ".join(f"{n} − FORMS-T [IC]" for n in noms if n != REFERENCE)
            + " |",
            "|---|---:|---:|" + "---:|" * (2 * len(noms) - 1),
        ]
        for portee, li in res["principal"][unite].items():
            cel = [
                f"{_f(li[n]['mae_m'])} [{_f(li[n]['ic95'][0])}–{_f(li[n]['ic95'][1])}]"
                for n in noms
            ]
            dif = [
                f"{_f(li[n]['mae_m'] - li[REFERENCE]['mae_m'])} "
                f"[{_f(li[n]['ecart_forms_t_ic95'][0])}–{_f(li[n]['ecart_forms_t_ic95'][1])}]"
                for n in noms
                if n != REFERENCE
            ]
            out.append(
                f"| {portee} | {li['n_unites']} | {li['n_dalles']} | "
                + " | ".join(cel + dif)
                + " |"
            )
        out.append("")
        paires = [k for k in next(iter(res["principal"][unite].values())).get("paires", {})]
        if paires:
            out += [
                f"Écarts appariés entre produits, par {lib} (m) [IC 95 %] :",
                "",
                "| Portée | " + " | ".join(paires) + " |",
                "|---|" + "---:|" * len(paires),
            ]
            for portee, li in res["principal"][unite].items():
                cel = [
                    f"{_f(li['paires'][k]['ecart_m'])} [{_f(li['paires'][k]['ic95'][0])}–"
                    f"{_f(li['paires'][k]['ic95'][1])}]"
                    for k in paires
                ]
                out.append(f"| {portee} | " + " | ".join(cel) + " |")
            out.append("")
    out += ["## Au pixel : MAE / biais (m)", "", "| Portée | n | " + " | ".join(noms) + " |"]
    out.append("|---|---:|" + "---|" * len(noms))
    for portee, r in res["secondaire"].items():
        cel = [f"{_f(r['pixel'][n]['mae_m'])} / {_f(r['pixel'][n]['biais_m'])}" for n in noms]
        out.append(f"| {portee} | {r['n_pixels']} | " + " | ".join(cel) + " |")
    out += ["", "## Par classe de hauteur cible : MAE / biais (m), total", ""]
    tot = res["secondaire"]["total"]
    out.append("| Classe | part | " + " | ".join(noms) + " |")
    out.append("|---|---:|" + "---|" * len(noms))
    for c, part in tot["part_classes"].items():
        cel = [
            f"{_f(tot['classes'][n][c]['mae_m'])} / {_f(tot['classes'][n][c]['biais_m'])}"
            for n in noms
        ]
        out.append(f"| {c} | {part:.1%} | " + " | ".join(cel) + " |")
    out += ["", "## Incertitude p10-p90", ""]
    out.append(
        "| Modèle | Portée | couverture | part nulle | largeur moy. (m) | part 1 scène claire "
        "| part nulle si ≥ 2 scènes |"
    )
    out.append("|---|---|---:|---:|---:|---:|---:|")
    for portee, r in res["secondaire"].items():
        for n, u in r["incertitude"].items():
            sup = u["part_nulle_si_plusieurs_scenes"]
            out.append(
                f"| {n} | {portee} | {u['couverture_p10_p90']:.1%} | "
                f"{u['part_incertitude_nulle']:.1%} | {_f(u['largeur_moyenne_m'])} | "
                f"{u['part_une_scene_claire']:.1%} | "
                f"{'—' if sup is None else format(sup, '.1%')} |"
            )
    for cle, titre in (
        ("bloc_classe", "Bloc × classe"),
        ("essence", "Essence BD Forêt"),
        ("altitude", "Tranche d'altitude (MNT)"),
    ):
        out += ["", f"## Causes : {titre}, MAE / biais au pixel (m)", ""]
        out.append("| Groupe | n | h moy. (m) | " + " | ".join(noms) + " |")
        out.append("|---|---:|---:|" + "---|" * len(noms))
        for g, v in res["causes"][cle].items():
            n0 = v[noms[0]]["n"]
            if n0 == 0:
                continue
            cel = [f"{_f(v[n]['mae_m'])} / {_f(v[n]['biais_m'])}" for n in noms]
            out.append(
                f"| {g} | {n0} | {_f(v.get('hauteur_moyenne_m'))} | " + " | ".join(cel) + " |"
            )
    autres = [n for n in noms if n != REFERENCE]
    if exces and REFERENCE in noms and autres:
        bc = res["causes"]["bloc_classe"]
        ex = {n: exces_sur_reference(bc, n) for n in autres}
        out += [
            "",
            "## Excès sur FORMS-T : n × (MAE produit − MAE FORMS-T), k m·cellule",
            "",
            "| Groupe | " + " | ".join(autres) + " |",
            "|---|" + "---:|" * len(autres),
        ]
        for g in ex[autres[0]]:
            out.append(f"| {g} | " + " | ".join(_f(ex[n][g] / 1e3, 1) for n in autres) + " |")
        noms_c = noms_classes(res["reglages"]["classes_m"])
        for lib, cl in (("sous 20 m", noms_c[:2]), ("total net", noms_c)):
            out.append(
                f"| **{lib}** | "
                + " | ".join(_f(exces_sous(ex[n], cl) / 1e3, 1) for n in autres)
                + " |"
            )
        out.append(
            "| **brut (positifs)** | "
            + " | ".join(_f(sum(v for v in ex[n].values() if v > 0) / 1e3, 1) for n in autres)
            + " |"
        )
    return "\n".join(out) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--modele", action="append", required=True, metavar="NOM=CONF")
    p.add_argument("--quantiles", nargs="*", default=["gbm", "unet"], help="modèles à p10-p90")
    p.add_argument("--sortie", required=True, help="JSON ; le Markdown est écrit à côté")
    p.add_argument("--surface-min-ha", type=float, default=0.5)
    p.add_argument("--part-min", type=float, default=0.5, help="part min. de cellules communes")
    p.add_argument("--cote-hectare", type=int, default=10, help="pixels de 10 m par côté")
    p.add_argument("--classes-m", type=float, nargs="+", default=[10, 20, 30])
    p.add_argument("--tirages", type=int, default=1000)
    p.add_argument("--graine", type=int, default=42)
    p.add_argument("--tranche-altitude-m", type=int, default=200)
    p.add_argument("--n-min-ventilation", type=int, default=500)
    p.add_argument("--exces", action="store_true", help="section Excès sur FORMS-T (014)")
    p.add_argument(
        "--paire", action="append", default=[], metavar="A-B", help="écart apparié A − B"
    )
    a = p.parse_args(argv)
    from nemeton_canopee.conf import charger

    confs = {n: charger(c) for n, c in (m.split("=", 1) for m in a.modele)}
    reglages = {
        "surface_min_ha": a.surface_min_ha,
        "part_min": a.part_min,
        "cote_hectare": a.cote_hectare,
        "classes_m": a.classes_m,
        "tirages": a.tirages,
        "graine": a.graine,
        "tranche_altitude_m": a.tranche_altitude_m,
        "n_min_ventilation": a.n_min_ventilation,
    }
    if a.paire:
        reglages["paires"] = [tuple(x.split("-", 1)) for x in a.paire]
    conf0 = next(iter(confs.values()))
    dalles = lire_test(confs, [q for q in a.quantiles if q in confs])
    polys = {
        d["dalle"]: polygones_dalle(conf0, d["dalle"], d["cible"].shape, a.surface_min_ha * 1e4)
        for d in dalles
    }
    res = mesurer(dalles, polys, reglages, conf0.nodata)
    res["confs"] = dict(m.split("=", 1) for m in a.modele)
    sortie = Path(a.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    sortie.with_suffix(".md").write_text(markdown(res, a.exces), encoding="utf-8")
    print(sortie.with_suffix(".md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
