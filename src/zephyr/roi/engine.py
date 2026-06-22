"""Moteur de calcul ROI : CAPEX, OPEX, actualisation, VAN, break-even.

Porte la spec CLAUDE.md §6. Convention de signe : le *delta* est l'**économie
de la VNC** = (coûts VMC − coûts VNC). Une VAN delta positive => VNC favorable.

Le terme clé `heating_penalty_eur_per_year` est une **entrée séparée** (sortie de
`thermal`), jamais postulée ici. Cf. §13.3.
"""

from __future__ import annotations

from zephyr.roi.parameters import ROIParameters
from zephyr.schemas.results import ROIResult

# Avertissements méthodologiques systématiques (CLAUDE.md §6).
_DEFAULT_WARNINGS: list[str] = [
    "Ratios €/m² VMC : ordres de grandeur marché LU/BE — à confronter à ≥ 2 devis réels.",
    "Aucune valeur résiduelle en fin d'horizon n'est comptée.",
    "Résultats sensibles : prix élec, WACC, nb d'ouvrants, abonnement BOS, pénalité de chauffage. "
    "Ne jamais présenter un point unique sans analyse de sensibilité (tornado).",
]


def _capex_vmc(p: ROIParameters) -> dict[str, float]:
    """CAPEX VMC DF par ratios €/m² (avant aléas)."""
    area = p.total_floor_area_m2
    return {
        "centrales_recuperateurs": p.vmc_centrales_eur_m2 * area,
        "reseau_gaines": p.vmc_reseau_gaines_eur_m2 * area,
        "pose_cvc": p.vmc_pose_cvc_eur_m2 * area,
        "regulation": p.vmc_regulation_eur_m2 * area,
        "etancheite": p.vmc_etancheite_eur_m2 * area,
        "etudes": p.vmc_etudes_eur_m2 * area,
        "commissioning": p.vmc_commissioning_eur_m2 * area,
    }


def _capex_vnc(p: ROIParameters) -> dict[str, float]:
    """CAPEX VNC par quantités (avant aléas)."""
    area = p.total_floor_area_m2
    return {
        "ouvrants_motorises": p.num_ouvrants * p.vnc_price_per_ouvrant_eur,
        "capteurs_4en1": p.num_capteurs * p.vnc_price_per_capteur_eur,
        "station_meteo": p.vnc_num_stations_meteo * p.vnc_price_station_meteo_eur,
        "plateforme_bos": p.vnc_bos_platform_eur,
        "cablage": p.vnc_cablage_eur_m2 * area,
        "extraction_humide": p.vnc_extraction_humide_eur,
        "std_ingenierie": p.vnc_std_engineering_eur,
        "commissioning_hypercare": p.vnc_commissioning_hypercare_eur,
    }


def _opex_vmc_year1(p: ROIParameters) -> dict[str, float]:
    """OPEX VMC an 1 (avant inflation)."""
    # Énergie ventilateurs : volume × ACH × SFP × heures / 1000 → kWh (cf. §6).
    fan_kwh = p.total_volume_m3 * p.vmc_ach * p.vmc_sfp_wh_m3 * p.vmc_operating_hours_year / 1000.0
    return {
        "energie_ventilateurs": fan_kwh * p.price_elec_eur_kwh,
        "maintenance_filtres": p.vmc_maintenance_eur_m2_year * p.total_floor_area_m2,
        "extraction_humide": p.wet_extraction_opex_eur_year,
    }


def _opex_vnc_year1(p: ROIParameters, heating_penalty_eur_per_year: float) -> dict[str, float]:
    """OPEX VNC an 1 (avant inflation), **pénalité de chauffage incluse**."""
    return {
        "energie_actionneurs": p.vnc_actuator_energy_kwh_year * p.price_elec_eur_kwh,
        "maintenance_ouvrants_capteurs": p.vnc_maintenance_eur_m2_year * p.total_floor_area_m2,
        "abonnement_bos": p.bos_subscription_eur_per_point_year * p.num_bos_points,
        "extraction_humide": p.wet_extraction_opex_eur_year,
        # Terme correctif obligatoire vs Excel (CLAUDE.md §6) — calculé par `thermal`.
        "penalite_chauffage": heating_penalty_eur_per_year,
    }


def _annual_cashflows(
    capex: float,
    opex_year1: float,
    renewal_amount: float,
    renewal_year: int,
    horizon: int,
    inflation: float,
) -> list[float]:
    """Flux de trésorerie nominaux an 0..horizon (sorties de caisse, positives)."""
    flows = [capex]  # an 0
    for year in range(1, horizon + 1):
        opex = opex_year1 * (1 + inflation) ** (year - 1)
        if year == renewal_year:
            opex += renewal_amount
        flows.append(opex)
    return flows


def _discount(flows: list[float], wacc: float) -> list[float]:
    """Actualise une série de flux an 0..N."""
    return [f / (1 + wacc) ** year for year, f in enumerate(flows)]


def compute_roi(
    params: ROIParameters | None = None,
    *,
    heating_penalty_eur_per_year: float,
    include_default_warnings: bool = True,
) -> ROIResult:
    """Calcule le comparatif ROI VNC vs VMC DF.

    Args:
        params: hypothèses (preset LU/Pommerloch par défaut).
        heating_penalty_eur_per_year: terme OPEX « pénalité de chauffage VNC »,
            sortie de `thermal`. **Obligatoire et explicite** : passer 0
            uniquement pour reproduire l'Excel d'origine (test de non-régression).
        include_default_warnings: ajoute les avertissements méthodologiques §6.

    Returns:
        ROIResult complet (CAPEX, OPEX, VAN delta, break-even, TCO).
    """
    p = params or ROIParameters()
    if heating_penalty_eur_per_year < 0:
        raise ValueError("La pénalité de chauffage ne peut pas être négative.")

    # --- CAPEX (avec aléas) ---
    capex_vmc_b = _capex_vmc(p)
    capex_vnc_b = _capex_vnc(p)
    k = 1 + p.contingency_rate
    capex_vmc_b = {name: v * k for name, v in capex_vmc_b.items()}
    capex_vnc_b = {name: v * k for name, v in capex_vnc_b.items()}
    capex_vmc = sum(capex_vmc_b.values())
    capex_vnc = sum(capex_vnc_b.values())

    # --- OPEX an 1 ---
    opex_vmc_b = _opex_vmc_year1(p)
    opex_vnc_b = _opex_vnc_year1(p, heating_penalty_eur_per_year)
    opex_vmc = sum(opex_vmc_b.values())
    opex_vnc = sum(opex_vnc_b.values())

    # --- Flux nominaux ---
    flows_vmc = _annual_cashflows(
        capex_vmc,
        opex_vmc,
        capex_vmc * p.vmc_renewal_rate,
        p.renewal_year,
        p.horizon_years,
        p.inflation,
    )
    flows_vnc = _annual_cashflows(
        capex_vnc,
        opex_vnc,
        capex_vnc * p.vnc_renewal_rate,
        p.renewal_year,
        p.horizon_years,
        p.inflation,
    )

    # --- Actualisation & delta (économie VNC = VMC − VNC) ---
    disc_vmc = _discount(flows_vmc, p.wacc)
    disc_vnc = _discount(flows_vnc, p.wacc)
    delta_disc = [m - n for m, n in zip(disc_vmc, disc_vnc, strict=True)]

    cumulative = []
    running = 0.0
    for d in delta_disc:
        running += d
        cumulative.append(running)
    npv_delta = cumulative[-1]

    # Break-even : première année où l'économie cumulée actualisée devient ≥ 0.
    break_even: int | None = None
    for year, c in enumerate(cumulative):
        if c >= 0:
            break_even = year
            break

    return ROIResult(
        capex_vmc_eur=capex_vmc,
        capex_vnc_eur=capex_vnc,
        capex_vmc_breakdown=capex_vmc_b,
        capex_vnc_breakdown=capex_vnc_b,
        opex_vmc_year1_eur=opex_vmc,
        opex_vnc_year1_eur=opex_vnc,
        opex_vmc_breakdown=opex_vmc_b,
        opex_vnc_breakdown=opex_vnc_b,
        horizon_years=p.horizon_years,
        npv_delta_eur=npv_delta,
        npv_delta_cumulative_eur=cumulative,
        break_even_year=break_even,
        tco_vmc_undiscounted_eur=sum(flows_vmc),
        tco_vnc_undiscounted_eur=sum(flows_vnc),
        assumptions={
            "convention_delta": "économie VNC = coûts VMC − coûts VNC ; VAN>0 => VNC favorable",
            "heating_penalty_eur_an": f"{heating_penalty_eur_per_year:.0f} (entrée de thermal)",
            "surface_totale_m2": f"{p.total_floor_area_m2:.0f}",
            "volume_total_m3": f"{p.total_volume_m3:.0f}",
            "nb_ouvrants": str(p.num_ouvrants),
            "wacc": f"{p.wacc:.1%}",
            "inflation": f"{p.inflation:.1%}",
            "prix_elec_eur_kwh": f"{p.price_elec_eur_kwh:.3f}",
        },
        warnings=list(_DEFAULT_WARNINGS) if include_default_warnings else [],
    )
