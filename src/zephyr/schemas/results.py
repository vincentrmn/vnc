"""Schémas de sortie : ThermalResult, ROIResult, StudyResult.

Principe directeur (CLAUDE.md §2.4) : **honnêteté sur l'incertitude**. Les
sorties chiffrées portent, quand c'est pertinent, une fourchette (low/high) et
non un point unique. Aucun chiffre orphelin non sourcé.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    """Verdict de faisabilité VNC rendu par `rules`."""

    GO = "go"
    CONDITIONNEL = "conditionnel"
    NO_GO = "no_go"


class Range(BaseModel):
    """Fourchette autour d'une estimation centrale (CLAUDE.md §2.4)."""

    low: float
    central: float
    high: float

    def __str__(self) -> str:  # pragma: no cover - confort d'affichage
        return f"{self.central:.0f} [{self.low:.0f} – {self.high:.0f}]"


class ThermalResult(BaseModel):
    """Sortie du module `thermal` (5R1C).

    La ``heating_penalty_*`` est le terme clé injecté dans l'OPEX VNC du ROI
    (CLAUDE.md §6). Il est **calculé** (besoin de chauffage différentiel dû à
    l'absence d'échangeur, atténué par commande/inertie/scheduling), jamais
    postulé. ``equivalent_recovery_pct`` est une sortie *dérivée* pour la
    lecture, jamais une entrée.
    """

    overheating_hours: float = Field(
        default=0.0, ge=0, description="Heures au-dessus du seuil de confort (h/an)."
    )
    degree_hours_overheating: float = Field(
        default=0.0, ge=0, description="Degrés-heures de surchauffe (°C·h/an)."
    )
    night_cooling_benefit_kwh: float = Field(
        default=0.0,
        ge=0,
        description="Rafraîchissement passif récupéré par night-cooling (kWh/an).",
    )
    heating_penalty_kwh_per_year: float = Field(
        default=0.0,
        ge=0,
        description="Surplus de besoin de chauffage VNC vs VMC DF récup (kWh/an), calculé.",
    )
    heating_penalty_eur_per_year: float = Field(
        default=0.0,
        ge=0,
        description="Coût annuel du surplus de chauffage VNC (€/an, an 1 avant inflation).",
    )
    equivalent_recovery_pct: float | None = Field(
        default=None,
        description="Récup équivalente dérivée (%), pour la com'. Sortie validée, jamais entrée.",
    )
    assumptions: dict[str, str] = Field(
        default_factory=dict, description="Hypothèses explicites du calcul thermique."
    )


class SensitivityEntry(BaseModel):
    """Une barre du tornado : effet d'un paramètre sur la sortie (VAN delta)."""

    parameter: str
    low_value: float
    high_value: float
    output_low: float = Field(description="Sortie quand le paramètre est à sa borne basse.")
    output_high: float = Field(description="Sortie quand le paramètre est à sa borne haute.")

    @property
    def swing(self) -> float:
        """Amplitude (valeur absolue) de l'effet sur la sortie."""
        return abs(self.output_high - self.output_low)


class ROIResult(BaseModel):
    """Sortie du module `roi` : TCO/VAN paramétrique VNC vs VMC DF.

    Convention de signe du delta : **économie de la VNC = coûts VMC − coûts
    VNC**. Une VAN delta positive = la VNC est économiquement favorable sur
    l'horizon (elle coûte moins cher en valeur actualisée).
    """

    # CAPEX (détail pour la traçabilité)
    capex_vmc_eur: float
    capex_vnc_eur: float
    capex_vmc_breakdown: dict[str, float] = Field(default_factory=dict)
    capex_vnc_breakdown: dict[str, float] = Field(default_factory=dict)

    # OPEX an 1 (avant inflation)
    opex_vmc_year1_eur: float
    opex_vnc_year1_eur: float
    opex_vmc_breakdown: dict[str, float] = Field(default_factory=dict)
    opex_vnc_breakdown: dict[str, float] = Field(default_factory=dict)

    # Flux & synthèse
    horizon_years: int
    npv_delta_eur: float = Field(
        description="VAN cumulée actualisée de l'économie VNC (coûts VMC − coûts VNC)."
    )
    npv_delta_cumulative_eur: list[float] = Field(
        default_factory=list,
        description="VAN cumulée de l'économie VNC, année par année (an 0..N).",
    )
    break_even_year: int | None = Field(
        default=None, description="Première année où la VAN cumulée de l'économie VNC devient ≥ 0."
    )
    tco_vmc_undiscounted_eur: float = Field(description="TCO non actualisé VMC sur l'horizon.")
    tco_vnc_undiscounted_eur: float = Field(description="TCO non actualisé VNC sur l'horizon.")

    # Fourchette sur la VAN delta + sensibilité
    npv_delta_range: Range | None = None
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)

    assumptions: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(
        default_factory=list, description="Avertissements méthodologiques (CLAUDE.md §6)."
    )


class StudyResult(BaseModel):
    """Agrégat final : verdict + thermique + ROI + traçabilité."""

    verdict: Verdict
    disqualifiers: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    thermal: ThermalResult | None = None
    roi: ROIResult | None = None
    narrative: str | None = Field(default=None, description="Narratif LLM (Opus), optionnel.")
    assumptions: dict[str, str] = Field(default_factory=dict)
