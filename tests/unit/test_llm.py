"""Tests du module `llm` (narratif) — sans appel API.

On teste la construction du prompt (pur) et les garde-fous, pas l'appel réseau.
"""

from __future__ import annotations

import json
from typing import Any

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.llm import (
    MODEL_NARRATIVE,
    build_narrative_messages,
    narrative_available,
)
from zephyr.schemas import StudyResult
from zephyr.study import compute_study


def _result() -> StudyResult:
    return compute_study(parametric_building(300.0), synthetic_climate())


def test_model_is_opus() -> None:
    assert MODEL_NARRATIVE == "claude-opus-4-8"


def test_narrative_payload_only_contains_provided_numbers() -> None:
    res = _result()
    system, messages = build_narrative_messages(res)
    # Le système est statique et caché (prompt caching).
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "inventer" not in system[0]["text"].lower() or "n'invente" in system[0]["text"].lower()

    # Le user contient un JSON des chiffres réels (verdict, roi, thermique).
    text = messages[0]["text"]
    payload = json.loads(text.split("\n", 1)[1])
    assert payload["verdict"] == res.verdict.value
    assert "roi" in payload and "thermique" in payload
    # Les chiffres correspondent au résultat (pas d'invention).
    assert payload["roi"]["capex_vnc_eur"] == round(res.roi.capex_vnc_eur)
    assert payload["thermique"]["penalite_chauffage_eur_an"] == round(
        res.thermal.heating_penalty_eur_per_year
    )


def test_narrative_available_false_without_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert narrative_available() is False
