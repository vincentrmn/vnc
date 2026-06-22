"""Orchestrateur d'étude : branche le thermique sur le ROI (boucle §6).

C'est ici que la **pénalité de chauffage calculée** par `thermal` alimente le
`roi` — fin de la valeur posée à la main (CLAUDE.md §6, §13.3). Le module reste
volontairement mince : le verdict `rules` et le narratif `llm` viendront s'y
greffer plus tard pour produire un `StudyResult` complet.
"""

from __future__ import annotations

from zephyr.climate import ClimateData
from zephyr.roi import ROIParameters, compute_roi
from zephyr.roi.sensitivity import tornado
from zephyr.rules import evaluate_feasibility
from zephyr.schemas import (
    Building,
    EnvelopeData,
    ROIResult,
    SiteContext,
    StudyResult,
    ThermalResult,
)
from zephyr.thermal import R5C1Params, simulate_5r1c
from zephyr.ventilation import VentilationParams, natural_airflow


def _penalty_for_roi(
    thermal: ThermalResult, building: Building, roi_params: ROIParameters
) -> float:
    """Pénalité de chauffage (€/an) à l'échelle du modèle ROI (intensité physique)."""
    area = max(building.total_floor_area_m2, 1.0)
    penalty_per_m2 = thermal.heating_penalty_eur_per_year / area
    return penalty_per_m2 * roi_params.total_floor_area_m2


def compute_roi_from_building(
    building: Building,
    climate: ClimateData,
    roi_params: ROIParameters | None = None,
    thermal_params: R5C1Params | None = None,
    envelope: EnvelopeData | None = None,
    *,
    with_sensitivity: bool = True,
) -> tuple[ThermalResult, ROIResult]:
    """Calcule le thermique puis le ROI, **pénalité de chauffage calculée incluse**.

    La pénalité est exprimée en €/m²/an par `thermal` (sur le bâtiment simulé)
    puis appliquée à la surface du modèle ROI — ce qui permet à `roi` de garder
    ses propres hypothèses de surface (paramétriques) tout en consommant
    l'intensité de pénalité issue de la physique.

    ⚠️ Pénalité actuellement **directionnelle** (ballpark), pas encore calée
    finement contre le besoin de chauffage STD. Cf. docs/COMMENT_CA_MARCHE.md.
    """
    roi_params = roi_params or ROIParameters()
    thermal = simulate_5r1c(building, climate, thermal_params, envelope)
    penalty_roi = _penalty_for_roi(thermal, building, roi_params)

    roi = compute_roi(roi_params, heating_penalty_eur_per_year=penalty_roi)
    roi.assumptions["heating_penalty_source"] = (
        f"calculée par thermal : {penalty_roi / roi_params.total_floor_area_m2:.2f} €/m²/an "
        f"× {roi_params.total_floor_area_m2:.0f} m² (directionnelle)"
    )
    if with_sensitivity:
        roi.sensitivity = tornado(roi_params, heating_penalty_eur_per_year=penalty_roi)
    return thermal, roi


def compute_study(
    building: Building,
    climate: ClimateData,
    roi_params: ROIParameters | None = None,
    thermal_params: R5C1Params | None = None,
    vent_params: VentilationParams | None = None,
    envelope: EnvelopeData | None = None,
    site: SiteContext | None = None,
) -> StudyResult:
    """Pipeline complet → `StudyResult` : thermal + ventilation + rules + roi.

    Thermique exécuté une seule fois et réutilisé (pénalité ROI + verdict). Le
    narratif LLM (`llm`) et le rapport (`report`) viendront se greffer ensuite.
    """
    roi_params = roi_params or ROIParameters()
    thermal = simulate_5r1c(building, climate, thermal_params, envelope)
    ventilation = natural_airflow(building, climate, vent_params)

    result = evaluate_feasibility(building, thermal, ventilation, site)

    penalty_roi = _penalty_for_roi(thermal, building, roi_params)
    roi = compute_roi(roi_params, heating_penalty_eur_per_year=penalty_roi)
    roi.sensitivity = tornado(roi_params, heating_penalty_eur_per_year=penalty_roi)
    result.roi = roi
    result.assumptions["surface_ventilee_m2"] = f"{roi_params.total_floor_area_m2:.0f}"
    return result
