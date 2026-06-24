"""Module `geometry` — reconstruction topologique → `Building` (Phase 3).

Reconstruit les pièces (polygones fermés), leurs labels, orientations et ouvrants
à partir des entités DXF brutes (`ingestion.RawDXF`). Le **code mesure** (surfaces
via shapely) ; le LLM n'intervient (plus tard) que pour le labelling sémantique.

⚠️ La reconstruction est **faillible** (CLAUDE.md §2.8) : orientations et ouvrants
sont des *estimations* destinées à être **validées/corrigées par l'ingénieur**
avant calcul. Les avertissements (`warnings`) signalent ce qui doit être vérifié.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zephyr.ingestion import RawDXF
from zephyr.schemas import Building, InertiaClass, Opening, Orientation, Room, RoomLabel

if TYPE_CHECKING:
    from shapely.geometry import Point as _Point
    from shapely.geometry.base import BaseGeometry as _Geom

# Mots-clés (texte/calque) → label de pièce (FR + EN).
_LABEL_KEYWORDS: list[tuple[tuple[str, ...], RoomLabel]] = [
    (("sejour", "séjour", "living", "salon", "lounge"), RoomLabel.SEJOUR),
    (("chambre", "bedroom", "ch.", "chbre", "bed"), RoomLabel.CHAMBRE),
    (("cuisine", "kitchen"), RoomLabel.CUISINE),
    (("sdb", "bain", "bath", "douche", "sdd", "shower"), RoomLabel.SDB),
    (("wc", "toilet"), RoomLabel.WC),
    (
        ("couloir", "circulation", "hall", "palier", "degagement", "dégagement",
         "corridor", "landing", "stair", "entrance", "mezzanine"),
        RoomLabel.CIRCULATION,
    ),
    (("bureau", "office", "study"), RoomLabel.BUREAU),
    (
        ("technique", "local", "garage", "buanderie", "cave", "grenier", "attic",
         "laundry", "pantry", "storage", "utility", "boiler"),
        RoomLabel.TECHNIQUE,
    ),
]

_WINDOW_KEYWORDS = ("fenetre", "fenêtre", "window", "baie", "ouvr", "vitr")


@dataclass
class GeometryResult:
    """Bâtiment reconstruit + avertissements pour la validation humaine."""

    building: Building
    warnings: list[str] = field(default_factory=list)


def _label_from_text(text: str) -> RoomLabel | None:
    low = text.strip().lower()
    for keys, label in _LABEL_KEYWORDS:
        if any(k in low for k in keys):
            return label
    return None


# Surface annoncée dans un libellé : « Bedroom 15.10m² », « Cuisine 19,6 m » …
_AREA_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m", re.IGNORECASE)


def _label_and_area(text: str) -> tuple[RoomLabel | None, float | None]:
    clean = text.replace("\\P", " ").replace("\\p", " ").strip()
    m = _AREA_RE.search(clean)
    return _label_from_text(clean), (float(m.group(1).replace(",", ".")) if m else None)


def _rooms_from_labels(raw: RawDXF, hsp_m: float, level: int) -> list[Room]:
    """Pièces depuis les **libellés** (nom + surface) — repli quand le fichier n'a
    pas de polygones de pièces (murs en lignes : PDF d'archi, export Home.io…).

    Sans polygone : ni façade ni châssis ni traversant déduits — à compléter dans
    la validation. Mais on récupère la liste des pièces, leurs types et surfaces.
    """
    rooms: list[Room] = []
    seen: set[tuple[str, float, float, float]] = set()
    for t in raw.texts:
        label, area = _label_and_area(t.text)
        if label is None or area is None or area <= 0:
            continue
        key = (label.value, round(area, 1), round(t.position[0], 2), round(t.position[1], 2))
        if key in seen:
            continue
        seen.add(key)
        rooms.append(
            Room(
                id=f"label_{len(rooms)}",
                label=label,
                area_m2=area,
                height_m=hsp_m,
                level=level,
            )
        )
    return rooms


# Secteurs de boussole (convention plan : +x = Est, +y = Nord ; angle math).
_SECTORS: list[tuple[float, Orientation]] = [
    (0.0, Orientation.E),
    (45.0, Orientation.NE),
    (90.0, Orientation.N),
    (135.0, Orientation.NW),
    (180.0, Orientation.W),
    (225.0, Orientation.SW),
    (270.0, Orientation.S),
    (315.0, Orientation.SE),
]


def _orientation_from_angle(angle_deg: float, north_offset_deg: float = 0.0) -> Orientation:
    """Mappe un angle (normale sortante, degrés math) vers une orientation cardinale.

    ``north_offset_deg`` corrige l'orientation du plan (angle du Nord vrai vs +y).
    """
    a = (angle_deg - north_offset_deg) % 360.0
    return min(_SECTORS, key=lambda s: min(abs(a - s[0]), 360.0 - abs(a - s[0])))[1]


def _segment_exterior_orientation(
    p1: tuple[float, float],
    p2: tuple[float, float],
    union: _Geom,
    point_cls: type[_Point],
    north: float,
    eps: float = 0.25,
) -> Orientation | None:
    """Orientation de la **façade extérieure** d'un segment, ou None s'il est intérieur.

    On échantillonne de part et d'autre du segment (le long de sa normale) : le
    côté qui sort de l'emprise du bâtiment donne la normale sortante → l'orientation.
    Un segment dont les deux côtés sont à l'intérieur est un mur **mitoyen**.
    """
    mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return None
    nx, ny = -dy / length, dx / length  # normale unitaire
    for sign in (1.0, -1.0):
        px, py = mx + sign * nx * eps, my + sign * ny * eps
        if not union.contains(point_cls(px, py)):
            return _orientation_from_angle(math.degrees(math.atan2(sign * ny, sign * nx)), north)
    return None


def build_building(
    raw: RawDXF,
    *,
    hsp_m: float = 2.6,
    level: int = 0,
    inertia: InertiaClass = InertiaClass.LOURDE,
    min_area_m2: float = 2.0,
    max_area_m2: float = 2000.0,
    window_height_m: float = 1.3,
    north_angle_deg: float = 0.0,
    default_window_area_m2: float = 1.5,
    building_id: str = "dxf",
) -> GeometryResult:
    """Reconstruit un `Building` depuis les entités DXF brutes.

    Pièces = polylignes fermées (surface shapely, filtrée par taille). Labels =
    texte contenu, sinon nom de calque. **Façades extérieures et orientations =
    déduites géométriquement** : on calcule l'emprise du bâtiment (union des
    pièces) et on teste, mur par mur, lequel donne sur l'extérieur (≠ mitoyen).
    ``north_angle_deg`` corrige l'orientation du plan (Nord vrai vs +y). Ouvrants
    = segments sur calque « fenêtre » + blocs (INSERT) « fenêtre », orientés par
    la façade qui les porte. Le **traversant** découle des façades (≥ 2).
    """
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union

    warnings = list(raw.warnings)

    # 1) Polygones de pièces (fermés, taille plausible).
    room_polys: list[tuple[Polygon, str]] = []
    for pl in raw.polylines:
        if not pl.closed or len(pl.points) < 3:
            continue
        poly = Polygon(pl.points)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        if min_area_m2 <= poly.area <= max_area_m2:
            room_polys.append((poly, pl.layer))

    if not room_polys:
        # Repli : pas de polygones (murs en lignes / PDF) → pièces depuis les libellés.
        label_rooms = _rooms_from_labels(raw, hsp_m, level)
        if label_rooms:
            total = sum(r.area_m2 for r in label_rooms)
            warnings.append(
                f"{len(label_rooms)} pièce(s) lues dans les LIBELLÉS (nom + surface, "
                f"total {total:.0f} m²) — pas de polygones de pièces dans ce fichier."
            )
            warnings.append(
                "Façades, châssis et traversant NON déduits — à saisir/valider pièce "
                "par pièce ci-dessous (§2.8)."
            )
            return GeometryResult(
                Building(id=building_id, rooms=label_rooms, inertia_class=inertia), warnings
            )
        warnings.append("Aucune pièce reconstructible (ni polygone fermé, ni libellé nom+surface).")
        return GeometryResult(Building(id=building_id, inertia_class=inertia), warnings)

    # Emprise du bâtiment (union des pièces) → distingue murs extérieurs/mitoyens.
    union = unary_union([p for p, _ in room_polys])

    # 2) Fenêtres candidates : segments sur calque « fenêtre » + blocs « fenêtre ».
    window_lines = [ln for ln in raw.lines if any(k in ln.layer.lower() for k in _WINDOW_KEYWORDS)]
    window_blocks = [
        b
        for b in raw.blocks
        if any(k in b.layer.lower() or k in b.name.lower() for k in _WINDOW_KEYWORDS)
    ]

    rooms: list[Room] = []
    labelled = 0
    for idx, (poly, layer) in enumerate(room_polys):
        # Label : texte contenu, sinon calque.
        label = RoomLabel.AUTRE
        for txt in raw.texts:
            if poly.contains(Point(txt.position)):
                found = _label_from_text(txt.text)
                if found:
                    label = found
                    break
        if label is RoomLabel.AUTRE:
            found = _label_from_text(layer)
            if found:
                label = found
        if label is not RoomLabel.AUTRE:
            labelled += 1

        # Façades extérieures : longueur cumulée par orientation (murs non mitoyens).
        coords = list(poly.exterior.coords)
        orient_len: dict[Orientation, float] = {}
        for a, b in zip(coords, coords[1:], strict=False):
            o = _segment_exterior_orientation(a, b, union, Point, north_angle_deg)
            if o is not None:
                orient_len[o] = orient_len.get(o, 0.0) + math.dist(a, b)
        orients = [
            o for o, length in sorted(orient_len.items(), key=lambda kv: -kv[1]) if length >= 0.5
        ]
        dominant = orients[0] if orients else Orientation.S

        # Ouvrants : lignes fenêtre proches (orientées par leur façade) + blocs.
        openings: list[Opening] = []
        for wl in window_lines:
            mid = Point((wl.start[0] + wl.end[0]) / 2, (wl.start[1] + wl.end[1]) / 2)
            if poly.distance(mid) <= 0.5:  # ~0,5 m de tolérance
                length = LineString([wl.start, wl.end]).length
                facing = (
                    _segment_exterior_orientation(
                        wl.start, wl.end, union, Point, north_angle_deg, eps=0.5
                    )
                    or dominant
                )
                openings.append(
                    Opening(
                        id=f"r{idx}_win{len(openings)}",
                        area_m2=max(length * window_height_m, 0.1),
                        orientation=facing,
                        head_height_m=min(hsp_m - 0.2, window_height_m + 0.9),
                    )
                )
        for blk in window_blocks:
            if poly.distance(Point(blk.position)) <= 0.5:
                openings.append(
                    Opening(
                        id=f"r{idx}_blk{len(openings)}",
                        area_m2=default_window_area_m2,
                        orientation=dominant,
                        head_height_m=min(hsp_m - 0.2, window_height_m + 0.9),
                    )
                )

        rooms.append(
            Room(
                id=f"room_{idx}",
                label=label,
                area_m2=round(poly.area, 2),
                height_m=hsp_m,
                level=level,
                polygon=[(round(x, 3), round(y, 3)) for x, y in poly.exterior.coords],
                exterior_wall_orientations=orients,
                openings=openings,
            )
        )

    # 3) Avertissements de validation humaine.
    warnings.append("Façades/orientations déduites de la géométrie — À VALIDER (§2.8).")
    if north_angle_deg == 0.0:
        warnings.append("Nord supposé = +y du plan : régler l'angle du Nord si le plan est tourné.")
    if not window_lines and not window_blocks:
        warnings.append("Aucun ouvrant détecté (ni calque ni bloc 'fenêtre') — à saisir.")
    if window_blocks:
        warnings.append(
            f"{len(window_blocks)} ouvrant(s) issus de blocs : largeur supposée — à confirmer."
        )
    n_through = sum(1 for r in rooms if r.is_through)
    warnings.append(f"Traversant : {n_through}/{len(rooms)} pièce(s) exposée(s) sur ≥ 2 façades.")
    if labelled < len(rooms):
        warnings.append(
            f"{len(rooms) - labelled}/{len(rooms)} pièce(s) non labellisées — à étiqueter."
        )

    building = Building(id=building_id, rooms=rooms, inertia_class=inertia)
    return GeometryResult(building, warnings)
