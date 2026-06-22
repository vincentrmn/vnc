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
from zephyr.schemas import (
    Building,
    EnvelopeData,
    InertiaClass,
    Orientation,
    Room,
    ThermalResult,
    ZoneResult,
)

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
    internal_gains_w_m2: float = 4.0  # apport constant (fallback si pas de profil)
    # Profils d'occupation horaires (24 valeurs W/m²) — sinon apport constant.
    gains_profile_24h_w_m2: list[float] | None = None
    gains_weekend_24h_w_m2: list[float] | None = None  # si None → profil semaine
    recovery_efficiency: float = 0.80  # rendement échangeur VMC DF (70–90 %)
    glazing_fraction: float = 0.7  # part vitrée d'un ouvrant (cadre)
    shading_factor: float = 0.9  # ombrage moyen
    heating_energy_price_eur_kwh: float = 0.12  # prix énergie de chauffage (€/kWh)
    ground_temp_c: float | None = None  # T sol ; si None → moyenne annuelle du climat
    # Nœud de cœur structurel partagé (dalles/cloisons béton couplant les zones).
    # Couple chaque air de pièce au cœur (W/K par m² plancher de la pièce), le cœur
    # à une capacité (kJ/K par m² plancher total) et au sol (W/K par m² total).
    core_coupling_w_m2k: float = 6.0
    core_capacity_kj_m2k: float = 120.0
    core_ground_coupling_w_m2k: float = 0.5
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
    phi_int: list[float]  # W (apports internes horaires)
    phi_sol: list[float]  # W (apports solaires horaires)


def _room_windows_by_orientation(room: Room) -> dict[Orientation, float]:
    """Surface vitrée d'une pièce par orientation (m²)."""
    out: dict[Orientation, float] = {}
    for op in room.openings:
        out[op.orientation] = out.get(op.orientation, 0.0) + op.area_m2
    return out


def _build_room_zone(
    room: Room,
    inertia: InertiaClass,
    env: EnvelopeData,
    params: R5C1Params,
    irradiance: dict[Orientation, list[float]],
    n_levels: int,
    gains_w_m2: list[float],
) -> _ZoneModel:
    """Construit le 5R1C d'**une pièce** (multi-zone).

    Seules les **surfaces réellement extérieures** de la pièce sont prises en
    compte :
      - façades exposées (orientations de ``exterior_wall_orientations`` ∪ celles
        des ouvrants), une façade ≈ √(surface)·HSP par orientation ;
      - toiture si la pièce est au dernier niveau ;
      - plancher sur sol si la pièce est au RdC (level 0) → couplé à T_sol.
    Les murs/planchers/plafonds intérieurs sont **adiabatiques** (les pièces
    voisines flottent à températures voisines en free-float).
    """
    a_f = room.area_m2
    h = room.height_m
    volume = a_f * h
    side = math.sqrt(max(a_f, 1.0))  # pièce ≈ carrée

    ext_orients = set(room.exterior_wall_orientations) | {op.orientation for op in room.openings}
    windows = _room_windows_by_orientation(room)
    a_w = sum(windows.values())

    gross_wall = len(ext_orients) * side * h
    a_wall_opaque = max(gross_wall - a_w, 0.1 * gross_wall) if gross_wall > 0 else 0.0
    a_roof = a_f if room.level >= n_levels - 1 else 0.0
    a_floor_ground = a_f if room.level <= 0 else 0.0

    u_wall = env.u_wall_w_m2k or _DEFAULT_ENVELOPE.u_wall_w_m2k
    u_roof = env.u_roof_w_m2k or _DEFAULT_ENVELOPE.u_roof_w_m2k
    u_floor = env.u_floor_w_m2k or _DEFAULT_ENVELOPE.u_floor_w_m2k
    u_win = env.u_window_w_m2k or _DEFAULT_ENVELOPE.u_window_w_m2k
    g_win = env.g_window or _DEFAULT_ENVELOPE.g_window
    assert u_wall and u_roof and u_floor and u_win and g_win  # défauts garantis non-None

    h_tr_op = u_wall * a_wall_opaque + u_roof * a_roof  # opaque hors-sol → air
    h_gr = u_floor * a_floor_ground  # plancher → sol (ISO 13370 simplifié)
    h_tr_w = u_win * a_w

    c_m_per_m2, a_m_factor = _INERTIA[inertia]
    c_m = c_m_per_m2 * a_f
    a_m = a_m_factor * a_f
    a_t = LAMBDA_AT * a_f
    h_tr_is = H_IS * a_t
    h_tr_ms = H_MS * a_m
    # H_tr_em : opaque côté masse (garde-fou si pas d'opaque hors-sol).
    if h_tr_op <= 0:
        h_tr_em = 0.0
    elif h_tr_op >= h_tr_ms:
        h_tr_em = h_tr_op
    else:
        h_tr_em = 1.0 / (1.0 / h_tr_op - 1.0 / h_tr_ms)

    # Apports internes horaires (profil d'occupation × surface de la pièce).
    phi_int = [g * a_f for g in gains_w_m2]

    # Apports solaires horaires (somme sur orientations vitrées de la pièce).
    n_hours = len(next(iter(irradiance.values()))) if irradiance else 8760
    phi_sol_total = [0.0] * n_hours
    for orient, area in windows.items():
        irr = irradiance[orient]
        gain_area = g_win * params.glazing_fraction * params.shading_factor * area
        for i in range(n_hours):
            phi_sol_total[i] += gain_area * irr[i]

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
    phi_int: float,
    h_ve: float,
    ground_temp: float,
    phi_hc: float,
    h_int: float = 0.0,
    theta_core: float = 0.0,
) -> tuple[float, float]:
    """Un pas horaire ISO 13790 → (θ_air, θ_m_t) pour une puissance phi_hc donnée.

    Le plancher bas est couplé au nœud de masse vers ``ground_temp`` (sol),
    via la conductance ``z.h_gr`` — en plus des pertes hors-sol vers ``theta_e``.
    Le nœud d'air est en outre couplé au **cœur structurel partagé**
    ``theta_core`` via ``h_int`` (redistribution inter-zones par les dalles).
    """
    h_ve = max(h_ve, 1e-6)
    h_tr_1 = 1.0 / (1.0 / h_ve + 1.0 / z.h_tr_is)
    h_tr_2 = h_tr_1 + z.h_tr_w
    h_tr_3 = 1.0 / (1.0 / h_tr_2 + 1.0 / z.h_tr_ms)
    theta_sup = theta_e

    phi_ia = 0.5 * phi_int
    common = 0.5 * phi_int + phi_sol
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
    theta_air = (z.h_tr_is * theta_s + h_ve * theta_sup + h_int * theta_core + phi_ia + phi_hc) / (
        z.h_tr_is + h_ve + h_int
    )
    return theta_air, theta_m_t


def _gains_series_w_m2(params: R5C1Params, n_hours: int) -> list[float]:
    """Série horaire d'apports internes (W/m²) à partir du profil d'occupation.

    Sans profil → apport constant ``internal_gains_w_m2``. Avec profil 24 h,
    distinction semaine/week-end (alignement calendaire approché : jour 0 =
    premier jour du fichier météo ; sans impact notable sur le bilan annuel).
    """
    if params.gains_profile_24h_w_m2 is None:
        return [params.internal_gains_w_m2] * n_hours
    weekday = params.gains_profile_24h_w_m2
    weekend = params.gains_weekend_24h_w_m2 or weekday
    if len(weekday) != 24 or len(weekend) != 24:
        raise ValueError("Les profils d'apports doivent comporter 24 valeurs horaires.")
    out = [0.0] * n_hours
    for i in range(n_hours):
        prof = weekday if (i // 24) % 7 < 5 else weekend
        out[i] = prof[i % 24]
    return out


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


def _simulate_multizone(
    zones: list[_ZoneModel],
    climate: ClimateData,
    h_ve_per_zone: list[list[float]],
    h_int_per_zone: list[float],
    *,
    heating_setpoint: float | None,
    ground_temp: float,
    c_core: float,
    h_core_ground: float,
) -> tuple[list[list[float]], list[float]]:
    """Simulation multi-zone en lockstep avec **nœud de cœur structurel partagé**.

    À chaque heure : chaque zone est résolue (5R1C) en voyant le cœur retardé
    ``θ_core(t-1)`` via ``h_int`` ; puis le cœur est réactualisé (schéma
    semi-explicite) par les échanges avec toutes les zones + le sol. Le cœur
    représente les dalles/cloisons béton : il stocke et **redistribue** la
    chaleur entre pièces (solaire d'une pièce ensoleillée → pièce aveugle).

    Renvoie (séries θ_air par zone, énergie de chauffage kWh par zone).
    """
    n = climate.n_hours
    nz = len(zones)
    theta_m = [18.0] * nz
    theta_core = ground_temp
    air = [[0.0] * n for _ in range(nz)]
    heating_wh = [0.0] * nz
    dt_over_c = 3600.0 / c_core if c_core > 0 else 0.0

    for i in range(n):
        theta_e = climate.dry_bulb_c[i]
        q_to_core = 0.0
        for j, z in enumerate(zones):
            phi_sol = z.phi_sol[i] if i < len(z.phi_sol) else 0.0
            phi_int = z.phi_int[i] if i < len(z.phi_int) else 0.0
            h_ve = h_ve_per_zone[j][i]
            h_int = h_int_per_zone[j]
            tm = theta_m[j]
            args = (z, tm, theta_e, phi_sol, phi_int, h_ve, ground_temp)
            t_air0, _ = _step(*args, 0.0, h_int, theta_core)
            if heating_setpoint is None or t_air0 >= heating_setpoint:
                phi_hc = 0.0
            else:
                t_air10, _ = _step(*args, 10.0 * z.a_f, h_int, theta_core)
                denom = t_air10 - t_air0
                phi_hc = 0.0 if denom == 0 else 10.0 * z.a_f * (heating_setpoint - t_air0) / denom
                phi_hc = max(phi_hc, 0.0)
            t_air, theta_m[j] = _step(*args, phi_hc, h_int, theta_core)
            air[j][i] = t_air
            heating_wh[j] += phi_hc
            q_to_core += h_int * (t_air - theta_core)
        # Mise à jour du cœur (échanges zones + sol), semi-explicite.
        theta_core += dt_over_c * (q_to_core + h_core_ground * (ground_temp - theta_core))

    return air, [w / 1000.0 for w in heating_wh]


def _core_params(building: Building, params: R5C1Params) -> tuple[float, float, list[float]]:
    """Capacité du cœur, conductance cœur↔sol, et h_int par pièce."""
    area = building.total_floor_area_m2
    c_core = params.core_capacity_kj_m2k * 1000.0 * area
    h_core_ground = params.core_ground_coupling_w_m2k * area
    h_int = [params.core_coupling_w_m2k * r.area_m2 for r in building.rooms]
    return c_core, h_core_ground, h_int


def _infiltration_ach(params: R5C1Params, env: EnvelopeData) -> float:
    """Renouvellement d'air par infiltration (vol/h)."""
    if params.infiltration_ach is not None:
        return params.infiltration_ach
    n50 = env.air_permeability_ach50 or _DEFAULT_ENVELOPE.air_permeability_ach50 or 1.5
    return n50 / 20.0  # règle de division usuelle


def _ground_temp(params: R5C1Params, climate: ClimateData) -> float:
    """Température de sol (ISO 13370 simplifié : ≈ moyenne annuelle de l'air)."""
    if params.ground_temp_c is not None:
        return params.ground_temp_c
    return sum(climate.dry_bulb_c) / climate.n_hours


def _irradiance_for(building: Building, climate: ClimateData) -> dict[Orientation, list[float]]:
    """Irradiance verticale horaire pour chaque orientation vitrée présente."""
    return {
        op.orientation: vertical_irradiance(climate, op.orientation)
        for room in building.rooms
        for op in room.openings
    }


def simulate_free_float(
    building: Building,
    climate: ClimateData,
    params: R5C1Params | None = None,
    envelope: EnvelopeData | None = None,
    ventilation_ach: float | None = None,
) -> list[ZoneResult]:
    """Free-float **passif** par pièce — reproduit le test STD « bâtiment à vide ».

    Aucun chauffage, aucune stratégie de ventilation (pas de night-cooling) :
    seule l'infiltration (ou ``ventilation_ach`` si fourni) agit. Renvoie les
    extrêmes de température opérative par pièce — la grandeur calée sur IDA ICE.
    """
    params = params or R5C1Params()
    env = envelope or _DEFAULT_ENVELOPE
    irr = _irradiance_for(building, climate)
    ground = _ground_temp(params, climate)
    ach = ventilation_ach if ventilation_ach is not None else _infiltration_ach(params, env)
    gains = _gains_series_w_m2(params, climate.n_hours)

    zones = [
        _build_room_zone(r, building.inertia_class, env, params, irr, building.num_levels, gains)
        for r in building.rooms
    ]
    c_core, h_core_ground, h_int = _core_params(building, params)
    h_ve_per_zone = [[_h_ve_constant(z, ach)] * climate.n_hours for z in zones]
    air, _ = _simulate_multizone(
        zones,
        climate,
        h_ve_per_zone,
        h_int,
        heating_setpoint=None,
        ground_temp=ground,
        c_core=c_core,
        h_core_ground=h_core_ground,
    )

    out: list[ZoneResult] = []
    for room, series in zip(building.rooms, air, strict=True):
        oh = sum(1.0 for t in series if t > params.comfort_temp_c)
        out.append(
            ZoneResult(
                zone_id=room.id, top_min_c=min(series), top_max_c=max(series), overheating_hours=oh
            )
        )
    return out


def simulate_5r1c(
    building: Building,
    climate: ClimateData,
    params: R5C1Params | None = None,
    envelope: EnvelopeData | None = None,
) -> ThermalResult:
    """Simule le comportement thermique horaire (5R1C **multi-zone**).

    Pour chaque pièce : pénalité de chauffage VNC vs VMC DF (récup η), heures de
    surchauffe (free-running + night-cooling) et extrêmes de température. Agrège
    au bâtiment. Cf. en-tête de module pour les réserves de validation.
    """
    params = params or R5C1Params()
    env = envelope or _DEFAULT_ENVELOPE
    irr = _irradiance_for(building, climate)
    ground = _ground_temp(params, climate)
    inf_ach = _infiltration_ach(params, env)
    n = climate.n_hours
    gains = _gains_series_w_m2(params, n)

    zone_models = [
        _build_room_zone(r, building.inertia_class, env, params, irr, building.num_levels, gains)
        for r in building.rooms
    ]
    c_core, h_core_ground, h_int = _core_params(building, params)

    nz = len(zone_models)
    h_inf = [_h_ve_constant(z, inf_ach) for z in zone_models]
    h_hyg = [_h_ve_constant(z, params.hygienic_ach) for z in zone_models]

    def run(
        h_ve_per_zone: list[list[float]], setpoint: float | None
    ) -> tuple[list[list[float]], list[float]]:
        return _simulate_multizone(
            zone_models,
            climate,
            h_ve_per_zone,
            h_int,
            heating_setpoint=setpoint,
            ground_temp=ground,
            c_core=c_core,
            h_core_ground=h_core_ground,
        )

    # Pénalité de chauffage : VNC (sans récup) vs VMC (récup η).
    eff = params.recovery_efficiency
    setpoint = params.heating_setpoint_c
    _, heat_vnc = run([[h_inf[j] + h_hyg[j]] * n for j in range(nz)], setpoint)
    _, heat_vmc = run([[h_inf[j] + h_hyg[j] * (1.0 - eff)] * n for j in range(nz)], setpoint)

    # Surchauffe : free-running VNC avec night-cooling.
    air_free, _ = run([_night_cooling_series(z, climate, params) for z in zone_models], None)

    penalty_kwh = 0.0
    overheating_max = 0.0
    dh_max = 0.0
    night_benefit_kwh = 0.0
    zones: list[ZoneResult] = []
    for j, room in enumerate(building.rooms):
        series = air_free[j]
        zone_penalty = max(heat_vnc[j] - heat_vmc[j], 0.0)
        penalty_kwh += zone_penalty
        oh = sum(1.0 for t in series if t > params.comfort_temp_c)
        dh = sum(max(t - params.comfort_temp_c, 0.0) for t in series)
        overheating_max = max(overheating_max, oh)
        dh_max = max(dh_max, dh)
        boost = _h_ve_constant(zone_models[j], params.night_cooling_ach) - h_hyg[j]
        for i in range(n):
            hour = i % 24
            if (hour >= 22 or hour < 7) and climate.dry_bulb_c[i] < 23.0:
                dt = series[i] - climate.dry_bulb_c[i]
                if dt > 0:
                    night_benefit_kwh += boost * dt / 1000.0
        zones.append(
            ZoneResult(
                zone_id=room.id,
                top_min_c=min(series),
                top_max_c=max(series),
                overheating_hours=oh,
                heating_vnc_kwh=heat_vnc[j],
                heating_penalty_kwh=zone_penalty,
            )
        )

    heat_vnc_total = sum(heat_vnc)
    heat_vmc_total = sum(heat_vmc)

    return ThermalResult(
        overheating_hours=overheating_max,
        degree_hours_overheating=dh_max,
        night_cooling_benefit_kwh=max(night_benefit_kwh, 0.0),
        heating_penalty_kwh_per_year=penalty_kwh,
        heating_penalty_eur_per_year=penalty_kwh * params.heating_energy_price_eur_kwh,
        equivalent_recovery_pct=None,  # dérivé/validé seulement (§7) — non posé
        zones=zones,
        assumptions={
            "modele": "5R1C ISO 13790 MULTI-ZONE (pré-étude, NON validé IDA ICE)",
            "n_zones": str(len(zones)),
            "inertie": building.inertia_class.value,
            "murs_interieurs": "adiabatiques (free-float : pièces voisines ≈ même T)",
            "recovery_efficiency_vmc": f"{params.recovery_efficiency:.0%}",
            "hygienic_ach": f"{params.hygienic_ach}",
            "infiltration_ach": f"{inf_ach:.2f}",
            "ground_temp_c": f"{ground:.1f}",
            "heating_setpoint_c": f"{params.heating_setpoint_c}",
            "comfort_temp_c": f"{params.comfort_temp_c}",
            "heat_vnc_kwh": f"{heat_vnc_total:.0f}",
            "heat_vmc_kwh": f"{heat_vmc_total:.0f}",
            "heating_energy_price_eur_kwh": f"{params.heating_energy_price_eur_kwh}",
            "penalite_note": "différence de deux runs (récup vs non) → robuste aux apports",
        },
    )
