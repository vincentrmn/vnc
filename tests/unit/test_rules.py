"""Tests du moteur de score d'aptitude VNC (déterministe)."""

from __future__ import annotations

from zephyr.rules import evaluate_vnc, score_building
from zephyr.schemas import (
    Building,
    EnvelopeData,
    InertiaClass,
    Opening,
    Orientation,
    Room,
    SiteContext,
    Verdict,
)


def _good_building() -> Building:
    """Maison traversante, châssis hauts, peu profonde, inertie lourde."""
    rooms = [
        Room(
            id="sejour",
            area_m2=25.0,
            height_m=2.6,
            polygon=[(0, 0), (5, 0), (5, 5), (0, 5)],
            exterior_wall_orientations=[Orientation.S, Orientation.N],
            openings=[
                Opening(id="fs", area_m2=2.0, orientation=Orientation.S, head_height_m=2.3),
                Opening(id="fn", area_m2=2.0, orientation=Orientation.N, head_height_m=2.3),
            ],
        )
    ]
    return Building(id="b1", rooms=rooms, inertia_class=InertiaClass.LOURDE)


# Vitrage bas (≤ 1/8) = bon (moins de surchauffe/déperditions) sous la nouvelle échelle.
_ENV = EnvelopeData(u_wall_w_m2k=0.18, u_window_w_m2k=0.9, glazing_to_floor_ratio=0.10)


def test_good_building_scores_high_and_go() -> None:
    res = evaluate_vnc(_good_building(), _ENV, SiteContext())
    assert res.verdict is Verdict.GO
    assert res.score is not None and res.score.global_score >= 70
    assert res.score.grade in {"A", "B"}
    assert not res.disqualifiers


def test_pollution_is_hard_flag_no_go() -> None:
    res = evaluate_vnc(_good_building(), _ENV, SiteContext(pollution_high=True))
    assert res.verdict is Verdict.NO_GO
    assert any("ollution" in d for d in res.disqualifiers)


def test_noise_is_soft_flag_conditionnel() -> None:
    res = evaluate_vnc(_good_building(), _ENV, SiteContext(exterior_noise_high=True))
    assert res.verdict is Verdict.CONDITIONNEL
    assert res.score is not None and res.score.flags


def test_traversant_beats_single_sided_low_sash() -> None:
    through = _good_building()
    single = Building(
        id="b2",
        rooms=[
            Room(
                id="sejour",
                area_m2=25.0,
                height_m=2.6,
                exterior_wall_orientations=[Orientation.S],
                openings=[Opening(id="f", area_m2=2.0, orientation=Orientation.S)],  # head None
            )
        ],
    )
    vent_through = next(c for c in score_building(through, _ENV).criteria if c.key == "ventilation")
    vent_single = next(c for c in score_building(single, _ENV).criteria if c.key == "ventilation")
    assert vent_through.score > vent_single.score


def test_excess_glazing_triggers_recommendation() -> None:
    # Sans châssis tracé : repli sur le ratio CPE/saisie (ici 45 % → surchauffe).
    no_glass = Building(
        id="ng",
        rooms=[Room(id="r", area_m2=25.0, height_m=2.6,
                    exterior_wall_orientations=[Orientation.S])],
    )
    env = EnvelopeData(u_wall_w_m2k=0.18, glazing_to_floor_ratio=0.45)
    score = score_building(no_glass, env)
    vit = next(c for c in score.criteria if c.key == "vitrage")
    assert vit.score < 100
    assert vit.recommendation is not None and "surchauffe" in vit.recommendation.lower()


def test_glazing_measured_from_traced_windows() -> None:
    """Le taux vient des châssis tracés (mesuré), pas du CPE, dès qu'il y a des ouvrants."""
    b = Building(
        id="g",
        rooms=[Room(id="r", area_m2=20.0, height_m=2.6,
                    exterior_wall_orientations=[Orientation.S],
                    openings=[Opening(id="w", area_m2=5.0, orientation=Orientation.S)])],
    )
    # CPE annonce 8 % mais 5 m² / 20 m² = 25 % réels → c'est le mesuré qui prime.
    env = EnvelopeData(u_wall_w_m2k=0.18, glazing_to_floor_ratio=0.08)
    vit = next(c for c in score_building(b, env).criteria if c.key == "vitrage")
    assert "châssis tracés" in vit.detail
    assert vit.score < 100  # 25 % → mauvais, alors que le CPE 8 % aurait donné 100


def test_light_inertia_triggers_recommendation() -> None:
    b = Building(id="b3", rooms=_good_building().rooms, inertia_class=InertiaClass.LEGERE)
    score = score_building(b, _ENV)
    inertie = next(c for c in score.criteria if c.key == "inertie")
    assert inertie.score < 60
    assert inertie.recommendation is not None


def test_deep_plan_lowers_ventilation_score() -> None:
    deep = Building(
        id="b4",
        rooms=[
            Room(
                id="couloir",
                area_m2=40.0,
                height_m=2.6,
                polygon=[(0, 0), (16, 0), (16, 2.5), (0, 2.5)],
                exterior_wall_orientations=[Orientation.S],
                openings=[Opening(id="f", area_m2=4.0, orientation=Orientation.S)],
            )
        ],
    )
    vent = next(c for c in score_building(deep, _ENV).criteria if c.key == "ventilation")
    assert vent.score < 50  # plan très profond → balayage médiocre
