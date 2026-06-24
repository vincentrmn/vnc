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

from fastapi import FastAPI, File, Form, Request, UploadFile
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
from zephyr.web import (
    building_from_form,
    render_error,
    render_landing,
    render_results,
    render_study_form,
    render_validation,
)

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
    north: float = Form(0.0),
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
        "north": str(north), "inertia": inertia, "area": str(area), "levels": str(levels),
        "u_wall": str(u_wall), "u_window": str(u_window), "glazing": str(glazing),
        "sash": str(sash), "n50": str(n50),
    }
    flags = {
        "noise": bool(noise), "pollution": bool(pollution),
        "security": bool(security), "occ_incompatible": bool(occ_incompatible),
    }

    raw = await dxf.read() if dxf is not None else b""
    name = (dxf.filename or "").lower() if dxf is not None else ""
    if raw:
        from zephyr.geometry import build_building
        from zephyr.ingestion import parse_dxf, parse_pdf

        is_pdf = name.endswith(".pdf") or raw[:5] == b"%PDF-"
        suffix = ".pdf" if is_pdf else ".dxf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        try:
            rawvec = parse_pdf(tmp_path) if is_pdf else parse_dxf(tmp_path)
            geo = build_building(rawvec, inertia=InertiaClass(inertia), north_angle_deg=north)
        except Exception as exc:  # noqa: BLE001 - surface l'erreur à l'utilisateur
            return render_error(str(exc))
        # Config + drapeaux en champs cachés (la géométrie éditable est rendue à part).
        cfg_with_flags = {**cfg, **{k: ("on" if v else "") for k, v in flags.items()}}
        hidden = _hidden_fields(cfg_with_flags, None)
        return render_validation(geo.building, hidden, geo.warnings)

    # Pas de DXF : pas de géométrie à valider → résultats directs (paramétrique).
    return _compute_page(_parametric(cfg), cfg, flags)


@app.post("/etude/resultat", response_class=HTMLResponse)
async def submit_geometry(request: Request) -> str:
    """Géométrie validée/corrigée (formulaire dynamique) → résultats."""
    form = await request.form()
    d = {k: str(v) for k, v in form.items()}
    cfg = {
        k: d.get(k, default)
        for k, default in {
            "nature": "neuf", "project_type": "mixte", "location": "Luxembourg",
            "inertia": "lourde", "area": "1200", "levels": "2",
            "u_wall": "0.20", "u_window": "0.9", "glazing": "0.18",
            "sash": "1.6", "n50": "1.5",
        }.items()
    }
    flags = {k: bool(d.get(k)) for k in ("noise", "pollution", "security", "occ_incompatible")}
    if d.get("building_json"):
        building = Building.model_validate_json(d["building_json"])  # éditeur visuel
    elif d.get("n_rooms"):
        building = building_from_form(d)  # repli formulaire indexé
    else:
        building = _parametric(cfg)
    return _compute_page(building, cfg, flags)
