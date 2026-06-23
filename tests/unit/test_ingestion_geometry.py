"""Tests ingestion DXF → géométrie (Phase 3).

On fabrique un petit DXF (deux pièces + labels + une fenêtre), on le parse et on
vérifie la reconstruction : surfaces, labels, orientations estimées, ouvrant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ezdxf = pytest.importorskip("ezdxf")
pytest.importorskip("shapely")

from zephyr.geometry import build_building  # noqa: E402
from zephyr.ingestion import parse_dxf  # noqa: E402
from zephyr.schemas import RoomLabel  # noqa: E402


def _make_dxf(path: Path) -> None:
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6  # mètres
    msp = doc.modelspace()
    for name in ("PIECES", "TEXTE", "FENETRE"):
        doc.layers.add(name)
    # Pièce 1 : séjour 5×4 = 20 m² (sud-ouest)
    msp.add_lwpolyline([(0, 0), (5, 0), (5, 4), (0, 4)], close=True, dxfattribs={"layer": "PIECES"})
    msp.add_text("Sejour", dxfattribs={"layer": "TEXTE"}).set_placement((2.5, 2.0))
    # Pièce 2 : chambre 4×4 = 16 m² (nord-est)
    msp.add_lwpolyline(
        [(6, 5), (10, 5), (10, 9), (6, 9)], close=True, dxfattribs={"layer": "PIECES"}
    )
    msp.add_text("Chambre 1", dxfattribs={"layer": "TEXTE"}).set_placement((8.0, 7.0))
    # Fenêtre (segment) sur la façade sud du séjour
    msp.add_line((1, 0), (3, 0), dxfattribs={"layer": "FENETRE"})
    doc.saveas(str(path))


def test_parse_and_build(tmp_path: Path) -> None:
    dxf = tmp_path / "plan.dxf"
    _make_dxf(dxf)

    raw = parse_dxf(dxf)
    assert raw.unit_scale_m == 1.0
    assert len([p for p in raw.polylines if p.closed]) == 2
    assert any("FENETRE" in layer for layer in raw.layers)

    res = build_building(raw)
    b = res.building
    assert len(b.rooms) == 2

    areas = sorted(round(r.area_m2) for r in b.rooms)
    assert areas == [16, 20]

    labels = {r.label for r in b.rooms}
    assert RoomLabel.SEJOUR in labels
    assert RoomLabel.CHAMBRE in labels

    # Orientations estimées présentes (à valider par l'humain).
    assert all(r.exterior_wall_orientations for r in b.rooms)

    # L'ouvrant a été rattaché au séjour (façade sud).
    sejour = next(r for r in b.rooms if r.label is RoomLabel.SEJOUR)
    assert sejour.openings
    assert sejour.openings[0].area_m2 > 0

    # Avertissements de validation humaine présents.
    assert any("VALIDER" in w for w in res.warnings)


def test_shared_wall_is_interior_and_windows_face_outward(tmp_path: Path) -> None:
    """Mur mitoyen non compté ; ouvrants orientés par leur façade réelle."""
    from zephyr.schemas import Orientation

    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for name in ("PIECES", "TEXTE", "FENETRE"):
        doc.layers.add(name)
    # Deux pièces accolées, mur commun en x=5.
    msp.add_lwpolyline([(0, 0), (5, 0), (5, 4), (0, 4)], close=True, dxfattribs={"layer": "PIECES"})
    msp.add_text("Sejour", dxfattribs={"layer": "TEXTE"}).set_placement((2.5, 2.0))
    msp.add_lwpolyline(
        [(5, 0), (10, 0), (10, 4), (5, 4)], close=True, dxfattribs={"layer": "PIECES"}
    )
    msp.add_text("Chambre", dxfattribs={"layer": "TEXTE"}).set_placement((7.5, 2.0))
    msp.add_line((1, 0), (3, 0), dxfattribs={"layer": "FENETRE"})  # séjour, façade sud
    msp.add_line((10, 1), (10, 3), dxfattribs={"layer": "FENETRE"})  # chambre, façade est
    p = tmp_path / "adj.dxf"
    doc.saveas(str(p))

    b = build_building(parse_dxf(p)).building
    sejour = next(r for r in b.rooms if r.label is RoomLabel.SEJOUR)
    chambre = next(r for r in b.rooms if r.label is RoomLabel.CHAMBRE)

    # Le mur commun (x=5) est mitoyen : pas d'Est pour le séjour, pas d'Ouest pour la chambre.
    assert Orientation.E not in sejour.exterior_wall_orientations
    assert Orientation.W not in chambre.exterior_wall_orientations
    # Ouvrants orientés par la façade qui les porte.
    assert sejour.openings[0].orientation is Orientation.S
    assert chambre.openings[0].orientation is Orientation.E


def test_north_angle_rotates_orientations(tmp_path: Path) -> None:
    """L'angle du Nord fait pivoter les orientations déduites."""
    from zephyr.schemas import Orientation

    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    doc.layers.add("FENETRE")
    msp.add_lwpolyline([(0, 0), (4, 0), (4, 4), (0, 4)], close=True)
    msp.add_line((1, 0), (3, 0), dxfattribs={"layer": "FENETRE"})  # mur −y du plan
    p = tmp_path / "rot.dxf"
    doc.saveas(str(p))
    raw = parse_dxf(p)

    south = build_building(raw).building.rooms[0].openings[0].orientation
    rotated = build_building(raw, north_angle_deg=90.0).building.rooms[0].openings[0].orientation
    assert south is Orientation.S
    assert rotated is Orientation.W  # +90° sur le Nord → la façade sud devient ouest


def test_window_block_detected(tmp_path: Path) -> None:
    """Une fenêtre dessinée en bloc (INSERT) est reconnue comme ouvrant."""
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6
    blk = doc.blocks.new(name="FENETRE_F1")
    blk.add_line((0, 0), (1, 0))
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (4, 0), (4, 4), (0, 4)], close=True, dxfattribs={"layer": "PIECES"})
    msp.add_blockref("FENETRE_F1", (2, 0))  # sur la façade sud
    p = tmp_path / "blk.dxf"
    doc.saveas(str(p))

    raw = parse_dxf(p)
    assert raw.blocks  # le bloc est lu
    b = build_building(raw).building
    assert b.rooms[0].openings  # converti en ouvrant


def test_unit_scale_mm(tmp_path: Path) -> None:
    """Un plan en mm est ramené en mètres."""
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4  # mm
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (5000, 0), (5000, 4000), (0, 4000)], close=True)  # 5 m × 4 m en mm
    p = tmp_path / "mm.dxf"
    doc.saveas(str(p))

    raw = parse_dxf(p)
    assert raw.unit_scale_m == 0.001
    res = build_building(raw)
    assert round(res.building.rooms[0].area_m2) == 20
