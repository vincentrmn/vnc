"""Harnais de calibration thermique — le test qui de-risque le projet (§7, §13.4).

Rejoue le 5R1C (`zephyr.thermal`) sur les cas de `data/validation/*.example.json`
et compare aux sorties IDA ICE de référence dans la tolérance du cas.

Régimes :
  - cas **synthétique** (``"synthetic": true``) : pas de référence réelle → on
    vérifie seulement la **sanité**. Comparer à des `expected` inventés n'aurait
    aucune valeur (§11).
  - cas **free-float réel** (``"kind": "free_float"``) : « bâtiment à vide »,
    comparaison **stricte** des températures opératives min/max par pièce dans la
    tolérance. C'est là que le harnais mord et valide le modèle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from zephyr.climate import ClimateData, read_epw, synthetic_climate
from zephyr.schemas import Building, EnvelopeData
from zephyr.thermal import R5C1Params, simulate_5r1c, simulate_free_float

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = REPO_ROOT / "data" / "validation"


def _load_cases() -> list[Path]:
    return sorted(VALIDATION_DIR.glob("*.example.json"))


def _climate(case: dict[str, Any]) -> ClimateData:
    epw = case.get("climate_epw")
    if epw and (REPO_ROOT / epw).exists():
        return read_epw(REPO_ROOT / epw)
    return synthetic_climate()


@pytest.mark.parametrize("case_path", _load_cases(), ids=lambda p: p.stem)
def test_5r1c_on_validation_case(case_path: Path) -> None:
    case = json.loads(case_path.read_text(encoding="utf-8"))

    # --- Cas synthétique (squelette) : sanité uniquement ---
    if case.get("synthetic"):
        building = Building.model_validate(case["inputs"]["building"])
        result = simulate_5r1c(building, synthetic_climate())
        assert 0 <= result.overheating_hours <= 8760
        assert result.heating_penalty_kwh_per_year >= 0
        pytest.skip(f"Cas synthétique '{case['name']}' : sanité OK, pas de réf réelle.")

    # --- Cas free-float réel : comparaison Top min/max par pièce ---
    if case.get("kind") == "free_float":
        building = Building.model_validate(case["building"])
        envelope = EnvelopeData.model_validate(case.get("envelope", {}))
        params = R5C1Params(**case.get("params", {}))
        climate = _climate(case)
        zones = {
            z.zone_id: z
            for z in simulate_free_float(
                building, climate, params, envelope, ventilation_ach=case.get("ventilation_ach")
            )
        }
        tol = case["tolerance"]["top_c"]
        for exp in case["expected"]["rooms"]:
            z = zones[exp["id"]]
            assert abs(z.top_min_c - exp["top_min_c"]) <= tol, (
                f"{exp['id']} Top min {z.top_min_c:.1f} vs {exp['top_min_c']} (tol {tol})"
            )
            assert abs(z.top_max_c - exp["top_max_c"]) <= tol, (
                f"{exp['id']} Top max {z.top_max_c:.1f} vs {exp['top_max_c']} (tol {tol})"
            )
        return

    pytest.skip(f"Type de cas non reconnu : {case_path.name}")


def test_validation_dir_has_at_least_one_case() -> None:
    """Garde-fou : au moins un cas de référence est présent."""
    assert _load_cases(), "Aucun cas *.example.json dans data/validation/."
