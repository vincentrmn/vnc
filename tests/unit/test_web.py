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
    render_tracing,
    render_validation,
)


def _floors() -> list[dict[str, object]]:
    return [
        {"level": 0, "image_uri": "data:image/png;base64,ABC", "w": 800, "h": 600, "mpp": 0.0353}
    ]


def test_landing_has_value_prop_and_cta() -> None:
    h = render_landing()
    assert "Zéphyr" in h
    assert "/etude" in h  # CTA vers le formulaire
    assert "opposable" in h  # disclaimer


def test_landing_leads_with_concept_not_jargon() -> None:
    """La home vend le concept (confort/sobriété/pérennité), pas le jargon « VNC »."""
    h = render_landing()
    assert "se régule seul" in h  # hero orienté concept
    for pillar in ("Confort", "Sobriété", "Pérennité"):
        assert pillar in h
    assert "peu ou pas de chauffage" in h  # promesse chauffage nuancée
    assert 'class="video-ph"' in h  # emplacement vidéo réservé sous le hero
    assert "Comment ça marche ?" in h  # avec le point d'interrogation


def test_design_system_charte() -> None:
    """DA KORR : Helvetica Neue, vert #3a5b42, tokens, bascule clair/sombre."""
    from zephyr.web import render_styleguide

    h = render_landing()
    assert "Helvetica Neue" in h  # police KORR
    assert "#3a5b42" in h  # vert KORR (token primary)
    assert "data-theme" in h and "toggleTheme" in h and 'id="themebtn"' in h  # dark mode
    assert "--primary:" in h and "--bg:" in h  # design tokens présents
    sg = render_styleguide()
    assert "Charte Zéphyr" in sg and "Helvetica Neue" in sg


def test_study_form_has_inputs() -> None:
    h = render_study_form()
    # Champs CPE + infos non lisibles des plans (nature, n50, occupation).
    for field in ("project_type", "nature", "u_wall", "glazing", "sash", "n50", "pollution"):
        assert f'name="{field}"' in h
    assert 'action="/etude"' in h
    assert 'action="/etude/cpe"' in h and 'name="cpe"' in h  # import CPE


def test_study_form_blocks_and_new_fields() -> None:
    """Page config friendly : blocs en cartes + champs projet (chauffage/ECS/châssis)."""
    h = render_study_form()
    assert 'id="mainform"' in h  # formulaire unique, champs rattachés via form=
    for field in ("chauffage", "ecs", "chassis_material"):
        assert f'name="{field}"' in h
    assert ">Plan</h2>" in h and ">Projet</h2>" in h  # blocs en cartes (icônes Lucide)
    assert "Passeport énergétique" in h  # carte enveloppe renommée + simplifiée
    assert 'class="ic"' in h  # icônes vectorielles inline (plus d'emoji)


def test_study_form_cpe_or_manual_toggle() -> None:
    """Choix exclusif CPE / saisie manuelle (segmented toggle) + flag extraction."""
    h = render_study_form()
    assert 'name="cpe_mode"' in h and 'class="seg"' in h
    assert 'id="cpe-upload"' in h and 'id="envelope-block"' in h
    assert "__CPE_EXTRACTED__=false" in h  # pas d'extraction encore
    # Après extraction (prefill + flag) : flag vrai → les valeurs extraites s'affichent.
    h2 = render_study_form({"u_wall": "0.122"}, cpe_extracted=True)
    assert "__CPE_EXTRACTED__=true" in h2 and 'value="0.122"' in h2


def test_study_form_requires_cpe_action() -> None:
    """Le passeport doit être renseigné (upload OU saisie) avant de continuer."""
    h = render_study_form()
    # Drapeau « touché » + message d'erreur de blocage, et l'extraction réussie compte.
    assert "__CPE_TOUCHED__" in h
    assert "Renseignez le passeport énergétique" in h
    assert "if(window.__CPE_EXTRACTED__){ window.__CPE_TOUCHED__=true; }" in h


def test_study_form_prefills_envelope() -> None:
    h = render_study_form({"u_wall": "0.18", "n50": "0.6", "inertia": "lourde", "glazing": "0.12"})
    assert 'name="u_wall" value="0.18"' in h
    assert 'name="n50" value="0.6"' in h
    assert 'name="glazing" value="0.12"' in h


def test_cpe_banner_shows_values_and_provenance() -> None:
    from zephyr.schemas import CpeExtraction, InertiaClass
    from zephyr.web import render_cpe_banner

    ext = CpeExtraction(
        u_wall_w_m2k=0.18, air_permeability_ach50=0.6, inertia_class=InertiaClass.LOURDE,
        sources={"u_wall_w_m2k": "valeur U 0,18 W/(m²K)"},
        notes=["u_roof_w_m2k=0.99 écarté : valeur non retrouvée verbatim dans le CPE."],
    )
    h = render_cpe_banner(ext)
    assert "CPE extrait" in h and "0.18" in h
    assert "valeur U 0,18" in h  # provenance affichée
    assert "écarté" in h  # note de garde-fou

    msg = render_cpe_banner(None, message="Texte du CPE lu, extraction indisponible.")
    assert "indisponible" in msg


def test_results_have_scale_and_detailed_financials() -> None:
    env = EnvelopeData(u_wall_w_m2k=0.18, u_window_w_m2k=0.9, glazing_to_floor_ratio=0.18)
    res = compute_study(parametric_building(800.0), synthetic_climate(), envelope=env)
    h = render_results(res)
    assert "Comment le score est-il calculé" in h  # barème/échelle
    # Détail financier façon Excel : CAPEX/OPEX postes + sensibilité.
    assert "Centrales + récupérateurs" in h and "Plateforme BOS" in h
    # Pénalité de chauffage désactivée par défaut → pas de poste dans l'OPEX VNC.
    assert "Pénalité de chauffage" not in h
    # ROI à livre ouvert : chaque poste est dépliable (formule sous la ligne) + graphe Chart.js.
    assert 'class="costrow"' in h and 'id="vanchart"' in h
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


def test_tracing_editor_renders() -> None:
    h = render_tracing(_floors(), "")
    assert "Tracer le plan" in h
    assert "data:image/png;base64,ABC" in h  # plan en fond
    assert "window.TRACE" in h and "finishRoom" in h
    assert 'id="stage"' in h and "konva" in h.lower()  # éditeur Konva (lib spécialisée)
    assert 'action="/etude/resultat"' in h and 'name="building_json"' in h


def test_tracing_editor_has_zoom_pan() -> None:
    """§10.1 — zoom/pan : boutons + handlers molette/glisser dans le JS."""
    h = render_tracing(_floors(), "")
    for ctrl in ('id="t-zin"', 'id="t-zout"', 'id="t-zreset"'):
        assert ctrl in h
    assert "onWheel" in h and "zoomBy" in h  # molette + boutons zoom
    assert "draggable" in h  # pan via Konva stage draggable
    assert "touch-action" in h  # pas de scroll page au glisser tactile
    assert 'id="t-mark"' in h and "markF()" in h  # taille réglable des repères


def test_tracing_editor_can_draw_windows() -> None:
    """§10.2 — tracer un châssis au glisser sur la façade."""
    h = render_tracing(_floors(), "")
    assert 'id="t-win"' in h  # bouton « Tracer un châssis »
    assert "addWindow" in h and "nearestOri" in h  # longueur→largeur + façade auto
    assert '"window"' in h  # mode de tracé de châssis


def test_tracing_editor_advanced_tools() -> None:
    """Konva : rectangle, magnétisme, déplacement de pièce, pinch tactile."""
    h = render_tracing(_floors(), "")
    assert 'id="t-rect"' in h and "finishRect" in h  # tracé rectangle
    assert 'id="t-snap"' in h and "snapPx" in h  # magnétisme
    assert "onTouchMove" in h  # pinch-to-zoom tactile
    assert "draggable" in h and "dragend" in h  # déplacer une pièce / coins


def test_tracing_editor_window_height_and_table() -> None:
    """Châssis : popup hauteur au relâcher + largeur/hauteur éditables dans le tableau."""
    h = render_tracing(_floors(), "")
    assert "showHeightPopup" in h  # bulle pour saisir la hauteur
    assert 'data-wf="w"' in h and 'data-wf="h"' in h  # largeur/hauteur éditables
    assert 'data-wf="facade"' in h  # façade corrigeable à la main par châssis
    assert "setWinWidth" in h and "winRecalc" in h


def test_tracing_editor_has_compass() -> None:
    h = render_tracing(_floors(), "")
    assert "rose des vents" in h  # rose des vents dans le cadre


def test_tracing_editor_multi_floor() -> None:
    """Multi-PDF par étage : plusieurs fonds, bascule par niveau."""
    floors = [
        {"level": 0, "image_uri": "data:,A", "w": 800, "h": 600, "mpp": 0.02},
        {"level": 1, "image_uri": "data:,B", "w": 700, "h": 500, "mpp": 0.03},
    ]
    h = render_tracing(floors, "")
    assert '"floors"' in h and '"level": 1' in h  # niveaux embarqués
    assert 'id="levelsel"' in h and 'id="stage"' in h  # sélecteur de niveaux + canvas Konva
    # Le JS doit lire la bonne clé d'image (régression : f.uri ≠ image_uri).
    assert "f.image_uri" in h and "f.uri" not in h


def test_tracing_editor_has_levels() -> None:
    """§10.5 — multi-niveaux : niveau courant + niveau par pièce (plans/planche)."""
    h = render_tracing(_floors(), "")
    assert 'id="levelsel"' in h  # sélecteur de niveau courant (RDC / R+1…)
    assert "curLevel()" in h  # appliqué au tracé
    assert "data-lvl=" in h  # réaffectation du niveau par pièce
    assert "num_levels" in h  # recalculé pour le bâtiment


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
    assert "à la VNC" in h
    assert "CAPEX VNC" in h and "VAN économie VNC" in h
    # Chaque critère apparaît (label échappé HTML).
    for c in res.score.criteria:
        assert html.escape(c.label) in h
