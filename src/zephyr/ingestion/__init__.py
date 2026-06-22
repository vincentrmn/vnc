"""Module `ingestion` — parse le DXF en entités CAO brutes (Phase 3).

Entrée = DXF vectoriel uniquement (CLAUDE.md §2.3). Pas de DWG, pas de raster.
Sortie = calques, blocs, polylignes, textes bruts, consommés par `geometry`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_dxf(path: str | Path) -> dict[str, Any]:
    """Parse un fichier DXF (ezdxf) en entités brutes.

    Args:
        path: chemin du fichier .dxf.

    Returns:
        Dictionnaire d'entités CAO brutes (calques, polylignes, textes, blocs).

    Raises:
        NotImplementedError: à implémenter en Phase 3.
    """
    raise NotImplementedError("ingestion.parse_dxf — Phase 3")
