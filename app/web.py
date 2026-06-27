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

from fastapi import FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.presets import penalty_params_for
from zephyr.report import render_report
from zephyr.roi import ROIParameters
from zephyr.schemas import (
    Building,
    EnvelopeData,
    InertiaClass,
    Orientation,
    ProjectType,
    SiteContext,
    StudyResult,
)
from zephyr.study import compute_study
from zephyr.web import (
    building_from_form,
    render_cpe_banner,
    render_error,
    render_landing,
    render_results,
    render_study_form,
    render_styleguide,
    render_tracing,
    render_validation,
)

app = FastAPI(title="Zéphyr — pré-étude VNC")


@app.get("/", response_class=HTMLResponse)
def landing() -> str:
    return render_landing()


@app.get("/etude", response_class=HTMLResponse)
def study_form() -> str:
    return render_study_form()


@app.get("/styleguide", response_class=HTMLResponse)
def styleguide() -> str:
    return render_styleguide()


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


def _apply_roi_overrides(roi_params: ROIParameters, cfg: dict[str, str]) -> ROIParameters:
    """Applique les hypothèses ajustées par l'utilisateur (champs ``ovr_*``) au ROI.

    Source unique des champs : ``zephyr.web.ROI_OVERRIDE_FIELDS`` (formulaire ↔ calcul).
    """
    from zephyr.web import ROI_OVERRIDE_FIELDS

    upd: dict[str, object] = {}
    for _group, attr, _label, _step, is_int in ROI_OVERRIDE_FIELDS:
        v = cfg.get("ovr_" + attr, "")
        if v in ("", None):
            continue
        try:
            upd[attr] = int(float(v)) if is_int else float(v)
        except (TypeError, ValueError):
            pass
    return roi_params.model_copy(update=upd) if upd else roi_params


def _study_for_report(
    building: Building, cfg: dict[str, str], flags: dict[str, bool], *, from_geometry: bool = False
) -> StudyResult:
    from zephyr.presets import cost_preset_for, heating_price_for

    ptype = ProjectType(cfg["project_type"])
    area = building.total_floor_area_m2 or float(cfg["area"])
    # P1 — forfaits CAPEX recalés par taille (corrige le défaut "petit projet").
    preset = cost_preset_for(ptype, area)
    roi_params = ROIParameters(
        num_logements=0, surface_per_logement_m2=0.0, surface_tertiaire_m2=max(area, 1.0),
        **preset,
    )
    roi_params = _apply_roi_overrides(roi_params, cfg)
    # Si l'utilisateur force un nombre d'ouvrants, il prime sur le comptage géométrique.
    if cfg.get("ovr_num_ouvrants_override", ""):
        from_geometry = False
    # P4 — prix de l'énergie de chauffage selon le vecteur capté (PAC/gaz/élec…).
    penalty = penalty_params_for(
        ptype, heating_energy_price_eur_kwh=heating_price_for(cfg.get("chauffage", "pac"))
    )
    return compute_study(
        building,
        synthetic_climate(),
        roi_params=roi_params,
        envelope=_envelope(cfg),
        site=_site(flags),
        project_type=ptype,
        penalty_params=penalty,
        size_from_geometry=from_geometry,
    )


def _compute_page(
    building: Building, cfg: dict[str, str], flags: dict[str, bool], *, from_geometry: bool = False
) -> str:
    result = _study_for_report(building, cfg, flags, from_geometry=from_geometry)
    return render_results(result, building=building, cfg=cfg)


def _dxf_tracing_page(raw: object, hidden: str) -> str:
    """Tracé **universel** sur DXF (§10.3) : DXF rendu en image de fond.

    Utilisé quand la reconstruction automatique ne sort pas de polygones de pièces
    propres (murs doublés, pas de polylignes fermées…). Le DXF étant en mètres,
    l'échelle est exacte (pas de calibrage nécessaire).
    """
    import base64

    from zephyr.viz import render_segments_background

    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for ln in getattr(raw, "lines", []):
        segs.append((ln.start, ln.end))
    for pl in getattr(raw, "polylines", []):
        pts = pl.points
        for i in range(len(pts) - 1):
            segs.append((pts[i], pts[i + 1]))
        if pl.closed and len(pts) >= 3:
            segs.append((pts[-1], pts[0]))
    png, w_px, h_px, m_per_px = render_segments_background(segs)
    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    floor = {"level": 0, "image_uri": uri, "w": w_px, "h": h_px, "mpp": m_per_px}
    return render_tracing([floor], hidden)


def _pdf_floor(pdf_path: Path, level: int) -> dict[str, object]:
    """Rend un PDF en image de fond + échelle → un « niveau » pour l'éditeur de tracé.

    Échelle estimée depuis le format A0 (1189 mm) à 1:50, déduite des dimensions
    réelles (indépendante du zoom de rastérisation) ; l'ingénieur recalibre au clic
    d'une cote connue si besoin.
    """
    import base64

    from zephyr.ingestion import render_pdf_page

    png, w_px, h_px, w_pt, _h_pt = render_pdf_page(pdf_path, zoom=3.0, max_side_px=4500)
    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    mm_per_pt = (1189.0 / w_pt) if w_pt > 0 else 0.3528  # hypothèse A0
    m_per_px = mm_per_pt * 50.0 / 1000.0 * w_pt / max(w_px, 1)  # 1:50 par défaut
    return {"level": level, "image_uri": uri, "w": w_px, "h": h_px, "mpp": m_per_px}


def _pdf_tracing_page(pdf_path: Path, hidden: str) -> str:
    """Éditeur de tracé sur un PDF unique (A0 / planche multi-plans)."""
    return render_tracing([_pdf_floor(pdf_path, 0)], hidden)


def _multi_pdf_tracing_page(pdf_paths: list[Path], hidden: str) -> str:
    """Éditeur de tracé multi-niveaux : un PDF par étage (ordre = niveau, 1er = RdC)."""
    floors = [_pdf_floor(p, i) for i, p in enumerate(pdf_paths)]
    return render_tracing(floors, hidden)


def _parametric(cfg: dict[str, str]) -> Building:
    return parametric_building(
        float(cfg["area"]),
        num_levels=int(float(cfg["levels"])),
        inertia=InertiaClass(cfg["inertia"]),
        main_orientation=Orientation.S,
    )


def _cpe_prefill(ext: object) -> dict[str, str]:
    """Mappe une CpeExtraction vers les champs du formulaire (valeurs chaînes)."""
    out: dict[str, str] = {}
    pairs = {
        "u_wall": "u_wall_w_m2k", "u_window": "u_window_w_m2k",
        "glazing": "glazing_to_floor_ratio", "n50": "air_permeability_ach50",
        "area": "floor_area_m2",
    }
    for field, attr in pairs.items():
        val = getattr(ext, attr, None)
        if val is not None:
            out[field] = f"{val:g}"
    inertia = getattr(ext, "inertia_class", None)
    if inertia is not None:
        out["inertia"] = inertia.value
    return out


@app.post("/etude/cpe", response_class=HTMLResponse)
async def submit_cpe(cpe: UploadFile | None = File(default=None)) -> str:  # noqa: B008
    """Extrait un CPE (PDF vectoriel) et pré-remplit le formulaire (humain valide)."""
    raw = await cpe.read() if cpe is not None else b""
    if not raw:
        return render_study_form(cpe_banner=render_cpe_banner(None, message="Aucun CPE déposé."))
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    from zephyr.ingestion import parse_cpe

    try:
        cpe_text = parse_cpe(tmp_path)
    except Exception as exc:  # noqa: BLE001 - surface l'erreur (scan refusé, etc.)
        return render_study_form(cpe_banner=render_cpe_banner(None, message=str(exc)))

    from zephyr.llm import cpe_extraction_available, extract_cpe

    if not cpe_extraction_available():
        return render_study_form(
            cpe_banner=render_cpe_banner(
                None,
                message="Texte du CPE lu, mais l'extraction automatique est indisponible "
                "(clé API absente sur ce déploiement). Saisissez l'enveloppe à la main.",
            )
        )
    try:
        ext = extract_cpe(cpe_text.text)
    except Exception as exc:  # noqa: BLE001 - l'extraction LLM peut échouer
        return render_study_form(
            cpe_banner=render_cpe_banner(None, message=f"Extraction CPE échouée : {exc}")
        )
    return render_study_form(_cpe_prefill(ext), cpe_banner=render_cpe_banner(ext))


@app.post("/etude/reprendre", response_class=HTMLResponse)
async def resume_study(study: UploadFile | None = File(default=None)) -> str:  # noqa: B008
    """Reprend une étude depuis un fichier .json téléchargé (géométrie + config)."""
    import json

    raw = await study.read() if study is not None else b""
    if not raw:
        return render_study_form(
            cpe_banner=render_cpe_banner(None, message="Aucun fichier d'étude.")
        )
    try:
        data = json.loads(raw)
        building = Building.model_validate_json(data["building_json"])
        cfg = {k: str(v) for k, v in (data.get("config") or {}).items()}
    except Exception as exc:  # noqa: BLE001 - fichier d'étude invalide
        return render_study_form(
            cpe_banner=render_cpe_banner(None, message=f"Fichier d'étude illisible : {exc}")
        )
    hidden = _hidden_fields(cfg, None)
    note = "Étude reprise depuis un fichier — vérifiez/éditez puis calculez."
    return render_validation(building, hidden, [note])


@app.post("/etude", response_class=HTMLResponse)
async def submit_config(
    dxf: UploadFile | None = File(default=None),  # noqa: B008
    floor_pdfs: list[UploadFile] = File(default=[]),  # noqa: B008 - un PDF par étage
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
    chauffage: str = Form("pac"),
    ecs: str = Form("thermodynamique"),
    chassis_material: str = Form("pvc"),
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
        # Captés (pas encore câblés au calcul) — transmis pour le futur/report.
        "chauffage": chauffage, "ecs": ecs, "chassis_material": chassis_material,
    }
    flags = {
        "noise": bool(noise), "pollution": bool(pollution),
        "security": bool(security), "occ_incompatible": bool(occ_incompatible),
    }

    cfg_with_flags = {**cfg, **{k: ("on" if v else "") for k, v in flags.items()}}

    # Multi-niveaux : un PDF par étage (ordre d'upload = niveau, 1er = RdC = 0).
    floor_files = [f for f in (floor_pdfs or []) if f is not None and (f.filename or "")]
    if floor_files:
        paths: list[Path] = []
        for f in floor_files:
            data = await f.read()
            if not data:
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                paths.append(Path(tmp.name))
        if paths:
            try:
                return _multi_pdf_tracing_page(paths, _hidden_fields(cfg_with_flags, None))
            except Exception as exc:  # noqa: BLE001 - surface l'erreur (PDF illisible…)
                return render_error(str(exc))

    raw = await dxf.read() if dxf is not None else b""
    name = (dxf.filename or "").lower() if dxf is not None else ""
    if raw:
        is_pdf = name.endswith(".pdf") or raw[:5] == b"%PDF-"
        suffix = ".pdf" if is_pdf else ".dxf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        hidden = _hidden_fields(cfg_with_flags, None)
        try:
            if is_pdf:
                return _pdf_tracing_page(tmp_path, hidden)
            from zephyr.geometry import build_building
            from zephyr.ingestion import parse_dxf

            raw_dxf = parse_dxf(tmp_path)
            geo = build_building(
                raw_dxf, inertia=InertiaClass(inertia), north_angle_deg=north
            )
        except Exception as exc:  # noqa: BLE001 - surface l'erreur à l'utilisateur
            return render_error(str(exc))
        # DXF propre (polygones de pièces) → validation auto ; sinon → tracé
        # universel sur le DXF rendu en fond (§10.3).
        if any(r.polygon for r in geo.building.rooms):
            return render_validation(geo.building, hidden, geo.warnings)
        return _dxf_tracing_page(raw_dxf, hidden)

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
            "chauffage": "pac", "ecs": "thermodynamique", "chassis_material": "pvc",
        }.items()
    }
    # Hypothèses ROI ajustées par l'utilisateur (recalcul depuis la page de résultats).
    cfg.update({k: v for k, v in d.items() if k.startswith("ovr_")})
    flags = {k: bool(d.get(k)) for k in ("noise", "pollution", "security", "occ_incompatible")}
    from_geometry = bool(d.get("building_json") or d.get("n_rooms"))
    if d.get("building_json"):
        building = Building.model_validate_json(d["building_json"])  # éditeur visuel
    elif d.get("n_rooms"):
        building = building_from_form(d)  # repli formulaire indexé
    else:
        building = _parametric(cfg)
    # Dimensionnement des ouvrants depuis la géométrie réellement tracée (pas paramétrique).
    return _compute_page(building, cfg, flags, from_geometry=from_geometry)


@app.post("/etude/rapport")
async def export_report(request: Request) -> Response:
    """Rapport PDF (ou HTML si WeasyPrint absent) à partir de la géométrie + hypothèses."""
    form = await request.form()
    d = {k: str(v) for k, v in form.items()}
    cfg = {
        k: d.get(k, default)
        for k, default in {
            "nature": "neuf", "project_type": "mixte", "location": "Luxembourg",
            "inertia": "lourde", "area": "1200", "levels": "2",
            "u_wall": "0.20", "u_window": "0.9", "glazing": "0.15",
            "sash": "1.6", "n50": "1.5",
            "chauffage": "pac", "ecs": "thermodynamique", "chassis_material": "pvc",
        }.items()
    }
    cfg.update({k: v for k, v in d.items() if k.startswith("ovr_")})
    flags = {k: bool(d.get(k)) for k in ("noise", "pollution", "security", "occ_incompatible")}
    from_geometry = bool(d.get("building_json"))
    building = (
        Building.model_validate_json(d["building_json"])
        if d.get("building_json")
        else _parametric(cfg)
    )
    if cfg.get("ovr_num_ouvrants_override", ""):
        from_geometry = False
    result = _study_for_report(building, cfg, flags, from_geometry=from_geometry)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        out = Path(tmp.name)
    written = render_report(result, out, building=building)
    media = "application/pdf" if written.suffix == ".pdf" else "text/html"
    fname = "rapport-vnc" + written.suffix
    return FileResponse(str(written), media_type=media, filename=fname)
