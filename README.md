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

**Lire [`CLAUDE.md`](./CLAUDE.md)** : mission, décisions d'architecture (non
négociables), glossaire métier, stack, spec ROI/thermique, roadmap et
garde-fous. C'est le document maître du projet.

## Architecture (pipeline)

`ingestion` (DXF) → `geometry` (topologie → `Building`) → `thermal` (5R1C) &
`ventilation` (tirage+vent) → `rules` (faisabilité) & `roi` (économie) →
`report`. Le `llm` est un service transverse (labelling + narratif), pas une
étape du pipeline.

## État (Phase 1)

| Module | État |
|---|---|
| `schemas` | ✅ contrat pydantic v2 (Building, StudyInput, résultats) |
| `roi` | ✅ TCO/VAN paramétrique + pénalité de chauffage + tornado |
| `thermal` | 🚧 stub + harnais de calibration (`tests/validation/`) |
| `climate`, `ventilation`, `rules` | 🚧 stubs (Phase 2) |
| `ingestion`, `geometry` | 🚧 stubs (Phase 3) |
| `llm`, `report` | 🚧 stubs (Phase 4) |

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
