#!/usr/bin/env python
"""Fabrique l'échantillon du Jura (mission 008) : blocs de 4 x 4 dalles de 1 km, hors dépôt.

Réutilise `scripts/fabriquer_jeu_essai.py` (mêmes sources, mêmes conventions, même arborescence
que `tests/data/`) : MNH réduit à la volée (maximum à 2 m, le brut de 0,5 m n'est jamais écrit),
MNT 10 m, scènes Sentinel-2 de l'année de vol, polygones BD Forêt, FORMS-T v1 de l'année de vol,
descripteurs de la BD ORTHO 20 cm à 10 m (mission 012, calculés à la volée, ortho non conservée).
Ajoute : blocs et rôles lus dans `conf/echantillon_jura.yaml`, fabrication en parallèle et
reprenable (un fragment par dalle dans `.etat/`), journal `fabrication.log`, `decoupage.yaml`
par blocs, manifeste lisible `MANIFESTE.md` et contrôle intégré du résultat.

Usage :
    python scripts/fabriquer_echantillon.py                  # tout (reprend où il s'est arrêté)
    python scripts/fabriquer_echantillon.py --controler      # contrôle seul, sans réseau
    python scripts/fabriquer_echantillon.py --dalles 0926-6646 --sortie /tmp/essai
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import rasterio
import yaml

CONF_DEFAUT = Path(__file__).resolve().parent.parent / "conf" / "echantillon_jura.yaml"


def _charger_base():
    """Module `fabriquer_jeu_essai` (même dossier), chargé par son chemin."""
    chemin = Path(__file__).resolve().with_name("fabriquer_jeu_essai.py")
    spec = importlib.util.spec_from_file_location("fabriquer_jeu_essai", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fabriquer_jeu_essai"] = module
    spec.loader.exec_module(module)
    return module


base = _charger_base()

# --------------------------------------------------------------------------- configuration


def charger_conf(chemin: Path) -> SimpleNamespace:
    """Conf de l'échantillon : `heritage` (conf du jeu d'essai) complété par les clés du fichier."""
    propre = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    herite = yaml.safe_load((chemin.parent / propre["heritage"]).read_text(encoding="utf-8"))
    conf = SimpleNamespace(**{**herite, **propre})
    conf.dalles = dalles_de_la_conf(conf)
    return conf


def dalles_du_bloc(nw_km: list[int], n: int = 4) -> list[str]:
    """Identifiants des n x n dalles d'un bloc dont le coin nord-ouest est `nw_km` (km)."""
    x0, y0 = nw_km
    return [f"{x:04d}-{y:04d}" for x in range(x0, x0 + n) for y in range(y0 - n + 1, y0 + 1)]


def dalles_de_la_conf(conf: SimpleNamespace) -> list[str]:
    n = conf.taille_bloc_dalles
    return sorted(d for b in conf.blocs for d in dalles_du_bloc(b["nw_km"], n))


def bloc_de(conf: SimpleNamespace, dalle: str) -> dict:
    n = conf.taille_bloc_dalles
    for b in conf.blocs:
        if dalle in dalles_du_bloc(b["nw_km"], n):
            return b
    raise KeyError(dalle)


def distance_blocs_m(conf: SimpleNamespace, a: dict, b: dict) -> float:
    """Plus courte distance (m) entre deux blocs de la conf."""
    n = conf.taille_bloc_dalles * 1000
    ax, ay = a["nw_km"][0] * 1000, a["nw_km"][1] * 1000
    bx, by = b["nw_km"][0] * 1000, b["nw_km"][1] * 1000
    dx = max(ax - (bx + n), bx - (ax + n), 0)
    dy = max((ay - n) - by, (by - n) - ay, 0)
    return float((dx**2 + dy**2) ** 0.5)


def controler_blocs(conf: SimpleNamespace) -> list[str]:
    """Erreurs de la définition des blocs : doublons, distance, rôles (vide si tout va bien)."""
    erreurs = []
    noms = [b["nom"] for b in conf.blocs]
    if len(set(noms)) != len(noms):
        erreurs.append(f"noms de blocs en double : {noms}")
    for b in conf.blocs:
        if b["role"] not in ("apprentissage", "test"):
            erreurs.append(f"bloc {b['nom']} : rôle {b['role']!r} inconnu")
    roles = {b["role"] for b in conf.blocs}
    if roles != {"apprentissage", "test"}:
        erreurs.append("il faut au moins un bloc d'apprentissage et un bloc de test")
    for i, a in enumerate(conf.blocs):
        for b in conf.blocs[i + 1 :]:
            d = distance_blocs_m(conf, a, b)
            if d < conf.distance_min_blocs_m:
                erreurs.append(f"blocs {a['nom']} et {b['nom']} à {d / 1000:.1f} km (< minimum)")
    return erreurs


# --------------------------------------------------------------------------- journal, reprises


class Journal:
    """Journal horodaté (`fabrication.log`), sûr entre fils d'exécution."""

    def __init__(self, chemin: Path, echo: bool = True):
        self.chemin, self.echo, self.verrou = chemin, echo, threading.Lock()
        chemin.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, message: str) -> None:
        ligne = f"{datetime.now().isoformat(timespec='seconds')} {message}"
        with self.verrou:
            with self.chemin.open("a", encoding="utf-8") as fh:
                fh.write(ligne + "\n")
            if self.echo:
                print(ligne, flush=True)


def avec_reprises(f: Callable, tentatives: int, journal: Callable, nom: str, pause: float = 5.0):
    """Appelle `f()` jusqu'à `tentatives` fois ; la dernière erreur est relevée."""
    for essai in range(1, tentatives + 1):
        try:
            return f()
        except Exception as e:  # réseau, service IGN ou AWS indisponible, fichier tronqué
            journal(f"ECHEC {nom} (essai {essai}/{tentatives}) : {type(e).__name__} : {e}"[:400])
            if essai == tentatives:
                raise
            time.sleep(pause * essai)


def chemin_fragment(sortie: Path, dalle: str) -> Path:
    return sortie / ".etat" / f"{dalle}.json"


# --------------------------------------------------------------------------- contrôles unitaires


def controler_mnh_publie(part_valide: float, valide_min: float) -> float:
    """Lève si le MNH n'est pas (assez) publié sur la dalle (part de cellules valides)."""
    if part_valide < valide_min:
        raise RuntimeError(
            f"MNH publié sur {part_valide:.0%} de la dalle seulement (minimum {valide_min:.0%})"
        )
    return part_valide


def statistiques_mnh(chemin: Path, seuil_m: float = 30.0) -> dict:
    """Hauteurs du MNH 2 m (uint16 en cm) : max, 99e centile, moyenne, part > seuil, part valide."""
    with rasterio.open(chemin) as src:
        cm, nodata = src.read(1), src.nodata
    valide = cm != nodata
    v = cm[valide].astype("float64") / 100.0
    if v.size == 0:
        return {
            "max_m": None,
            "p99_m": None,
            "moyenne_m": None,
            "part_sup_seuil": 0.0,
            "valide": 0.0,
        }
    return {
        "max_m": round(float(v.max()), 1),
        "p99_m": round(float(np.percentile(v, 99)), 1),
        "moyenne_m": round(float(v.mean()), 1),
        "part_sup_seuil": round(float((v > seuil_m).mean()), 4),
        "valide": round(float(valide.mean()), 4),
    }


def meme_annee(meta: dict[str, dict]) -> str:
    """Année de vol commune à toutes les dalles d'un bloc ; lève sinon."""
    annees = {base.annee_vol(m) for m in meta.values()}
    if len(annees) != 1:
        raise RuntimeError(f"plusieurs années de vol dans un bloc : {sorted(annees)}")
    return annees.pop()


# --------------------------------------------------------------------------- une dalle


def fabriquer_dalle(conf: SimpleNamespace, dalle: str, sortie: Path, journal: Callable) -> dict:
    """Fabrique MNH, MNT, BD Forêt et scènes S2 d'une dalle ; écrit et renvoie son fragment."""
    frag = chemin_fragment(sortie, dalle)
    if frag.is_file():
        etat = json.loads(frag.read_text(encoding="utf-8"))
        if all((sortie / f).is_file() for f in etat["prov"]):
            journal(f"{dalle} déjà fabriquée (reprise)")
            return etat
    t0 = time.time()
    prov: dict = {}
    scenes: list[dict] = []
    meta = base.metadonnees_vol(conf, dalle)
    annee = base.annee_vol(meta)
    base.fabriquer_lidar(conf, dalle, sortie, prov)
    stats = statistiques_mnh(sortie / f"lidar/{dalle}_MNH_2m.tif", conf.seuil_grands_arbres_m)
    controler_mnh_publie(stats["valide"], conf.mnh_min_valide)
    essences = base.fabriquer_foret(conf, dalle, sortie, prov)
    base.fabriquer_sentinel2(conf, dalle, annee, sortie, prov, scenes)
    etat = {
        "dalle": dalle,
        "meta": meta,
        "annee": annee,
        "prov": prov,
        "scenes": scenes,
        "essences": essences,
        "stats": stats,
        "duree_s": round(time.time() - t0, 1),
    }
    frag.parent.mkdir(parents=True, exist_ok=True)
    frag.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    journal(
        f"{dalle} faite en {etat['duree_s']:.0f} s : vol {meta['date_vol_debut']}, "
        f"{len(scenes) // 2} scènes S2, MNH max {stats['max_m']} m"
    )
    return etat


def fabriquer_reference_dalle(
    conf: SimpleNamespace, dalle: str, etat: dict, sortie: Path, journal: Callable
) -> dict:
    """FORMS-T v1 de l'année de vol (2018-2024) ; renvoie les entrées de PROVENANCE ajoutées."""
    annee = int(etat["annee"])
    if not conf.forms_t_annees[0] <= annee <= conf.forms_t_annees[1]:
        journal(f"{dalle} : pas de FORMS-T v1 pour {annee}")
        return {}
    f = conf.references["forms_t_v1"]["fichier"].format(dalle=dalle, annee=annee)
    prov: dict = {}
    if (sortie / f).is_file() and f in etat.get("prov_references", {}):
        return etat["prov_references"]
    base.fabriquer_reference(conf, "forms_t_v1", dalle, str(annee), sortie, prov)
    etat["prov_references"] = prov
    chemin_fragment(sortie, dalle).write_text(
        json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return prov


def fabriquer_ortho_dalle(
    conf: SimpleNamespace, dalle: str, etat: dict, sortie: Path, journal: Callable
) -> dict:
    """Descripteurs ortho 10 m de la dalle (mission 012) ; renvoie les entrées de PROVENANCE."""
    f = conf.ortho["fichier"].format(dalle=dalle)
    if (sortie / f).is_file() and f in etat.get("prov_ortho", {}):
        return etat["prov_ortho"]
    prov: dict = {}
    r = base.fabriquer_ortho(conf, dalle, sortie, prov, etat["meta"])
    erreurs = base.controler_ortho(conf, sortie / f, dalle)
    if erreurs:
        raise RuntimeError("; ".join(erreurs))
    etat["prov_ortho"] = prov
    etat["ortho"] = {"date": r["date"], "ecart_jours": r["ecart_jours"]}
    chemin_fragment(sortie, dalle).write_text(
        json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    journal(f"{dalle} ortho du {r['date']} ({r['ecart_jours']:+d} j) en {r['duree_s']:.0f} s")
    return prov


# --------------------------------------------------------------------------- assemblage


def ecrire_decoupage(conf: SimpleNamespace, sortie: Path, etats: dict, prov: dict) -> dict:
    """`decoupage.yaml` par blocs (mêmes clés que `tests/data/decoupage.yaml`) ; renvoie le dict."""

    def entrees(role: str) -> list[dict]:
        return [
            {"dalle": d, "bloc": base.bloc(conf, d), "bloc_echantillon": b["nom"]}
            for b in conf.blocs
            if b["role"] == role
            for d in dalles_du_bloc(b["nw_km"], conf.taille_bloc_dalles)
        ]

    doc = {
        "version": 1,
        "statut": conf.statut_decoupage,
        "taille_bloc_m": conf.taille_bloc_m,
        "bloc": "indice (xmin // taille_bloc_m, ymin // taille_bloc_m) de l'emprise de la dalle",
        "apprentissage": entrees("apprentissage"),
        "test": entrees("test"),
        "justification": justification(conf, etats),
    }
    (sortie / "decoupage.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    prov["decoupage.yaml"] = {
        "source": "choix du projet (scripts/fabriquer_echantillon.py, conf/echantillon_jura.yaml)",
        "requete": "sans objet (aucun accès réseau)",
        "date": base.date.today().isoformat(),
        "licence": "Licence Ouverte 2.0 (identifiants de dalles IGN)",
        "traitement": "blocs de la conf : rôle apprentissage ou test",
    }
    return doc


def surfaces_foret(chemin: Path) -> tuple[dict[str, float], float]:
    """(ha par essence, ha de forêt) d'une dalle, polygones fusionnés (pas de double compte)."""
    g = gpd.read_file(chemin)
    if g.empty:
        return {}, 0.0
    par_essence = {
        str(k): float(v.geometry.union_all().area / 1e4) for k, v in g.groupby("essence")
    }
    return par_essence, float(g.geometry.union_all().area / 1e4)


def essences_bloc(conf: SimpleNamespace, bloc: dict, etats: dict) -> dict[str, float]:
    tot: dict[str, float] = {}
    for d in dalles_du_bloc(bloc["nw_km"], conf.taille_bloc_dalles):
        for nom, ha in etats[d]["essences"].items():
            tot[nom] = tot.get(nom, 0.0) + ha
    return dict(sorted(tot.items(), key=lambda kv: -kv[1]))


def resume_bloc(conf: SimpleNamespace, bloc: dict, etats: dict) -> dict:
    """Chiffres d'un bloc : année et dates de vol, forêt, essences, hauteurs, S2."""
    ds = dalles_du_bloc(bloc["nw_km"], conf.taille_bloc_dalles)
    meta = {d: etats[d]["meta"] for d in ds}
    ess = essences_bloc(conf, bloc, etats)
    haut = [etats[d]["stats"] for d in ds]
    return {
        "annee": meme_annee(meta),
        "vol_debut": min(m["date_vol_debut"][:10] for m in meta.values()),
        "vol_fin": max(m["date_vol_fin"][:10] for m in meta.values()),
        "foret_ha": round(sum(etats[d]["foret_ha"] for d in ds)),
        "essences": [(k, round(v)) for k, v in list(ess.items())[:3]],
        "mnh_max_m": max(s["max_m"] for s in haut if s["max_m"] is not None),
        "p99_max_m": max(s["p99_m"] for s in haut if s["p99_m"] is not None),
        "part_sup_seuil": round(float(np.mean([s["part_sup_seuil"] for s in haut])), 4),
        "scenes": sum(len(etats[d]["scenes"]) // 2 for d in ds),
    }


def justification(conf: SimpleNamespace, etats: dict) -> str:
    morceaux = []
    for role in ("apprentissage", "test"):
        for b in (x for x in conf.blocs if x["role"] == role):
            r = resume_bloc(conf, b, etats)
            ess = ", ".join(f"{k} {ha} ha" for k, ha in r["essences"])
            morceaux.append(
                f"{role} : bloc {b['nom']} ({b['type']}), vol {r['vol_debut']} -> {r['vol_fin']}, "
                f"essences BD Forêt {ess}, MNH max {r['mnh_max_m']} m"
            )
    dmin = min(
        distance_blocs_m(conf, a, b) for i, a in enumerate(conf.blocs) for b in conf.blocs[i + 1 :]
    )
    return (
        f"{len(conf.blocs)} blocs de {conf.taille_bloc_dalles} x {conf.taille_bloc_dalles} dalles, "
        f"distants d'au moins {dmin / 1000:.0f} km : aucune dalle de test ne touche une dalle "
        f"d'apprentissage et aucun bloc de {conf.taille_bloc_m // 1000} km n'est partagé. "
        + " ; ".join(morceaux)
        + ". "
        + conf.justification_roles
    )


def ecrire_provenance(sortie: Path, prov: dict) -> None:
    entete = (
        "# PROVENANCE de l'échantillon du Jura (mission 008), générée par\n"
        "# scripts/fabriquer_echantillon.py. Une entrée par fichier de données : source, requête,\n"
        "# date d'accès, licence. Dates de vol : une seule source (WFS IGN).\n"
    )
    corps = yaml.safe_dump(
        {"fichiers": dict(sorted(prov.items()))}, allow_unicode=True, sort_keys=False, width=100
    )
    (sortie / "PROVENANCE").write_text(entete + corps, encoding="utf-8")


def taille_octets(dossier: Path) -> int:
    return sum(p.stat().st_size for p in dossier.rglob("*") if p.is_file())


def rapport_markdown(conf: SimpleNamespace, etats: dict, octets: int) -> str:
    """Manifeste lisible : blocs, dalles, dates de vol, essences, hauteurs max, taille."""
    L = [
        f"Taille de l'échantillon : {octets / 1e6:.0f} Mo ({octets / 2**30:.2f} Gio), "
        f"budget {conf.budget_octets / 2**30:.0f} Gio.",
        "",
        "| Bloc | Rôle | Type de forêt | Coin NO (km) | Vol | Forêt (ha) | Essences BD Forêt "
        f"| MNH max (m) | Part > {conf.seuil_grands_arbres_m:g} m | Scènes S2 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in conf.blocs:
        r = resume_bloc(conf, b, etats)
        ess = ", ".join(f"{k} {ha} ha" for k, ha in r["essences"])
        L.append(
            f"| {b['nom']} | {b['role']} | {b['type']} | {b['nw_km'][0]}-{b['nw_km'][1]} "
            f"| {r['vol_debut']} -> {r['vol_fin']} | {r['foret_ha']} | {ess} | {r['mnh_max_m']} "
            f"| {r['part_sup_seuil']:.1%} | {r['scenes']} |"
        )
    for b in conf.blocs:
        L += ["", f"### Bloc {b['nom']} ({b['role']})", ""]
        L += [
            "| Dalle | Vol (début -> fin) | Ortho (prise de vue, écart au vol) | Forêt (ha) "
            "| Essence dominante | MNH max | MNH p99 |"
        ]
        L += ["|---|---|---|---|---|---|---|"]
        for d in dalles_du_bloc(b["nw_km"], conf.taille_bloc_dalles):
            e = etats[d]
            ess = max(e["essences"].items(), key=lambda kv: kv[1]) if e["essences"] else ("-", 0)
            ortho = e.get("ortho")
            o = f"{ortho['date']} ({ortho['ecart_jours']:+d} j)" if ortho else "-"
            L.append(
                f"| {d} | {e['meta']['date_vol_debut'][:10]} -> {e['meta']['date_vol_fin'][:10]} "
                f"| {o} | {e['foret_ha']:.0f} | {ess[0]} {ess[1]:.0f} ha "
                f"| {e['stats']['max_m']} | {e['stats']['p99_m']} |"
            )
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- contrôle intégré


def controler_echantillon(conf: SimpleNamespace, sortie: Path) -> list[str]:
    """Contrôle l'échantillon fabriqué : CRS, alignement, provenance, taille, appariement S2.

    Renvoie la liste des erreurs (vide si tout est conforme). Aucun accès réseau.
    """
    erreurs = controler_blocs(conf)
    if not (sortie / "PROVENANCE").is_file():
        return erreurs + ["PROVENANCE absente"]
    prov = yaml.safe_load((sortie / "PROVENANCE").read_text(encoding="utf-8"))["fichiers"]
    fichiers = sorted(
        p.relative_to(sortie).as_posix()
        for p in sortie.rglob("*")
        if p.is_file()
        and p.name not in ("PROVENANCE", "fabrication.log", "MANIFESTE.md")
        and ".etat" not in p.parts
    )
    if sorted(prov) != fichiers:
        manque = sorted(set(fichiers) - set(prov))[:3]
        en_trop = sorted(set(prov) - set(fichiers))[:3]
        erreurs.append(f"PROVENANCE et fichiers diffèrent (non listés {manque}, absents {en_trop})")
    for nom, e in prov.items():
        for cle in ("source", "requete", "date", "licence"):
            if not e.get(cle):
                erreurs.append(f"PROVENANCE {nom} : champ {cle} vide")
    if taille_octets(sortie) > conf.budget_octets:
        erreurs.append(f"taille {taille_octets(sortie)} octets > budget {conf.budget_octets}")

    chemin_man = sortie / "manifeste_dalles.parquet"
    if not chemin_man.is_file():
        return erreurs + ["manifeste_dalles.parquet absent"]
    man = gpd.read_parquet(chemin_man).set_index("id")
    if sorted(man.index) != sorted(conf.dalles):
        erreurs.append("le manifeste ne liste pas exactement les dalles de la conf")
    crs = pyproj.CRS.from_user_input(conf.crs)
    scenes = pd.read_csv(sortie / "sentinel2_scenes.csv", dtype=str)
    for d in conf.dalles:
        if d not in man.index:
            continue
        annee = base.annee_vol({k: man.loc[d, k] for k in ("date_vol_debut", "date_vol_fin")})
        attendu = tuple(float(v) for v in base.emprise(d))
        a_verifier: list[tuple[str, float | None]] = [
            (f"lidar/{d}_MNH_2m.tif", 2.0),
            (f"lidar/{d}_MNT_10m.tif", 10.0),
            (f"foret/{d}_bdforet_v2.gpkg", None),
        ]
        for f in scenes.loc[scenes["dalle"] == d, "fichier"]:
            a_verifier.append((f, 10.0 if f.endswith("_10m.tif") else 20.0))
        if conf.forms_t_annees[0] <= int(annee) <= conf.forms_t_annees[1]:
            ref = conf.references["forms_t_v1"]["fichier"].format(dalle=d, annee=annee)
            a_verifier.append((ref, 10.0))
        for f, pas in a_verifier:
            chemin = sortie / f
            if not chemin.is_file():
                erreurs.append(f"{f} absent")
            elif pas is not None:
                with rasterio.open(chemin) as src:
                    if pyproj.CRS.from_user_input(src.crs.to_wkt()) != crs:
                        erreurs.append(f"{f} : CRS {src.crs} différent de {conf.crs}")
                    if tuple(round(v, 6) for v in src.bounds) != attendu:
                        erreurs.append(f"{f} : emprise {tuple(src.bounds)} != {attendu}")
                    if src.res != (pas, pas):
                        erreurs.append(f"{f} : pas {src.res} != {pas}")
        if hasattr(conf, "ortho"):
            erreurs += base.controler_ortho(conf, sortie / conf.ortho["fichier"].format(dalle=d), d)
        ds = scenes.loc[scenes["dalle"] == d]
        if ds.empty:
            erreurs.append(f"{d} : aucune scène Sentinel-2")
        for r in ds.itertuples():
            if r.date_scene[:4] != annee:
                erreurs.append(f"{d} : scène {r.scene} hors de l'année de vol {annee}")
    return erreurs


# --------------------------------------------------------------------------- principal


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--conf", type=Path, default=CONF_DEFAUT)
    ap.add_argument("--sortie", type=Path, help="remplace `sortie` de la conf")
    ap.add_argument("--dalles", nargs="+", help="restreindre la fabrication à ces dalles")
    ap.add_argument("--controler", action="store_true", help="contrôle seul, sans réseau")
    args = ap.parse_args()
    conf = charger_conf(args.conf)
    sortie = args.sortie or Path(conf.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    journal = Journal(sortie / "fabrication.log")

    erreurs = controler_blocs(conf)
    if erreurs:
        sys.exit("conf refusée : " + " ; ".join(erreurs))
    if args.controler:
        erreurs = controler_echantillon(conf, sortie)
        print("\n".join(erreurs) if erreurs else "contrôle : conforme")
        sys.exit(1 if erreurs else 0)

    voulues = args.dalles or conf.dalles
    t0 = time.time()
    journal(f"début : {len(voulues)} dalles, {conf.travailleurs} fils, sortie {sortie}")
    etats: dict[str, dict] = {}

    def une(d: str) -> dict:
        return avec_reprises(
            lambda: fabriquer_dalle(conf, d, sortie, journal), conf.tentatives, journal, d
        )

    with ThreadPoolExecutor(conf.travailleurs) as ex:
        for d, e in zip(voulues, ex.map(une, voulues), strict=True):
            etats[d] = e
    journal(f"dalles faites en {(time.time() - t0) / 60:.1f} min ; références FORMS-T v1")

    def ref(d: str) -> dict:
        return avec_reprises(
            lambda: fabriquer_reference_dalle(conf, d, etats[d], sortie, journal),
            conf.tentatives,
            journal,
            f"{d} FORMS-T",
            pause=30.0,
        )

    with ThreadPoolExecutor(2) as ex:  # Zenodo limite le débit : peu de lectures simultanées
        list(ex.map(ref, voulues))

    journal(f"références faites ; descripteurs ortho ({conf.travailleurs_ortho} fils)")

    def ortho(d: str) -> dict:
        return avec_reprises(
            lambda: fabriquer_ortho_dalle(conf, d, etats[d], sortie, journal),
            conf.tentatives,
            journal,
            f"{d} ortho",
            pause=30.0,
        )

    with ThreadPoolExecutor(
        conf.travailleurs_ortho
    ) as ex:  # le serveur IGN rend l'ortho dalle par dalle
        list(ex.map(ortho, voulues))

    if args.dalles:
        journal("fabrication partielle (--dalles) : pas d'assemblage")
        return
    for d in conf.dalles:  # surfaces recalculées depuis les GPKG, sans réseau
        ess, tot = surfaces_foret(sortie / f"foret/{d}_bdforet_v2.gpkg")
        etats[d]["essences"], etats[d]["foret_ha"] = ess, tot
    prov: dict = {}
    scenes: list[dict] = []
    meta = {d: etats[d]["meta"] for d in conf.dalles}
    for d in conf.dalles:
        prov.update(etats[d]["prov"])
        prov.update(etats[d].get("prov_references", {}))
        prov.update(etats[d].get("prov_ortho", {}))
        scenes += etats[d]["scenes"]
    base.ecrire_manifeste(conf, sortie, meta, prov)
    ecrire_decoupage(conf, sortie, etats, prov)
    base.ecrire_scenes(conf, sortie, scenes, prov, sorted({etats[d]["annee"] for d in conf.dalles}))
    ecrire_provenance(sortie, prov)
    octets = taille_octets(sortie)
    (sortie / "MANIFESTE.md").write_text(rapport_markdown(conf, etats, octets), encoding="utf-8")
    erreurs = controler_echantillon(conf, sortie)
    journal(
        f"terminé en {(time.time() - t0) / 60:.1f} min, {octets / 1e6:.0f} Mo ; contrôle : "
        + ("conforme" if not erreurs else f"{len(erreurs)} erreurs")
    )
    if erreurs:
        sys.exit("contrôle en échec :\n" + "\n".join(erreurs))


if __name__ == "__main__":
    main()
