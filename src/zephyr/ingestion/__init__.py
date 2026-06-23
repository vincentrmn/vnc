"""Module `ingestion` — parse le DXF en entités CAO brutes (Phase 3).

Entrée = DXF vectoriel uniquement (CLAUDE.md §2.3). Pas de DWG, pas de raster.
Sortie = entités brutes (calques, polylignes fermées, textes, segments) en
**mètres**, consommées par `geometry` pour reconstruire la topologie.

On ne *mesure* rien d'autre que ce que le DXF contient (le code mesure, §2.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

# Facteurs de conversion vers le mètre selon $INSUNITS (codes DXF).
_UNIT_TO_M: dict[int, float] = {
    1: 0.0254,  # pouces
    2: 0.3048,  # pieds
    4: 0.001,  # mm
    5: 0.01,  # cm
    6: 1.0,  # m
}


@dataclass
class RawPolyline:
    layer: str
    points: list[tuple[float, float]]
    closed: bool


@dataclass
class RawText:
    layer: str
    text: str
    position: tuple[float, float]


@dataclass
class RawLine:
    layer: str
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass
class RawBlock:
    """Référence de bloc (INSERT) — souvent une fenêtre/porte/symbole."""

    layer: str
    name: str
    position: tuple[float, float]


@dataclass
class RawDXF:
    """Entités CAO brutes extraites du DXF (coordonnées en mètres)."""

    layers: list[str]
    polylines: list[RawPolyline]
    texts: list[RawText]
    lines: list[RawLine]
    unit_scale_m: float
    blocks: list[RawBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_dxf(path: str | Path, *, unit_scale_m: float | None = None) -> RawDXF:
    """Parse un fichier DXF (ezdxf) en entités brutes, mises à l'échelle en mètres.

    Args:
        path: chemin du fichier .dxf.
        unit_scale_m: facteur de conversion forcé vers le mètre (sinon déduit de
            ``$INSUNITS`` ; mètre par défaut si inconnu, avec avertissement).
    """
    import ezdxf

    path = Path(path)
    warnings: list[str] = []
    doc = cast(Any, ezdxf).readfile(str(path))
    msp = doc.modelspace()

    if unit_scale_m is None:
        insunits = int(doc.header.get("$INSUNITS", 0))
        unit_scale_m = _UNIT_TO_M.get(insunits, 1.0)
        if insunits not in _UNIT_TO_M:
            warnings.append(
                f"Unités DXF inconnues ($INSUNITS={insunits}) : mètre supposé. "
                "Vérifier l'échelle (passer unit_scale_m si besoin)."
            )
    s = unit_scale_m

    layers = sorted(layer.dxf.name for layer in doc.layers)
    polylines: list[RawPolyline] = []
    texts: list[RawText] = []
    lines: list[RawLine] = []
    blocks: list[RawBlock] = []

    for entity in msp:
        # ezdxf type les entités par sous-classe ; on accède dynamiquement aux
        # attributs spécifiques (closed, vertices, text…) après dispatch dxftype.
        e = cast(Any, entity)
        kind = e.dxftype()
        layer = e.dxf.layer
        if kind == "LWPOLYLINE":
            pts = [(p[0] * s, p[1] * s) for p in e.get_points("xy")]
            polylines.append(RawPolyline(layer, pts, bool(e.closed)))
        elif kind == "POLYLINE":
            pts = [(v.dxf.location.x * s, v.dxf.location.y * s) for v in e.vertices]
            polylines.append(RawPolyline(layer, pts, bool(e.is_closed)))
        elif kind == "TEXT":
            ins = e.dxf.insert
            texts.append(RawText(layer, e.dxf.text, (ins.x * s, ins.y * s)))
        elif kind == "MTEXT":
            ins = e.dxf.insert
            texts.append(RawText(layer, e.text, (ins.x * s, ins.y * s)))
        elif kind == "LINE":
            a, b = e.dxf.start, e.dxf.end
            lines.append(RawLine(layer, (a.x * s, a.y * s), (b.x * s, b.y * s)))
        elif kind == "INSERT":
            ins = e.dxf.insert
            blocks.append(RawBlock(layer, str(e.dxf.name), (ins.x * s, ins.y * s)))

    if not polylines:
        warnings.append("Aucune polyligne trouvée — pièces non reconstructibles.")

    return RawDXF(
        layers=layers,
        polylines=polylines,
        texts=texts,
        lines=lines,
        unit_scale_m=s,
        blocks=blocks,
        warnings=warnings,
    )
