"""Module `report` — génération du rapport (HTML → PDF) (Phase 4).

Assemble verdict + ROI + graphes + explications en un rapport exportable
(weasyprint). Toute sortie expose ses hypothèses et son incertitude ; jamais de
chiffre orphelin (CLAUDE.md §12). Ce n'est jamais une étude opposable (§11).
"""

from __future__ import annotations

from pathlib import Path

from zephyr.schemas import StudyResult


def render_report(result: StudyResult, output_path: str | Path) -> Path:
    """Génère le rapport PDF d'une étude.

    Raises:
        NotImplementedError: à implémenter en Phase 4.
    """
    raise NotImplementedError("report.render_report — Phase 4")
