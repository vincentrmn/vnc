"""Tests du rendu de plan (viz) — la géométrie reconstruite, à donner à voir."""

from __future__ import annotations

import pytest

from zephyr.schemas import Building, Opening, Orientation, Room, RoomLabel

pytest.importorskip("matplotlib")
from zephyr.viz import (  # noqa: E402
    render_plan_data_uri,
    render_plan_png,
    render_segments_background,
)


def _building() -> Building:
    rooms = [
        Room(
            id="sejour",
            label=RoomLabel.SEJOUR,
            area_m2=30.0,
            height_m=2.6,
            polygon=[(0, 0), (6, 0), (6, 5), (0, 5)],
            exterior_wall_orientations=[Orientation.S, Orientation.E],
            openings=[Opening(id="fs", area_m2=4.0, orientation=Orientation.S)],
        ),
        Room(
            id="chambre",
            label=RoomLabel.CHAMBRE,
            area_m2=16.0,
            height_m=2.6,
            polygon=[(0, 5), (4, 5), (4, 9), (0, 9)],
            exterior_wall_orientations=[Orientation.N],
            openings=[Opening(id="fn", area_m2=2.0, orientation=Orientation.N)],
        ),
    ]
    return Building(id="x", rooms=rooms)


def test_render_plan_png_is_png() -> None:
    png = render_plan_png(_building())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # signature PNG
    assert len(png) > 1000


def test_render_plan_data_uri() -> None:
    uri = render_plan_data_uri(_building())
    assert uri.startswith("data:image/png;base64,")


def test_render_segments_background_scale_and_size() -> None:
    """§10.3 — fond de tracé DXF : PNG + échelle exacte (m/px) issue des mètres."""
    # Bbox 10 m × 5 m.
    segs = [((0.0, 0.0), (10.0, 0.0)), ((10.0, 0.0), (10.0, 5.0)),
            ((10.0, 5.0), (0.0, 5.0)), ((0.0, 5.0), (0.0, 0.0))]
    png, w_px, h_px, m_per_px = render_segments_background(segs, max_px=1000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # Plus grande dimension (10 m) → ~1000 px ; ratio respecté (2:1).
    assert w_px == pytest.approx(1000, abs=2)
    assert h_px == pytest.approx(500, abs=2)
    # Échelle exacte : 10 m sur ~1000 px → ~0.01 m/px.
    assert m_per_px == pytest.approx(0.01, rel=0.01)


def test_render_segments_background_empty_raises() -> None:
    with pytest.raises(ValueError, match="Aucun segment"):
        render_segments_background([])
