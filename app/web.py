"""Serveur web Zéphyr (FastAPI) — flow config → validation géométrie → résultats.

Pages rendues par `zephyr.web` (fonctions pures). Flow :
  1. GET ``/etude`` : configuration & dépôt DXF (infos non lisibles des plans).
  2. POST ``/etude`` : si DXF → reconstruit la géométrie et affiche la page de
     **validation** (§2.8) ; sinon (paramétrique) → résultats directement.
  3. POST ``/etude/resultat`` : géométrie confirmée → `compute_study` → résultats.

La config et la géométrie validée transitent en champs cachés (sans état serveur).

Lancer :  ``uv run --extra full uvicorn app.web:app --reload``
"""

from __future__ import annotations

import html
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
from zephyr.web import render_landing, render_results, render_study_form, render_validation

app = FastAPI(title="Zéphyr — pré-étude VNC")


@app.get("/", response_class=HTMLResponse)
def landing() -> str:
    return render_landing()


@app.get("/etude", response_class=HTMLResponse)
def study_form() -> str:
    return render_study_form()


# Champs de configuration transmis de page en page (non géométriques).
_CONFIG_FIELDS = (
    "nature", "project_type", "location", "inertia", "area", "levels",
    "u_wall", "u_window", "glazing", "sash", "n50",
)
_CONFIG_FLAGS = ("noise", "pollution", "security", "occ_incompatible")


def _hidden_fields(cfg: dict[str, str], building_json: str | None) -> str:
    parts = [
        f'<input type="hidden" name="{k}" value="{html.escape(v)}">' for k, v in cfg.items()
    ]
    if building_json is not None:
        parts.append(
            '<input type="hidden" name="building_json" value="'
            f'{html.escape(building_json)}">'
        )
    return "".join(parts)


def _envelope(cfg: dict[str, str]) -> EnvelopeData:
    return EnvelopeData(
        u_wall_w_m2k=float(cfg["u_wall"]),
        u_window_w_m2k=float(cfg["u_window"]),
        glazing_to_floor_ratio=float(cfg["glazing"]),
        sash_height_m=float(cfg["sash"]),
        air_permeability_ach50=float(cfg["n50"]),
    )


def _site(flags: dict[str, bool]) -> SiteContext:
    return SiteContext(
        exterior_noise_high=flags["noise"],
        pollution_high=flags["pollution"],
        ground_floor_security_risk=flags["security"],
        occupancy_compatible=not flags["occ_incompatible"],
    )


def _compute_page(building: Building, cfg: dict[str, str], flags: dict[str, bool]) -> str:
    ptype = ProjectType(cfg["project_type"])
    area = building.total_floor_area_m2 or float(cfg["area"])
    roi_params = ROIParameters(
        num_logements=0, surface_per_logement_m2=0.0, surface_tertiaire_m2=max(area, 1.0)
    )
    result = compute_study(
        building,
        synthetic_climate(),
        roi_params=roi_params,
        envelope=_envelope(cfg),
        site=_site(flags),
        project_type=ptype,
        penalty_params=penalty_params_for(ptype),
    )
    return render_results(result, building=building)


def _parametric(cfg: dict[str, str]) -> Building:
    return parametric_building(
        float(cfg["area"]),
        num_levels=int(float(cfg["levels"])),
        inertia=InertiaClass(cfg["inertia"]),
        main_orientation=Orientation.S,
    )


@app.post("/etude", response_class=HTMLResponse)
async def submit_config(
    dxf: UploadFile | None = File(default=None),  # noqa: B008
    nature: str = Form("neuf"),
    project_type: str = Form("mixte"),
    location: str = Form("Luxembourg"),
    inertia: str = Form("lourde"),
    area: float = Form(1200.0),
    levels: int = Form(2),
    u_wall: float = Form(0.20),
    u_window: float = Form(0.9),
    glazing: float = Form(0.18),
    sash: float = Form(1.6),
    n50: float = Form(1.5),
    noise: str | None = Form(None),
    pollution: str | None = Form(None),
    security: str | None = Form(None),
    occ_incompatible: str | None = Form(None),
) -> str:
    cfg = {
        "nature": nature, "project_type": project_type, "location": location,
        "inertia": inertia, "area": str(area), "levels": str(levels),
        "u_wall": str(u_wall), "u_window": str(u_window), "glazing": str(glazing),
        "sash": str(sash), "n50": str(n50),
    }
    flags = {
        "noise": bool(noise), "pollution": bool(pollution),
        "security": bool(security), "occ_incompatible": bool(occ_incompatible),
    }

    raw = await dxf.read() if dxf is not None else b""
    if raw:
        from zephyr.geometry import build_building
        from zephyr.ingestion import parse_dxf

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        geo = build_building(parse_dxf(tmp_path), inertia=InertiaClass(inertia))
        # Conserve les drapeaux dans la config cachée (re-cochés à l'étape résultats).
        cfg_with_flags = {**cfg, **{k: ("on" if v else "") for k, v in flags.items()}}
        hidden = _hidden_fields(cfg_with_flags, geo.building.model_dump_json())
        return render_validation(geo.building, hidden, geo.warnings)

    # Pas de DXF : pas de géométrie à valider → résultats directs (paramétrique).
    return _compute_page(_parametric(cfg), cfg, flags)


@app.post("/etude/resultat", response_class=HTMLResponse)
async def submit_geometry(
    building_json: str | None = Form(None),
    nature: str = Form("neuf"),
    project_type: str = Form("mixte"),
    location: str = Form("Luxembourg"),
    inertia: str = Form("lourde"),
    area: float = Form(1200.0),
    levels: int = Form(2),
    u_wall: float = Form(0.20),
    u_window: float = Form(0.9),
    glazing: float = Form(0.18),
    sash: float = Form(1.6),
    n50: float = Form(1.5),
    noise: str | None = Form(None),
    pollution: str | None = Form(None),
    security: str | None = Form(None),
    occ_incompatible: str | None = Form(None),
) -> str:
    cfg = {
        "nature": nature, "project_type": project_type, "location": location,
        "inertia": inertia, "area": str(area), "levels": str(levels),
        "u_wall": str(u_wall), "u_window": str(u_window), "glazing": str(glazing),
        "sash": str(sash), "n50": str(n50),
    }
    flags = {
        "noise": bool(noise), "pollution": bool(pollution),
        "security": bool(security), "occ_incompatible": bool(occ_incompatible),
    }
    building = (
        Building.model_validate_json(building_json) if building_json else _parametric(cfg)
    )
    return _compute_page(building, cfg, flags)
