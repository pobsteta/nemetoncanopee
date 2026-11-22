"""Étape `train` : entraîne le modèle décrit par `conf/modele/*.yaml` sur les dalles
d'apprentissage du découpage figé, et l'écrit dans `modeles/{version}/modele.json`.

Le modèle se choisit par la conf (`modele:` de `conf/chaine.yaml`, clé `nom` du fichier) :
`mediane` (modèle trivial du jalon 1, `modele/trivial.yaml`) ou `gbm` (LightGBM, mission 009,
`modele/gbm.yaml`), dont les modèles en texte LightGBM s'écrivent à côté de `modele.json`,
qui porte leurs sha256.

La version du modèle est `{nom}-` + 12 caractères du sha256 de `modele.json` : deux
entraînements identiques donnent la même version. Un nouvel entraînement remplace le modèle
précédent (un seul modèle actif dans le dossier de travail).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from typing import Any

from nemeton_canopee import decoupage
from nemeton_canopee.chemins import Chemins
from nemeton_canopee.conf import Configuration
from nemeton_canopee.ecriture import ecrire_texte, lire_bande
from nemeton_canopee.erreurs import DonneeRefusee, EntreeManquante, exiger_fichier
from nemeton_canopee.ingest import Dalle, lire_manifeste
from nemeton_canopee.models import gbm, trivial

MODELES = {"mediane": trivial, "gbm": gbm}


def executer(conf: Configuration) -> str:
    """Entraîne et écrit le modèle ; renvoie sa version."""
    nom = conf.modele.get("nom")
    if nom not in MODELES:
        raise DonneeRefusee(f"modèle inconnu : {nom!r} (connus : {sorted(MODELES)})")
    ch = Chemins(conf.travail)
    dec = decoupage.lire(conf)
    dalles = lire_manifeste(ch, dec.apprentissage)
    fichiers: dict[str, str] = {}
    if nom == "gbm":
        resultat, fichiers = gbm.entrainer(conf, ch, dalles, dec.test)
    else:
        cibles = {
            d.id: lire_bande(exiger_fichier(ch.cible(d.annee, d.id), "targets"))[0] for d in dalles
        }
        resultat = trivial.entrainer(cibles, dec.test, conf.nodata, conf.modele["arrondi"])
    modele: dict[str, Any] = {
        "nom": nom,
        "unite": conf.hauteur["unite"],
        **resultat,
        "graine": conf.graine,
        "dalles_apprentissage": dec.apprentissage,
        "dalles_test": dec.test,
        "version_donnees": dalles[0].version_donnees,
    }
    contenu = json.dumps(modele, ensure_ascii=False, indent=2) + "\n"
    version = f"{nom}-{hashlib.sha256(contenu.encode('utf-8')).hexdigest()[:12]}"
    for fichier, texte in sorted(fichiers.items()):  # modele.json en dernier : il fait foi
        ecrire_texte(ch.modele(version).parent / fichier, texte)
    ecrire_texte(ch.modele(version), contenu)
    for ancien in ch.modeles.glob("*/modele.json"):
        if ancien.parent.name != version:
            shutil.rmtree(ancien.parent)
    return version


def modele_actif(ch: Chemins) -> tuple[str, dict[str, Any]]:
    """(version, contenu) du modèle écrit par `train`."""
    trouves = sorted(ch.modeles.glob("*/modele.json"))
    if len(trouves) != 1:
        raise EntreeManquante(f"{len(trouves)} modèle(s) dans {ch.modeles} (relancer train)")
    return trouves[0].parent.name, json.loads(trouves[0].read_text(encoding="utf-8"))


def predire(
    conf: Configuration,
    ch: Chemins,
    version: str,
    modele: dict[str, Any],
    dalle: Dalle,
    masque: Any,
) -> dict[str, Any]:
    """Couches prédites d'une dalle : `hauteur` toujours, `incertitude` pour le modèle gbm."""
    if modele["nom"] == "gbm":
        return gbm.predire(conf, ch, version, modele, dalle, masque)
    return {"hauteur": trivial.predire(modele, masque, conf.nodata)}
