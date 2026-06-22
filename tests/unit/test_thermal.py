"""Tests du module `thermal` (5R1C) — sanité physique + invariants clés.

Sans cas IDA ICE réel, on ne valide pas les valeurs absolues : on vérifie le
*comportement* (signe, monotonies, ordres de grandeur) — c'est ce qui rend la
pénalité de chauffage directionnellement fiable (CLAUDE.md §2.4).
"""

from __future__ import annotations

import pytest

from zephyr.climate import synthetic_climate
from zephyr.schemas import Building, InertiaClass, Opening, Orientation, Room
from zephyr.thermal import R5C1Params, simulate_5r1c

CLIMATE = synthetic_climate()


def _building(inertia: InertiaClass = InertiaClass.LOURDE) -> Building:
    rooms = [
        Room(
            id="sejour",
            area_m2=28.0,
            height_m=2.6,
            exterior_wall_orientations=[Orientation.S, Orientation.N],
            openings=[
                Opening(id="fs", area_m2=4.2, orientation=Orientation.S),
                Opening(id="fn", area_m2=1.8, orientation=Orientation.N),
            ],
        ),
        Room(
            id="chambre",
            area_m2=14.0,
            height_m=2.6,
            exterior_wall_orientations=[Orientation.E],
            openings=[Opening(id="fe", area_m2=1.8, orientation=Orientation.E)],
        ),
    ]
    return Building(id="b1", rooms=rooms, inertia_class=inertia)


def test_heating_penalty_is_positive() -> None:
    """La VNC (sans récup) chauffe plus que la VMC DF (récup) → pénalité > 0."""
    r = simulate_5r1c(_building(), CLIMATE)
    assert r.heating_penalty_kwh_per_year > 0
    assert r.heating_penalty_eur_per_year > 0


def test_penalty_grows_with_recovery_efficiency() -> None:
    """Plus l'échangeur VMC est performant, plus la pénalité VNC est grande."""
    low = simulate_5r1c(_building(), CLIMATE, R5C1Params(recovery_efficiency=0.5))
    high = simulate_5r1c(_building(), CLIMATE, R5C1Params(recovery_efficiency=0.9))
    assert high.heating_penalty_kwh_per_year > low.heating_penalty_kwh_per_year


def test_zero_recovery_gives_zero_penalty() -> None:
    """Sans récupération côté VMC, les deux scénarios sont identiques."""
    r = simulate_5r1c(_building(), CLIMATE, R5C1Params(recovery_efficiency=0.0))
    assert r.heating_penalty_kwh_per_year == pytest.approx(0.0, abs=1.0)


def test_equivalent_recovery_pct_not_fabricated() -> None:
    """Métrique 'récup équivalente' non posée tant que non validée (§7)."""
    r = simulate_5r1c(_building(), CLIMATE)
    assert r.equivalent_recovery_pct is None


def test_heavy_inertia_reduces_overheating() -> None:
    """L'inertie lourde amortit la surchauffe vs inertie légère (§2.7)."""
    light = simulate_5r1c(_building(InertiaClass.LEGERE), CLIMATE)
    heavy = simulate_5r1c(_building(InertiaClass.LOURDE), CLIMATE)
    assert heavy.overheating_hours <= light.overheating_hours


def test_occupancy_profile_reduces_heating() -> None:
    """Un profil d'apports internes réduit le besoin de chauffage (apports gratuits)."""

    def heat(params: R5C1Params) -> float:
        r = simulate_5r1c(_building(), CLIMATE, params)
        return sum(z.heating_vnc_kwh or 0.0 for z in r.zones)

    none = heat(R5C1Params(internal_gains_w_m2=0.0))
    profile = [3.0] * 8 + [10.0] * 8 + [5.0] * 8  # occupation type logement
    loaded = heat(R5C1Params(gains_profile_24h_w_m2=profile))
    assert loaded < none  # les apports compensent une partie du chauffage


def test_bad_gains_profile_rejected() -> None:
    """Un profil d'apports mal dimensionné (≠ 24 valeurs) est refusé."""
    with pytest.raises(ValueError):
        simulate_5r1c(_building(), CLIMATE, R5C1Params(gains_profile_24h_w_m2=[4.0] * 10))


def test_outputs_plausible_ranges() -> None:
    r = simulate_5r1c(_building(), CLIMATE)
    assert 0 <= r.overheating_hours <= 8760
    assert r.degree_hours_overheating >= 0
    assert r.night_cooling_benefit_kwh >= 0
    # Pénalité par m² : ordre de grandeur raisonnable (qq kWh/m²/an).
    area = _building().total_floor_area_m2
    assert 0 < r.heating_penalty_kwh_per_year / area < 60
    assert "5R1C" in r.assumptions["modele"]
