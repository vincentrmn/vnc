"""Module `llm` — service transverse (labelling + narratif) (Phase 4).

Deux rôles, et seulement ceux-là (CLAUDE.md §8) :
  1. Labelling sémantique à l'ingestion (Sonnet 4.6 / Haiku 4.5).
  2. Narratif en sortie (Opus 4.8).

Interdits : mesurer une géométrie par vision, inventer des chiffres, remplacer un
calcul déterministe. Prompt caching sur le bloc statique ; bornes `max_tokens`
serrées.
"""

from __future__ import annotations

# Modèles de référence (CLAUDE.md §5/§8). Ne pas confondre avec l'identité du
# modèle qui exécute Claude Code.
MODEL_NARRATIVE = "claude-opus-4-8"
MODEL_LABELLING = "claude-sonnet-4-6"
MODEL_LABELLING_BULK = "claude-haiku-4-5-20251001"


def label_room(context: str) -> str:
    """Étiquette sémantique d'une pièce (séjour, SDB, circulation…).

    Raises:
        NotImplementedError: à implémenter en Phase 4.
    """
    raise NotImplementedError("llm.label_room — Phase 4")


def write_narrative(study_result_json: str) -> str:
    """Rédige le narratif lisible à partir des résultats chiffrés.

    Raises:
        NotImplementedError: à implémenter en Phase 4.
    """
    raise NotImplementedError("llm.write_narrative — Phase 4")
