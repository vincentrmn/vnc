"""UI interne Streamlit (stub) — Zéphyr.

Pragmatique pour l'interne (CLAUDE.md §5). À ce stade : upload DXF (branché sur
rien), formulaire de paramètres, et une **démo ROI fonctionnelle** (la seule
brique calculatoire prête en Phase 1).

Lancer :  ``streamlit run app/main.py``
"""

from __future__ import annotations

import streamlit as st

from zephyr.roi import ROIParameters, compute_roi, tornado


def main() -> None:
    st.set_page_config(page_title="Zéphyr — pré-étude VNC", layout="wide")
    st.title("Zéphyr — pré-étude de faisabilité VNC")
    st.caption(
        "Pré-étude / aide à la décision interne. **Pas une étude opposable.** "
        "Toute sortie expose ses hypothèses et son incertitude."
    )

    with st.sidebar:
        st.header("1. Plans (DXF)")
        st.file_uploader("Déposer un plan DXF vectorisé", type=["dxf"], disabled=True)
        st.info("Ingestion DXF + validation géométrie : Phase 3 (à venir).")

        st.header("2. Paramètres ROI")
        num_log = st.number_input("Nombre de logements", min_value=0, value=40)
        s_log = st.number_input("Surface / logement (m²)", min_value=0.0, value=75.0)
        s_tert = st.number_input("Surface tertiaire (m²)", min_value=0.0, value=1200.0)
        price = st.number_input("Prix élec (€/kWh)", min_value=0.0, value=0.28, step=0.01)
        penalty = st.number_input(
            "Pénalité chauffage VNC (€/an) — sortie de `thermal`",
            min_value=0.0,
            value=4000.0,
            help="Calculée par le module thermique (Phase 2). Conservatrice ici. Jamais 0.",
        )

    params = ROIParameters(
        num_logements=int(num_log),
        surface_per_logement_m2=s_log,
        surface_tertiaire_m2=s_tert,
        price_elec_eur_kwh=price,
    )
    result = compute_roi(params, heating_penalty_eur_per_year=penalty)

    st.subheader("Résultat ROI (VNC vs VMC DF)")
    c1, c2, c3 = st.columns(3)
    c1.metric("CAPEX VNC", f"{result.capex_vnc_eur:,.0f} €")
    c2.metric("CAPEX VMC", f"{result.capex_vmc_eur:,.0f} €")
    c3.metric(
        "VAN économie VNC (actualisée)",
        f"{result.npv_delta_eur:,.0f} €",
        help="Coûts VMC − coûts VNC. >0 => VNC favorable.",
    )
    be = result.break_even_year
    be_txt = f"an {be}" if be is not None else "au-delà de l'horizon"
    st.write(f"**Break-even** : {be_txt}")

    st.line_chart(
        {"VAN cumulée économie VNC (€)": result.npv_delta_cumulative_eur},
    )

    st.subheader("Sensibilité (tornado)")
    bars = tornado(params, heating_penalty_eur_per_year=penalty)
    st.bar_chart({b.parameter: b.swing for b in bars})

    with st.expander("Hypothèses & avertissements"):
        st.json(result.assumptions)
        for w in result.warnings:
            st.warning(w)


if __name__ == "__main__":
    main()
