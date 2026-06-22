"""Constructeur de `Building` paramétrique (sans DXF).

Permet de faire tourner le pipeline complet à partir de quelques paramètres
haut-niveau, le temps que l'ingestion DXF (Phase 3) soit prête. Utile pour l'UI
interne et les démos : on décrit un bâtiment « type » plutôt qu'un plan réel.

Ce n'est PAS de la reconstruction géométrique (cf. `geometry`) : c'est un
générateur de cas représentatif.
"""

from __future__ import annotations

import math

from zephyr.schemas import Building, InertiaClass, Opening, Orientation, Room, RoomLabel

# Paires d'orientations opposées pour des pièces traversantes.
_OPPOSITE = {
    Orientation.S: Orientation.N,
    Orientation.E: Orientation.W,
    Orientation.N: Orientation.S,
    Orientation.W: Orientation.E,
}


def parametric_building(
    total_floor_area_m2: float,
    *,
    num_levels: int = 2,
    room_size_m2: float = 25.0,
    hsp_m: float = 2.6,
    window_to_floor_ratio: float = 0.15,
    inertia: InertiaClass = InertiaClass.LOURDE,
    through: bool = True,
    main_orientation: Orientation = Orientation.S,
    building_id: str = "param",
) -> Building:
    """Construit un bâtiment représentatif tuilé en pièces.

    Les pièces sont réparties sur les niveaux ; chacune reçoit des ouvrants sur sa
    façade principale (et la façade opposée si ``through``), dimensionnés par
    ``window_to_floor_ratio``. Approximation de pré-étude, pas un plan réel.
    """
    n_rooms = max(1, round(total_floor_area_m2 / room_size_m2))
    area_each = total_floor_area_m2 / n_rooms
    side = math.sqrt(area_each)
    head = min(hsp_m - 0.3, 2.2)

    rooms: list[Room] = []
    for i in range(n_rooms):
        level = i % num_levels
        # Alterne l'orientation principale pour diversifier l'exposition.
        primary = main_orientation if i % 2 == 0 else _OPPOSITE[main_orientation]
        orients = [primary, _OPPOSITE[primary]] if through else [primary]

        win_total = window_to_floor_ratio * area_each
        win_each = win_total / len(orients)
        openings = [
            Opening(
                id=f"r{i}_{o.value}",
                area_m2=max(win_each, 0.1),
                orientation=o,
                head_height_m=head,
            )
            for o in orients
        ]
        rooms.append(
            Room(
                id=f"room_{i}",
                label=RoomLabel.AUTRE,
                area_m2=area_each,
                height_m=hsp_m,
                level=level,
                polygon=[(0, 0), (side, 0), (side, side), (0, side)],
                exterior_wall_orientations=orients,
                openings=openings,
            )
        )

    return Building(id=building_id, rooms=rooms, inertia_class=inertia, num_levels=num_levels)
