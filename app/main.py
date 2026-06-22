"""UI interne Streamlit — Zéphyr.

Pragmatique pour l'interne (CLAUDE.md §5). En attendant l'ingestion DXF
(Phase 3), on décrit un **bâtiment paramétrique** et on fait tourner le pipeline
complet : thermal → ventilation → rules → roi, avec verdict + rapport.

Lancer :  ``uv run --extra app streamlit run app/main.py``
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from zephyr.builders import parametric_building
from zephyr.climate import read_epw, synthetic_climate
from zephyr.geometry import build_building
from zephyr.ingestion import parse_dxf
from zephyr.llm import narrative_available, write_narrative
from zephyr.presets import thermal_params_for, ventilation_params_for
from zephyr.report import render_report_html
from zephyr.roi import ROIParameters
from zephyr.schemas import (
    Building,
    EnvelopeData,
    InertiaClass,
    Orientation,
    ProjectType,
    SiteContext,
    Verdict,
)
from zephyr.study import compute_study
from zephyr.viz import render_plan_png

_VERDICT_COLOR = {Verdict.GO: "🟢", Verdict.CONDITIONNEL: "🟠", Verdict.NO_GO: "🔴"}


def main() -> None:
    st.set_page_config(page_title="Zéphyr — pré-étude VNC", layout="wide")
    st.title("Zéphyr — pré-étude de faisabilité VNC")
    st.caption(
        "Pré-étude / aide à la décision interne. **Pas une étude opposable.** "
        "Toute sortie expose ses hypothèses et son incertitude."
    )

    with st.sidebar:
        st.header("1. Plans (DXF)")
        dxf_file = st.file_uploader("Déposer un plan DXF vectorisé", type=["dxf"])

        st.header("2. Bâtiment")
        project_type = st.selectbox(
            "Type de projet", list(ProjectType), index=2, format_func=lambda x: x.value
        )
        total_area = st.number_input("Surface ventilée totale (m²)", 50.0, 50000.0, 1200.0, 50.0)
        n_levels = st.slider("Niveaux", 1, 8, 2)
        window_ratio = st.slider("Ratio vitrage / surface", 0.05, 0.40, 0.15, 0.01)
        through = st.checkbox("Pièces traversantes", value=True)
        inertia = st.selectbox(
            "Inertie", list(InertiaClass), index=2, format_func=lambda x: x.value
        )

        st.header("3. Enveloppe")
        u_wall = st.number_input("U murs (W/m²K)", 0.05, 1.5, 0.20, 0.01)
        u_win = st.number_input("U vitrage (W/m²K)", 0.5, 3.0, 0.9, 0.1)

        st.header("4. Site (qualitatif)")
        noise = st.checkbox("Bruit extérieur excessif")
        pollution = st.checkbox("Pollution / pollen élevés")
        security = st.checkbox("Risque sécurité au RdC")

        st.header("5. ROI")
        price = st.number_input("Prix élec (€/kWh)", 0.05, 1.0, 0.28, 0.01)

    building: Building
    if dxf_file is not None:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(dxf_file.getvalue())
            tmp_path = Path(tmp.name)
        geo = build_building(parse_dxf(tmp_path), inertia=inertia)
        building = geo.building
        st.subheader("Géométrie reconstruite (DXF) — à valider")
        if not building.rooms:
            st.error("Aucune pièce reconstruite — vérifier le DXF (polylignes fermées).")
        st.caption(
            f"{len(building.rooms)} pièce(s), {building.total_floor_area_m2:.0f} m² au total"
        )
        st.dataframe(
            [
                {
                    "pièce": r.id,
                    "label": r.label.value,
                    "surface m²": round(r.area_m2, 1),
                    "niveau": r.level,
                    "façades": ", ".join(o.value for o in r.exterior_wall_orientations),
                    "ouvrants": len(r.openings),
                }
                for r in building.rooms
            ]
        )
        for w in geo.warnings:
            st.warning(w)
        st.info("⚠️ Validez/corrigez orientations, labels et ouvrants avant de conclure (§2.8).")
    else:
        building = parametric_building(
            total_area,
            num_levels=int(n_levels),
            window_to_floor_ratio=window_ratio,
            inertia=inertia,
            through=through,
            main_orientation=Orientation.S,
        )
    envelope = EnvelopeData(u_wall_w_m2k=u_wall, u_window_w_m2k=u_win, g_window=0.5)
    site = SiteContext(
        exterior_noise_high=noise, pollution_high=pollution, ground_floor_security_risk=security
    )
    # Surface ROI = celle du bâtiment DXF s'il y en a un, sinon la saisie.
    roi_area = building.total_floor_area_m2 if dxf_file is not None else total_area
    roi_params = ROIParameters(
        num_logements=0,
        surface_per_logement_m2=0.0,
        surface_tertiaire_m2=max(roi_area, 1.0),
        price_elec_eur_kwh=price,
    )

    epw = st.session_state.get("epw_path")
    climate = read_epw(epw) if epw else synthetic_climate()
    if not epw:
        st.warning("Climat synthétique (déposer un EPW pour un calcul réel).")

    result = compute_study(
        building,
        climate,
        roi_params=roi_params,
        thermal_params=thermal_params_for(project_type),
        vent_params=ventilation_params_for(project_type),
        envelope=envelope,
        site=site,
    )

    icon = _VERDICT_COLOR[result.verdict]
    st.subheader(f"{icon} Verdict : {result.verdict.value.upper()}")
    if result.disqualifiers:
        st.error("Disqualifiants : " + " ; ".join(result.disqualifiers))
    if result.conditions:
        st.warning("Conditions : " + " ; ".join(result.conditions))

    c1, c2, c3 = st.columns(3)
    assert result.roi and result.thermal
    c1.metric("CAPEX VNC", f"{result.roi.capex_vnc_eur:,.0f} €")
    c2.metric("VAN économie VNC", f"{result.roi.npv_delta_eur:,.0f} €")
    be = result.roi.break_even_year
    c3.metric("Break-even", f"an {be}" if be is not None else "hors horizon")

    st.line_chart({"VAN cumulée économie VNC (€)": result.roi.npv_delta_cumulative_eur})

    st.subheader("Thermique")
    tc1, tc2, tc3, tc4 = st.columns(4)
    tc1.metric("Besoin chauffage VNC", f"{result.thermal.heating_need_kwh_per_year:,.0f} kWh/an")
    tc2.metric("Besoin froid actif", f"{result.thermal.cooling_need_kwh_per_year:,.0f} kWh/an")
    tc3.metric("Pénalité chauffage", f"{result.thermal.heating_penalty_eur_per_year:,.0f} €/an")
    tc4.metric("Night-cooling", f"{result.thermal.night_cooling_benefit_kwh:,.0f} kWh/an")
    st.caption(
        "Températures **libres** (VNC en marche, sans chauffage ni froid actifs) : "
        "elles montrent où le bâtiment dérive trop froid (h<18 °C) ou trop chaud (h>26 °C)."
    )

    if result.thermal.zones:
        st.subheader("Détail thermique par pièce")
        st.dataframe(
            [
                {
                    "pièce": z.zone_id,
                    "label": z.label,
                    "m²": z.area_m2,
                    "T° libre min °C": z.top_min_c,
                    "T° libre max °C": z.top_max_c,
                    "h<18 °C": round(z.hours_below_comfort),
                    "h>26 °C": round(z.overheating_hours),
                    "chauffage kWh/an": round(z.heating_need_kwh or 0),
                    "froid kWh/an": round(z.cooling_need_kwh or 0),
                    "CO₂ moy ppm": z.co2_mean_ppm,
                    "h CO₂>1000": round(z.co2_hours_above_1000 or 0),
                }
                for z in result.thermal.zones
            ]
        )

    if dxf_file is not None and any(r.polygon for r in building.rooms):
        st.subheader("Plan reconstruit")
        st.image(render_plan_png(building))

    st.subheader("Sensibilité (tornado)")
    st.bar_chart({e.parameter: e.swing for e in result.roi.sensitivity})

    st.subheader("Narratif (Opus 4.8)")
    if narrative_available():
        if st.button("Générer le narratif"):
            with st.spinner("Rédaction…"):
                try:
                    result.narrative = write_narrative(result)
                except Exception as e:  # noqa: BLE001 - surface l'erreur API à l'utilisateur
                    st.error(f"Narratif indisponible : {e}")
        if result.narrative:
            st.write(result.narrative)
    else:
        st.caption("Narratif désactivé (définir ANTHROPIC_API_KEY + extra `llm`).")

    with st.expander("Rapport HTML"):
        st.download_button(
            "Télécharger le rapport",
            render_report_html(result, building=building),
            file_name="prestude_vnc.html",
            mime="text/html",
        )

    with st.expander("Hypothèses & avertissements"):
        st.json(result.assumptions)
        for w in result.roi.warnings:
            st.warning(w)


if __name__ == "__main__":
    main()
