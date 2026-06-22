"""Tests du builder paramétrique et du rapport HTML (Phase 4)."""

from __future__ import annotations

from pathlib import Path

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.report import render_report, render_report_html
from zephyr.schemas import InertiaClass, Verdict
from zephyr.study import compute_study


def test_parametric_building_area_conserved() -> None:
    b = parametric_building(1000.0, num_levels=3, room_size_m2=25.0)
    assert b.total_floor_area_m2 == 1000.0
    assert b.num_levels == 3
    assert len(b.rooms) == 40
    assert all(r.openings for r in b.rooms)


def test_parametric_building_through_has_two_orientations() -> None:
    b = parametric_building(200.0, through=True)
    assert all(len(set(r.exterior_wall_orientations)) == 2 for r in b.rooms)
    b2 = parametric_building(200.0, through=False)
    assert all(len(r.exterior_wall_orientations) == 1 for r in b2.rooms)


def test_report_html_contains_verdict_and_disclaimer() -> None:
    b = parametric_building(300.0, inertia=InertiaClass.LOURDE)
    res = compute_study(b, synthetic_climate())
    html_text = render_report_html(res)
    assert "VERDICT" in html_text
    assert res.verdict.value.upper() in {Verdict.GO.value.upper(), "GO", "CONDITIONNEL", "NO-GO"}
    assert "opposable" in html_text  # disclaimer présent
    assert "ROI" in html_text and "thermique" in html_text.lower()


def test_render_report_writes_file(tmp_path: Path) -> None:
    b = parametric_building(300.0)
    res = compute_study(b, synthetic_climate())
    # Demande un PDF : sans WeasyPrint, repli HTML attendu.
    out = render_report(res, tmp_path / "rapport.pdf")
    assert out.exists()
    assert out.suffix in {".pdf", ".html"}
    assert out.stat().st_size > 0
