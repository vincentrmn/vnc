# CLAUDE.md — Zéphyr

> Moteur de pré-étude de faisabilité pour l'intégration de la **VNC** (Ventilation Naturelle Contrôlée) dans les bâtiments.
> Ce fichier est le contexte de référence pour toute session Claude Code sur ce repo. Lis-le en entier avant d'écrire du code.

> **Repo** : `/vnc` (racine). **Codename moteur** : Zéphyr. **Un seul repo (monorepo)** — jamais de split front/back.

---

## 1. Mission

À partir de plans, de quelques paramètres techniques et du type de projet, Zéphyr doit produire **en quelques minutes** une pré-étude qu'un ingénieur mettait des heures à faire :

1. un **verdict de faisabilité** VNC (go / no-go / conditionnel) ;
2. un **ROI chiffré** (VNC vs VMC double-flux), avec fourchettes ;
3. des **explications** lisibles et un **rapport exportable**.

Deux usages, deux niveaux d'exigence :
- **Interne (priorité actuelle)** : aller vite, pré-qualifier des bâtiments. Tolérance à l'approximation, tant que l'outil est *honnête sur son incertitude*.
- **Client (plus tard)** : argumentaire commercial. Relève fortement le curseur QA et la prudence juridique. **Pas le sujet de la v1.**

Contexte business : on **vend de la VNC** (ouvrants motorisés + capteurs + plateforme BOS). Zéphyr est d'abord un accélérateur interne et un outil de pré-qualification, **jamais une étude opposable**.

---

## 2. Décisions d'architecture (NON négociables sauf décision explicite)

Ces décisions ont été actées en cadrage. Ne les rouvre pas sans raison.

1. **Déterministe d'abord, ML différé.** Le cœur est un moteur de règles + physique simplifiée. Le surrogate ML (métamodèle de STD) est repoussé en **Phase 5**, conditionné à : (a) un produit déterministe qui marche, (b) un dataset suffisant. Ne commence **pas** par le ML.

2. **Le code mesure, le LLM interprète et explique.** Toute grandeur géométrique ou physique est calculée par du code déterministe. Le LLM sert au *labelling sémantique* (à l'ingestion) et à la *rédaction* (en sortie). **Interdit** : faire « lire » des cotes ou mesurer une surface par un modèle de vision.

3. **Entrée = DXF uniquement (v1).** On exige des plans **vectorisés à l'échelle, au format DXF** (export 1 clic depuis n'importe quel outil CAO). Pas de DWG (format fermé, non lu par ezdxf — éviter l'étape de conversion), pas de raster scanné. L'IFC est un bonus futur (sémantique native), pas un prérequis.

4. **Honnêteté sur l'incertitude > fausse précision.** L'outil affiche des **fourchettes**, pas des points magiques. Un outil biaisé toujours dans le même sens (typiquement trop optimiste sur la VNC, puisqu'on la vend) détruit la confiance. Toute sortie doit être *directionnellement fiable* et exposer ses hypothèses.

5. **Pénalité de chauffage VNC : CALCULÉE, jamais postulée.** Voir §6. En VNC il n'y a **aucun échangeur air-air** → la récupération stricte est ~0 %. MAIS la pénalité *effective* est très inférieure aux pertes pleines grâce à la commande à la demande, à l'inertie et au scheduling. Ce delta est **sorti par le modèle thermique**, pas codé en dur. Si un chiffre de « récupération équivalente » est affiché, c'est une **sortie dérivée et validée**, pas une entrée.

6. **STD = validation, pas entraînement.** On a peu de projets STD (IDA ICE). C'est trop peu pour entraîner un modèle qui généralise, mais c'est le **banc de validation** du screen thermique. Cible : `data/validation/` contient les exports IDA ICE (température par pièce/saison) ; `tests/validation/` vérifie que le modèle 5R1C les reproduit dans une tolérance définie.

7. **Bâtiments cibles : inertie lourde** (dalle béton, murs béton/maçonnés). C'est l'hypothèse par défaut et le cas le plus favorable (stockage de fraîcheur nocturne l'été, amortissement de la pénalité de chauffe l'hiver). Le modèle thermique doit avoir un **nœud de masse** capable de représenter ça.

8. **Human-in-the-loop sur la géométrie.** La reconstruction topologique depuis un DXF est faillible. L'ingénieur valide/corrige la géométrie extraite avant calcul. C'est une étape produit, pas un détail.

---

## 3. Glossaire métier

- **VNC** — Ventilation Naturelle Contrôlée. Renouvellement d'air par forces naturelles (tirage thermique + vent) via **ouvrants motorisés** pilotés par capteurs/BOS. C'est notre produit.
- **VMC DF** — Ventilation Mécanique Contrôlée double-flux. Référence de comparaison. Ventilateurs + **récupérateur de chaleur** (70–90 %).
- **BOS** — Building Operating System. La plateforme qui pilote ouvrants + capteurs (gateways, edge, supervision cloud). Fourni dans notre offre.
- **STD** — Simulation Thermique Dynamique. Modélisation horaire annuelle du comportement thermique. Notre outil de référence interne : **IDA ICE**.
- **CPE** — Certificat de Performance Énergétique (passeport énergétique LU ; équivalent du DPE français). Source de données d'enveloppe.
- **Free-cooling / rafraîchissement passif** — refroidir le bâtiment par ventilation (souvent nocturne) sans machine frigorifique. Bénéfice clé de la VNC.
- **Effet de cheminée (tirage)** — débit d'air induit par différence de température et de hauteur. ∝ √(Δh · ΔT).
- **Degrés-heures (DH)** — cumul horaire des écarts de température à un seuil ; indicateur de surchauffe/free-cooling, purement déterministe à partir d'un fichier météo.
- **Inertie thermique** — capacité du bâtiment à stocker/déphaser la chaleur. Lourde ici. Modélisée par la capacité `C` du 5R1C.
- **5R1C** — modèle thermique réduit (5 résistances, 1 capacité) de l'ISO 52016/13790. Léger, horaire, avec nœud de masse. Notre niveau de modélisation Phase 2.
- **TMY / EPW** — fichier météo typique (Typical Meteorological Year), format EnergyPlus Weather. Entrée du calcul climatique.

---

## 4. Architecture (cf. schéma moteur)

Pipeline, des entrées vers les sorties. Couleurs du schéma : teal = code déterministe, corail = cœur physique, gris = données/LLM.

| Module | Rôle | Tech principale |
|---|---|---|
| `ingestion` | Parse le DXF → entités CAO brutes (calques, blocs, polylignes, textes) | ezdxf |
| `geometry` | Reconstruit la **topologie** : pièces (polygones fermés), murs int/ext, ouvrants, orientations, hauteurs. → objet `Building`. Étape de **validation humaine + labelling LLM**. | shapely, networkx |
| `climate` | Lit le TMY/EPW, calcule degrés-heures, potentiel de free-cooling | parseur EPW (ladybug/pvlib) |
| `thermal` | Modèle **5R1C** (inertie) → heures de surchauffe + **pénalité de chauffage saisonnière** | numpy |
| `ventilation` | Débits naturels (tirage + vent), dimensionnement des ouvrants, vérifs géométriques | numpy |
| `rules` | Moteur déterministe de faisabilité : go/no-go/conditionnel + disqualifiants | code pur |
| `roi` | TCO/VAN paramétrique VNC vs VMC (cf. §6), sensibilité, fourchettes | numpy, SALib |
| `llm` | Service transverse : labelling sémantique (Sonnet/Haiku) + narratif (Opus) | SDK Anthropic |
| `report` | Génère le rapport (verdict + ROI + graphes + explications) | HTML → PDF (weasyprint/playwright) |
| `schemas` | Modèles de données transverses (pydantic) | pydantic v2 |

**Flux de données (logique, simplifiée) :**
`Building` (+ `climate`) → `thermal` & `ventilation` → `rules` (faisabilité) & `roi` (économie) → `report`.
Le LLM n'est **pas** une étape du pipeline : c'est un service appelé à deux endroits (labelling géométrie, narratif rapport).

**Disqualifiants à coder dans `rules`** (chacun avec son seuil et son explication) : bruit extérieur excessif, pollution/pollen, sécurité au RdC, plan trop profond sans traversant possible (profondeur > ~2,5× HSP en simple-face, > ~5× en traversant), surface d'ouvrants insuffisante, absence d'exposition au vent, occupation incompatible.

---

## 5. Stack technique

- **Langage** : Python 3.11+. Tout l'écosystème nécessaire (CAO, physique, ML futur) est en Python.
- **Gestion projet** : `pyproject.toml` (uv ou poetry). Lockfile committé.
- **Données** : `pydantic` v2 partout pour les schémas (validation + typage).
- **CAO** : `ezdxf` (DXF). `shapely` (géométrie/topologie), `networkx` (adjacences) si besoin.
- **Climat** : fichiers `.epw`. Parseur léger (ladybug-core ou pvlib).
- **Thermique** : modèle 5R1C maison en `numpy` (pas de dépendance lourde type EnergyPlus en Phase 2).
- **ROI / sensibilité** : `numpy`, `SALib` (analyse de sensibilité / tornado).
- **LLM** : SDK Anthropic. Modèles :
  - `claude-opus-4-8` — synthèse de faisabilité + narratif (qualité/jugement).
  - `claude-sonnet-4-6` — labelling sémantique, tâches structurées (par défaut).
  - `claude-haiku-4-5-20251001` — labelling massif/bon marché si volume.
  - **Prompt caching** sur le bloc statique (règles, normes, exemples) → jusqu'à 90 % d'économie sur l'input répété. **Batch API** (−50 %) pour le non temps-réel.
- **API** : `FastAPI`.
- **UI interne** : `Streamlit` (rapide, pragmatique pour l'interne). Une vraie front React n'arrive que si on passe au client.
- **Rapport** : HTML templaté → PDF via `weasyprint` (ou `playwright` si besoin de JS/graphes complexes).
- **Tests** : `pytest`. Dossier dédié `tests/validation/` adossé à `data/validation/` (cas IDA ICE).
- **Qualité** : `ruff` (lint+format), `mypy` (typage).

---

## 6. Modèle ROI (spec à implémenter dans `roi`)

Porté du comparatif Excel `comparatif_VNC_VMC` (cas Pommerloch, mixte logements + bureaux, LU). **Tous les ratios et hypothèses doivent être des paramètres exposés**, pas des constantes en dur. Presets régionaux prévus (`data/presets/`).

**Hypothèses bâtiment & financières** (exemples Pommerloch) :
- surface totale ventilée = nb_logements × surface/logement + surface tertiaire ; volume = surface × HSP.
- horizon 20 ans ; WACC 3 % ; inflation OPEX/énergie 2,5 % ; prix élec 0,28 €/kWh (Eurostat LU).

**CAPEX VMC DF** — par ratios €/m² (centrales+récupérateurs, réseau gaines, pose CVC, régulation, étanchéité, études, commissioning) + 10 % aléas.

**CAPEX VNC** — par quantités : ouvrants motorisés (~1 ratio 1/25 m²), capteurs 4-en-1, station météo, plateforme BOS, câblage €/m², **extraction dédiée pièces humides** (hors VNC), forfait STD + ingénierie, commissioning/hypercare + 10 % aléas.

**OPEX annuel (an 1, avant inflation)** :
- VMC : énergie ventilateurs = `volume × ACH × SFP × heures / 1000 × prix_élec` ; maintenance €/m²/an (filtres) ; extraction pièces humides.
- VNC : énergie actionneurs (~200 kWh/an total) ; maintenance ouvrants/capteurs €/m²/an ; **abonnement BOS cloud** €/pt/an × nb_points ; extraction pièces humides.

**Renouvellement** à mi-vie (an 12) : VMC ~25 % du CAPEX, VNC ~15 %.

**Sorties** : VAN cumulée actualisée du delta (VNC − VMC), année de break-even, TCO non actualisé des deux options.

### ⚠️ Correction obligatoire vs l'Excel : la pénalité de chauffage
L'Excel **ne compte que** l'énergie des ventilateurs, la maintenance et l'abonnement BOS. Il **omet** le coût de chauffage différentiel : la VMC DF **récupère** la chaleur de l'air extrait, la VNC non. En climat de chauffe (LU), c'est plusieurs MWh/an potentiels en faveur de la VMC.

Le module `roi` doit recevoir de `thermal` un **terme OPEX « pénalité de chauffage VNC »** = besoin de chauffage supplémentaire dû à l'absence de récupération, **atténué** par : commande à la demande (débits hygiéniques mini hors occupation), inertie lourde, scheduling saisonnier. Ce terme est **calculé**, jamais un % posé. Sans lui, la VAN de la VNC est artificiellement flatteuse — inacceptable même en interne.

### Avertissements méthodologiques (à reporter dans le rapport)
- Les ratios €/m² VMC sont des ordres de grandeur marché LU/BE ; à confronter à ≥ 2 devis réels.
- Aucune valeur résiduelle en fin d'horizon.
- Résultats sensibles à : prix élec, WACC, nb d'ouvrants, abonnement BOS, pénalité de chauffage. **Toujours afficher une analyse de sensibilité (tornado), pas un point unique.**

---

## 7. Le screen thermique (module `thermal`)

- **Pourquoi 5R1C** : c'est le bon niveau d'honnêteté — horaire, léger, avec un **nœud de masse** (capacité `C`) qui capture l'inertie lourde et donc à la fois le free-cooling nocturne et l'atténuation de la pénalité de chauffe. Pas besoin d'EnergyPlus en Phase 2.
- **Ce qu'il calcule** : heures de surchauffe (DH au-dessus de seuils de confort), bénéfice du night-cooling VNC, et le **delta de besoin de chauffage** VNC vs récupération.
- **Calibration** : toute évolution du modèle est validée contre `data/validation/` (exports IDA ICE). Si le 5R1C ne reproduit pas les répartitions de température observées dans la tolérance, on recale **avant** de construire dessus. C'est le test qui de-risque le projet au moindre coût.
- **Sortie « récup équivalente »** (optionnelle, pour la com') : dérivée du delta calculé, exprimée en % pour le lecteur, et validée. Jamais une entrée.

---

## 8. Couche LLM (module `llm`)

- **Rôles** (et seulement ceux-là) :
  1. *Labelling sémantique* à l'ingestion : « cette polyligne fermée est-elle un séjour, une SDB, une circulation ? », « cet ouvrant est-il ouvrable ? ». Modèle : Sonnet 4.6 (ou Haiku si volume).
  2. *Narratif* en sortie : transformer les résultats chiffrés en explications lisibles. Modèle : Opus 4.8.
- **Interdits** : mesurer/estimer une géométrie par vision ; inventer des chiffres ; remplacer un calcul déterministe.
- **Coût** : négligeable. ~1–5 € par étude tout compris, plausiblement < 1 € avec caching + Sonnet/Haiku sur les sous-tâches + batch. Tarifs (standard, par M tokens) : Opus 4.8 5/25 \$ ; Sonnet 4.6 3/15 \$ ; Haiku 4.5 1/5 \$. Le vrai coût du projet est le **dev + la validation**, pas l'inférence.
- **Caching** : mettre le bloc statique (règles, normes, exemples few-shot) en cache. **Bornes** : `max_tokens` serré, effort adapté à la tâche (pas `xhigh` pour du labelling).

---

## 9. Structure du repo (cible)

Racine du repo : `/vnc`. Le layout ci-dessous est la forme **MVP interne** (Phases 0–4). Plus tard, évolution dans le **même repo** vers un monorepo à workspaces (jamais de split front/back) : `packages/zephyr/` (moteur), `apps/api/` (FastAPI), `apps/web/` (front React). Le front est la couche jetable, le moteur est l'actif.

```
/vnc/                        (racine — projet : Zéphyr)
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .env.example              # clés API, chemins — JAMAIS de secret committé
├── data/
│   ├── climate/              # fichiers .epw (Luxembourg, etc.)
│   ├── presets/              # presets coûts/réglementaires régionaux
│   └── validation/           # exports IDA ICE (gitignored ou anonymisés)
├── src/zephyr/
│   ├── schemas/              # StudyInput, Building, Room, Opening, ThermalResult, ROIResult, StudyResult
│   ├── ingestion/            # DXF (ezdxf)
│   ├── geometry/             # topologie (shapely): pièces, murs, ouvrants, orientation
│   ├── climate/              # EPW, degrés-heures, free-cooling
│   ├── thermal/              # 5R1C, surchauffe, pénalité de chauffage
│   ├── ventilation/          # tirage + vent, dimensionnement ouvrants
│   ├── rules/                # moteur de faisabilité + disqualifiants
│   ├── roi/                  # TCO/VAN paramétrique (cf. §6)
│   ├── llm/                  # client Anthropic, prompts, caching
│   └── report/               # HTML → PDF
├── app/                      # FastAPI + UI Streamlit interne
├── tests/
│   ├── unit/
│   └── validation/           # tests adossés à data/validation (IDA ICE)
└── notebooks/                # exploration, calibration thermique
```

---

## 10. Roadmap (ordre de construction)

| Phase | Contenu | Estimation |
|---|---|---|
| **0** | Cadrage : schéma d'entrée, jeu de règles avec un thermicien, presets, disclaimers | ~1 sem |
| **1** | `roi` paramétré (port Excel + **terme pénalité chauffage**) + sensibilité/fourchettes + **test de calibration thermique** sur 1-2 cas IDA ICE | qq jours–1 sem |
| **2** | `climate` + `thermal` (5R1C) + `ventilation` + `rules`. **Cœur technique du MVP.** | ~2–4 sem |
| **3** | `ingestion` + `geometry` + **UI de validation humaine**. La phase difficile, mais bornée par DXF. | ~3–6 sem |
| **4** | `llm` (narratif) + `report` + UI Streamlit interne | ~2–4 sem |
| **5 (différé)** | Surrogate ML de STD : générateur paramétrique (EnergyPlus) → dataset → métamodèle → validation contre IDA ICE | ~4–6 mois, track séparé |

**MVP interne utile** ≈ Phases 0–2 + UI fine, ~4–7 semaines. La v1 « montrable » (jusqu'à Phase 4) ≈ 3–5 mois. Le temps écoulé est dominé par les **décisions métier, l'itération sur le parsing DXF et la validation** — pas par la vitesse d'écriture du code.

**Première brique à attaquer** : Phase 1 — `roi` propre + le test de calibration thermique. C'est le test le moins cher qui dit si l'approche déterministe tient avant qu'on construise tout dessus.

---

## 11. Garde-fous — ce qu'il NE faut PAS faire

- ❌ Faire mesurer une géométrie par un modèle de vision. Le code mesure (DXF → shapely).
- ❌ Coder un « % de récupération » de la VNC en dur. Il est calculé par `thermal`.
- ❌ Démarrer le surrogate ML avant un produit déterministe qui marche **et** un dataset suffisant.
- ❌ Afficher un point unique de ROI sans fourchette/sensibilité.
- ❌ Présenter l'outil comme une étude opposable ou « compliant ». C'est une pré-étude / aide à la décision.
- ❌ Committer des plans, CPE ou exports STD réels (données clients sensibles). `data/validation/` et `data/` sensibles → gitignore ou anonymisation.
- ❌ Accepter du DWG ou du raster en v1. DXF vectoriel uniquement.
- ❌ Laisser un chiffre thermique non validé contre IDA ICE partir dans un rapport quand un cas de validation existe.

---

## 12. Definition of Done — MVP interne

- `roi` reproduit le comparatif Excel **+ le terme de pénalité de chauffage**, avec fourchettes et tornado.
- `thermal` (5R1C) reproduit les répartitions de température IDA ICE de `data/validation/` dans la tolérance définie.
- `rules` rend un verdict go/no-go/conditionnel justifié, avec disqualifiants explicites.
- Un ingénieur peut uploader un DXF, valider/corriger la géométrie, et obtenir verdict + ROI + rapport.
- Toute sortie expose ses hypothèses et son incertitude. Aucun chiffre orphelin non sourcé.

---

## 13. Bootstrap — premier scaffold (à exécuter par Claude Code dans `/vnc`)

Ordre conseillé pour la toute première session. Cette conversation n'est pas en mémoire : ce qui suit *est* le plan de démarrage.

### 13.1 Squelette du repo
Créer :
- `pyproject.toml` (Python 3.11+). Runtime : `ezdxf`, `shapely`, `numpy`, `pydantic>=2`, `pandas`, `SALib`, `fastapi`, `streamlit`, `anthropic`, `weasyprint`. Dev : `pytest`, `ruff`, `mypy`. Committer le lockfile.
- `src/zephyr/` avec un sous-package par module (`schemas`, `ingestion`, `geometry`, `climate`, `thermal`, `ventilation`, `rules`, `roi`, `llm`, `report`), chacun avec `__init__.py` + un stub (signatures typées, docstring FR, `raise NotImplementedError`).
- `app/main.py` : stub Streamlit (upload DXF + formulaire + zone résultats, branché sur rien pour l'instant).
- `data/climate/`, `data/presets/`, `data/validation/` (avec `.gitkeep`).
- `tests/unit/`, `tests/validation/`.
- `.gitignore` : `data/validation/`, `.env`, `__pycache__/`, `.venv/`, `node_modules/`, `.claude/worktrees/`, exports STD bruts (`*.idm`, etc.). **Les fichiers STD/CPE clients ne sont JAMAIS committés.**
- `.env.example` : `ANTHROPIC_API_KEY=`, chemins de données.
- `README.md` minimal qui pointe vers ce CLAUDE.md.

### 13.2 Schémas (`schemas`) — à écrire en premier
Pydantic v2 : `Opening`, `Room`, `Building` (géométrie + inertie + orientations), `StudyInput` (type de projet, paramètres, CPE), `ThermalResult` (heures de surchauffe, pénalité de chauffage), `ROIResult`, `StudyResult` (agrégat). C'est le contrat transverse.

### 13.3 Module `roi` — la première vraie brique
Porter le modèle de §6 en module paramétré :
- Toutes les hypothèses/ratios = paramètres (presets par défaut LU/Pommerloch), **rien en dur**.
- Implémenter : CAPEX VMC (ratios €/m²), CAPEX VNC (quantités), OPEX an 1, inflation, actualisation (WACC), renouvellement an 12, VAN cumulée, break-even.
- **Brancher le terme `heating_penalty_eur_per_year`** dans l'OPEX VNC. Tant que `thermal` n'existe pas, le passer en paramètre (valeur conservatrice explicite) — **jamais 0, jamais un % de récup posé en dur**.
- Sorties avec **fourchettes + analyse de sensibilité (tornado, SALib)** sur : prix élec, WACC, nb d'ouvrants, abonnement BOS, pénalité chauffage.
- Test de non-régression : reproduire les chiffres clés de l'Excel (pénalité = 0 pour comparer au modèle d'origine), puis montrer l'écart une fois le terme activé.

### 13.4 Calibration thermique — le test qui de-risque
- Déposer 2-3 cas IDA ICE **anonymisés** dans `data/validation/` : le couple **entrées + sorties** (géométrie / enveloppe / apports / ventilation / météo + températures par pièce-saison).
- `tests/validation/` rejouera (quand `thermal` existera) le 5R1C sur ces cas avec une tolérance définie. Poser le harnais + un cas de référence dès maintenant.
- C'est le test le moins cher qui dit si l'approche déterministe tient. Le faire tôt.

### 13.5 Suite
Phase 2 (`climate` → `thermal` 5R1C → `ventilation` → `rules`), puis Phase 4 (`llm` narratif + `report` + UI). Cf. §10. **Ne pas démarrer le surrogate ML (Phase 5).**
