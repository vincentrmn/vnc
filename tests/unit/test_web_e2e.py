"""Test end-to-end de la plateforme web (vrai serveur ASGI via TestClient).

Couvre le flow réel : landing → config → (DXF) validation → résultats, et le
chemin paramétrique. Nécessite les extras `app` (fastapi, python-multipart) et
`cao` (ezdxf/shapely) ; sinon le test est ignoré.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")  # python-multipart : lecture des formulaires
pytest.importorskip("shapely")

from app.web import app  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

_DXF = Path(__file__).resolve().parents[2] / "examples" / "plan_exemple.dxf"
client = TestClient(app)


def test_landing_and_form() -> None:
    assert client.get("/").status_code == 200
    r = client.get("/etude")
    assert r.status_code == 200 and 'action="/etude"' in r.text


def test_parametric_flow_to_results() -> None:
    r = client.post("/etude", data={"area": "800", "project_type": "bureau", "glazing": "0.2"})
    assert r.status_code == 200
    assert "Aptitude à la VNC" in r.text and "Bilan financier" in r.text


def test_dxf_flow_validation_then_results() -> None:
    assert _DXF.exists(), "lancer scripts/make_sample_dxf.py"
    with _DXF.open("rb") as fh:
        r = client.post(
            "/etude",
            data={"project_type": "logement", "inertia": "lourde", "glazing": "0.16"},
            files={"dxf": ("plan_exemple.dxf", fh, "application/dxf")},
        )
    assert r.status_code == 200
    assert "Validation de la géométrie" in r.text
    assert 'id="plan"' in r.text and "window.BUILDING" in r.text  # éditeur visuel

    # Soumet la géométrie validée/corrigée (building_json de l'éditeur) → résultats.
    from zephyr.schemas import Building, Opening, Orientation, Room, RoomLabel

    b = Building(
        id="dxf",
        rooms=[
            Room(
                id="room_0", label=RoomLabel.SEJOUR, area_m2=30.0, height_m=2.6,
                polygon=[(0, 0), (6, 0), (6, 5), (0, 5)],
                exterior_wall_orientations=[Orientation.S, Orientation.W],
                openings=[
                    Opening(id="w", area_m2=4.0, orientation=Orientation.S, head_height_m=2.5)
                ],
            )
        ],
    )
    r2 = client.post(
        "/etude/resultat",
        data={"project_type": "logement", "inertia": "lourde",
              "building_json": b.model_dump_json()},
    )
    assert r2.status_code == 200
    assert "Aptitude à la VNC" in r2.text
    assert "Détail par critère" in r2.text


def test_dxf_without_polygons_routes_to_tracing() -> None:
    """§10.3 — DXF sans polygones de pièces propres → éditeur de tracé universel."""
    pytest.importorskip("matplotlib")
    import tempfile
    from typing import Any, cast

    import ezdxf

    doc = cast(Any, ezdxf).new()
    msp = doc.modelspace()
    # Que des LINE (murs en traits) + clutter : pas de polyligne fermée → 0 pièce.
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)),
                 ((0, 4), (0, 0)), ((1, 1), (2, 2))]:
        msp.add_line(a, b)
    path = Path(tempfile.mktemp(suffix=".dxf"))
    doc.saveas(path)

    with path.open("rb") as fh:
        r = client.post(
            "/etude",
            data={"project_type": "logement", "inertia": "lourde"},
            files={"dxf": ("messy.dxf", fh, "application/dxf")},
        )
    assert r.status_code == 200
    assert "Tracer les pièces" in r.text and "window.TRACE" in r.text
    assert "data:image/png;base64," in r.text  # DXF rendu en image de fond
