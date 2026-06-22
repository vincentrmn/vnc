"""Module `thermal` — modèle 5R1C (inertie) — ISO 13790 / 52016 (Phase 2).

Cœur du screen thermique (CLAUDE.md §7). À partir du `Building`, de l'enveloppe
et du climat, calcule par simulation horaire :
  - les **heures de surchauffe** (free-running + night-cooling VNC) ;
  - le **bénéfice de night-cooling** ;
  - et surtout la **pénalité de chauffage VNC** = besoin de chauffage
    différentiel dû à l'absence d'échangeur air-air (VMC DF récupère, VNC non),
    **atténué** par : commande à la demande (débit hygiénique mini), inertie
    lourde (nœud de masse C_m du 5R1C) et scheduling. Ce terme est **calculé**,
    jamais postulé (CLAUDE.md §2.5, §5).

⚠️ Honnêteté (§2.4, §11) : tant qu'aucun cas IDA ICE réel n'est déposé dans
`data/validation/`, ces sorties ne sont **pas validées**. La pénalité de
chauffage, étant une *différence* entre deux runs ne différant que par la
récupération, est directionnellement robuste aux approximations d'apports ; la
surchauffe (sensible au solaire/occupation) porte une incertitude plus forte.
`equivalent_recovery_pct` reste `None` tant qu'il n'est pas validé.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from zephyr.climate import ClimateData, vertical_irradiance
from zephyr.schemas import Building, EnvelopeData, InertiaClass, Orientation, ThermalResult

# Constantes ISO 13790
H_IS = 3.45  # W/m²K, couplage air <-> surface
H_MS = 9.1  # W/m²K, couplage surface <-> masse
LAMBDA_AT = 4.5  # A_t = LAMBDA_AT * A_f
RHO_C_AIR = 0.34  # Wh/(m³·K) ≈ 1200 J/m³K / 3600

# Inertie : (C_m [J/(K·m² plancher)], facteur A_m) — table ISO 13790.
_INERTIA: dict[InertiaClass, tuple[float, float]] = {
    InertiaClass.LEGERE: (110_000.0, 2.5),
    InertiaClass.MOYENNE: (165_000.0, 2.5),
    InertiaClass.LOURDE: (260_000.0, 3.0),
}

# Enveloppe par défaut (ordres de grandeur LU récent) si CPE absent.
_DEFAULT_ENVELOPE = EnvelopeData(
    u_wall_w_m2k=0.22,
    u_roof_w_m2k=0.18,
    u_floor_w_m2k=0.28,
    u_window_w_m2k=1.1,
    g_window=0.5,
    air_permeability_ach50=1.5,
)


@dataclass
class R5C1Params:
    """Hypothèses de pilotage et physiques du screen thermique (non géométriques).

    Valeurs par défaut à caler en Phase 2 contre IDA ICE. Tout est exposé.
    """

    heating_setpoint_c: float = 20.0
    comfort_temp_c: float = 26.0  # seuil de surchauffe
    hygienic_ach: float = 0.5  # débit hygiénique (commande à la demande VNC)
    infiltration_ach: float | None = None  # déduit de n50/20 si None
    night_cooling_ach: float = 4.0  # boost ventilation nocturne VNC (été)
    internal_gains_w_m2: float = 4.0
    recovery_efficiency: float = 0.80  # rendement échangeur VMC DF (70–90 %)
    glazing_fraction: float = 0.7  # part vitrée d'un ouvrant (cadre)
    shading_factor: float = 0.9  # ombrage moyen
    heating_energy_price_eur_kwh: float = 0.12  # prix énergie de chauffage (€/kWh)
    ground_temp_c: float | None = None  # T sol ; si None → moyenne annuelle du climat
    extra: dict[str, float] = field(default_factory=dict)


@dataclass
class _ZoneModel:
    """Conductances 5R1C dérivées (mono-zone bâtiment)."""

    a_f: float  # surface plancher (m²)
    a_t: float
    a_m: float
    c_m: float  # J/K
    h_tr_w: float
    h_tr_op: float  # opaque hors-sol (murs + toiture) → air extérieur
    h_tr_is: float
    h_tr_ms: float
    h_tr_em: float
    h_gr: float  # plancher bas → sol (ISO 13370 simplifié)
    volume: float
    phi_int: float  # W (apports internes constants)
    phi_sol: list[float]  # W (apports solaires horaires)


def _windows_by_orientation(building: Building) -> dict[Orientation, float]:
    """Surface vitrée totale par orientation (m²)."""
    out: dict[Orientation, float] = {}
    for room in building.rooms:
        for op in room.openings:
            out[op.orientation] = out.get(op.orientation, 0.0) + op.area_m2
    return out


def _build_zone(
    building: Building,
    env: EnvelopeData,
    params: R5C1Params,
    irradiance: dict[Orientation, list[float]],
) -> _ZoneModel:
    """Construit le modèle mono-zone 5R1C depuis géométrie + enveloppe.

    Les surfaces opaques sont estimées par forme compacte (empreinte carrée),
    approximation assumée de niveau pré-étude. `irradiance` donne, par
    orientation, la série horaire d'irradiance verticale (W/m²).
    """
    a_f = building.total_floor_area_m2
    volume = building.total_volume_m3
    heights = [r.height_m for r in building.rooms] or [2.6]
    mean_h = sum(heights) / len(heights)
    levels = max(building.num_levels, 1)

    footprint = a_f / levels
    perimeter = 4.0 * math.sqrt(max(footprint, 1.0))
    total_height = levels * mean_h
    gross_wall = perimeter * total_height

    windows = _windows_by_orientation(building)
    a_w = sum(windows.values())
    a_wall_opaque = max(gross_wall - a_w, 0.3 * gross_wall)
    a_roof = footprint
    a_floor = footprint

    u_wall = env.u_wall_w_m2k or _DEFAULT_ENVELOPE.u_wall_w_m2k
    u_roof = env.u_roof_w_m2k or _DEFAULT_ENVELOPE.u_roof_w_m2k
    u_floor = env.u_floor_w_m2k or _DEFAULT_ENVELOPE.u_floor_w_m2k
    u_win = env.u_window_w_m2k or _DEFAULT_ENVELOPE.u_window_w_m2k
    g_win = env.g_window or _DEFAULT_ENVELOPE.g_window
    assert u_wall and u_roof and u_floor and u_win and g_win  # défauts garantis non-None

    # Opaque hors-sol (murs + toiture) → air extérieur.
    h_tr_op = u_wall * a_wall_opaque + u_roof * a_roof
    # Plancher bas → SOL (température stable ~moyenne annuelle), pas l'air extérieur.
    # ISO 13370 simplifié : couplage direct à T_sol via U plancher.
    h_gr = u_floor * a_floor
    h_tr_w = u_win * a_w

    c_m_per_m2, a_m_factor = _INERTIA[building.inertia_class]
    c_m = c_m_per_m2 * a_f
    a_m = a_m_factor * a_f
    a_t = LAMBDA_AT * a_f
    h_tr_is = H_IS * a_t
    h_tr_ms = H_MS * a_m
    # H_tr_em : opaque côté masse (garde-fou si H_tr_op proche de H_tr_ms).
    if h_tr_op >= h_tr_ms:
        h_tr_em = h_tr_op
    else:
        h_tr_em = 1.0 / (1.0 / h_tr_op - 1.0 / h_tr_ms)

    phi_int = params.internal_gains_w_m2 * a_f

    # Apports solaires horaires (somme sur orientations vitrées).
    phi_sol_total: list[float] = []
    for orient, area in windows.items():
        irr = irradiance[orient]
        gain_area = g_win * params.glazing_fraction * params.shading_factor * area
        if not phi_sol_total:
            phi_sol_total = [0.0] * len(irr)
        for i in range(len(irr)):
            phi_sol_total[i] += gain_area * irr[i]
    if not phi_sol_total:
        phi_sol_total = [0.0] * 8760

    return _ZoneModel(
        a_f=a_f,
        a_t=a_t,
        a_m=a_m,
        c_m=c_m,
        h_tr_w=h_tr_w,
        h_tr_op=h_tr_op,
        h_tr_is=h_tr_is,
        h_tr_ms=h_tr_ms,
        h_tr_em=h_tr_em,
        h_gr=h_gr,
        volume=volume,
        phi_int=phi_int,
        phi_sol=phi_sol_total,
    )


def _step(
    z: _ZoneModel,
    theta_m_prev: float,
    theta_e: float,
    phi_sol: float,
    h_ve: float,
    ground_temp: float,
    phi_hc: float,
) -> tuple[float, float]:
    """Un pas horaire ISO 13790 → (θ_air, θ_m_t) pour une puissance phi_hc donnée.

    Le plancher bas est couplé au nœud de masse vers ``ground_temp`` (sol),
    via la conductance ``z.h_gr`` — en plus des pertes hors-sol vers ``theta_e``.
    """
    h_ve = max(h_ve, 1e-6)
    h_tr_1 = 1.0 / (1.0 / h_ve + 1.0 / z.h_tr_is)
    h_tr_2 = h_tr_1 + z.h_tr_w
    h_tr_3 = 1.0 / (1.0 / h_tr_2 + 1.0 / z.h_tr_ms)
    theta_sup = theta_e

    phi_ia = 0.5 * z.phi_int
    common = 0.5 * z.phi_int + phi_sol
    phi_st = (1.0 - z.a_m / z.a_t - z.h_tr_w / (H_MS * z.a_t)) * common
    phi_m = (z.a_m / z.a_t) * common

    phi_mtot = (
        phi_m
        + z.h_tr_em * theta_e
        + z.h_gr * ground_temp
        + h_tr_3
        * (phi_st + z.h_tr_w * theta_e + h_tr_1 * ((phi_ia + phi_hc) / h_ve + theta_sup))
        / h_tr_2
    )
    cm_h = z.c_m / 3600.0
    theta_m_t = (theta_m_prev * (cm_h - 0.5 * (h_tr_3 + z.h_tr_em + z.h_gr)) + phi_mtot) / (
        cm_h + 0.5 * (h_tr_3 + z.h_tr_em + z.h_gr)
    )
    theta_m_avg = (theta_m_t + theta_m_prev) / 2.0
    theta_s = (
        z.h_tr_ms * theta_m_avg
        + phi_st
        + z.h_tr_w * theta_e
        + h_tr_1 * (theta_sup + (phi_ia + phi_hc) / h_ve)
    ) / (z.h_tr_ms + z.h_tr_w + h_tr_1)
    theta_air = (z.h_tr_is * theta_s + h_ve * theta_sup + phi_ia + phi_hc) / (z.h_tr_is + h_ve)
    return theta_air, theta_m_t


def _simulate(
    z: _ZoneModel,
    climate: ClimateData,
    h_ve_series: list[float],
    *,
    heating_setpoint: float | None,
    ground_temp: float,
) -> tuple[list[float], float]:
    """Simule l'année. Si `heating_setpoint` est None → free-running (Φ_HC=0).

    Sinon maintient θ_air ≥ setpoint (chauffage illimité, **pas** de
    refroidissement actif). Renvoie (θ_air horaire, énergie de chauffage kWh).
    """
    n = climate.n_hours
    theta_m = 18.0  # init masse
    air = [0.0] * n
    heating_wh = 0.0
    for i in range(n):
        theta_e = climate.dry_bulb_c[i]
        phi_sol = z.phi_sol[i] if i < len(z.phi_sol) else 0.0
        h_ve = h_ve_series[i]
        theta_air0, _ = _step(z, theta_m, theta_e, phi_sol, h_ve, ground_temp, 0.0)
        if heating_setpoint is None or theta_air0 >= heating_setpoint:
            phi_hc = 0.0
        else:
            theta_air10, _ = _step(z, theta_m, theta_e, phi_sol, h_ve, ground_temp, 10.0 * z.a_f)
            denom = theta_air10 - theta_air0
            phi_hc = 0.0 if denom == 0 else 10.0 * z.a_f * (heating_setpoint - theta_air0) / denom
            phi_hc = max(phi_hc, 0.0)
        theta_air, theta_m = _step(z, theta_m, theta_e, phi_sol, h_ve, ground_temp, phi_hc)
        air[i] = theta_air
        heating_wh += phi_hc
    return air, heating_wh / 1000.0


def _h_ve_constant(z: _ZoneModel, ach: float) -> float:
    """Conductance de ventilation (W/K) pour un taux de renouvellement donné."""
    return RHO_C_AIR * ach * z.volume


def _night_cooling_series(z: _ZoneModel, climate: ClimateData, params: R5C1Params) -> list[float]:
    """Série H_ve pour le free-running VNC : hygiénique + boost nocturne utile."""
    base = _h_ve_constant(z, params.hygienic_ach)
    boost = _h_ve_constant(z, params.night_cooling_ach)
    series = [base] * climate.n_hours
    for i in range(climate.n_hours):
        hour = i % 24
        is_night = hour >= 22 or hour < 7
        # boost si nuit, extérieur plus frais et besoin (température douce → été).
        if is_night and climate.dry_bulb_c[i] < 23.0:
            series[i] = boost
    return series


def simulate_5r1c(
    building: Building,
    climate: ClimateData,
    params: R5C1Params | None = None,
    envelope: EnvelopeData | None = None,
) -> ThermalResult:
    """Simule le comportement thermique horaire (5R1C) et renvoie un `ThermalResult`.

    Calcule la pénalité de chauffage VNC (vs VMC DF avec récupération), les heures
    de surchauffe et un bénéfice de night-cooling. Cf. en-tête de module pour les
    réserves de validation.
    """
    params = params or R5C1Params()
    env = envelope or _DEFAULT_ENVELOPE

    # Pré-calcul de l'irradiance verticale par orientation présente.
    irradiance = {
        op.orientation: vertical_irradiance(climate, op.orientation)
        for room in building.rooms
        for op in room.openings
    }

    z = _build_zone(building, env, params, irradiance)

    # Infiltration (sans récupération pour les deux scénarios).
    if params.infiltration_ach is not None:
        inf_ach = params.infiltration_ach
    else:
        n50 = env.air_permeability_ach50 or _DEFAULT_ENVELOPE.air_permeability_ach50 or 1.5
        inf_ach = n50 / 20.0  # règle de division usuelle

    h_inf = _h_ve_constant(z, inf_ach)
    h_hyg = _h_ve_constant(z, params.hygienic_ach)

    # Température de sol : override explicite, sinon moyenne annuelle du climat
    # (ISO 13370 simplifié : le sol profond ≈ T air moyenne annuelle).
    if params.ground_temp_c is not None:
        ground_temp = params.ground_temp_c
    else:
        ground_temp = sum(climate.dry_bulb_c) / climate.n_hours

    # --- Pénalité de chauffage : VNC (sans récup) vs VMC (récup η) ---
    h_ve_vnc = h_inf + h_hyg
    h_ve_vmc = h_inf + h_hyg * (1.0 - params.recovery_efficiency)
    _, heat_vnc = _simulate(
        z,
        climate,
        [h_ve_vnc] * climate.n_hours,
        heating_setpoint=params.heating_setpoint_c,
        ground_temp=ground_temp,
    )
    _, heat_vmc = _simulate(
        z,
        climate,
        [h_ve_vmc] * climate.n_hours,
        heating_setpoint=params.heating_setpoint_c,
        ground_temp=ground_temp,
    )
    penalty_kwh = max(heat_vnc - heat_vmc, 0.0)
    penalty_eur = penalty_kwh * params.heating_energy_price_eur_kwh

    # --- Surchauffe : free-running VNC avec night-cooling ---
    h_ve_summer = _night_cooling_series(z, climate, params)
    air_free, _ = _simulate(
        z, climate, h_ve_summer, heating_setpoint=None, ground_temp=ground_temp
    )
    overheating_hours = sum(1.0 for t in air_free if t > params.comfort_temp_c)
    dh_overheat = sum(max(t - params.comfort_temp_c, 0.0) for t in air_free)

    # --- Bénéfice night-cooling (chaleur évacuée la nuit, proxy) ---
    boost = _h_ve_constant(z, params.night_cooling_ach) - h_hyg
    night_benefit_wh = 0.0
    for i in range(climate.n_hours):
        hour = i % 24
        if (hour >= 22 or hour < 7) and climate.dry_bulb_c[i] < 23.0:
            dt = air_free[i] - climate.dry_bulb_c[i]
            if dt > 0:
                night_benefit_wh += boost * dt
    night_benefit_kwh = max(night_benefit_wh / 1000.0, 0.0)

    return ThermalResult(
        overheating_hours=overheating_hours,
        degree_hours_overheating=dh_overheat,
        night_cooling_benefit_kwh=night_benefit_kwh,
        heating_penalty_kwh_per_year=penalty_kwh,
        heating_penalty_eur_per_year=penalty_eur,
        equivalent_recovery_pct=None,  # dérivé/validé seulement (§7) — non posé
        assumptions={
            "modele": "5R1C ISO 13790 mono-zone (pré-étude, NON validé IDA ICE)",
            "inertie": building.inertia_class.value,
            "recovery_efficiency_vmc": f"{params.recovery_efficiency:.0%}",
            "hygienic_ach": f"{params.hygienic_ach}",
            "infiltration_ach": f"{inf_ach:.2f}",
            "ground_temp_c": f"{ground_temp:.1f}",
            "heating_setpoint_c": f"{params.heating_setpoint_c}",
            "comfort_temp_c": f"{params.comfort_temp_c}",
            "heat_vnc_kwh": f"{heat_vnc:.0f}",
            "heat_vmc_kwh": f"{heat_vmc:.0f}",
            "heating_energy_price_eur_kwh": f"{params.heating_energy_price_eur_kwh}",
            "penalite_note": "différence de deux runs (récup vs non) → robuste aux apports",
        },
    )
