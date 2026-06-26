"""Presets par type de projet (pénalité de chauffage, pondérations de score).

Le moteur est déterministe et le même pour tous les bâtiments ; ce qui change,
c'est le **débit hygiénique de référence** (plus élevé en bureau occupé) et,
éventuellement, les **pondérations** du score. Tout est surchargeable.
"""

from __future__ import annotations

from zephyr.rules import ScoreWeights
from zephyr.schemas import ProjectType
from zephyr.thermal import PenaltyParams


def penalty_params_for(project_type: ProjectType, **overrides: object) -> PenaltyParams:
    """Hypothèses de pénalité de chauffage selon le type de projet.

    Le bureau occupé demande plus d'air neuf (débit hygiénique plus élevé) → la
    part non récupérée par la VNC est plus grande.
    """
    base: dict[str, object] = {"hygienic_ach": 0.5}
    if project_type is ProjectType.BUREAU:
        base["hygienic_ach"] = 1.0
    elif project_type is ProjectType.SCOLAIRE:
        base["hygienic_ach"] = 1.2
    elif project_type is ProjectType.MIXTE:
        base["hygienic_ach"] = 0.7
    base.update(overrides)
    return PenaltyParams(**base)  # type: ignore[arg-type]


def score_weights_for(project_type: ProjectType) -> ScoreWeights:
    """Pondérations du score (par défaut identiques ; point d'ajustement futur)."""
    return ScoreWeights()


# Prix de l'énergie de chauffage par vecteur (€/kWh utile). PAC = élec / COP.
_HEATING_PRICE_EUR_KWH: dict[str, float] = {
    "pac": 0.09,          # ~0,28 €/kWh élec ÷ COP 3,1
    "electrique": 0.28,
    "gaz": 0.10,
    "fioul": 0.115,
    "reseau": 0.10,       # réseau de chaleur
    "bois": 0.07,
}


def heating_price_for(chauffage: str) -> float:
    """Prix de l'énergie de chauffage (€/kWh) selon le vecteur (défaut PAC)."""
    return _HEATING_PRICE_EUR_KWH.get(chauffage, _HEATING_PRICE_EUR_KWH["pac"])


def cost_preset_for(project_type: ProjectType, area_m2: float) -> dict[str, float]:
    """Forfaits CAPEX recalés par **taille** (corrige le défaut « petit projet ».

    Les coûts fixes VNC (BOS, STD, commissioning, extraction) sont calibrés gros
    tertiaire ; sur une maison ils écrasent le ROI. On les échelonne par palier, et
    on donne une part fixe au CAPEX VMC (symétrie de modélisation). Surchargeable.
    Renvoie un dict d'overrides pour `ROIParameters`.
    """
    if area_m2 < 300:  # maison individuelle / très petit
        return {
            "vnc_bos_platform_eur": 6000.0, "vnc_std_engineering_eur": 5000.0,
            "vnc_commissioning_hypercare_eur": 3000.0, "vnc_extraction_humide_eur": 6000.0,
            "vmc_fixed_eur": 4000.0,
        }
    if area_m2 < 1500:  # petit collectif / petit tertiaire
        return {
            "vnc_bos_platform_eur": 14000.0, "vnc_std_engineering_eur": 12000.0,
            "vnc_commissioning_hypercare_eur": 8000.0, "vnc_extraction_humide_eur": 12000.0,
            "vmc_fixed_eur": 8000.0,
        }
    return {}  # gros tertiaire : forfaits par défaut (calibration Pommerloch)
