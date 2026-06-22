"""Tests des presets par type de projet (logement vs bureau)."""

from __future__ import annotations

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.presets import (
    office_thermal_params,
    residential_thermal_params,
    thermal_params_for,
    ventilation_params_for,
)
from zephyr.schemas import ProjectType
from zephyr.thermal import simulate_5r1c

CLIMATE = synthetic_climate()


def test_profiles_have_24_values() -> None:
    for p in (residential_thermal_params(), office_thermal_params()):
        assert p.gains_profile_24h_w_m2 is not None
        assert len(p.gains_profile_24h_w_m2) == 24


def test_office_has_higher_daytime_gains_than_residential() -> None:
    res = residential_thermal_params().gains_profile_24h_w_m2
    off = office_thermal_params().gains_profile_24h_w_m2
    assert res and off
    # Milieu de journée (14 h) : le bureau chauffe plus que le logement.
    assert off[14] > res[14]
    # La nuit (3 h) : le bureau est quasi vide.
    assert off[3] < res[3]


def test_thermal_params_dispatch() -> None:
    assert thermal_params_for(ProjectType.BUREAU).heating_setpoint_c == 21.0
    assert thermal_params_for(ProjectType.LOGEMENT).heating_setpoint_c == 20.0
    # Mixte : profil défini, intermédiaire.
    mixed = thermal_params_for(ProjectType.MIXTE)
    assert mixed.gains_profile_24h_w_m2 is not None


def test_office_overrides_apply() -> None:
    p = office_thermal_params(heating_setpoint_c=19.0)
    assert p.heating_setpoint_c == 19.0


def test_office_more_overheating_than_residential() -> None:
    """Plus d'apports diurnes en bureau → plus de surchauffe (toutes choses égales)."""
    b = parametric_building(200.0, window_to_floor_ratio=0.25)
    res = simulate_5r1c(b, CLIMATE, residential_thermal_params())
    off = simulate_5r1c(b, CLIMATE, office_thermal_params())
    assert off.degree_hours_overheating >= res.degree_hours_overheating


def test_ventilation_preset_office() -> None:
    assert ventilation_params_for(ProjectType.BUREAU).target_freecool_ach == 5.0
    assert ventilation_params_for(ProjectType.LOGEMENT).target_freecool_ach == 4.0
