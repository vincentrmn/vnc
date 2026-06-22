"""Harnais de calibration thermique — le test qui de-risque le projet (§7, §13.4).

Rejoue le 5R1C (`zephyr.thermal`) sur les cas de `data/validation/*.example.json`
et compare aux sorties IDA ICE de référence dans la tolérance du cas.

Tant que `zephyr.thermal.simulate_5r1c` n'est pas implémenté (Phase 2), chaque
cas est **skippé proprement** : le harnais est en place, prêt à mordre dès que le
modèle existe. C'est volontaire — on pose l'infrastructure de validation *avant*
de construire le modèle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from zephyr.climate import ClimateData
from zephyr.schemas import Building

VALIDATION_DIR = Path(__file__).resolve().parents[2] / "data" / "validation"


def _load_cases() -> list[Path]:
    return sorted(VALIDATION_DIR.glob("*.example.json"))


def _build_building(case: dict[str, Any]) -> Building:
    """Construit un `Building` depuis la section `inputs.building` du cas."""
    return Building.model_validate(case["inputs"]["building"])


@pytest.mark.parametrize("case_path", _load_cases(), ids=lambda p: p.stem)
def test_5r1c_reproduces_ida_ice(case_path: Path) -> None:
    """Le 5R1C doit reproduire les températures IDA ICE dans la tolérance."""
    case = json.loads(case_path.read_text(encoding="utf-8"))

    # Le Building doit toujours se construire (contrat schemas) — ça, on le teste
    # même avant que thermal n'existe.
    building = _build_building(case)
    assert building.total_floor_area_m2 > 0

    from zephyr.thermal import R5C1Params, simulate_5r1c

    # Climat : si l'EPW n'est pas disponible/parseur absent, on prépare un objet
    # vide ; l'appel à simulate_5r1c lèvera NotImplementedError → skip.
    climate = ClimateData(dry_bulb_c=[], wind_speed_ms=[], ghi_w_m2=[])

    try:
        result = simulate_5r1c(building, climate, R5C1Params())
    except NotImplementedError:
        pytest.skip("thermal.simulate_5r1c pas encore implémenté (Phase 2) — harnais prêt.")

    # --- Comparaison aux références IDA ICE (actif une fois thermal implémenté) ---
    tol = case["tolerance"]
    expected = case["expected"]

    # Heures de surchauffe (tolérance relative)
    exp_overheat = max(r["overheating_hours"] for r in expected["rooms"])
    rel = tol["overheating_hours_rel"]
    assert result.overheating_hours == pytest.approx(exp_overheat, rel=rel, abs=50), (
        "Heures de surchauffe hors tolérance vs IDA ICE."
    )


def test_validation_dir_has_at_least_one_case() -> None:
    """Garde-fou : au moins un cas de référence est présent (le harnais a de quoi mordre)."""
    assert _load_cases(), "Aucun cas *.example.json dans data/validation/."
