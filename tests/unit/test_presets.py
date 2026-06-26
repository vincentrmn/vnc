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


def test_cost_preset_scales_with_size() -> None:
    """Forfaits VNC plus petits sur petit projet ; gros tertiaire = défauts."""
    from zephyr.presets import cost_preset_for, heating_price_for
    from zephyr.schemas import ProjectType

    small = cost_preset_for(ProjectType.LOGEMENT, 150)
    large = cost_preset_for(ProjectType.MIXTE, 4200)
    assert small["vnc_bos_platform_eur"] < 25000.0
    assert large == {}  # gros tertiaire garde les forfaits par défaut
    assert heating_price_for("pac") < heating_price_for("electrique")
