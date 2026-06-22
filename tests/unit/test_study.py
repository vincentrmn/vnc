"""Test du pipeline complet `compute_study` (thermal + ventilation + rules + roi)."""

from __future__ import annotations

from zephyr.climate import synthetic_climate
from zephyr.schemas import Building, Opening, Orientation, Room, SiteContext, Verdict
from zephyr.study import compute_study


def _building() -> Building:
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


def test_compute_study_full_pipeline() -> None:
    res = compute_study(_building(), synthetic_climate())
    # Verdict rendu, thermique et ROI attachés.
    assert res.verdict in {Verdict.GO, Verdict.CONDITIONNEL, Verdict.NO_GO}
    assert res.thermal is not None
    assert res.roi is not None
    assert res.roi.sensitivity  # tornado présent
    # La pénalité du ROI provient bien du thermique (non nulle).
    assert res.roi.opex_vnc_breakdown["penalite_chauffage"] > 0


def test_compute_study_no_go_propagates() -> None:
    res = compute_study(_building(), synthetic_climate(), site=SiteContext(pollution_high=True))
    assert res.verdict is Verdict.NO_GO
    # Même en no-go, le ROI reste calculé (info de décision).
    assert res.roi is not None
