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
    assert "à la VNC" in r.text and "Bilan financier" in r.text


def test_quick_mode_flow_to_results() -> None:
    """Mode rapide : formulaire (sans plan) → résultats indicatifs (tendance + bilan allégé)."""
    r = client.post(
        "/etude",
        data={"etude_mode": "rapide", "project_type": "logement", "area": "800", "levels": "2",
              "q_through": "60", "q_depth": "compact", "glazing": "0.12", "sash": "1.8",
              "inertia": "lourde", "chauffage": "pac"},
    )
    assert r.status_code == 200
    assert "Estimation rapide" in r.text and "Tendance :" in r.text
    assert "Bilan financier — estimation" in r.text  # bilan allégé
    assert 'id="valform"' not in r.text  # pas d'hypothèses éditables en rapide


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
    assert "à la VNC" in r2.text
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
    assert "Tracer le plan" in r.text and "window.TRACE" in r.text
    assert "data:image/png;base64," in r.text  # DXF rendu en image de fond


def test_cpe_upload_reads_text_then_back_to_form(monkeypatch: object) -> None:
    """CPE vectoriel uploadé → texte lu ; sans clé API → message + formulaire."""
    pytest.importorskip("fitz")
    import tempfile

    import fitz

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # type: ignore[attr-defined]
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((40, 60), "Coefficient U mur 0,18 W/(m2.K) n50 0,60")
    p = Path(tempfile.mktemp(suffix=".pdf"))
    doc.save(str(p))
    with p.open("rb") as fh:
        r = client.post("/etude/cpe", files={"cpe": ("cpe.pdf", fh, "application/pdf")})
    assert r.status_code == 200
    assert "indisponible" in r.text  # pas de clé → message honnête
    assert 'name="u_wall"' in r.text  # le formulaire est re-rendu


def test_multi_pdf_per_floor_tracing() -> None:
    """§10.5 — un PDF par étage → éditeur de tracé multi-niveaux (bascule de fond)."""
    pytest.importorskip("fitz")
    import io

    import fitz

    def vec_pdf() -> bytes:
        doc = fitz.open()
        page = doc.new_page(width=600, height=400)
        page.draw_line((10, 10), (300, 10))
        return bytes(doc.tobytes())

    files = [
        ("floor_pdfs", ("rdc.pdf", io.BytesIO(vec_pdf()), "application/pdf")),
        ("floor_pdfs", ("etage.pdf", io.BytesIO(vec_pdf()), "application/pdf")),
    ]
    r = client.post("/etude", files=files, data={"project_type": "logement"})
    assert r.status_code == 200
    assert "window.TRACE" in r.text and '"floors"' in r.text
    assert 'id="levelsel"' in r.text and r.text.count('"level":') >= 2


def test_resume_study_from_file() -> None:
    """Sauvegarde/reprise sans BDD : un .json d'étude rouvre la géométrie."""
    import io
    import json as _json

    from zephyr.schemas import Building, Orientation, Room, RoomLabel

    b = Building(
        id="x",
        rooms=[Room(id="r0", label=RoomLabel.SEJOUR, area_m2=25.0, height_m=2.6,
                    polygon=[(0, 0), (5, 0), (5, 5), (0, 5)],
                    exterior_wall_orientations=[Orientation.S, Orientation.W])],
    )
    study = {"zephyr_study": 1, "config": {"project_type": "logement", "inertia": "lourde"},
             "building_json": b.model_dump_json()}
    blob = io.BytesIO(_json.dumps(study).encode())
    r = client.post("/etude/reprendre", files={"study": ("etude.json", blob, "application/json")})
    assert r.status_code == 200
    assert "Validation de la géométrie" in r.text and "reprise depuis un fichier" in r.text


def test_config_has_resume_and_editor_has_download() -> None:
    from zephyr.web import render_tracing

    assert "Reprendre une étude" in client.get("/etude").text
    floors = [{"level": 0, "image_uri": "data:image/png;base64,A", "w": 800, "h": 600, "mpp": 0.03}]
    assert "downloadStudy()" in render_tracing(floors, "")


def test_cpe_upload_rejects_scan() -> None:
    pytest.importorskip("fitz")
    import tempfile

    import fitz

    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60))
    pix.clear_with(220)
    page.insert_image(fitz.Rect(0, 0, 60, 60), pixmap=pix)
    p = Path(tempfile.mktemp(suffix=".pdf"))
    doc.save(str(p))
    with p.open("rb") as fh:
        r = client.post("/etude/cpe", files={"cpe": ("scan.pdf", fh, "application/pdf")})
    assert r.status_code == 200
    assert "scanné" in r.text  # refusé (zéro vision)
