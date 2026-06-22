"""Tests du moteur `rules` (verdict go/no-go/conditionnel)."""

from __future__ import annotations

from zephyr.climate import synthetic_climate
from zephyr.rules import evaluate_feasibility
from zephyr.schemas import Building, Opening, Orientation, Room, SiteContext, Verdict
from zephyr.ventilation import natural_airflow


def _good_building() -> Building:
    """Maison traversante, bien ouvrante, peu profonde."""
    rooms = [
        Room(
            id="sejour",
            area_m2=25.0,
            height_m=2.6,
            polygon=[(0, 0), (5, 0), (5, 5), (0, 5)],
            exterior_wall_orientations=[Orientation.S, Orientation.N],
            openings=[
                Opening(id="fs", area_m2=5.0, orientation=Orientation.S, head_height_m=2.2),
                Opening(id="fn", area_m2=5.0, orientation=Orientation.N, head_height_m=2.2),
            ],
        )
    ]
    return Building(id="b1", rooms=rooms)


def test_go_when_all_favorable() -> None:
    b = _good_building()
    vent = natural_airflow(b, synthetic_climate())
    res = evaluate_feasibility(b, ventilation=vent, site=SiteContext())
    assert res.verdict is Verdict.GO
    assert not res.disqualifiers


def test_no_go_on_hard_disqualifier() -> None:
    b = _good_building()
    vent = natural_airflow(b, synthetic_climate())
    res = evaluate_feasibility(b, ventilation=vent, site=SiteContext(pollution_high=True))
    assert res.verdict is Verdict.NO_GO
    assert any("ollution" in d for d in res.disqualifiers)


def test_conditionnel_on_soft_finding() -> None:
    b = _good_building()
    vent = natural_airflow(b, synthetic_climate())
    res = evaluate_feasibility(b, ventilation=vent, site=SiteContext(exterior_noise_high=True))
    assert res.verdict is Verdict.CONDITIONNEL
    assert res.conditions


def test_no_go_when_openings_insufficient() -> None:
    """Surface d'ouvrants minuscule → ventilation hygiénique impossible → no-go."""
    room = Room(
        id="sejour",
        area_m2=25.0,
        height_m=2.6,
        exterior_wall_orientations=[Orientation.S],
        openings=[Opening(id="f", area_m2=0.05, orientation=Orientation.S)],
    )
    b = Building(id="b1", rooms=[room])
    vent = natural_airflow(b, synthetic_climate())
    res = evaluate_feasibility(b, ventilation=vent)
    assert res.verdict is Verdict.NO_GO
    assert any("ouvrants" in d.lower() for d in res.disqualifiers)


def test_deep_plan_flagged() -> None:
    """Pièce simple-face très profonde → condition 'plan profond'."""
    room = Room(
        id="couloir",
        area_m2=40.0,
        height_m=2.6,
        polygon=[(0, 0), (16, 0), (16, 2.5), (0, 2.5)],  # profondeur 16 m >> 2.5×2.6
        exterior_wall_orientations=[Orientation.S],
        openings=[Opening(id="f", area_m2=4.0, orientation=Orientation.S)],
    )
    b = Building(id="b1", rooms=[room])
    res = evaluate_feasibility(b)
    assert any("profonde" in c for c in res.conditions)
