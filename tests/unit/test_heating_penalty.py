"""Tests de la pénalité de chauffage VNC (déterministe, degrés-jours)."""

from __future__ import annotations

import pytest

from zephyr.climate import synthetic_climate
from zephyr.schemas import Building, Opening, Orientation, Room
from zephyr.thermal import PenaltyParams, heating_penalty

CLIMATE = synthetic_climate()


def _building() -> Building:
    rooms = [
        Room(
            id="sejour",
            area_m2=28.0,
            height_m=2.6,
            exterior_wall_orientations=[Orientation.S, Orientation.N],
            openings=[Opening(id="fs", area_m2=4.2, orientation=Orientation.S)],
        ),
        Room(id="chambre", area_m2=14.0, height_m=2.6),
    ]
    return Building(id="b1", rooms=rooms)


def test_penalty_positive_and_has_dju() -> None:
    p = heating_penalty(_building(), CLIMATE)
    assert p.kwh_per_year > 0
    assert p.eur_per_year > 0
    assert p.heating_degree_days > 0  # climat de chauffe


def test_penalty_grows_with_recovery_efficiency() -> None:
    low = heating_penalty(_building(), CLIMATE, PenaltyParams(recovery_efficiency=0.5))
    high = heating_penalty(_building(), CLIMATE, PenaltyParams(recovery_efficiency=0.9))
    assert high.kwh_per_year > low.kwh_per_year


def test_zero_recovery_gives_zero_penalty() -> None:
    p = heating_penalty(_building(), CLIMATE, PenaltyParams(recovery_efficiency=0.0))
    assert p.kwh_per_year == pytest.approx(0.0, abs=1e-6)


def test_demand_factor_scales_penalty() -> None:
    full = heating_penalty(_building(), CLIMATE, PenaltyParams(demand_factor=1.0))
    half = heating_penalty(_building(), CLIMATE, PenaltyParams(demand_factor=0.5))
    assert half.kwh_per_year == pytest.approx(0.5 * full.kwh_per_year, rel=1e-6)


def test_penalty_intensity_plausible() -> None:
    p = heating_penalty(_building(), CLIMATE)
    area = _building().total_floor_area_m2
    assert 0 < p.kwh_per_year / area < 60  # kWh/m²/an, garde-fou
    assert "degrés-jours" in p.assumptions["methode"]
