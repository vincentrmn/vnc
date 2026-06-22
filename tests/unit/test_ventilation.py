"""Tests du module `ventilation` (tirage + vent) — sanité physique."""

from __future__ import annotations

from zephyr.climate import synthetic_climate
from zephyr.schemas import Building, Opening, Orientation, Room
from zephyr.ventilation import VentilationParams, natural_airflow

CLIMATE = synthetic_climate()


def _building(window_area: float = 4.0, head: float = 2.2) -> Building:
    room = Room(
        id="sejour",
        area_m2=28.0,
        height_m=2.6,
        exterior_wall_orientations=[Orientation.S, Orientation.N],
        openings=[
            Opening(id="fs", area_m2=window_area, orientation=Orientation.S, head_height_m=head),
            Opening(id="fn", area_m2=window_area, orientation=Orientation.N, head_height_m=head),
        ],
    )
    return Building(id="b1", rooms=[room])


def test_more_openings_more_flow() -> None:
    """Plus de surface ouvrable → plus de débit."""
    small = natural_airflow(_building(window_area=1.0), CLIMATE)
    big = natural_airflow(_building(window_area=6.0), CLIMATE)
    assert big.combined_flow_m3h > small.combined_flow_m3h
    assert big.achievable_ach > small.achievable_ach


def test_stack_increases_with_delta_t() -> None:
    """Le tirage augmente avec l'écart de température."""
    cold = natural_airflow(_building(), CLIMATE, VentilationParams(design_delta_t_k=1.0))
    warm = natural_airflow(_building(), CLIMATE, VentilationParams(design_delta_t_k=8.0))
    assert warm.stack_flow_m3h > cold.stack_flow_m3h


def test_wind_increases_flow() -> None:
    calm = natural_airflow(_building(), CLIMATE, VentilationParams(design_wind_ms=0.5))
    windy = natural_airflow(_building(), CLIMATE, VentilationParams(design_wind_ms=8.0))
    assert windy.wind_flow_m3h > calm.wind_flow_m3h


def test_meets_flags() -> None:
    """Une grande surface ouvrable atteint l'hygiénique et le free-cooling."""
    r = natural_airflow(_building(window_area=6.0), CLIMATE)
    assert r.meets_hygienic
    # Et une surface minuscule ne suffit pas à l'hygiénique.
    tiny = natural_airflow(_building(window_area=0.01), CLIMATE)
    assert not tiny.meets_hygienic
