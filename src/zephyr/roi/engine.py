"""Moteur de calcul ROI : CAPEX, OPEX, actualisation, VAN, break-even.

Porte la spec CLAUDE.md §6. Convention de signe : le *delta* est l'**économie
de la VNC** = (coûts VMC − coûts VNC). Une VAN delta positive => VNC favorable.

Le terme clé `heating_penalty_eur_per_year` est une **entrée séparée** (sortie de
`thermal`), jamais postulée ici. Cf. §13.3.

Postes optionnels (subvention, carbone, free-cooling, TVA, part fixe VMC) sont
**neutres par défaut** (0) : aux valeurs par défaut, le calcul est identique à
l'historique (tests golden). Chaque poste produit une **ligne traçable**
(`CalcLine`) avec sa formule et son montant.
"""

from __future__ import annotations

from zephyr.roi.parameters import ROIParameters
from zephyr.schemas.results import CalcLine, ROIResult

_DEFAULT_WARNINGS: list[str] = [
    "Ratios €/m² VMC : ordres de grandeur marché LU/BE — à confronter à ≥ 2 devis réels.",
    "Aucune valeur résiduelle en fin d'horizon n'est comptée.",
    "Résultats sensibles : prix élec, WACC, nb d'ouvrants, abonnement BOS, pénalité de chauffage. "
    "Ne jamais présenter un point unique sans analyse de sensibilité (tornado / fourchette).",
]

_VMC_ENERGY_KEYS = {"energie_ventilateurs", "cout_carbone"}
_VNC_ENERGY_KEYS = {"energie_actionneurs", "penalite_chauffage", "cout_carbone", "benefice_freecooling"}


def _n(x: float) -> str:
    """Nombre lisible pour une formule (espace fin comme séparateur de milliers)."""
    return f"{x:,.0f}".replace(",", " ") if abs(x) >= 100 else f"{x:g}"


def _capex_vmc(p: ROIParameters) -> dict[str, float]:
    area = p.total_floor_area_m2
    b = {
        "centrales_recuperateurs": p.vmc_centrales_eur_m2 * area,
        "reseau_gaines": p.vmc_reseau_gaines_eur_m2 * area,
        "pose_cvc": p.vmc_pose_cvc_eur_m2 * area,
        "regulation": p.vmc_regulation_eur_m2 * area,
        "etancheite": p.vmc_etancheite_eur_m2 * area,
        "etudes": p.vmc_etudes_eur_m2 * area,
        "commissioning": p.vmc_commissioning_eur_m2 * area,
    }
    if p.vmc_fixed_eur:
        b["base_fixe"] = p.vmc_fixed_eur
    return b


def _capex_vnc(p: ROIParameters) -> dict[str, float]:
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


def _opex_vmc_year1(p: ROIParameters) -> tuple[dict[str, float], float]:
    fan_kwh = p.total_volume_m3 * p.vmc_ach * p.vmc_sfp_wh_m3 * p.vmc_operating_hours_year / 1000.0
    carbon = fan_kwh * p.grid_carbon_kg_kwh / 1000.0 * p.carbon_price_eur_t
    b = {
        "energie_ventilateurs": fan_kwh * p.price_elec_eur_kwh,
        "maintenance_filtres": p.vmc_maintenance_eur_m2_year * p.total_floor_area_m2,
        "extraction_humide": p.wet_extraction_opex_eur_year,
    }
    if p.carbon_price_eur_t and p.grid_carbon_kg_kwh:
        b["cout_carbone"] = carbon
    return b, fan_kwh


def _opex_vnc_year1(p: ROIParameters, heating_penalty: float) -> dict[str, float]:
    carbon = p.vnc_actuator_energy_kwh_year * p.grid_carbon_kg_kwh / 1000.0 * p.carbon_price_eur_t
    b = {
        "energie_actionneurs": p.vnc_actuator_energy_kwh_year * p.price_elec_eur_kwh,
        "maintenance_ouvrants_capteurs": p.vnc_maintenance_eur_m2_year * p.total_floor_area_m2,
        "abonnement_bos": p.bos_subscription_eur_per_point_year * p.num_bos_points,
        "extraction_humide": p.wet_extraction_opex_eur_year,
        "penalite_chauffage": heating_penalty,
    }
    if p.carbon_price_eur_t and p.grid_carbon_kg_kwh:
        b["cout_carbone"] = carbon
    if p.freecooling_kwh_year:
        b["benefice_freecooling"] = -p.freecooling_kwh_year * p.price_elec_eur_kwh
    return b


def _split_energy(breakdown: dict[str, float], energy_keys: set[str]) -> tuple[float, float]:
    energy = sum(v for k, v in breakdown.items() if k in energy_keys)
    rest = sum(v for k, v in breakdown.items() if k not in energy_keys)
    return energy, rest


def _cashflows(
    capex_an0: float, opex_energy: float, opex_rest: float, renewal: float,
    renewal_year: int, horizon: int, infl: float, einfl: float,
) -> list[float]:
    flows = [capex_an0]
    for year in range(1, horizon + 1):
        o = opex_rest * (1 + infl) ** (year - 1) + opex_energy * (1 + einfl) ** (year - 1)
        if year == renewal_year:
            o += renewal
        flows.append(o)
    return flows


def _discount(flows: list[float], wacc: float) -> list[float]:
    return [f / (1 + wacc) ** year for year, f in enumerate(flows)]


def _capex_lines(p: ROIParameters, section: str, b: dict[str, float], k: float) -> list[CalcLine]:
    """Formules CAPEX (avant aléas) → ligne traçable (valeur = avec aléas)."""
    area = p.total_floor_area_m2
    labels = {**_CAPEX_VMC_LABELS, **_CAPEX_VNC_LABELS}
    qty = {
        "ouvrants_motorises": (p.num_ouvrants, p.vnc_price_per_ouvrant_eur, "ouvrants"),
        "capteurs_4en1": (p.num_capteurs, p.vnc_price_per_capteur_eur, "capteurs"),
        "station_meteo": (p.vnc_num_stations_meteo, p.vnc_price_station_meteo_eur, "stations"),
    }
    per_m2 = {
        "centrales_recuperateurs": p.vmc_centrales_eur_m2, "reseau_gaines": p.vmc_reseau_gaines_eur_m2,
        "pose_cvc": p.vmc_pose_cvc_eur_m2, "regulation": p.vmc_regulation_eur_m2,
        "etancheite": p.vmc_etancheite_eur_m2, "etudes": p.vmc_etudes_eur_m2,
        "commissioning": p.vmc_commissioning_eur_m2, "cablage": p.vnc_cablage_eur_m2,
    }
    lines: list[CalcLine] = []
    for key, base in b.items():
        if key in qty:
            n, price, unit = qty[key]
            formula = f"{n} {unit} × {_n(price)} € × {k:.2f} (aléas)"
        elif key in per_m2:
            formula = f"{_n(per_m2[key])} €/m² × {_n(area)} m² × {k:.2f} (aléas)"
        else:  # forfait
            formula = f"forfait {_n(base / k)} € × {k:.2f} (aléas)"
        lines.append(CalcLine(section=section, label=labels.get(key, key), formula=formula, value_eur=base))
    return lines


_CAPEX_VMC_LABELS = {
    "centrales_recuperateurs": "Centrales + récupérateurs", "reseau_gaines": "Réseau de gaines",
    "pose_cvc": "Pose CVC", "regulation": "Régulation", "etancheite": "Étanchéité",
    "etudes": "Études", "commissioning": "Commissioning", "base_fixe": "Part fixe (centrale de base)",
}
_CAPEX_VNC_LABELS = {
    "ouvrants_motorises": "Ouvrants motorisés", "capteurs_4en1": "Capteurs 4-en-1",
    "station_meteo": "Station météo", "plateforme_bos": "Plateforme BOS", "cablage": "Câblage",
    "extraction_humide": "Extraction pièces humides", "std_ingenierie": "STD + ingénierie",
    "commissioning_hypercare": "Commissioning + hypercare",
}


def compute_roi(
    params: ROIParameters | None = None,
    *,
    heating_penalty_eur_per_year: float,
    include_default_warnings: bool = True,
) -> ROIResult:
    """Calcule le comparatif ROI VNC vs VMC DF. Cf. docstring module."""
    p = params or ROIParameters()
    if heating_penalty_eur_per_year < 0:
        raise ValueError("La pénalité de chauffage ne peut pas être négative.")

    k = 1 + p.contingency_rate
    capex_vmc_b = {name: v * k for name, v in _capex_vmc(p).items()}
    capex_vnc_b = {name: v * k for name, v in _capex_vnc(p).items()}
    capex_vmc = sum(capex_vmc_b.values())
    capex_vnc = sum(capex_vnc_b.values())

    opex_vmc_b, fan_kwh = _opex_vmc_year1(p)
    opex_vnc_b = _opex_vnc_year1(p, heating_penalty_eur_per_year)
    opex_vmc = sum(opex_vmc_b.values())
    opex_vnc = sum(opex_vnc_b.values())

    # CAPEX an 0 : TTC (TVA) − subventions. Neutres par défaut.
    tva = 1 + p.tva_rate
    capex_an0_vmc = capex_vmc * tva - p.subsidy_vmc_eur
    capex_an0_vnc = capex_vnc * tva - p.subsidy_vnc_eur

    e_vmc, r_vmc = _split_energy(opex_vmc_b, _VMC_ENERGY_KEYS)
    e_vnc, r_vnc = _split_energy(opex_vnc_b, _VNC_ENERGY_KEYS)
    infl, einfl = p.inflation, p.energy_inflation_rate

    flows_vmc = _cashflows(capex_an0_vmc, e_vmc, r_vmc, capex_vmc * p.vmc_renewal_rate,
                           p.renewal_year, p.horizon_years, infl, einfl)
    flows_vnc = _cashflows(capex_an0_vnc, e_vnc, r_vnc, capex_vnc * p.vnc_renewal_rate,
                           p.renewal_year, p.horizon_years, infl, einfl)

    delta_disc = [m - n for m, n in zip(_discount(flows_vmc, p.wacc), _discount(flows_vnc, p.wacc),
                                        strict=True)]
    cumulative, running = [], 0.0
    for d in delta_disc:
        running += d
        cumulative.append(running)
    npv_delta = cumulative[-1]

    break_even: int | None = next((y for y, c in enumerate(cumulative) if c >= 0), None)

    # Lignes traçables.
    lines = _capex_lines(p, "capex_vmc", capex_vmc_b, k) + _capex_lines(p, "capex_vnc", capex_vnc_b, k)
    lines += _opex_lines(p, fan_kwh, opex_vmc_b, opex_vnc_b)

    return ROIResult(
        capex_vmc_eur=capex_vmc, capex_vnc_eur=capex_vnc,
        capex_vmc_breakdown=capex_vmc_b, capex_vnc_breakdown=capex_vnc_b,
        opex_vmc_year1_eur=opex_vmc, opex_vnc_year1_eur=opex_vnc,
        opex_vmc_breakdown=opex_vmc_b, opex_vnc_breakdown=opex_vnc_b,
        horizon_years=p.horizon_years,
        npv_delta_eur=npv_delta, npv_delta_cumulative_eur=cumulative, break_even_year=break_even,
        tco_vmc_undiscounted_eur=sum(flows_vmc), tco_vnc_undiscounted_eur=sum(flows_vnc),
        calc_lines=lines,
        assumptions={
            "convention_delta": "économie VNC = coûts VMC − coûts VNC ; VAN>0 => VNC favorable",
            "heating_penalty_eur_an": f"{heating_penalty_eur_per_year:.0f} (entrée de thermal)",
            "surface_totale_m2": f"{p.total_floor_area_m2:.0f}",
            "volume_total_m3": f"{p.total_volume_m3:.0f}",
            "nb_ouvrants": str(p.num_ouvrants), "wacc": f"{p.wacc:.1%}",
            "inflation": f"{p.inflation:.1%}", "inflation_energie": f"{p.energy_inflation_rate:.1%}",
            "prix_elec_eur_kwh": f"{p.price_elec_eur_kwh:.3f}",
            "tva": f"{p.tva_rate:.0%}", "subvention_vnc_eur": f"{p.subsidy_vnc_eur:.0f}",
        },
        warnings=list(_DEFAULT_WARNINGS) if include_default_warnings else [],
    )


def _opex_lines(
    p: ROIParameters, fan_kwh: float, vmc_b: dict[str, float], vnc_b: dict[str, float]
) -> list[CalcLine]:
    """Formules OPEX an 1 (avant inflation) → lignes traçables."""
    area = p.total_floor_area_m2
    f: list[CalcLine] = []

    def line(section: str, key: str, b: dict[str, float], formula: str, label: str) -> None:
        if key in b:
            f.append(CalcLine(section=section, label=label, formula=formula, value_eur=b[key]))

    line("opex_vmc", "energie_ventilateurs", vmc_b,
         f"{_n(p.total_volume_m3)} m³ × {p.vmc_ach:g} vol/h × {p.vmc_sfp_wh_m3:g} Wh/m³ × "
         f"{_n(p.vmc_operating_hours_year)} h ÷ 1000 = {_n(fan_kwh)} kWh × {p.price_elec_eur_kwh:g} €",
         "Énergie ventilateurs")
    line("opex_vmc", "maintenance_filtres", vmc_b,
         f"{p.vmc_maintenance_eur_m2_year:g} €/m²/an × {_n(area)} m²", "Maintenance (filtres)")
    line("opex_vmc", "extraction_humide", vmc_b, f"forfait {_n(p.wet_extraction_opex_eur_year)} €/an",
         "Extraction pièces humides")
    line("opex_vmc", "cout_carbone", vmc_b,
         f"{_n(fan_kwh)} kWh × {p.grid_carbon_kg_kwh:g} kgCO₂ ÷ 1000 × {p.carbon_price_eur_t:g} €/t",
         "Coût carbone")

    line("opex_vnc", "energie_actionneurs", vnc_b,
         f"{_n(p.vnc_actuator_energy_kwh_year)} kWh × {p.price_elec_eur_kwh:g} €", "Énergie actionneurs")
    line("opex_vnc", "maintenance_ouvrants_capteurs", vnc_b,
         f"{p.vnc_maintenance_eur_m2_year:g} €/m²/an × {_n(area)} m²", "Maintenance ouvrants/capteurs")
    line("opex_vnc", "abonnement_bos", vnc_b,
         f"{p.bos_subscription_eur_per_point_year:g} €/pt/an × {p.num_bos_points} pts "
         f"({p.num_ouvrants} ouvrants + {p.num_capteurs} capteurs + {p.vnc_num_stations_meteo})",
         "Abonnement BOS")
    line("opex_vnc", "extraction_humide", vnc_b, f"forfait {_n(p.wet_extraction_opex_eur_year)} €/an",
         "Extraction pièces humides")
    line("opex_vnc", "penalite_chauffage", vnc_b,
         "pertes de ventilation non récupérées (module thermal, degrés-jours)",
         "Pénalité de chauffage")
    line("opex_vnc", "cout_carbone", vnc_b,
         f"{_n(p.vnc_actuator_energy_kwh_year)} kWh × {p.grid_carbon_kg_kwh:g} kgCO₂ ÷ 1000 × "
         f"{p.carbon_price_eur_t:g} €/t", "Coût carbone")
    line("opex_vnc", "benefice_freecooling", vnc_b,
         f"− {_n(p.freecooling_kwh_year)} kWh évités × {p.price_elec_eur_kwh:g} €",
         "Bénéfice free-cooling")
    return f
