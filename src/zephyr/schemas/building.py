"""Schémas géométriques : Opening, Room, Building.

Ces objets sont la sortie du couple `ingestion` → `geometry` (reconstruction
topologique depuis le DXF, validée par l'humain). Ils sont l'entrée des modules
physiques (`thermal`, `ventilation`) et des `rules`.

Toute grandeur géométrique est *calculée par du code déterministe* (cf. CLAUDE.md
§2.2) ; le LLM ne fait que du labelling sémantique (champ ``label``).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Orientation(StrEnum):
    """Orientation cardinale d'une façade / d'un ouvrant."""

    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SW = "SW"
    W = "W"
    NW = "NW"


class InertiaClass(StrEnum):
    """Classe d'inertie thermique (pilote la capacité C du 5R1C).

    Bâtiments cibles = inertie lourde (cf. CLAUDE.md §2.7). C'est l'hypothèse
    par défaut.
    """

    LEGERE = "legere"
    MOYENNE = "moyenne"
    LOURDE = "lourde"


class OpeningKind(StrEnum):
    """Nature de l'ouvrant."""

    WINDOW = "window"
    DOOR = "door"
    LOUVRE = "louvre"
    GRILLE = "grille"


class RoomLabel(StrEnum):
    """Étiquette sémantique d'une pièce (sortie du labelling LLM)."""

    SEJOUR = "sejour"
    SALLE_A_MANGER = "salle_a_manger"
    CHAMBRE = "chambre"
    CUISINE = "cuisine"
    SDB = "sdb"  # salle de bain / pièce humide
    WC = "wc"
    ENTREE = "entree"
    CIRCULATION = "circulation"
    BUREAU = "bureau"
    BUANDERIE = "buanderie"
    CELLIER = "cellier"
    DRESSING = "dressing"
    GARAGE = "garage"
    TECHNIQUE = "technique"
    AUTRE = "autre"


class Opening(BaseModel):
    """Un ouvrant (fenêtre, porte, grille). Brique du dimensionnement VNC.

    ``area_m2`` est la surface géométrique totale ; ``free_area_ratio`` est la
    fraction réellement ouvrable utile au débit (un châssis oscillo-battant
    n'offre pas 100 % de sa surface au passage d'air).
    """

    id: str
    kind: OpeningKind = OpeningKind.WINDOW
    area_m2: float = Field(gt=0, description="Surface géométrique de l'ouvrant (m²).")
    orientation: Orientation
    sill_height_m: float = Field(
        default=0.9,
        ge=0,
        description="Hauteur d'allège (bas de l'ouvrant au-dessus du sol fini), en m.",
    )
    head_height_m: float | None = Field(
        default=None,
        ge=0,
        description="Hauteur du haut de l'ouvrant au-dessus du sol (m). Sert au tirage (Δh).",
    )
    openable: bool = Field(
        default=True,
        description="L'ouvrant peut-il être ouvert (motorisable) ? Un fixe ne ventile pas.",
    )
    free_area_ratio: float = Field(
        default=0.5,
        gt=0,
        le=1,
        description="Fraction de la surface réellement utile au débit d'air.",
    )

    @property
    def free_area_m2(self) -> float:
        """Surface libre effective au passage de l'air (m²)."""
        return self.area_m2 * self.free_area_ratio


class Room(BaseModel):
    """Une pièce : polygone fermé reconstruit + métadonnées thermiques/VNC.

    ``polygon`` est la liste ordonnée des sommets (x, y) en mètres. ``area_m2``
    et ``volume_m3`` sont calculés par `geometry` ; on les stocke pour ne pas
    recalculer partout, mais ils restent dérivés du polygone.
    """

    id: str
    name: str | None = None
    label: RoomLabel = RoomLabel.AUTRE
    level: int = Field(default=0, description="Niveau / étage (0 = RdC).")
    polygon: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Sommets (x, y) en m du contour fermé de la pièce.",
    )
    area_m2: float = Field(gt=0, description="Surface au sol (m²).")
    height_m: float = Field(gt=0, description="Hauteur sous plafond HSP (m).")
    openings: list[Opening] = Field(default_factory=list)
    exterior_wall_orientations: list[Orientation] = Field(
        default_factory=list,
        description="Orientations des murs donnant sur l'extérieur (exposition).",
    )
    is_occupied: bool = True
    is_wet_room: bool = Field(
        default=False,
        description="Pièce humide (extraction dédiée hors VNC, cf. CLAUDE.md §6).",
    )

    @property
    def volume_m3(self) -> float:
        """Volume de la pièce (m³)."""
        return self.area_m2 * self.height_m

    @property
    def is_through(self) -> bool:
        """Pièce traversante : exposée sur au moins deux orientations distinctes."""
        return len(set(self.exterior_wall_orientations)) >= 2

    @property
    def depth_to_height_ratio(self) -> float | None:
        """Ratio profondeur/HSP, approximé (aire / plus petite dimension utile).

        Indicatif pour le disqualifiant « plan trop profond » (CLAUDE.md §4).
        Renvoie ``None`` si le polygone est insuffisant pour estimer la profondeur.
        """
        if not self.polygon or len(self.polygon) < 3:
            return None
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        width = max(xs) - min(xs)
        depth = max(ys) - min(ys)
        smaller = min(width, depth)
        larger = max(width, depth)
        if smaller <= 0:
            return None
        return larger / self.height_m


class Building(BaseModel):
    """Le bâtiment reconstruit : agrégat de pièces + inertie + localisation.

    C'est l'objet pivot du pipeline (cf. CLAUDE.md §4) : sortie de `geometry`,
    entrée de `thermal` / `ventilation` / `rules`.
    """

    id: str
    name: str | None = None
    rooms: list[Room] = Field(default_factory=list)
    inertia_class: InertiaClass = InertiaClass.LOURDE
    num_levels: int = Field(default=1, ge=1)
    total_height_m: float | None = Field(
        default=None,
        description="Hauteur totale du bâtiment (m), utile au tirage thermique global.",
    )
    location: str | None = Field(default=None, description="Localisation (ex. 'Pommerloch, LU').")
    epw_path: str | None = Field(default=None, description="Chemin du fichier météo .epw associé.")

    @property
    def total_floor_area_m2(self) -> float:
        """Surface au sol totale ventilée (m²)."""
        return sum(r.area_m2 for r in self.rooms)

    @property
    def total_volume_m3(self) -> float:
        """Volume total ventilé (m³)."""
        return sum(r.volume_m3 for r in self.rooms)

    @property
    def total_openable_area_m2(self) -> float:
        """Surface libre ouvrable cumulée (m²)."""
        return sum(o.free_area_m2 for r in self.rooms for o in r.openings if o.openable)

    @model_validator(mode="after")
    def _check_levels(self) -> Building:
        if self.rooms:
            max_level = max(r.level for r in self.rooms)
            if max_level + 1 > self.num_levels:
                # On ne lève pas : on corrige pour rester tolérant à l'ingestion.
                object.__setattr__(self, "num_levels", max_level + 1)
        return self
