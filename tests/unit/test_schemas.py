"""Tests du contrat schemas (pydantic v2)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from zephyr.schemas import (
    Building,
    InertiaClass,
    Opening,
    Orientation,
    Room,
    RoomLabel,
)


def _opening(**kw: Any) -> Opening:
    base: dict[str, Any] = {"id": "o1", "area_m2": 2.0, "orientation": Orientation.S}
    base.update(kw)
    return Opening(**base)


def test_opening_free_area() -> None:
    o = _opening(area_m2=4.0, free_area_ratio=0.5)
    assert o.free_area_m2 == 2.0


def test_opening_rejects_bad_ratio() -> None:
    with pytest.raises(ValidationError):
        _opening(free_area_ratio=1.5)


def test_room_volume_and_through() -> None:
    r = Room(
        id="r1",
        area_m2=20.0,
        height_m=2.5,
        exterior_wall_orientations=[Orientation.S, Orientation.N],
    )
    assert r.volume_m3 == pytest.approx(50.0)
    assert r.is_through is True


def test_room_single_face_not_through() -> None:
    r = Room(id="r1", area_m2=10.0, height_m=2.6, exterior_wall_orientations=[Orientation.S])
    assert r.is_through is False


def test_building_aggregates() -> None:
    rooms = [
        Room(
            id="sejour",
            label=RoomLabel.SEJOUR,
            area_m2=28.0,
            height_m=2.6,
            openings=[_opening(area_m2=4.0, free_area_ratio=0.5)],
        ),
        Room(id="chambre", label=RoomLabel.CHAMBRE, area_m2=14.0, height_m=2.6),
    ]
    b = Building(id="b1", rooms=rooms, inertia_class=InertiaClass.LOURDE)
    assert b.total_floor_area_m2 == pytest.approx(42.0)
    assert b.total_volume_m3 == pytest.approx(42.0 * 2.6)
    assert b.total_openable_area_m2 == pytest.approx(2.0)


def test_building_default_inertia_is_heavy() -> None:
    """Hypothèse par défaut = inertie lourde (CLAUDE.md §2.7)."""
    b = Building(id="b1")
    assert b.inertia_class is InertiaClass.LOURDE


def test_building_num_levels_corrected_from_rooms() -> None:
    rooms = [
        Room(id="r0", area_m2=10, height_m=2.6, level=0),
        Room(id="r1", area_m2=10, height_m=2.6, level=2),
    ]
    b = Building(id="b1", rooms=rooms, num_levels=1)
    assert b.num_levels == 3
