# CLAUDE.md — Zéphyr

> Moteur de **pré-étude de faisabilité** pour l'intégration de la **VNC** (Ventilation Naturelle Contrôlée) dans les bâtiments.
> Ce fichier est le contexte de référence pour toute session Claude Code sur ce repo. **Lis-le en entier avant d'écrire du code.**

> **Repo** : `/vnc` (racine). **Codename moteur** : Zéphyr. **Monorepo** — jamais de split front/back.

> ⚠️ **Ce document a été réécrit après un pivot produit majeur (voir §0).** Si tu trouves de vieux artefacts qui parlent de « 5R1C / STD / verdict », c'est obsolète — c'est le présent fichier qui fait foi.

---

## 0. Pivot produit (à lire en premier)

Le projet a démarré sur l'idée d'un **screen thermique** (modèle 5R1C validé contre STD IDA ICE) rendant un **verdict** go/no-go. **On a abandonné cette approche** au profit d'un produit plus simple, plus honnête et déployable. Décisions actées :

1. **La VNC est éligible sur ~95 % des bâtiments** (le principe est universel ; reste à savoir s'il faut un appoint de chauffage selon l'inertie). Donc un **verdict** binaire n'a quasiment pas de valeur : **simuler finement la température ne sert à rien**.
2. **On ne fait PAS de STD** : ni 5R1C maison, ni EnergyPlus, ni surrogate ML. **Full déterministe.**
3. Le produit est : **lire les plans (DXF/PDF) + le CPE → un SCORE d'aptitude VNC (0–100) avec recommandations → un BILAN FINANCIER** (VNC vs VMC double-flux).
4. Le **seul terme thermique** nécessaire est le **surcoût de chauffage** VNC vs VMC (la VMC récupère la chaleur de l'air extrait, la VNC non) — calculé en **degrés-jours** (déterministe), jamais par simulation.
5. **Plateforme web** (FastAPI + HTML/CSS/JS) déployée sur **Railway**. Plus de Streamlit comme cible.
6. **Priorité actuelle : la DÉFINITION du bâtiment** (pièces, châssis, traversant) et la **méthode**. L'interprétation (notes/ROI) est secondaire tant que la définition n'est pas fiable.

Le 5R1C avait été calibré contre une STD réelle (maison Heffingen) à ±2,5 °C — ce travail a confirmé que le déterministe simple tenait, puis on l'a retiré. La pénalité degrés-jours est encore plus robuste (différence de pertes de ventilation).

---

## 1. Mission

À partir de plans (DXF ou **PDF vectoriel**) et du CPE, Zéphyr produit **en quelques minutes** :

1. un **score d'aptitude VNC** (déterministe, 4 critères pondérés) avec des **recommandations** d'amélioration ;
2. un **bilan financier** chiffré (VNC vs VMC double-flux), avec fourchettes et sensibilité (tornado) ;
3. le tout via une **plateforme web** où l'ingénieur dépose un plan, **valide/trace la géométrie**, et obtient le résultat.

Contexte business : on **vend de la VNC** (ouvrants motorisés + capteurs + plateforme BOS). Zéphyr est un **accélérateur interne / outil de pré-qualification**, **jamais une étude opposable**.

Deux usages : **interne** (priorité, tolérance à l'approximation si honnête sur l'incertitude) et **client** (plus tard, curseur QA relevé — pas le sujet v1).

---

## 2. Décisions d'architecture (NON négociables sauf décision explicite)

1. **Déterministe, point.** Cœur = règles + calculs déterministes. **Pas de ML, pas de STD, pas de moteur de simulation thermique.** Si un jour on veut des chiffres opposables sur un cas précis, le bon outil serait EnergyPlus + AirflowNetwork — **pas** un modèle maison —, mais ce n'est pas le produit.
2. **Le code mesure, l'humain donne la topologie, le LLM explique.** Toute grandeur géométrique/physique est calculée par du code déterministe. Le LLM ne sert qu'au *narratif* (rédaction de sortie) et, plus tard, au *labelling* sémantique. **Interdit** : faire « mesurer » une géométrie par un modèle de vision.
3. **Entrée = vecteur à l'échelle.** **DXF** (ezdxf) **et PDF vectoriel** (PyMuPDF). Un **PDF scanné** (image) est **refusé** — ce serait de la vision. Pas de DWG.
4. **Reconnaissance auto faillible → tracé assisté.** Les vrais plans (présentation archi) n'ont souvent **ni libellés de pièces ni polygones propres** (murs en lignes doublées + mobilier + hachures, plusieurs plans par planche, échelle non triviale). La reconstruction automatique n'est **pas fiable** dessus. La réponse déterministe honnête : **afficher le plan en fond et laisser l'ingénieur tracer les pièces au clic**, le code mesurant à partir de coordonnées **calibrées** (échelle). C'est l'esprit « code mesure » : l'humain fournit la topologie, le code calcule surfaces/façades.
5. **Honnêteté sur l'incertitude > fausse précision.** Fourchettes, pas de points magiques. Toujours afficher une sensibilité (tornado). Ne jamais survendre la VNC (on la vend → rester crédible).
6. **Surcoût de chauffage VNC : CALCULÉ en degrés-jours, jamais postulé.** Voir §6. C'est une *différence de pertes de ventilation* non récupérées par la VNC, atténuée par la **commande à la demande**. Jamais 0, jamais un % de récupération posé en dur.
7. **Bâtiments cibles : inertie lourde** (béton/maçonnerie) — hypothèse par défaut, lue du CPE.
8. **Human-in-the-loop sur la géométrie.** L'ingénieur **valide/corrige/trace** la géométrie avant calcul (éditeur web). Étape produit centrale, pas un détail.

---

## 3. Glossaire métier

- **VNC** — Ventilation Naturelle Contrôlée : renouvellement d'air par forces naturelles (tirage + vent) via **ouvrants motorisés** pilotés (capteurs/BOS). Notre produit.
- **VMC DF** — Ventilation Mécanique Contrôlée double-flux : référence de comparaison. Ventilateurs + **récupérateur de chaleur** (70–90 %).
- **BOS** — Building Operating System : plateforme qui pilote ouvrants + capteurs. Fourni dans l'offre.
- **CPE** — Certificat de Performance Énergétique (passeport énergétique LU). Source des données d'enveloppe **non lisibles sur un plan**.
- **Traversant** — pièce/logement balayé(e) par un flux d'air d'une façade à l'autre. (Aujourd'hui : pièce exposée sur ≥ 2 façades. *Question ouverte* : restreindre aux façades **opposées** — voir §11.)
- **Châssis** — ouvrant (fenêtre). À partir de ~**1,5 m de hauteur**, l'air circule par tirage **mono-façade** (suffisant à défaut de traversant).
- **Effet de cheminée (tirage)** — débit ∝ √(Δh·ΔT).
- **Degrés-jours (DJU)** — cumul des écarts de température à un seuil (base 18 °C). Déterministe, depuis l'EPW.
- **Free-cooling** — rafraîchissement passif par ventilation (souvent nocturne).
- **TMY / EPW** — fichier météo typique (EnergyPlus Weather).

---

## 4. Architecture (pipeline déterministe)

`ingestion` (DXF/PDF) → `geometry` (topologie → `Building`, **validée/tracée par l'humain**) → `rules` (**score d'aptitude**) & `thermal` (**pénalité chauffage degrés-jours**) → `roi` (économie) → `web` / `report`.

| Module | Rôle | Tech |
|---|---|---|
| `schemas` | Contrat pydantic v2 : `Building`/`Room`/`Opening`, `EnvelopeData`, `SiteContext`, `VNCScore`/`ScoreCriterion`, `HeatingPenalty`, `ROIResult`, `StudyResult`, `Verdict` | pydantic |
| `ingestion` | DXF → entités brutes (`RawDXF` : polylignes, textes, lignes, **blocs INSERT**). **PDF vectoriel** → mêmes entités (`parse_pdf`) + `render_pdf_page` (image de fond pour le tracé). **CPE** → texte (`parse_cpe`). Refuse les scans. | ezdxf, **pymupdf** |
| `geometry` | Reconstruit pièces (polygones fermés), labels (texte/calque FR/EN), **façades extérieures géométriques** (union des pièces → mur extérieur vs mitoyen, orientation cardinale, angle du Nord), châssis (lignes/blocs « fenêtre »), traversant. **Repli « pièces depuis les libellés »** (nom + surface) quand pas de polygones. | shapely |
| `rules` | **Moteur de SCORE** (0–100) pondéré + recommandations : ventilation (traversant/châssis ≥1,5 m), vitrage (vitrée/sol), inertie (CPE), isolation (U). Drapeaux durs de site (pollution, occupation incompatible) → verdict NO_GO. | code pur |
| `thermal` | **Pénalité de chauffage VNC en degrés-jours** (déterministe). C'est tout. | code pur + climate |
| `climate` | EPW → degrés-jours/heures, irradiance verticale (géométrie solaire auto-portée). | parseur EPW maison |
| `roi` | TCO/VAN paramétrique VNC vs VMC (cf. §6), sensibilité (tornado, SALib), fourchettes. | numpy, SALib |
| `study` | Orchestrateur `compute_study` → `StudyResult` (score + pénalité + ROI). | — |
| `web` | **Pages HTML du produit** (fonctions pures testables) : landing, formulaire de config, **éditeur de validation** (DXF reconstruit) et **éditeur de tracé** (PDF/plan en fond), page de résultats. + un peu de **JS vanilla** (SVG interactif). | stdlib HTML + JS |
| `llm` | Service transverse : **narratif** (Opus) en sortie ; **extraction CPE** (Sonnet) texte → champs d'enveloppe, **chiffres vérifiés verbatim** (`extract_cpe` / `verify_cpe_extraction`). Labelling pièces différé. | SDK Anthropic |
| `report` | Rapport HTML (PDF optionnel WeasyPrint). | HTML → PDF |
| `viz` | Rendu matplotlib d'un plan reconstruit (PNG / data-URI). | matplotlib |
| `builders` | `parametric_building` (saisie sans plan). | — |
| `presets` | Hypothèses par type de projet (débit hygiénique, pondérations score). | — |

**App** (`app/web.py`) : serveur **FastAPI**. Flow : `GET /` (landing) → `GET/POST /etude` (config + upload) → **validation/tracé** → `POST /etude/resultat` (géométrie confirmée via `building_json`) → résultats.

---

## 5. Stack technique

- **Python 3.11+**, gestion par **uv** (lockfile committé).
- **pydantic v2** partout (schémas).
- **CAO** : `ezdxf` (DXF), `shapely` (géométrie/topologie). **PDF** : `pymupdf` (fitz) — extraction vectorielle + rendu d'image.
- **Climat** : parseur `.epw` maison.
- **ROI / sensibilité** : `numpy`, `SALib`.
- **Web** : `FastAPI` + `uvicorn` + `python-multipart` (formulaires/upload). Pages rendues en **fonctions pures** retournant du HTML (testables sans serveur, comme `report`). `httpx` en dev pour le TestClient.
- **Principe lib (NON négociable)** : pour tout besoin non trivial, **on s'appuie sur la meilleure lib spécialisée** plutôt que de réécrire à la main. Ne PAS bricoler en vanilla ce qu'une lib éprouvée fait mieux. Choisir la lib la plus adaptée au besoin précis (et la noter ici). Le JS « vanilla » reste pour le collage/glue ; le cœur métier d'un composant s'appuie sur du solide.
- **Éditeur de tracé** : **Konva.js** (canvas 2D scene-graph, chargé via CDN `unpkg`) — zoom/pan, formes/poignées draggables, hit-testing natifs. Remplace l'ancien SVG vanilla (zoom/pan/coordonnées codés main, trop fragile).
- **Graphes (résultats financiers)** : **Chart.js** (chargé via CDN `unpkg`) — axes/échelles/grille/tooltips natifs. Données injectées en bloc JSON, JS statique (validable `node --check`). Remplace les `polyline`/`svg` tracés à la main.
- **Icônes** : **Lucide** (jeu minimaliste mono-couleur, trait, ISC). Les SVG sont **inlinés** (dict `_ICONS` + helper `_icon(name, size)` dans `web/__init__.py`) plutôt que chargés par CDN : rendu instantané, couleur héritée via `currentColor` (donc thème-aware), et **fonctionne dans le PDF WeasyPrint** où aucun JS ne tourne. Plus aucun emoji « type iPhone » dans l'UI. La charte (`/styleguide`) liste le jeu d'icônes. Le rapport PDF porte sa propre constante `_ALERT_SVG` (pas de dépendance `web`).
- **LLM** : SDK Anthropic. Modèles : `claude-opus-4-8` (narratif), `claude-sonnet-4-6` (labelling), `claude-haiku-4-5-20251001` (labelling volume). Prompt caching sur le bloc statique. **Le narratif n'invente AUCUN chiffre.**
- **Rapport** : HTML → PDF (`weasyprint`, optionnel).
- **Viz** : `matplotlib` (backend Agg).
- **Tests** : `pytest`. **Qualité** : `ruff` (lint+format, line-length 100) + `mypy` (strict). `[tool.ruff.lint.per-file-ignores]` ignore E501 sur `src/zephyr/web/__init__.py` (JS/CSS embarqués).
- **Extras** : `cao`, `climate`, `llm`, `report`, `viz`, `app`, `pdf`, `full`.
- **Déploiement** : `Dockerfile` (python:3.11-slim + uv, extras `app cao viz pdf`, bind `0.0.0.0:$PORT`) + `railway.json`. Déployé sur **Railway** depuis `main` (auto-redeploy au push). Lancer en local : `./scripts/run_web.sh`.

---

## 6. Modèle ROI (module `roi`)

Porté du comparatif Excel `comparatif_VNC_VMC` (Pommerloch, LU). **Tous les ratios/hypothèses = paramètres exposés**, rien en dur. Inchangé par le pivot.

- **CAPEX VMC** : ratios €/m² (centrales+récupérateurs, gaines, pose CVC, régulation, étanchéité, études, commissioning) + aléas.
- **CAPEX VNC** : quantités (ouvrants motorisés, capteurs 4-en-1, station météo, plateforme BOS, câblage €/m², extraction pièces humides, forfait STD+ingénierie, commissioning/hypercare) + aléas. **Les ouvrants qu'on dimensionne sont un poste de CAPEX** (ce ne sont pas un critère de score).
- **OPEX an 1** : VMC (énergie ventilateurs = volume×ACH×SFP×heures/1000×prix_élec, maintenance filtres, extraction) ; VNC (énergie actionneurs, maintenance, **abonnement BOS** €/pt/an, extraction, **+ pénalité de chauffage**).
- **Renouvellement** mi-vie ; **VAN** cumulée actualisée du delta (économie VNC = coûts VMC − coûts VNC) ; **break-even** ; TCO.
- **Sorties** : fourchettes + **tornado** (SALib) sur prix élec, WACC, nb ouvrants, abonnement BOS, pénalité chauffage.

### ⚠️ Pénalité de chauffage — désormais en degrés-jours (module `thermal`)
La VMC DF récupère η de la chaleur de l'air extrait, la VNC non. Terme **déterministe** :

```
pertes_ventilation_saison ≈ ρc · Q_hyg · DJU · 24        [Wh]
pénalité_VNC ≈ η_VMC · pertes · f_commande               [Wh]
```

avec `f_commande` < 1 l'atténuation par la **commande à la demande**. Jamais 0, jamais un % posé.

> ⚠️ **Désactivée par défaut depuis (simplification produit, décision utilisateur).** La pénalité est **toujours calculée** et stockée sur `result.heating_penalty` (info), mais **n'alimente plus le ROI** : `compute_study(..., include_heating_penalty=False)` par défaut. Tout le câblage (thermal → OPEX VNC, tornado, Monte-Carlo) reste en place — on rebranche d'un seul drapeau (`include_heating_penalty=True`) le jour où on veut affiner. Quand le terme est nul, ni la ligne OPEX `penalite_chauffage` ni le driver de sensibilité n'apparaissent (pas de « 0 € » parasite).

### Évolutions financières (faites)
- **Presets de coûts par taille** (`presets.cost_preset_for`) : les forfaits VNC (BOS, STD, commissioning, extraction) sont échelonnés maison / petit collectif / gros tertiaire, + une **part fixe VMC** (symétrie de modélisation). Corrige la limite « petite échelle ».
- **Type de chauffage → prix de l'énergie** de la pénalité (`heating_price_for` : PAC via COP, gaz, élec…). Effet majeur : en chauffage **électrique**, la pénalité explose et peut renverser le verdict.
- **Dimensionnement des ouvrants depuis la géométrie tracée** (`size_from_geometry`) : sur un vrai plan, nb d'ouvrants = châssis ouvrables réels ; sinon ratio surface/ouvrant (paramétrique).
- **Fourchette Monte-Carlo P10/P50/P90** sur la VAN + **break-even probabiliste** + **probabilité VNC favorable** (`sensitivity.monte_carlo`) → on n'affiche plus un point unique.
- **Postes optionnels** exposés et **neutres par défaut** : subvention VNC/VMC, coût carbone, free-cooling, TVA, inflation énergie distincte.
- **ROI « à livre ouvert »** : chaque poste porte sa **formule avec les nombres** (`CalcLine`). Affichage : **une ligne dépliable par poste** (clic → la formule et les nombres s'ouvrent **sous** la ligne, à côté du montant), plus de gros tableau séparé.
- **Graphe VAN** : courbe de la VAN cumulée rendue par **Chart.js** (CDN `unpkg`, cf. §5) — axes, échelle, grille, ligne de zéro, point vert au seuil de rentabilité, tooltips €. Remplace l'ancien `polyline` SVG sans repères.

### Avertissements méthodologiques (reportés dans le rapport)
Ratios €/m² = ordres de grandeur LU/BE (à confronter à ≥ 2 devis), pas de valeur résiduelle, résultats sensibles → toujours fourchette + tornado.

---

## 7. Le score d'aptitude VNC (module `rules`)

**Score (0–100)** = moyenne pondérée de 4 critères, chacun noté en déterministe avec son **barème** (`ScoreCriterion.scale`) et une **recommandation** d'amélioration. Pondérations par défaut (`ScoreWeights`, surchargeables) :

| Critère | Poids | Mesure | Source |
|---|---|---|---|
| **Ventilation** | 35 | au prorata de la surface : traversant = 100, mono-façade **châssis ≥ 1,5 m** = 60, mono-façade bas = 20 (plancher), aveugle = 0 ; × 0,5 si plan trop profond (> 2,5× HSP simple-face, > 5× traversant) | plans + hauteurs |
| **Vitrage** | 20 | **taux de surface vitrée, plus bas = mieux** : ≤ 1/8 (12,5 %) = 100, décroissance linéaire jusqu'au max 20 %, plancher 20 au-delà. **Mesuré en priorité depuis les châssis tracés** (Σ surfaces de châssis ÷ surface) ; CPE/saisie en repli ; **sans châssis tracé : 0** | châssis tracés (sinon CPE) |
| **Inertie** | 25 | masse : lourde 100 / moyenne 60 / légère 25 | **CPE (composition parois)** |
| **Isolation** | 20 | U mur 0,15→100 … 1,0→0 (70 %) ; Uw 0,8→100 … 2,5→0 (30 %) | CPE |

- Lettres : A ≥ 80, B ≥ 65, C ≥ 50, D ≥ 35, E < 35.
- **Les ouvrants ne sont PAS un critère** : c'est notre dimensionnement → un coût ROI.
- **Drapeaux de site** : pollution/pollen élevés et occupation incompatible → **NO_GO** ; bruit, sécurité RdC → réserves (CONDITIONNEL). Le `Verdict` (GO/CONDITIONNEL/NO_GO) devient une **éligibilité** ; le détail est porté par le score.

---

## 8. Définition du bâtiment — DXF, PDF, tracé (priorité actuelle)

C'est **le cœur du travail en cours**. Trois éléments à fiabiliser : **reconnaissance des pièces**, **des châssis**, **des espaces traversants**.

### Données : plans vs CPE
- **Plan (DXF/PDF) → géométrie** : pièces, **largeur** des baies, façades. Un plan 2D ne porte **pas** les hauteurs ni les matériaux.
- **CPE / saisie client → le non-lisible** : **hauteur des châssis**, **ratio vitrage**, **composition des parois (inertie/masse)**, **isolation (U)**, perméabilité n50, nature (neuf/réno), angle du Nord. *Aujourd'hui ces champs sont saisis à la main dans le formulaire de config ; parser un CPE PDF automatiquement est un chantier futur (cf. §11).*

### Deux modes selon le fichier
1. **DXF avec polygones de pièces propres** → reconstruction auto (`build_building`) : pièces, façades extérieures **géométriques** (union → extérieur vs mitoyen, orientation, angle du Nord), châssis (lignes/blocs), traversant → **éditeur de validation interactif** (SVG cliquable : on corrige label/façades/châssis, le traversant se recalcule, châssis affichés sur la façade).
2. **PDF (ou DXF sans polygones)** → **éditeur de TRACÉ** : plan rendu en image de fond, l'ingénieur **trace les pièces au clic**, le code calcule la surface réelle via l'**échelle calibrée** (par défaut A0 + 1:50 ; sinon **calibrage au clic d'une cote connue**). Façades et label par pièce. → produit le même `Building`.

Les deux éditeurs produisent un **`building_json`** (polygones en mètres) posté à `POST /etude/resultat`.

### Réalité apprise sur un vrai plan (PDF A0 d'archi, 1:50)
~500 000 segments vectoriels (murs doublés + mobilier + hachures + cotes), **aucun libellé pièce+surface**, 3 plans/planche, 1 image (logo). → **auto-reconstruction non fiable**, mais on **affiche le plan** et on **calcule l'échelle** (A0 = 1189 mm → 0,3528 mm/pt → **0,01764 m/pt à 1:50**) automatiquement. Le **tracé** est la bonne voie universelle.

---

## 9. Structure du repo

```
/vnc/
├── CLAUDE.md  README.md  pyproject.toml  uv.lock
├── Dockerfile  railway.json  .dockerignore        # déploiement Railway
├── scripts/        run_web.sh, make_sample_dxf.py
├── examples/       plan_exemple.dxf                # DXF d'exemple (6 pièces)
├── data/           climate/ (EPW), presets/, validation/ (gitignore sauf *.example.json)
├── src/zephyr/
│   ├── schemas/    building.py, study.py, results.py
│   ├── ingestion/  DXF + PDF (parse_dxf, parse_pdf, render_pdf_page)
│   ├── geometry/   reconstruction + façades + libellés
│   ├── climate/    EPW, degrés-jours, solaire
│   ├── thermal/    pénalité chauffage degrés-jours
│   ├── rules/      moteur de score
│   ├── roi/        TCO/VAN + sensibilité
│   ├── study.py    compute_study
│   ├── web/        pages HTML + JS (landing, config, validation, tracé, résultats)
│   ├── viz/        rendu plan matplotlib
│   ├── llm/        narratif Opus
│   ├── report/     rapport HTML/PDF
│   ├── builders.py presets.py
├── app/            web.py (FastAPI), main.py (ancien Streamlit, secondaire)
└── tests/unit/  tests/validation/
```

---

## 10. Roadmap

**Fait cette session** : pivot déterministe ; score + recommandations ; pénalité degrés-jours ; bilan financier détaillé ; plateforme web (landing/config/validation/résultats) ; déploiement Railway ; ingestion **PDF vectoriel** + rejet scans ; reconnaissance géométrique des **façades/traversant** + angle du Nord + blocs ; repli **pièces depuis libellés** ; **éditeur de validation interactif** (SVG) ; **éditeur de tracé** (plan en fond, calibrage, surfaces réelles).

**Fait depuis (éditeur de tracé)** : **zoom/pan** (molette + glisser, poignées à taille constante) ; **tracé des châssis** au glisser sur la façade (longueur → largeur de baie, façade déduite) ; **tracé universel sur DXF** (DXF rendu en image de fond quand la reconstruction auto ne donne pas de polygones propres — échelle exacte, sans calibrage) ; **multi-niveaux** (niveau courant + niveau par pièce, badge N{n}) ; **curseur de taille des repères** de tracé.

**Fait depuis (UX / page config)** : page de config repensée en **cartes** (Plan & tracé / CPE / Enveloppe / Projet / Site) ; champs projet ajoutés (**type de chauffage, ECS, matériau des châssis** — captés, pas encore câblés) ; CPE : extraction + **provenance par variable** + champs éditables (validation par variable). **Châssis** : hauteur saisie en **bulle pop-up** au relâcher (largeur = glisser), **tableau éditable** largeur×hauteur sous chaque pièce. **Rose des vents** dans le cadre de tracé. **Sauvegarde/reprise par fichier** (`.json` téléchargé/rechargé, zéro BDD). **Multi-PDF par étage** : un PDF par niveau (échelle propre), bascule de fond par niveau dans l'éditeur (ou plan A0 unique + niveau par pièce).

**Fait depuis (CPE)** : **parsing hybride** du CPE (passeport énergétique LU). `ingestion.parse_cpe` extrait le **texte** (déterministe, refuse les scans) ; `llm.extract_cpe` (Sonnet) **mappe** le texte aux champs d'enveloppe (U murs/toit/plancher, Uw, n50, inertie, surface, année) ; chaque **chiffre est vérifié verbatim** dans le texte source (`verify_cpe_extraction`) — un nombre absent est écarté et signalé (jamais inventé, §11). Le résultat **pré-remplit** le formulaire (`POST /etude/cpe`), l'ingénieur valide. Extra `llm` ajouté au Dockerfile ; actif si `ANTHROPIC_API_KEY` est défini sur Railway, sinon message honnête « indisponible » (le texte est quand même lu). **Validé en live sur le CPE Pommerloch** : 9/9 champs corrects avec provenance (mur « Façade » 0,122, toiture 0,109, plancher « Radier » 0,121, Uw 0,714, n50 0,60, ratio AFe/An 0,19, inertie lourde, surface 739,3 m², année 2026).

**Fait depuis (refonte UX — itération remarques utilisateur)** :
- **Critères** : ventilation au prorata avec plancher 20 (mono-façade bas) ; vitrage « plus bas = mieux » (≤ 1/8 → 100, max 20 %, plancher 20, **0 sans châssis tracé**) ; inertie lourde = 100.
- **Page config simplifiée** : carte **« Passeport énergétique »** (toggle simple upload / saisie), plan sans tirets ni « … » ni mention paramétrique, **retrait** des champs surface/angle/occupation incompatible, **reprise d'étude discrète en haut**, boutons d'action (Extraire/Reprendre) **hors du cadre d'upload**, **calcul bloqué tant qu'aucun plan** n'est importé.
- **Éditeur de tracé** : explication aérée (objectif puis comment, **touches clavier stylées** `<kbd>`) ; **bulle de validation** à la création d'une pièce (rectangle relâché / polygone refermé) ; bouton **« Terminer »** masqué hors traçage ; **pièces récentes en haut** ; **zone de dessin + palette figées** (seule la liste défile, fin du double-scroll) ; **sélecteur de niveaux RDC / R+1** en ligne ; **échelle en 1/xx** (au lieu de mm/px) ; **points cardinaux FR** (N/E/O/S — la valeur stockée reste le code `Orientation`) ; **plus de types de pièces** (majuscules + accents, enum `RoomLabel` étendu).
- **Bilan financier** : **infobulles « i »** sur chaque terme (VAN, TCO, break-even, CAPEX, proba) ; **hypothèses éditables** (prix élec, WACC, horizon, abonnement BOS, prix/nb d'ouvrants) → **recalcul serveur** (`ovr_*` → `_apply_roi_overrides`) ; **export Excel (CSV)** côté client et **export PDF** (`POST /etude/rapport` → `render_report`).
- **Design** : champs/sélecteurs épurés (fond `--surface-2`, **flèche custom** sur les `<select>` — fin du « combo noir »), suppression du séparateur « · », **enregistrement du projet (JSON)** en tête de résultats.

**Fait depuis (deux modes d'étude)** :
- **Mode « rapide » vs « complet »**, choisi en tête de `/etude` (toggle). **Complet** = flux actuel (plan obligatoire → traçage → analyse fine). **Rapide** = formulaire seul (surface, niveaux, % traversant, profondeur, + Passeport/CPE et taux vitrage/hauteur châssis), **sans plan ni traçage** — l'upload CPE reste possible. Un **seul moteur** : le rapide fabrique un `Building` représentatif (`builders.representative_building`) passé dans `compute_study(quick=True)`.
- **Sortie rapide** : une **tendance** (Favorable ≥ 65 / À étudier 45–65 / Défavorable < 45) + **bandeau « estimation rapide »** + **bilan financier allégé** (ordres de grandeur, pas de livre ouvert/hypothèses/tornado) + **fourchette ROI élargie** (`StudyResult.mode = "rapide"`).
- **Vitrage par pièce** (mode complet) : le taux est noté **pièce de vie par pièce de vie** (taux pièce → note → moyenne pondérée surface), les pièces de service (WC, sdb, circulation, technique…) étant exclues ; reco ciblée sur la pièce la plus vitrée.

**Prochaines étapes (priorité = définition du bâtiment, puis méthode)** — cf. §11 pour les questions ouvertes :
1. **CPE** : couvrir d'autres mises en page/versions (l'extraction est validée sur le format LuxEEB v6.25) ; affiner le choix Uw quand plusieurs types de fenêtres.
2. **Portes intérieures** → chemins d'air pour un traversant « réel » (pas juste ≥ 2 façades).
3. **Recalibrer les coûts ROI** par taille/typologie (cf. §6, limite petite échelle).

---

## 11. Garde-fous & questions ouvertes

**Garde-fous (ne pas violer) :**
- ❌ Faire **mesurer** une géométrie par un modèle de vision. Le code mesure (DXF/PDF vectoriel → shapely ; ou clics calibrés du tracé). Afficher un plan raster pour que l'**humain** trace = OK ; en **déduire** des mesures par CV = NON.
- ❌ Accepter un **PDF scanné** comme source de mesure auto. (Le tracé manuel dessus resterait possible, mais ce n'est pas la cible v1.)
- ❌ STD / 5R1C / EnergyPlus / ML dans le produit. Pénalité chauffage = degrés-jours.
- ❌ Coder un « % de récupération » VNC en dur, ou une pénalité = 0.
- ❌ Afficher un point unique de ROI sans fourchette/sensibilité.
- ❌ Présenter l'outil comme une étude opposable.
- ❌ Committer des plans / CPE / fichiers clients (sensibles). `data/validation/` gitignore sauf `*.example.json` distillés/anonymisés. Les fichiers uploadés par l'utilisateur (DXF/PDF de test) ne sont pas committés.
- ❌ Le **narratif LLM** n'invente aucun chiffre (reformule les valeurs fournies).
- ❌ Faire apparaître l'identifiant de modèle (`claude-opus-4-8`, etc.) dans un commit/PR/code — réponses de chat uniquement.

**Questions ouvertes (à trancher avec l'utilisateur) :**
- **Traversant = façades opposées ?** Aujourd'hui `Room.is_through` = ≥ 2 façades distinctes. Une pièce d'angle (N + W, perpendiculaires) est donc comptée traversante — l'utilisateur a relevé que c'est discutable, puis a préféré laisser tel quel. À reconsidérer (seuil ≈ ≥ 135° entre façades).
- **Échelle PDF** : par défaut A0 + 1:50. Généraliser (détection format, choix d'échelle, calibrage obligatoire si ambigu).
- **CPE** : entrée manuelle vs parsing automatique.

---

## 12. Definition of Done — produit interne

- Un ingénieur dépose un **DXF ou un PDF**, **valide ou trace** la géométrie (pièces, châssis, façades, traversant), et obtient **score + recommandations + bilan financier**.
- La **définition du bâtiment** est fiable (surfaces justes via échelle calibrée ; façades/traversant corrects ou corrigeables).
- Le **surcoût de chauffage** est calculé (degrés-jours), branché au ROI.
- Toute sortie expose ses **hypothèses** et son **incertitude** (fourchettes, tornado). Aucun chiffre orphelin.
- La plateforme tourne en local (`run_web.sh`) **et** sur Railway.

---

## 13. Conventions de dev (pour Claude Code)

- **Qualité avant commit** : `uv run ruff check .` , `uv run mypy` , `uv run pytest` doivent passer. Pour les tests web/PDF : `uv run --extra app --extra cao --extra viz --extra pdf pytest`.
- **JS embarqué** : validé par `node --check` (extraire la constante `_*_JS` dans un fichier `.js` et vérifier la syntaxe — on ne peut pas tester le navigateur ici). Le **cœur du tracé s'appuie sur Konva** (CDN) ; le JS local ne fait que l'orchestration. Toujours préférer une lib spécialisée à du DOM/SVG/canvas à la main (cf. §5).
- **Pages web = fonctions pures** retournant du HTML (testables) ; le serveur (`app/web.py`) ne fait que router. La géométrie transite en `building_json` (sérialisation `Building`).
- **Branche de dev** dédiée ; **merge fast-forward dans `main`** pour déclencher le redeploy Railway (workflow validé avec l'utilisateur).
- **Tester en réel** : penser aux dépendances runtime (ex. `python-multipart` est OBLIGATOIRE pour FastAPI). Lancer le vrai serveur (uvicorn) + curl/TestClient quand on touche au web.
- Commits en français, footers requis :
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` et `Claude-Session: …`.

---

## 14. Journal des décisions (session de pivot)

Chronologie des choix actés avec l'utilisateur (pour qu'une nouvelle session ne les rouvre pas par erreur) :

1. **Abandon STD/5R1C** : la VNC est ~universellement éligible → pas de verdict thermique, un **score**. Pas de simulation (ni maison, ni EnergyPlus, ni ML).
2. **Pénalité chauffage** : remplacée par un calcul **degrés-jours**.
3. **Produit** : plateforme qui lit plans + CPE → **score (4 critères : ventilation/vitrage/inertie/isolation) + recos + ROI**.
4. **Critère ventilation** : traversant idéal, sinon **châssis ≥ 1,5 m** (tirage mono-façade). **Les ouvrants = notre dimensionnement → coût ROI**, pas un critère.
5. **Web** : FastAPI + pages HTML pures + JS vanilla. Streamlit relégué. Déploiement **Railway** (Dockerfile + railway.json).
6. **Entrées** : DXF **et PDF vectoriel** (déterministe, zéro vision) ; **PDF scanné refusé**.
7. **Reconstruction auto faillible** sur vrais plans → **éditeur de tracé** (plan en fond, clics calibrés). Validé sur un vrai PDF A0 1:50.
8. **Focus** : d'abord la **définition du bâtiment** (pièces, châssis, traversant) et la **méthode** ; l'interprétation (notes/ROI) ensuite.
