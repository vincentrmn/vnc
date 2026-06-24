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
class CpeText:
    """Texte brut extrait d'un CPE (passeport énergétique) PDF vectoriel.

    Brique **layout-indépendante** du parsing CPE (CLAUDE.md §10) : on extrait le
    texte (déterministe), on refuse les scans (zéro vision, §2.3). Le mapping
    texte → champs d'enveloppe (U, n50, inertie…) se fait ensuite (hybride :
    règles + LLM, chiffres vérifiés verbatim, pré-remplit le formulaire).
    """

    text: str  # texte concaténé de toutes les pages
    pages: list[str]  # texte par page (ordre du document)
    n_images: int = 0


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


def parse_pdf(path: str | Path, *, page_index: int = 0, unit_scale_m: float = 1.0) -> RawDXF:
    """Parse un **PDF vectoriel** (PyMuPDF) en entités brutes — **déterministe, zéro vision**.

    On extrait les segments vectoriels (lignes, rectangles, courbes échantillonnées)
    et les **textes réels** (noms/surfaces de pièces). Un PDF **scanné** (que des
    images, aucun vecteur) est refusé : ce serait de la vision, exclue en v1
    (CLAUDE.md §2.3). L'axe Y est retourné (origine en bas, +y = haut).

    ⚠️ L'échelle d'un PDF d'archi n'est pas auto-déductible (coordonnées en points
    à l'échelle papier) : ``unit_scale_m`` est à calibrer, et les **surfaces
    fiables viennent des libellés**. Les coordonnées servent surtout au tracé.
    """
    import fitz  # PyMuPDF

    path = Path(path)
    warnings: list[str] = []
    doc = fitz.open(str(path))
    if page_index >= doc.page_count:
        raise ValueError(f"Page {page_index} absente (PDF à {doc.page_count} page(s)).")
    page = doc[page_index]
    height = page.rect.height
    s = unit_scale_m

    def pt(p: Any) -> tuple[float, float]:
        x = getattr(p, "x", None)
        if x is None:
            x, y = p[0], p[1]
        else:
            y = p.y
        return (x * s, (height - y) * s)  # mise à l'échelle + flip vertical

    lines: list[RawLine] = []
    polylines: list[RawPolyline] = []
    for d in page.get_drawings():
        for it in d["items"]:
            kind = it[0]
            if kind == "l":  # segment
                lines.append(RawLine("pdf", pt(it[1]), pt(it[2])))
            elif kind == "re":  # rectangle → polyligne fermée
                r = it[1]
                polylines.append(
                    RawPolyline(
                        "pdf",
                        [pt((r.x0, r.y0)), pt((r.x1, r.y0)), pt((r.x1, r.y1)), pt((r.x0, r.y1))],
                        True,
                    )
                )
            elif kind == "c":  # bézier cubique → segment entre extrémités
                lines.append(RawLine("pdf", pt(it[1]), pt(it[4])))
            elif kind == "qu":  # quad → ses deux diagonales d'extrémité
                q = it[1]
                lines.append(RawLine("pdf", pt(q.ul), pt(q.lr)))

    texts: list[RawText] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "").strip()
                if txt:
                    bx = span["bbox"]
                    texts.append(RawText("pdf", txt, pt((bx[0], bx[3]))))

    n_images = len(page.get_images())
    if not lines and not polylines and n_images:
        raise ValueError(
            "PDF scanné (image, aucun vecteur) : non supporté en v1 — il faudrait de la "
            "vision. Fournir un PDF vectoriel (export depuis le logiciel d'archi/CAO)."
        )
    warnings.append(
        "PDF vectoriel : échelle non auto-déduite (points) — à calibrer ; surfaces "
        "fiables via les libellés."
    )
    if n_images:
        warnings.append(f"{n_images} image(s) dans le PDF — ignorée(s) (on ne lit que le vecteur).")

    return RawDXF(
        layers=["pdf"],
        polylines=polylines,
        texts=texts,
        lines=lines,
        unit_scale_m=s,
        warnings=warnings,
    )


def render_pdf_page(
    path: str | Path, *, page_index: int = 0, zoom: float = 0.5, max_side_px: int | None = None
) -> tuple[bytes, int, int, float, float]:
    """Rend une page PDF en PNG **pour l'affichage** (tracé humain), + dimensions.

    Le raster sert UNIQUEMENT de fond pour que l'ingénieur trace les pièces ; on
    ne **mesure** rien dessus par vision — la mesure vient des clics calibrés.
    ``max_side_px`` plafonne le côté le plus long (le zoom est réduit en
    conséquence) pour borner le poids du PNG embarqué — l'échelle reste correcte
    si on la déduit des dimensions retournées, pas du zoom demandé.
    Renvoie (png, largeur_px, hauteur_px, largeur_pt, hauteur_pt).
    """
    import fitz

    doc = fitz.open(str(path))
    page = doc[page_index]
    if max_side_px is not None:
        longest_pt = max(page.rect.width, page.rect.height) or 1.0
        zoom = min(zoom, max_side_px / longest_pt)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix.tobytes("png"), pix.width, pix.height, page.rect.width, page.rect.height


def parse_cpe(path: str | Path) -> CpeText:
    """Extrait le **texte** d'un CPE PDF vectoriel — déterministe, zéro vision.

    Brique générique du parsing CPE : on lit le texte réel du PDF (pas d'OCR).
    Un CPE **scanné** (que des images, aucun texte) est **refusé** (CLAUDE.md
    §2.3) — il faudrait de la vision/OCR, hors périmètre v1. Le mapping du texte
    vers les champs d'enveloppe (U, Uw, n50, inertie…) est fait en aval (hybride).
    """
    import fitz

    doc = fitz.open(str(path))
    pages: list[str] = [page.get_text("text") for page in doc]
    n_images = sum(len(page.get_images()) for page in doc)
    text = "\n".join(pages)
    if not text.strip():
        if n_images:
            raise ValueError(
                "CPE scanné (image, aucun texte) : non supporté en v1 — il faudrait de "
                "l'OCR/vision. Fournir un CPE PDF vectoriel (texte sélectionnable)."
            )
        raise ValueError("CPE vide : aucun texte extractible du PDF.")
    return CpeText(text=text, pages=pages, n_images=n_images)
