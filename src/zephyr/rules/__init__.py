"""Module `rules` — moteur déterministe de faisabilité VNC (Phase 2).

Rend un verdict go / no-go / conditionnel avec disqualifiants explicites
(CLAUDE.md §4) : bruit extérieur, pollution/pollen, sécurité RdC, plan trop
profond sans traversant (profondeur > ~2,5× HSP simple-face, > ~5× traversant),
surface d'ouvrants insuffisante, absence d'exposition au vent, occupation
incompatible. Chaque règle porte son seuil et son explication.
"""

from __future__ import annotations

from zephyr.schemas import Building, StudyResult, ThermalResult
from zephyr.ventilation import VentilationResult


def evaluate_feasibility(
    building: Building,
    thermal: ThermalResult,
    ventilation: VentilationResult,
) -> StudyResult:
    """Évalue la faisabilité VNC et renvoie un verdict justifié.

    Raises:
        NotImplementedError: à implémenter en Phase 2.
    """
    raise NotImplementedError("rules.evaluate_feasibility — Phase 2")
