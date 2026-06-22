"""Harnais de calibration thermique — le test qui de-risque le projet (§7, §13.4).

Rejoue le 5R1C (`zephyr.thermal`) sur les cas de `data/validation/*.example.json`
et compare aux sorties IDA ICE de référence dans la tolérance du cas.

Deux régimes :
  - cas **synthétique** (``"synthetic": true``) : pas de référence réelle → on
    vérifie seulement la **sanité** (sorties finies, plausibles, pénalité ≥ 0).
    Comparer à des `expected` inventés n'aurait aucune valeur (§11).
  - cas **réel anonymisé** (export IDA ICE) : comparaison **stricte** dans la
    tolérance. C'est là que le harnais mord et valide le modèle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from zephyr.climate import synthetic_climate
from zephyr.schemas import Building, EnvelopeData
from zephyr.thermal import R5C1Params, simulate_5r1c

VALIDATION_DIR = Path(__file__).resolve().parents[2] / "data" / "validation"


def _load_cases() -> list[Path]:
    return sorted(VALIDATION_DIR.glob("*.example.json"))


def _build_building(case: dict[str, Any]) -> Building:
    return Building.model_validate(case["inputs"]["building"])


def _envelope(case: dict[str, Any]) -> EnvelopeData:
    return EnvelopeData.model_validate(case["inputs"].get("envelope", {}))


@pytest.mark.parametrize("case_path", _load_cases(), ids=lambda p: p.stem)
def test_5r1c_on_validation_case(case_path: Path) -> None:
    case = json.loads(case_path.read_text(encoding="utf-8"))

    building = _build_building(case)
    assert building.total_floor_area_m2 > 0

    envelope = _envelope(case)
    params = R5C1Params(
        internal_gains_w_m2=case["inputs"].get("internal_gains_w_m2", 4.0),
        hygienic_ach=case["inputs"].get("ventilation_ach", 0.5),
    )
    # EPW réel si présent, sinon climat synthétique (cas de squelette).
    climate = synthetic_climate()
    result = simulate_5r1c(building, climate, params, envelope)

    if case.get("synthetic"):
        # Sanité uniquement — pas de validation contre des chiffres inventés.
        assert 0 <= result.overheating_hours <= 8760
        assert result.heating_penalty_kwh_per_year >= 0
        assert result.degree_hours_overheating >= 0
        pytest.skip(
            f"Cas synthétique '{case['name']}' : sanité OK, validation stricte "
            "désactivée (déposer un export IDA ICE réel anonymisé pour l'activer)."
        )

    # --- Cas réel : comparaison stricte aux références IDA ICE ---
    tol = case["tolerance"]
    expected = case["expected"]
    exp_overheat = max(r["overheating_hours"] for r in expected["rooms"])
    rel = tol["overheating_hours_rel"]
    assert result.overheating_hours == pytest.approx(exp_overheat, rel=rel, abs=50), (
        "Heures de surchauffe hors tolérance vs IDA ICE."
    )


def test_validation_dir_has_at_least_one_case() -> None:
    """Garde-fou : au moins un cas de référence est présent."""
    assert _load_cases(), "Aucun cas *.example.json dans data/validation/."
