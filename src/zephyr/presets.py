"""Presets par type de projet (occupation, thermique, ventilation).

Le moteur physique est le même pour tous les bâtiments ; ce qui change, ce sont
les **profils** (CLAUDE.md — explications « bureaux »). Ce module fournit des
presets prêts à l'emploi, **tous surchargeables** (rien en dur dans le moteur).

- **Logement** : occupation surtout matin/soir et nuit, apports modérés.
- **Bureau** : occupation diurne (gens + ordis + éclairage), **vide la nuit et le
  week-end** → fort potentiel de free-cooling nocturne, là où la VNC brille.

⚠️ La pénalité de chauffage reste **directionnelle** tant qu'elle n'est pas calée
finement contre un besoin de chauffage STD (cf. docs/COMMENT_CA_MARCHE.md).
"""

from __future__ import annotations

from zephyr.schemas import ProjectType
from zephyr.thermal import R5C1Params
from zephyr.ventilation import VentilationParams

# --- Profils d'apports internes horaires (W/m²) ---------------------------- #
# Logement : creux la journée (occupants absents), pics matin/soir, nuit douce.
_RESIDENTIAL_WEEKDAY = [
    3,
    3,
    3,
    3,
    3,
    3,
    5,
    7,
    5,
    3,
    3,
    3,
    4,
    4,
    3,
    3,
    4,
    6,
    9,
    9,
    7,
    5,
    4,
    3,
]
_RESIDENTIAL_WEEKEND = [
    3,
    3,
    3,
    3,
    3,
    3,
    4,
    5,
    6,
    6,
    6,
    6,
    7,
    6,
    5,
    5,
    5,
    6,
    8,
    9,
    7,
    5,
    4,
    3,
]
# Bureau : quasi nul la nuit, plateau d'occupation 8h–18h (gens+équipements+éclairage).
_OFFICE_WEEKDAY = [
    1,
    1,
    1,
    1,
    1,
    1,
    2,
    6,
    14,
    18,
    18,
    18,
    14,
    16,
    18,
    18,
    16,
    10,
    4,
    2,
    2,
    1,
    1,
    1,
]
_OFFICE_WEEKEND = [1] * 24


def residential_thermal_params(**overrides: object) -> R5C1Params:
    """Preset thermique logement (apports matin/soir, consigne 20 °C)."""
    base = {
        "gains_profile_24h_w_m2": [float(x) for x in _RESIDENTIAL_WEEKDAY],
        "gains_weekend_24h_w_m2": [float(x) for x in _RESIDENTIAL_WEEKEND],
        "heating_setpoint_c": 20.0,
        "comfort_temp_c": 26.0,
        "hygienic_ach": 0.5,
    }
    base.update(overrides)
    return R5C1Params(**base)  # type: ignore[arg-type]


def office_thermal_params(**overrides: object) -> R5C1Params:
    """Preset thermique bureau (apports diurnes élevés, vide nuit/week-end)."""
    base = {
        "gains_profile_24h_w_m2": [float(x) for x in _OFFICE_WEEKDAY],
        "gains_weekend_24h_w_m2": [float(x) for x in _OFFICE_WEEKEND],
        "heating_setpoint_c": 21.0,
        "comfort_temp_c": 26.0,
        "hygienic_ach": 1.0,  # besoin d'air plus élevé quand occupé
        "night_cooling_ach": 5.0,  # sur-ventilation nocturne (free-cooling)
    }
    base.update(overrides)
    return R5C1Params(**base)  # type: ignore[arg-type]


def thermal_params_for(project_type: ProjectType, **overrides: object) -> R5C1Params:
    """Preset thermique selon le type de projet (mixte → moyenne logement/bureau)."""
    if project_type is ProjectType.BUREAU:
        return office_thermal_params(**overrides)
    if project_type is ProjectType.LOGEMENT:
        return residential_thermal_params(**overrides)
    # Mixte / scolaire / autre : profil intermédiaire (moyenne logement+bureau).
    mixed = [(r + o) / 2 for r, o in zip(_RESIDENTIAL_WEEKDAY, _OFFICE_WEEKDAY, strict=True)]
    base = {
        "gains_profile_24h_w_m2": mixed,
        "heating_setpoint_c": 20.0,
        "hygienic_ach": 0.7,
    }
    base.update(overrides)
    return R5C1Params(**base)  # type: ignore[arg-type]


def ventilation_params_for(project_type: ProjectType) -> VentilationParams:
    """Preset ventilation : cible de free-cooling plus haute en bureau."""
    if project_type is ProjectType.BUREAU:
        return VentilationParams(target_freecool_ach=5.0, hygienic_ach=1.0)
    return VentilationParams()
