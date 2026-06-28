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
    # La pénalité reste calculée pour information…
    assert res.heating_penalty is not None and res.heating_penalty.eur_per_year > 0
    assert res.roi is not None and res.roi.sensitivity
    # …mais n'alimente pas le ROI par défaut (simplification produit).
    assert "penalite_chauffage" not in res.roi.opex_vnc_breakdown
    # …et n'apparaît donc pas comme driver de sensibilité.
    assert all("heating_penalty" not in e.parameter for e in res.roi.sensitivity)


def test_penalty_can_be_reenabled_and_degrades_vnc_economics() -> None:
    """Le câblage thermal → ROI reste correct quand on active le drapeau."""
    from zephyr.thermal import PenaltyParams

    res = compute_study(
        _building(), synthetic_climate(), envelope=_ENV, include_heating_penalty=True
    )
    res0 = compute_study(
        _building(), synthetic_climate(), envelope=_ENV, include_heating_penalty=True,
        penalty_params=PenaltyParams(recovery_efficiency=0.0),
    )
    assert res.roi is not None and res0.roi is not None
    assert res.roi.opex_vnc_breakdown["penalite_chauffage"] > 0
    assert res.roi.npv_delta_eur < res0.roi.npv_delta_eur


def test_compute_study_no_go_propagates() -> None:
    res = compute_study(
        _building(), synthetic_climate(), envelope=_ENV, site=SiteContext(pollution_high=True)
    )
    assert res.verdict is Verdict.NO_GO
    # Même en no-go, le ROI reste calculé (info de décision).
    assert res.roi is not None


def test_quick_mode_marks_mode_and_widens_range() -> None:
    """Mode rapide : marque le résultat et élargit la fourchette ROI (entrées peu fiables)."""
    full = compute_study(_building(), synthetic_climate(), envelope=_ENV)
    quick = compute_study(_building(), synthetic_climate(), envelope=_ENV, quick=True)
    assert quick.mode == "rapide" and full.mode == "complete"
    assert quick.roi is not None and full.roi is not None
    assert quick.roi.npv_delta_range is not None and full.roi.npv_delta_range is not None
    span_q = quick.roi.npv_delta_range.high - quick.roi.npv_delta_range.low
    span_f = full.roi.npv_delta_range.high - full.roi.npv_delta_range.low
    assert span_q > span_f  # incertitude plus large en rapide
