"""Schéma de l'extraction CPE (passeport énergétique) — résultat du parsing hybride.

Champs d'enveloppe tirés du CPE, **chacun avec sa provenance** (extrait verbatim
du texte source). Tous optionnels : un champ absent ou non vérifiable est laissé
à `None` et signalé — jamais inventé (CLAUDE.md §11). Sert à **pré-remplir** le
formulaire, que l'ingénieur valide (human-in-the-loop).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from zephyr.schemas.building import InertiaClass


class CpeExtraction(BaseModel):
    """Valeurs d'enveloppe extraites d'un CPE, avec extraits source par champ."""

    u_wall_w_m2k: float | None = Field(default=None, gt=0, description="U murs (W/m²K).")
    u_roof_w_m2k: float | None = Field(default=None, gt=0, description="U toiture (W/m²K).")
    u_floor_w_m2k: float | None = Field(default=None, gt=0, description="U plancher bas (W/m²K).")
    u_window_w_m2k: float | None = Field(default=None, gt=0, description="Uw vitrages (W/m²K).")
    air_permeability_ach50: float | None = Field(
        default=None, ge=0, description="Perméabilité n50 (vol/h sous 50 Pa)."
    )
    glazing_to_floor_ratio: float | None = Field(
        default=None, ge=0, description="Ratio surface vitrée / surface au sol."
    )
    inertia_class: InertiaClass | None = Field(
        default=None, description="Inertie déduite de la composition des parois."
    )
    floor_area_m2: float | None = Field(
        default=None, gt=0, description="Surface de référence énergétique (m²)."
    )
    construction_year: int | None = Field(default=None, description="Année de construction.")

    # Provenance : champ → extrait verbatim du texte source (justifie chaque valeur).
    sources: dict[str, str] = Field(default_factory=dict)
    # Champs proposés par le modèle mais écartés (non vérifiables verbatim) + raisons.
    notes: list[str] = Field(default_factory=list)
