# Journal de nemetoncanopee

> **Règle du sommier : on n'efface pas, on ajoute.**
> Chaque inscription est datée et signée (agent ou personne). Une correction est une
> nouvelle ligne qui renvoie à l'ancienne. Un hook refuse toute modification qui
> supprimerait ou réécrirait une inscription existante.
>
> Format : `AAAA-MM-JJ · auteur · mission · ce qui a été fait / décidé / bloqué`
>
> **Le carnet des écarts** (fiche n° 3), en une ligne marquée `écart` :
> `AAAA-MM-JJ · auteur · mission · écart · attendu : … · vu : … · vérifié : comment (ou « non ») · décision : …`
> La décision est l'une des trois : **garder** (vérifié : on adopte), **creuser** (prochain
> essai, daté), **abandonner** (vrai hasard : on le note).
> Règle : on ne sanctionne pas un écart signalé ; on regarde d'abord, on corrige ensuite,
> s'il le faut.
>
> **Les changements de cap** (fiche n° 13), en une ligne marquée `cap`, signée par qui l'a
> décidé : `AAAA-MM-JJ · auteur · mission · cap · ancien → nouveau · pourquoi : … · fait : …`
>
> **La délégation**, en une ligne marquée `délégation`, signée de Pascal :
> `AAAA-MM-JJ · Pascal · — · délégation · portée : … · jusqu'à : … · réservé : …`
> Chaque décision prise par délégation :
> `AAAA-MM-JJ · Claude (orchestrateur, par délégation) · mission · décidé : … · pourquoi : … · ce que Pascal peut défaire : …`

2026-11-22 · Claude (orchestrateur) · — · méthode installée (/demarrer) : CLAUDE.md, .claude/settings.json (plugin imperatrice), pilotage/ (équipe, kanban, journal, missions), docs/adr/. docs/brief.md (rédigé par Pascal le 2026-11-21) et .claude/test-command laissés tels quels. Reste à remplir : rubrique « Ma réponse d'abord » absente du brief ; spec, ADR, équipe.
2026-11-22 · Pascal · brief · ma réponse d'abord : « Je m'en passe, A terme il sera un projet pour nemeton » ; recopiée dans docs/brief.md. Brief déjà rédigé par Pascal le 2026-11-21 : on passe à la critique du contradicteur.
2026-11-22 · contradicteur · brief · 7 critiques : FORMSpoT (même labo, 1,5 m, 2014–2024, arXiv 2512.17021) absent de l'existant ; coordonnées IFN au km rendent le modèle volume et les critères IFN invérifiables sans convention ; définition du volume et coefficients biomasse à reprendre d'IGN/IPCC/CITEPA ; lissage isotone aveugle aux éclaircies ; fuite possible via Open-Canopy ; passerelle r/ en double avec le package R nemeton ; test CPU < 10 min dépendant du réseau. Non vérifié : chiffres FORMS-T v1 (ScienceDirect 403). Pascal tranche.
2026-11-22 · Pascal · brief · arbitrages : les 7 propositions du contradicteur retenues ; précision sur la 1 : le projet calcule aussi la hauteur, FORMSpoT s'arrêtant à 2024 (vérifié : THEIA et Zenodo 22111200, aucune mise à jour annoncée). Reportées dans docs/brief.md et CLAUDE.md par l'orchestrateur. Reste à trancher : où vit la fonction de statistiques zonales.
2026-11-22 · Pascal · brief · arbitrage : la fonction de statistiques zonales vit ici, en Python ; nemeton charge le paquet selon ses besoins. Reporté dans docs/brief.md (livrables, stack, arborescence : zonal/).
2026-11-22 · Claude (orchestrateur) · brief · docs/spec.md rédigée (statut proposée : parcours, données, hors périmètre, critères du jalon 1, référentiels) ; ADR 0001 (stack du squelette), 0002 (définition du volume), 0003 (licence, question de valeur) proposées ; à critiquer par le contradicteur, puis à trancher par Pascal.
2026-11-22 · contradicteur · spec et ADR · 13 critiques : blocs de 10 km sans objet sur 4 dalles (mécanique seule) ; jeu embarqué sans provenance ni budget de taille ; validation STAC des extensions exige le réseau (pystac) ; nodata uint16 et targets absents du brief ; ADR 0001 sans jsonschema, validateur COG, pyarrow ; zonal à aligner sur exactextractr de nemeton ; extensions STAC non nommées ; FORMS (2023) = bois fort tige jusqu'à 7 cm mais biomasse par ratios CARBOFOR (0,59/0,89), pas CITEPA ; IGN : expansion via CARBOFOR/EMERGE ; tables OMINEA introuvables ; nemeton GPL-3, aucune option de code incompatible ; mention Copernicus manquante ; ODbL peu adaptée aux rasters. Non vérifié : définition du volume dans FORMS-T v1, tables OMINEA. Pascal tranche.
2026-11-22 · Pascal · brief · « Oui je valide » : brief et spec validés (porte n° 1), propositions S1 à S4 (spec) et A1 à A3 (ADR 0001) retenues, ADR 0001 acceptée. Restent proposées, non bloquantes pour le jalon 1 : ADR 0002 (choix de la biomasse) et ADR 0003 (licences).
2026-11-22 · Claude (orchestrateur) · /mission · jalon 1 découpé en 4 missions (001 référentiels · acquereur ; 002 jeu d'essai · dev ; 003 tests d'acceptation · testeur ; 004 squelette · dev opus, main prise : plan validé par Pascal avant code) ; équipe proposée dans pilotage/equipe.md, cartes au bac à sable. Manque : choix des 4 dalles (zone pilote) pour 002. À valider par Pascal (porte n° 2).
