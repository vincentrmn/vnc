"""Tests du rendu de plan (viz) — la géométrie reconstruite, à donner à voir."""

from __future__ import annotations

import pytest

from zephyr.schemas import Building, Opening, Orientation, Room, RoomLabel

pytest.importorskip("matplotlib")
from zephyr.viz import render_plan_data_uri, render_plan_png  # noqa: E402


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
