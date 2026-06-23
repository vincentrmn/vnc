"""Module `thermal` — pénalité de chauffage VNC, **déterministe** (degrés-jours).

Décision produit : la VNC est éligible sur ~95 % des bâtiments, donc on ne fait
**pas** de STD (ni 5R1C maison, ni EnergyPlus) pour rendre un verdict. Le seul
terme thermique nécessaire est le **surcoût de chauffage** VNC vs VMC double-flux
(CLAUDE.md §6) : la VMC DF récupère η de la chaleur de l'air extrait, la VNC non.

Ce terme est calculé en **degrés-jours** (DJU), pur déterministe :

    pertes_ventilation_saison ≈ ρc · Q_hyg · DJU · 24      [Wh]
    pénalité_VNC ≈ η_VMC · pertes · f_commande              [Wh]

avec ``f_commande`` < 1 l'atténuation par la **commande à la demande** (débit
réduit hors occupation, propre à la VNC pilotée). Jamais 0, jamais un % posé en
sortie — c'est une *différence de pertes de ventilation*, robuste et honnête.
"""

from __future__ import annotations

from dataclasses import dataclass

from zephyr.climate import ClimateData, heating_degree_days
from zephyr.schemas import Building, HeatingPenalty

RHO_C_AIR = 0.34  # Wh/(m³·K) ≈ 1200 J/m³K / 3600 — capacité thermique volumique de l'air


@dataclass
class PenaltyParams:
    """Hypothèses (toutes exposées et surchargeables) du calcul de pénalité."""

    hygienic_ach: float = 0.5  # débit hygiénique de référence (vol/h)
    recovery_efficiency: float = 0.80  # rendement du récupérateur VMC DF (70–90 %)
    demand_factor: float = 0.65  # atténuation par commande à la demande (0..1)
    base_temp_c: float = 18.0  # base des degrés-jours
    heating_energy_price_eur_kwh: float = 0.12  # prix de l'énergie de chauffage (€/kWh)


def heating_penalty(
    building: Building,
    climate: ClimateData,
    params: PenaltyParams | None = None,
) -> HeatingPenalty:
    """Surcoût de chauffage VNC vs VMC DF (kWh/an et €/an), en degrés-jours.

    Déterministe : aucune simulation horaire. La pénalité est l'énergie de
    ventilation **non récupérée** par la VNC (alors que la VMC en récupère η),
    sur la saison de chauffe (DJU), atténuée par la commande à la demande.
    """
    params = params or PenaltyParams()
    dju = heating_degree_days(climate, params.base_temp_c)
    volume = max(building.total_volume_m3, 1.0)
    q_hyg_m3h = params.hygienic_ach * volume  # débit hygiénique (m³/h)

    # Pertes de ventilation sur la saison (Wh) ; ρc en Wh/(m³·K), DJU·24 en °C·h.
    vent_losses_kwh = RHO_C_AIR * q_hyg_m3h * dju * 24.0 / 1000.0
    # La VMC récupère η ; la VNC non → la pénalité = la part récupérable, atténuée
    # par la commande à la demande (débit réduit hors occupation).
    penalty_kwh = params.recovery_efficiency * vent_losses_kwh * params.demand_factor
    penalty_eur = penalty_kwh * params.heating_energy_price_eur_kwh

    return HeatingPenalty(
        kwh_per_year=round(penalty_kwh, 1),
        eur_per_year=round(penalty_eur, 1),
        heating_degree_days=round(dju, 1),
        assumptions={
            "methode": "degrés-jours (déterministe, sans STD)",
            "dju_base_c": f"{params.base_temp_c:.0f}",
            "dju": f"{dju:.0f}",
            "debit_hygienique_ach": f"{params.hygienic_ach}",
            "volume_m3": f"{volume:.0f}",
            "rendement_recup_vmc": f"{params.recovery_efficiency:.0%}",
            "facteur_commande_demande": f"{params.demand_factor}",
            "prix_energie_chauffage_eur_kwh": f"{params.heating_energy_price_eur_kwh}",
            "note": "surcoût = pertes de ventilation non récupérées par la VNC (≠ STD)",
        },
    )
