"""Tests des pages web (rendu pur, sans serveur)."""

from __future__ import annotations

import html

import pytest

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.schemas import Building, EnvelopeData
from zephyr.study import compute_study
from zephyr.web import (
    building_from_form,
    render_landing,
    render_results,
    render_study_form,
    render_validation,
)


def test_landing_has_value_prop_and_cta() -> None:
    h = render_landing()
    assert "Zéphyr" in h
    assert "/etude" in h  # CTA vers le formulaire
    assert "opposable" in h  # disclaimer


def test_study_form_has_inputs() -> None:
    h = render_study_form()
    # Champs CPE + infos non lisibles des plans (nature, n50, occupation).
    for field in ("project_type", "nature", "u_wall", "glazing", "sash", "n50", "pollution"):
        assert f'name="{field}"' in h
    assert 'action="/etude"' in h


def test_results_have_scale_and_detailed_financials() -> None:
    env = EnvelopeData(u_wall_w_m2k=0.18, u_window_w_m2k=0.9, glazing_to_floor_ratio=0.18)
    res = compute_study(parametric_building(800.0), synthetic_climate(), envelope=env)
    h = render_results(res)
    assert "Comment le score est calculé" in h  # barème/échelle
    # Détail financier façon Excel : CAPEX/OPEX postes + sensibilité.
    assert "Centrales + récupérateurs" in h and "Plateforme BOS" in h
    assert "Pénalité de chauffage" in h
    assert "tornado" in h.lower()
    assert "TCO non actualisé" in h


def _poly_building() -> Building:
    from zephyr.schemas import Building, Opening, Orientation, Room, RoomLabel

    rooms = [
        Room(
            id="r0", label=RoomLabel.SEJOUR, area_m2=25.0, height_m=2.6,
            polygon=[(0, 0), (5, 0), (5, 5), (0, 5)],
            exterior_wall_orientations=[Orientation.S, Orientation.W],
            openings=[Opening(id="w", area_m2=4.0, orientation=Orientation.S, head_height_m=2.3)],
        ),
        Room(
            id="r1", label=RoomLabel.CHAMBRE, area_m2=16.0, height_m=2.6,
            polygon=[(5, 0), (9, 0), (9, 4), (5, 4)],
            exterior_wall_orientations=[Orientation.E],
        ),
    ]
    return Building(id="x", rooms=rooms)


def _label_only_building() -> Building:
    from zephyr.schemas import Building, Room, RoomLabel

    return Building(
        id="x",
        rooms=[Room(id="l0", label=RoomLabel.SEJOUR, area_m2=20.0, height_m=2.6)],
    )


def test_validation_visual_editor_when_polygons() -> None:
    h = render_validation(_poly_building(), '<input type="hidden" name="x" value="1">', ["warn!"])
    assert "Validation de la géométrie" in h and "warn!" in h
    assert 'action="/etude/resultat"' in h
    # Éditeur interactif : SVG + données + script.
    assert 'id="plan"' in h and 'name="building_json"' in h
    assert "window.BUILDING" in h and "syncHidden" in h
    assert '"sejour"' in h  # données embarquées


def test_validation_fallback_form_when_no_polygons() -> None:
    h = render_validation(_label_only_building(), "", [])
    assert 'name="n_rooms"' in h
    assert 'name="r0_label"' in h and 'name="r0_orient"' in h


def test_building_from_form_roundtrip() -> None:
    form = {
        "n_rooms": "1",
        "inertia": "lourde",
        "r0_id": "room_0",
        "r0_area": "30",
        "r0_height": "2.6",
        "r0_level": "0",
        "r0_label": "sejour",
        "r0_orient": "S, W",
        "r0_polygon": "[[0,0],[6,0],[6,5],[0,5]]",
        "r0_nslots": "2",
        "r0_o0_facade": "S",
        "r0_o0_area": "4",
        "r0_o0_sash": "1.6",
        "r0_o0_openable": "on",
        "r0_o1_facade": "",  # slot vide → ignoré
    }
    b = building_from_form(form)
    assert b.inertia_class.value == "lourde"
    assert len(b.rooms) == 1
    r = b.rooms[0]
    assert r.label.value == "sejour"
    assert {o.value for o in r.exterior_wall_orientations} == {"S", "W"}
    assert r.is_through  # 2 façades → traversant
    assert len(r.openings) == 1
    op = r.openings[0]
    assert op.orientation.value == "S" and op.area_m2 == 4.0 and op.openable
    assert op.head_height_m == pytest.approx(0.9 + 1.6)  # sill + hauteur châssis


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
