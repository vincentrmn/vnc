"""Module `geometry` — reconstruction topologique → `Building` (Phase 3).

Reconstruit pièces (polygones fermés), murs int/ext, ouvrants, orientations et
hauteurs à partir des entités DXF brutes. Étape de **validation humaine** +
**labelling LLM** (CLAUDE.md §2.8). Le code mesure, le LLM étiquette.
"""

from __future__ import annotations

from typing import Any

from zephyr.schemas import Building


def build_building(raw_entities: dict[str, Any]) -> Building:
    """Reconstruit un `Building` depuis les entités CAO brutes.

    Raises:
        NotImplementedError: à implémenter en Phase 3.
    """
    raise NotImplementedError("geometry.build_building — Phase 3")
