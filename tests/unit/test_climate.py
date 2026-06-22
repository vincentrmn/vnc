"""Tests du module `climate` (EPW, degrés-heures, solaire, climat synthétique)."""

from __future__ import annotations

from pathlib import Path

import pytest

from zephyr.climate import (
    HOURS_PER_YEAR,
    degree_hours,
    read_epw,
    synthetic_climate,
    vertical_irradiance,
)
from zephyr.schemas import Orientation

_EPW_HEADER = [
    "LOCATION,Luxembourg,-,-,TMY,-,49.62,6.20,1.0,376.0",
    "DESIGN CONDITIONS,0",
    "TYPICAL/EXTREME PERIODS,0",
    "GROUND TEMPERATURES,0",
    "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
    "COMMENTS 1,synthetic",
    "COMMENTS 2,synthetic",
    "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
]


def _epw_row(temp: float, ghi: float, dni: float, dhi: float, wind: float) -> str:
    f = ["0"] * 35
    f[0], f[1], f[2], f[3], f[4] = "2020", "1", "1", "1", "0"
    f[6] = str(temp)
    f[13] = str(ghi)
    f[14] = str(dni)
    f[15] = str(dhi)
    f[21] = str(wind)
    return ",".join(f)


def test_read_epw(tmp_path: Path) -> None:
    rows = [_epw_row(5.0, 100.0, 80.0, 20.0, 3.5) for _ in range(24)]
    content = "\n".join(_EPW_HEADER + rows)
    p = tmp_path / "test.epw"
    p.write_text(content, encoding="utf-8")

    c = read_epw(p)
    assert c.n_hours == 24
    assert c.latitude_deg == pytest.approx(49.62)
    assert c.longitude_deg == pytest.approx(6.20)
    assert c.dry_bulb_c[0] == pytest.approx(5.0)
    assert c.dni_w_m2[0] == pytest.approx(80.0)
    assert c.wind_speed_ms[0] == pytest.approx(3.5)


def test_read_epw_rejects_short(tmp_path: Path) -> None:
    p = tmp_path / "bad.epw"
    p.write_text("too short", encoding="utf-8")
    with pytest.raises(ValueError):
        read_epw(p)


def test_degree_hours_modes() -> None:
    temps = [18.0, 20.0, 28.0]
    assert degree_hours(temps, 26.0, mode="above") == pytest.approx(2.0)
    assert degree_hours(temps, 19.0, mode="below") == pytest.approx(1.0)
    with pytest.raises(ValueError):
        degree_hours(temps, 20.0, mode="sideways")


def test_synthetic_climate_shape_and_seasonality() -> None:
    c = synthetic_climate()
    assert c.n_hours == HOURS_PER_YEAR
    # Janvier (hiver) plus froid que juillet (été).
    jan_mean = sum(c.dry_bulb_c[: 31 * 24]) / (31 * 24)
    jul = slice(181 * 24, 212 * 24)
    jul_mean = sum(c.dry_bulb_c[jul]) / (31 * 24)
    assert jul_mean > jan_mean + 5


def test_vertical_irradiance_south_beats_north() -> None:
    """En hémisphère Nord, une façade Sud reçoit plus qu'une façade Nord."""
    c = synthetic_climate()
    south = sum(vertical_irradiance(c, Orientation.S))
    north = sum(vertical_irradiance(c, Orientation.N))
    assert south > north
