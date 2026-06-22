"""Module `thermal` — modèle 5R1C (inertie) (Phase 2).

Cœur du screen thermique (CLAUDE.md §7). Calcule, à partir du `Building` et du
climat :
  - les heures de surchauffe (degrés-heures au-dessus du confort) ;
  - le bénéfice du night-cooling VNC ;
  - et surtout la **pénalité de chauffage VNC** = besoin de chauffage
    différentiel dû à l'absence d'échangeur air-air, **atténué** par commande à
    la demande, inertie lourde et scheduling. Ce terme est **calculé**, jamais
    postulé (CLAUDE.md §2.5, §5).

Toute évolution est validée contre `data/validation/` (exports IDA ICE) via
`tests/validation/` — c'est le test qui de-risque le projet (§7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zephyr.climate import ClimateData
from zephyr.schemas import Building, ThermalResult


@dataclass
class R5C1Params:
    """Paramètres du réseau 5R1C (ISO 52016/13790).

    Renseignés depuis l'enveloppe (`StudyInput.envelope`) et l'inertie du
    `Building`. Valeurs par défaut à caler en Phase 2 contre IDA ICE.
    """

    comfort_temp_c: float = 26.0
    heating_setpoint_c: float = 20.0
    hygienic_ach: float = 0.5
    extra: dict[str, float] = field(default_factory=dict)


def simulate_5r1c(
    building: Building,
    climate: ClimateData,
    params: R5C1Params | None = None,
) -> ThermalResult:
    """Simule le comportement thermique horaire (5R1C) sur l'année.

    Raises:
        NotImplementedError: à implémenter en Phase 2.
    """
    raise NotImplementedError("thermal.simulate_5r1c — Phase 2")
