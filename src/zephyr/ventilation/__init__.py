"""Module `ventilation` — débits naturels & dimensionnement ouvrants (Phase 2).

Calcule les débits induits par tirage thermique (∝ √(Δh·ΔT)) et par le vent,
dimensionne les ouvrants et effectue les vérifications géométriques. numpy pur.
"""

from __future__ import annotations

from dataclasses import dataclass

from zephyr.climate import ClimateData
from zephyr.schemas import Building


@dataclass
class VentilationResult:
    """Résultat du calcul de ventilation naturelle (à étoffer en Phase 2)."""

    stack_flow_m3h: float
    wind_flow_m3h: float
    achievable_ach: float


def natural_airflow(building: Building, climate: ClimateData) -> VentilationResult:
    """Estime les débits naturels (tirage + vent) du bâtiment.

    Raises:
        NotImplementedError: à implémenter en Phase 2.
    """
    raise NotImplementedError("ventilation.natural_airflow — Phase 2")
