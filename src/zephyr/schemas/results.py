"""Schémas de sortie : ThermalResult, ROIResult, StudyResult.

Principe directeur (CLAUDE.md §2.4) : **honnêteté sur l'incertitude**. Les
sorties chiffrées portent, quand c'est pertinent, une fourchette (low/high) et
non un point unique. Aucun chiffre orphelin non sourcé.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    """Éligibilité VNC. Le principe VNC est quasi universel (≈ 95 % des bâtiments) ;
    le verdict nuance surtout des *drapeaux* contextuels, le **score** porte le détail."""

    GO = "go"  # bon candidat VNC
    CONDITIONNEL = "conditionnel"  # éligible, avec réserves / améliorations
    NO_GO = "no_go"  # drapeau dur (air non admissible, occupation incompatible)


class Range(BaseModel):
    """Fourchette autour d'une estimation centrale (CLAUDE.md §2.4)."""

    low: float
    central: float
    high: float

    def __str__(self) -> str:  # pragma: no cover - confort d'affichage
        return f"{self.central:.0f} [{self.low:.0f} – {self.high:.0f}]"


class ScoreCriterion(BaseModel):
    """Une composante du score d'aptitude VNC (déterministe).

    ``score`` est sur 0–100, ``weight`` la pondération dans le score global, et
    ``recommendation`` (optionnelle) dit comment améliorer le projet.
    """

    key: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0)
    detail: str = Field(description="Mesure déterministe qui justifie la note.")
    scale: str | None = Field(default=None, description="Échelle de notation (barème) du critère.")
    recommendation: str | None = None


class VNCScore(BaseModel):
    """Score d'aptitude à la VNC : note globale + détail par critère + recos.

    Remplace l'ancien verdict binaire : 95 % des bâtiments sont éligibles, donc
    l'utile n'est pas « oui/non » mais « à quel point, et comment améliorer ».
    """

    global_score: float = Field(ge=0, le=100)
    grade: str = Field(description="Lettre (A–E) dérivée du score global.")
    criteria: list[ScoreCriterion] = Field(default_factory=list)
    recommendations: list[str] = Field(
        default_factory=list, description="Pistes d'amélioration priorisées."
    )
    flags: list[str] = Field(
        default_factory=list, description="Drapeaux contextuels (bruit, pollution, sécurité)."
    )


class HeatingPenalty(BaseModel):
    """Surcoût de chauffage VNC vs VMC double-flux — calculé en **degrés-jours**.

    La VMC DF récupère η de la chaleur de l'air extrait, la VNC non (CLAUDE.md §6).
    Terme **déterministe** (pas de STD) = pertes de ventilation non récupérées sur
    la saison de chauffe, atténuées par la commande à la demande (débit réduit
    hors occupation). Alimente l'OPEX VNC du ROI. Jamais 0, jamais un % posé.
    """

    kwh_per_year: float = Field(ge=0)
    eur_per_year: float = Field(ge=0)
    heating_degree_days: float = Field(ge=0, description="DJU base 18 °C (°C·jour).")
    assumptions: dict[str, str] = Field(default_factory=dict)


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


class CalcLine(BaseModel):
    """Une ligne de calcul **traçable** : libellé, formule avec ses nombres, montant.

    Sert à afficher le ROI « à livre ouvert » : chaque poste montre sa formule et
    son résultat (CLAUDE.md §2.5 honnêteté). ``section`` regroupe (capex_vmc,
    capex_vnc, opex_vmc, opex_vnc, penalite, synthese).
    """

    section: str
    label: str
    formula: str = Field(description="Formule avec les valeurs substituées.")
    value_eur: float
    note: str | None = None


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
    break_even_range: Range | None = Field(
        default=None, description="Break-even probabiliste (P10/médiane/P90), en années."
    )
    sensitivity: list[SensitivityEntry] = Field(default_factory=list)

    # Détail traçable : chaque poste avec sa formule et son montant.
    calc_lines: list[CalcLine] = Field(default_factory=list)

    assumptions: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(
        default_factory=list, description="Avertissements méthodologiques (CLAUDE.md §6)."
    )


class StudyResult(BaseModel):
    """Agrégat final : éligibilité + score d'aptitude + pénalité chauffage + ROI."""

    verdict: Verdict
    score: VNCScore | None = None
    heating_penalty: HeatingPenalty | None = None
    roi: ROIResult | None = None
    disqualifiers: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    narrative: str | None = Field(default=None, description="Narratif LLM (Opus), optionnel.")
    assumptions: dict[str, str] = Field(default_factory=dict)
