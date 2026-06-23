"""Presets par type de projet (pénalité de chauffage, pondérations de score).

Le moteur est déterministe et le même pour tous les bâtiments ; ce qui change,
c'est le **débit hygiénique de référence** (plus élevé en bureau occupé) et,
éventuellement, les **pondérations** du score. Tout est surchargeable.
"""

from __future__ import annotations

from zephyr.rules import ScoreWeights
from zephyr.schemas import ProjectType
from zephyr.thermal import PenaltyParams


def penalty_params_for(project_type: ProjectType, **overrides: object) -> PenaltyParams:
    """Hypothèses de pénalité de chauffage selon le type de projet.

    Le bureau occupé demande plus d'air neuf (débit hygiénique plus élevé) → la
    part non récupérée par la VNC est plus grande.
    """
    base: dict[str, object] = {"hygienic_ach": 0.5}
    if project_type is ProjectType.BUREAU:
        base["hygienic_ach"] = 1.0
    elif project_type is ProjectType.SCOLAIRE:
        base["hygienic_ach"] = 1.2
    elif project_type is ProjectType.MIXTE:
        base["hygienic_ach"] = 0.7
    base.update(overrides)
    return PenaltyParams(**base)  # type: ignore[arg-type]


def score_weights_for(project_type: ProjectType) -> ScoreWeights:
    """Pondérations du score (par défaut identiques ; point d'ajustement futur)."""
    return ScoreWeights()
