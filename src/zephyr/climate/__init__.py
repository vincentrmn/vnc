"""Module `climate` — lecture EPW/TMY, degrés-heures, free-cooling (Phase 2).

Calcule à partir d'un fichier météo .epw : degrés-heures de chauffe/surchauffe et
le potentiel de free-cooling (nocturne). Purement déterministe (CLAUDE.md §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClimateData:
    """Séries météo horaires utiles au screen thermique.

    Attributs (à remplir en Phase 2) :
        dry_bulb_c: température sèche horaire (°C), 8760 valeurs.
        wind_speed_ms: vitesse du vent horaire (m/s).
        ghi_w_m2: irradiance globale horizontale (W/m²).
    """

    dry_bulb_c: list[float]
    wind_speed_ms: list[float]
    ghi_w_m2: list[float]


def read_epw(path: str | Path) -> ClimateData:
    """Lit un fichier météo .epw et renvoie les séries horaires.

    Raises:
        NotImplementedError: à implémenter en Phase 2.
    """
    raise NotImplementedError("climate.read_epw — Phase 2")


def degree_hours(temperatures_c: list[float], base_c: float) -> float:
    """Cumul des degrés-heures au-dessus (ou en deçà) d'un seuil.

    Raises:
        NotImplementedError: à implémenter en Phase 2.
    """
    raise NotImplementedError("climate.degree_hours — Phase 2")
