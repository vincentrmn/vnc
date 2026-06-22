"""Intégration : la pénalité de chauffage *calculée* par `thermal` alimente `roi`.

C'est la boucle clé du §6 : plus de pénalité postulée à la main — elle vient du
modèle 5R1C. On vérifie que le branchement tient et dégrade la VAN de la VNC.
"""

from __future__ import annotations

from zephyr.climate import synthetic_climate
from zephyr.roi import ROIParameters, compute_roi
from zephyr.schemas import Building, Opening, Orientation, Room
from zephyr.thermal import simulate_5r1c


def _building() -> Building:
    rooms = [
        Room(
            id="sejour",
            area_m2=28.0,
            height_m=2.6,
            exterior_wall_orientations=[Orientation.S, Orientation.N],
            openings=[
                Opening(id="fs", area_m2=4.2, orientation=Orientation.S),
                Opening(id="fn", area_m2=1.8, orientation=Orientation.N),
            ],
        )
    ]
    return Building(id="b1", rooms=rooms)


def test_thermal_penalty_feeds_roi() -> None:
    thermal = simulate_5r1c(_building(), synthetic_climate())
    penalty = thermal.heating_penalty_eur_per_year
    assert penalty > 0

    roi = compute_roi(ROIParameters(), heating_penalty_eur_per_year=penalty)
    roi_zero = compute_roi(ROIParameters(), heating_penalty_eur_per_year=0.0)

    # La pénalité calculée réduit bien l'économie VNC actualisée.
    assert roi.npv_delta_eur < roi_zero.npv_delta_eur
    assert roi.assumptions["heating_penalty_eur_an"].startswith(f"{penalty:.0f}")
