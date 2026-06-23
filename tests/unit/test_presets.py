"""Tests des presets par type de projet (pénalité de chauffage, pondérations)."""

from __future__ import annotations

from zephyr.presets import penalty_params_for, score_weights_for
from zephyr.rules import ScoreWeights
from zephyr.schemas import ProjectType


def test_office_has_higher_hygienic_airflow() -> None:
    assert penalty_params_for(ProjectType.BUREAU).hygienic_ach == 1.0
    assert penalty_params_for(ProjectType.LOGEMENT).hygienic_ach == 0.5
    assert penalty_params_for(ProjectType.MIXTE).hygienic_ach == 0.7


def test_overrides_apply() -> None:
    p = penalty_params_for(ProjectType.LOGEMENT, recovery_efficiency=0.7)
    assert p.recovery_efficiency == 0.7


def test_score_weights_default() -> None:
    w = score_weights_for(ProjectType.LOGEMENT)
    assert isinstance(w, ScoreWeights)
    assert w.ventilation > 0
