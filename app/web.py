"""Serveur web Zéphyr (FastAPI) — landing + flow d'étude + résultats.

Pages rendues par `zephyr.web` (fonctions pures). Ici : routage, lecture du
formulaire, dépôt DXF optionnel, et appel du pipeline déterministe `compute_study`.

Lancer :  ``uv run --extra full uvicorn app.web:app --reload``
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.presets import penalty_params_for
from zephyr.roi import ROIParameters
from zephyr.schemas import (
    Building,
    EnvelopeData,
    InertiaClass,
    Orientation,
    ProjectType,
    SiteContext,
)
from zephyr.study import compute_study
from zephyr.web import render_landing, render_results, render_study_form

app = FastAPI(title="Zéphyr — pré-étude VNC")


@app.get("/", response_class=HTMLResponse)
def landing() -> str:
    return render_landing()


@app.get("/etude", response_class=HTMLResponse)
def study_form() -> str:
    return render_study_form()


def _building_from_dxf(data: bytes, inertia: InertiaClass) -> Building:
    from zephyr.geometry import build_building
    from zephyr.ingestion import parse_dxf

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    return build_building(parse_dxf(tmp_path), inertia=inertia).building


@app.post("/etude", response_class=HTMLResponse)
async def run_study(
    dxf: UploadFile | None = File(default=None),  # noqa: B008 - FastAPI dependency
    project_type: str = Form("mixte"),
    area: float = Form(1200.0),
    levels: int = Form(2),
    inertia: str = Form("lourde"),
    u_wall: float = Form(0.20),
    u_window: float = Form(0.9),
    glazing: float = Form(0.18),
    sash: float = Form(1.6),
    noise: str | None = Form(None),
    pollution: str | None = Form(None),
    security: str | None = Form(None),
) -> str:
    inertia_cls = InertiaClass(inertia)
    ptype = ProjectType(project_type)

    building: Building
    raw = await dxf.read() if dxf is not None else b""
    if raw:
        building = _building_from_dxf(raw, inertia_cls)
        area = building.total_floor_area_m2 or area
    else:
        building = parametric_building(
            area, num_levels=int(levels), inertia=inertia_cls, main_orientation=Orientation.S
        )

    envelope = EnvelopeData(
        u_wall_w_m2k=u_wall,
        u_window_w_m2k=u_window,
        glazing_to_floor_ratio=glazing,
        sash_height_m=sash,
    )
    site = SiteContext(
        exterior_noise_high=bool(noise),
        pollution_high=bool(pollution),
        ground_floor_security_risk=bool(security),
    )
    roi_params = ROIParameters(
        num_logements=0, surface_per_logement_m2=0.0, surface_tertiaire_m2=max(area, 1.0)
    )
    result = compute_study(
        building,
        synthetic_climate(),
        roi_params=roi_params,
        envelope=envelope,
        site=site,
        project_type=ptype,
        penalty_params=penalty_params_for(ptype),
    )
    return render_results(result, building=building)
