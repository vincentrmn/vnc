# Zéphyr

> Moteur de **pré-étude de faisabilité** pour l'intégration de la **VNC**
> (Ventilation Naturelle Contrôlée) dans les bâtiments.

À partir de plans (DXF), de quelques paramètres et du type de projet, Zéphyr
produit en quelques minutes : un **verdict de faisabilité** (go / no-go /
conditionnel), un **ROI chiffré** (VNC vs VMC double-flux) avec fourchettes, et
un **rapport exportable**.

⚠️ Outil interne de **pré-qualification / aide à la décision**. Ce n'est **pas**
une étude opposable. Toute sortie expose ses hypothèses et son incertitude.

## 📖 Contexte de référence

- **[`docs/COMMENT_CA_MARCHE.md`](./docs/COMMENT_CA_MARCHE.md)** — explications
  **claires** (niveau ingénieur généraliste) : quel modèle, STD vs régression,
  fiabilité, paramètres, bureaux. À lire pour présenter/faire tester l'outil.
- **[`CLAUDE.md`](./CLAUDE.md)** — document maître : mission, décisions
  d'architecture (non négociables), glossaire, stack, spec ROI/thermique,
  roadmap, garde-fous.

## Architecture (pipeline)

`ingestion` (DXF) → `geometry` (topologie → `Building`) → `thermal` (5R1C) &
`ventilation` (tirage+vent) → `rules` (faisabilité) & `roi` (économie) →
`report`. Le `llm` est un service transverse (labelling + narratif), pas une
étape du pipeline.

## État (pipeline complet bout-en-bout)

| Module | État |
|---|---|
| `schemas` | ✅ contrat pydantic v2 (Building, StudyInput, résultats, ZoneResult, SiteContext) |
| `roi` | ✅ TCO/VAN paramétrique + pénalité **calculée** + tornado |
| `climate` | ✅ EPW réel (TMYx Findel) validé + degrés-heures + solaire |
| `thermal` | ✅ 5R1C **multi-zone** (sol + cœur structurel) — free-float **validé STD** ; pénalité directionnelle |
| `ventilation` | ✅ débits naturels (tirage + vent) + vérifs hygiénique/free-cooling |
| `rules` | ✅ verdict go/no-go/conditionnel + disqualifiants §4 |
| `study` | ✅ pipeline `compute_study` → `StudyResult` complet |
| `ingestion` / `geometry` | ✅ DXF → pièces (surfaces, labels, orientations estimées, ouvrants) — à valider humainement |
| `report` | ✅ rapport HTML (PDF optionnel WeasyPrint) |
| `presets` | ✅ profils logement / **bureau** |
| `llm` | 🚧 narratif (Phase 4 — à venir) |

Presets bureau + logement (`zephyr.presets`). Pénalité de chauffage **calculée**
mais encore *directionnelle* (calage fin en attente d'un besoin de chauffage STD).

## Démarrage

```bash
# Cœur (schemas + roi + thermal), suffisant pour les tests :
uv sync

# Runtime complet (CAO, climat, LLM, rapport, UI) :
uv sync --extra full

# Tests
uv run pytest

# UI interne (démo ROI) — nécessite l'extra app
uv run --extra app streamlit run app/main.py
```

## Garde-fous (rappel — cf. CLAUDE.md §11)

- Le **code mesure**, le **LLM interprète**. Jamais de géométrie « lue » par vision.
- La **pénalité de chauffage VNC** est **calculée** par `thermal`, jamais postulée.
- Toujours afficher une **fourchette / sensibilité**, pas un point unique.
- **DXF vectoriel uniquement** (pas de DWG, pas de raster).
- Jamais de plans / CPE / exports STD clients committés.
