"""Schéma d'entrée d'une étude : StudyInput.

Regroupe le type de projet, les paramètres techniques saisis par l'ingénieur,
et les données d'enveloppe (CPE). C'est l'entrée de haut niveau du pipeline.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ProjectType(StrEnum):
    """Type de projet (pilote des hypothèses d'occupation / réglementaires)."""

    LOGEMENT = "logement"
    BUREAU = "bureau"
    MIXTE = "mixte"
    SCOLAIRE = "scolaire"
    AUTRE = "autre"


class EnvelopeData(BaseModel):
    """Données d'enveloppe issues du CPE (ou saisies).

    Ordres de grandeur LU. Tous optionnels : le moteur retombe sur des presets
    si absents, en exposant l'hypothèse.
    """

    u_wall_w_m2k: float | None = Field(default=None, gt=0, description="U murs (W/m²K).")
    u_roof_w_m2k: float | None = Field(default=None, gt=0, description="U toiture (W/m²K).")
    u_floor_w_m2k: float | None = Field(default=None, gt=0, description="U plancher bas (W/m²K).")
    u_window_w_m2k: float | None = Field(default=None, gt=0, description="Uw vitrages (W/m²K).")
    g_window: float | None = Field(
        default=None, gt=0, le=1, description="Facteur solaire g des vitrages."
    )
    air_permeability_ach50: float | None = Field(
        default=None, ge=0, description="Perméabilité à l'air n50 (vol/h sous 50 Pa)."
    )


class SiteContext(BaseModel):
    """Contexte qualitatif du site (saisi par l'ingénieur).

    Ces facteurs ne se calculent pas depuis la géométrie : ils alimentent les
    disqualifiants du moteur `rules` (CLAUDE.md §4). Valeurs par défaut =
    favorables/neutres.
    """

    exterior_noise_high: bool = Field(
        default=False, description="Bruit extérieur excessif (ouverture des fenêtres gênante)."
    )
    pollution_high: bool = Field(
        default=False, description="Pollution / pollen élevés (air extérieur peu admissible)."
    )
    ground_floor_security_risk: bool = Field(
        default=False, description="Risque d'intrusion au RdC si ouvrants ouverts."
    )
    occupancy_compatible: bool = Field(
        default=True, description="Occupation compatible avec une ventilation naturelle pilotée."
    )


class StudyInput(BaseModel):
    """Entrée complète d'une pré-étude Zéphyr.

    Le ``building`` peut être absent au tout début (avant ingestion DXF) : on
    autorise une saisie purement paramétrique pour faire tourner `roi` seul.
    """

    project_type: ProjectType = ProjectType.MIXTE
    location: str | None = Field(default=None, description="Localisation (ex. 'Pommerloch, LU').")
    epw_path: str | None = Field(default=None, description="Fichier météo .epw.")
    envelope: EnvelopeData = Field(default_factory=EnvelopeData)
    site: SiteContext = Field(default_factory=SiteContext)
    notes: str | None = None
