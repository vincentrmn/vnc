"""Tests des pages web (rendu pur, sans serveur)."""

from __future__ import annotations

import html

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.schemas import EnvelopeData
from zephyr.study import compute_study
from zephyr.web import render_landing, render_results, render_study_form


def test_landing_has_value_prop_and_cta() -> None:
    h = render_landing()
    assert "Zéphyr" in h
    assert "/etude" in h  # CTA vers le formulaire
    assert "opposable" in h  # disclaimer


def test_study_form_has_inputs() -> None:
    h = render_study_form()
    for field in ("project_type", "u_wall", "glazing", "sash", "pollution"):
        assert f'name="{field}"' in h
    assert 'action="/etude"' in h


def test_results_render_contains_score_and_kpis() -> None:
    env = EnvelopeData(u_wall_w_m2k=0.18, u_window_w_m2k=0.9, glazing_to_floor_ratio=0.18)
    res = compute_study(parametric_building(300.0), synthetic_climate(), envelope=env)
    h = render_results(res)
    assert res.score is not None
    assert "Aptitude à la VNC" in h
    assert "CAPEX VNC" in h and "VAN économie VNC" in h
    # Chaque critère apparaît (label échappé HTML).
    for c in res.score.criteria:
        assert html.escape(c.label) in h
