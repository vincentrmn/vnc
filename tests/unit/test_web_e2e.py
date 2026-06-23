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
    assert "sejour" in r.text and "Confirmer" in r.text
    assert 'name="n_rooms"' in r.text  # formulaire éditable

    # Soumet une géométrie validée/corrigée (formulaire édité) → résultats.
    data = {
        "n_rooms": "1",
        "project_type": "logement",
        "inertia": "lourde",
        "r0_id": "room_0",
        "r0_area": "30",
        "r0_height": "2.6",
        "r0_level": "0",
        "r0_label": "sejour",
        "r0_orient": "S, W",
        "r0_polygon": "[[0,0],[6,0],[6,5],[0,5]]",
        "r0_nslots": "1",
        "r0_o0_facade": "S",
        "r0_o0_area": "4",
        "r0_o0_sash": "1.6",
        "r0_o0_openable": "on",
    }
    r2 = client.post("/etude/resultat", data=data)
    assert r2.status_code == 200
    assert "Aptitude à la VNC" in r2.text
    assert "Détail par critère" in r2.text
