"""Test du pipeline complet `compute_study` (score + pénalité + ROI)."""

from __future__ import annotations

from zephyr.climate import synthetic_climate
from zephyr.schemas import (
    Building,
    EnvelopeData,
    Opening,
    Orientation,
    Room,
    SiteContext,
    Verdict,
)
from zephyr.study import compute_study

_ENV = EnvelopeData(u_wall_w_m2k=0.18, u_window_w_m2k=0.9, glazing_to_floor_ratio=0.18)


def _building() -> Building:
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
    return Building(id="b1", rooms=rooms)


def test_compute_study_full_pipeline() -> None:
    res = compute_study(_building(), synthetic_climate(), envelope=_ENV)
    assert res.verdict in {Verdict.GO, Verdict.CONDITIONNEL, Verdict.NO_GO}
    assert res.score is not None and res.score.criteria
    assert res.heating_penalty is not None and res.heating_penalty.eur_per_year > 0
    assert res.roi is not None and res.roi.sensitivity
    # La pénalité de chauffage alimente bien l'OPEX VNC du ROI.
    assert res.roi.opex_vnc_breakdown["penalite_chauffage"] > 0


def test_penalty_degrades_vnc_economics() -> None:
    res = compute_study(_building(), synthetic_climate(), envelope=_ENV)
    from zephyr.thermal import PenaltyParams

    res0 = compute_study(
        _building(), synthetic_climate(), envelope=_ENV,
        penalty_params=PenaltyParams(recovery_efficiency=0.0),
    )
    assert res.roi is not None and res0.roi is not None
    assert res.roi.npv_delta_eur < res0.roi.npv_delta_eur


def test_compute_study_no_go_propagates() -> None:
    res = compute_study(
        _building(), synthetic_climate(), envelope=_ENV, site=SiteContext(pollution_high=True)
    )
    assert res.verdict is Verdict.NO_GO
    # Même en no-go, le ROI reste calculé (info de décision).
    assert res.roi is not None
