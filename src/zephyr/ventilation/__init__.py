"""Module `ventilation` — débits naturels (tirage + vent) & dimensionnement.

Vérifie que la VNC peut **physiquement** assurer les débits visés (hygiénique et
free-cooling), à partir des forces naturelles :

- **Tirage thermique** (effet cheminée) : ∝ √(Δh · ΔT) — différence de hauteur
  entre entrées basses et sorties hautes × écart de température.
- **Vent** : ∝ vitesse du vent × surface ouvrable.

Niveau pré-étude : formules d'ingénierie simplifiées (CIBSE/AIVC), bâtiment
mono-bloc. Le but est de *disqualifier* ou *qualifier*, pas de dimensionner au
m³/h près. numpy non requis (calcul scalaire).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from zephyr.climate import ClimateData
from zephyr.schemas import Building

G = 9.81  # m/s²


@dataclass
class VentilationParams:
    """Conditions de dimensionnement de la ventilation naturelle."""

    cd: float = 0.6  # coefficient de décharge des ouvrants
    cv_wind: float = 0.20  # efficacité du vent (différence de Cp moyenne)
    design_delta_t_k: float = 3.0  # écart T int/ext de dimensionnement (nuit d'été)
    design_wind_ms: float | None = None  # sinon vent moyen du climat
    target_freecool_ach: float = 4.0  # cible de rafraîchissement passif (vol/h)
    hygienic_ach: float = 0.5  # débit hygiénique mini (vol/h)
    default_stack_height_m: float = 2.5  # Δh de repli si hauteurs d'ouvrants absentes


@dataclass
class VentilationResult:
    """Débits naturels atteignables + verdicts de dimensionnement."""

    openable_area_m2: float
    stack_height_m: float
    design_wind_ms: float
    stack_flow_m3h: float
    wind_flow_m3h: float
    combined_flow_m3h: float
    achievable_ach: float
    hygienic_ach: float
    target_freecool_ach: float
    meets_hygienic: bool
    meets_freecool: bool
    assumptions: dict[str, str] = field(default_factory=dict)


def _openable_free_area(building: Building) -> float:
    """Surface libre cumulée des ouvrants motorisables (m²)."""
    return building.total_openable_area_m2


def _stack_height(building: Building, params: VentilationParams) -> float:
    """Hauteur de tirage Δh (m) entre entrées basses et sorties hautes.

    Estimée depuis les hauteurs absolues des ouvrants motorisables (niveau ×
    HSP + allège/linteau) ; repli sur ``default_stack_height_m``.
    """
    lows: list[float] = []
    highs: list[float] = []
    for room in building.rooms:
        base = room.level * room.height_m
        for op in room.openings:
            if not op.openable:
                continue
            lows.append(base + op.sill_height_m)
            head = op.head_height_m if op.head_height_m is not None else op.sill_height_m + 1.0
            highs.append(base + head)
    if not lows or not highs:
        return params.default_stack_height_m
    dh = max(highs) - min(lows)
    return max(dh, 0.5)


def natural_airflow(
    building: Building,
    climate: ClimateData,
    params: VentilationParams | None = None,
) -> VentilationResult:
    """Estime les débits naturels (tirage + vent) et les confronte aux cibles.

    Combinaison tirage/vent en quadrature (Q = √(Q_tirage² + Q_vent²)), usuelle
    en ventilation naturelle. Les débits sont rapportés au volume du bâtiment
    pour un taux de renouvellement (ACH) atteignable.
    """
    params = params or VentilationParams()
    volume = max(building.total_volume_m3, 1.0)
    a_free = _openable_free_area(building)
    dh = _stack_height(building, params)

    wind = params.design_wind_ms
    if wind is None:
        wind = (
            sum(climate.wind_speed_ms) / len(climate.wind_speed_ms)
            if climate.wind_speed_ms
            else 3.0
        )

    # Surface effective : entrées ≈ sorties ≈ A_free/2, en série → A_free/(2√2).
    a_eff = a_free / (2.0 * math.sqrt(2.0))

    # Tirage thermique : Q = Cd · A_eff · √(2 g Δh ΔT / T_moy).  [m³/s → m³/h]
    t_avg_k = 293.0  # ~20 °C, référence absolue
    stack_ms = params.cd * a_eff * math.sqrt(2.0 * G * dh * params.design_delta_t_k / t_avg_k)
    stack_m3h = stack_ms * 3600.0

    # Vent : Q = Cv · A_eff · v.  [m³/s → m³/h]
    wind_m3h = params.cv_wind * a_eff * wind * 3600.0

    combined_m3h = math.hypot(stack_m3h, wind_m3h)
    achievable_ach = combined_m3h / volume

    return VentilationResult(
        openable_area_m2=a_free,
        stack_height_m=dh,
        design_wind_ms=wind,
        stack_flow_m3h=stack_m3h,
        wind_flow_m3h=wind_m3h,
        combined_flow_m3h=combined_m3h,
        achievable_ach=achievable_ach,
        hygienic_ach=params.hygienic_ach,
        target_freecool_ach=params.target_freecool_ach,
        meets_hygienic=achievable_ach >= params.hygienic_ach,
        meets_freecool=achievable_ach >= params.target_freecool_ach,
        assumptions={
            "modele": "ventilation naturelle simplifiée (tirage + vent, quadrature)",
            "surface_ouvrable_m2": f"{a_free:.1f}",
            "hauteur_tirage_m": f"{dh:.1f}",
            "delta_t_dimensionnement_k": f"{params.design_delta_t_k}",
            "vent_dimensionnement_ms": f"{wind:.1f}",
            "cd": f"{params.cd}",
            "cv_wind": f"{params.cv_wind}",
        },
    )
