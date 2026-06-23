"""Orchestrateur d'étude : score d'aptitude VNC + pénalité chauffage + ROI.

Pipeline déterministe (CLAUDE.md, décision produit) :
  `geometry` + CPE → `rules` (score) & `thermal` (pénalité degrés-jours) → `roi`.
Plus de STD : la pénalité de chauffage est un calcul en degrés-jours, et le
verdict est un **score** d'aptitude, pas une simulation horaire.
"""

from __future__ import annotations

from zephyr.climate import ClimateData
from zephyr.roi import ROIParameters, compute_roi
from zephyr.roi.sensitivity import tornado
from zephyr.rules import ScoreWeights, evaluate_vnc
from zephyr.schemas import (
    Building,
    EnvelopeData,
    HeatingPenalty,
    ProjectType,
    SiteContext,
    StudyResult,
)
from zephyr.thermal import PenaltyParams, heating_penalty


def _penalty_for_roi(
    penalty: HeatingPenalty, building: Building, roi_params: ROIParameters
) -> float:
    """Pénalité de chauffage (€/an) ramenée à la surface du modèle ROI (intensité)."""
    area = max(building.total_floor_area_m2, 1.0)
    penalty_per_m2 = penalty.eur_per_year / area
    return penalty_per_m2 * roi_params.total_floor_area_m2


def compute_study(
    building: Building,
    climate: ClimateData,
    *,
    roi_params: ROIParameters | None = None,
    envelope: EnvelopeData | None = None,
    site: SiteContext | None = None,
    project_type: ProjectType = ProjectType.MIXTE,
    penalty_params: PenaltyParams | None = None,
    weights: ScoreWeights | None = None,
    with_narrative: bool = False,
) -> StudyResult:
    """Pipeline complet → `StudyResult` : score + pénalité chauffage + ROI.

    Si ``with_narrative`` et qu'une clé API est disponible, ajoute le narratif Opus.
    """
    roi_params = roi_params or ROIParameters()
    envelope = envelope or EnvelopeData()

    result = evaluate_vnc(building, envelope, site, weights)

    penalty = heating_penalty(building, climate, penalty_params)
    result.heating_penalty = penalty

    penalty_roi = _penalty_for_roi(penalty, building, roi_params)
    roi = compute_roi(roi_params, heating_penalty_eur_per_year=penalty_roi)
    roi.sensitivity = tornado(roi_params, heating_penalty_eur_per_year=penalty_roi)
    result.roi = roi
    result.assumptions["surface_ventilee_m2"] = f"{roi_params.total_floor_area_m2:.0f}"
    result.assumptions["type_projet"] = project_type.value

    if with_narrative:
        from zephyr.llm import narrative_available, write_narrative

        if narrative_available():
            result.narrative = write_narrative(result)
    return result
