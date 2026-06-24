"""Tests du module `llm` (narratif) — sans appel API.

On teste la construction du prompt (pur) et les garde-fous, pas l'appel réseau.
"""

from __future__ import annotations

import json
from typing import Any

from zephyr.builders import parametric_building
from zephyr.climate import synthetic_climate
from zephyr.llm import (
    MODEL_LABELLING,
    MODEL_NARRATIVE,
    build_cpe_messages,
    build_narrative_messages,
    narrative_available,
    parse_cpe_response,
    verify_cpe_extraction,
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

    # Le user contient un JSON des chiffres réels (verdict, score, roi, surcoût).
    text = messages[0]["text"]
    payload = json.loads(text.split("\n", 1)[1])
    assert payload["verdict"] == res.verdict.value
    assert "roi" in payload and "score" in payload and "surcout_chauffage" in payload
    # Les chiffres correspondent au résultat (pas d'invention).
    assert res.roi is not None and res.heating_penalty is not None
    assert payload["roi"]["capex_vnc_eur"] == round(res.roi.capex_vnc_eur)
    assert payload["surcout_chauffage"]["eur_an"] == round(res.heating_penalty.eur_per_year)


def test_narrative_available_false_without_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert narrative_available() is False


# --- Extraction CPE (hybride) : on teste le pur + la vérif verbatim, sans API. ---

_CPE_TEXT = (
    "Surface de référence énergétique | 739,3 m² | Année de construction | 2026 | "
    "Bauteil Name: Mur extérieur valeur U 0,18 W/(m²K) | Dalle béton 20,0 cm | "
    "Fenster Uw 0,90 | Luftdichtheitswert n50 | 0,60 | h-1"
)


def test_cpe_messages_static_system_and_model() -> None:
    assert MODEL_LABELLING == "claude-sonnet-4-6"
    system, user = build_cpe_messages(_CPE_TEXT)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "N'INVENTE AUCUN CHIFFRE" in system[0]["text"]
    assert _CPE_TEXT in user[0]["text"]


def test_parse_cpe_response_tolerates_code_fence() -> None:
    parsed = parse_cpe_response('```json\n{"u_wall_w_m2k": {"value": 0.18}}\n```')
    assert parsed["u_wall_w_m2k"]["value"] == 0.18


def test_verify_keeps_grounded_numbers_and_drops_hallucinated() -> None:
    parsed = {
        "u_wall_w_m2k": {"value": 0.18, "source": "valeur U 0,18 W/(m²K)"},
        "u_window_w_m2k": {"value": 0.90, "source": "Fenster Uw 0,90"},
        "air_permeability_ach50": {"value": 0.60, "source": "n50 | 0,60 | h-1"},
        "floor_area_m2": {"value": 739.3, "source": "739,3 m²"},
        "construction_year": {"value": 2026, "source": "Année de construction | 2026"},
        "inertia_class": {"value": "lourde", "source": "Dalle béton"},
        "u_roof_w_m2k": {"value": 0.99, "source": "inventé"},  # absent du texte
    }
    ext = verify_cpe_extraction(parsed, _CPE_TEXT)
    assert ext.u_wall_w_m2k == 0.18  # virgule décimale retrouvée
    assert ext.u_window_w_m2k == 0.90 and ext.air_permeability_ach50 == 0.60
    assert ext.floor_area_m2 == 739.3 and ext.construction_year == 2026
    assert ext.inertia_class is not None and ext.inertia_class.value == "lourde"
    assert ext.u_roof_w_m2k is None  # hallucination écartée
    assert any("u_roof_w_m2k" in n for n in ext.notes)
    assert ext.sources["u_wall_w_m2k"] == "valeur U 0,18 W/(m²K)"


def test_verify_no_false_positive_on_rounding() -> None:
    # 0,18 ne doit pas être "validé" par un 0,2 présent ailleurs dans le texte.
    parsed = {"u_wall_w_m2k": {"value": 0.18, "source": "x"}}
    assert verify_cpe_extraction(parsed, "rendement 0,2 et 0,5").u_wall_w_m2k is None
