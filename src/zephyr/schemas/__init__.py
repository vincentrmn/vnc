"""Schémas transverses Zéphyr (pydantic v2) — le contrat entre modules.

Cf. CLAUDE.md §13.2. Tout passe par ces objets : géométrie (`Building`),
entrée d'étude (`StudyInput`), sorties (`ThermalResult`, `ROIResult`,
`StudyResult`).
"""

from zephyr.schemas.building import (
    Building,
    InertiaClass,
    Opening,
    OpeningKind,
    Orientation,
    Room,
    RoomLabel,
    SolarProtection,
)
from zephyr.schemas.cpe import CpeExtraction
from zephyr.schemas.results import (
    CalcLine,
    HeatingPenalty,
    Range,
    ROIResult,
    ScoreBreakdown,
    ScoreCriterion,
    SensitivityEntry,
    StudyResult,
    Verdict,
    VNCScore,
)
from zephyr.schemas.study import EnvelopeData, ProjectType, SiteContext, StudyInput

__all__ = [
    # building
    "Building",
    "InertiaClass",
    "Opening",
    "OpeningKind",
    "Orientation",
    "Room",
    "RoomLabel",
    "SolarProtection",
    # cpe
    "CpeExtraction",
    # study
    "EnvelopeData",
    "ProjectType",
    "SiteContext",
    "StudyInput",
    # results
    "CalcLine",
    "HeatingPenalty",
    "Range",
    "ROIResult",
    "ScoreBreakdown",
    "ScoreCriterion",
    "SensitivityEntry",
    "StudyResult",
    "Verdict",
    "VNCScore",
]
