"""Module `roi` — TCO/VAN paramétrique VNC vs VMC DF (CLAUDE.md §6).

Première vraie brique du moteur (Phase 1). Tout est paramétré (`ROIParameters`),
rien en dur. La pénalité de chauffage est une entrée explicite calculée par
`thermal`.
"""

from zephyr.roi.engine import compute_roi
from zephyr.roi.parameters import ROIParameters
from zephyr.roi.sensitivity import default_tornado_specs, sobol_indices, tornado

__all__ = [
    "ROIParameters",
    "compute_roi",
    "tornado",
    "sobol_indices",
    "default_tornado_specs",
]
