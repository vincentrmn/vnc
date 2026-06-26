"""Module `viz` — rendu de la géométrie reconstruite (plan).

Donne à voir ce que `geometry` a reconstruit : pièces (polygones), labels,
ouvrants. Indispensable à la validation humaine (§2.8) — l'ingénieur doit
*voir* le plan extrait avant de faire confiance aux calculs.

Niveau pré-étude : un plan schématique par niveau, pas un rendu CAO.
"""

from __future__ import annotations

import base64
import io

from zephyr.schemas import Building, Opening, Orientation, RoomLabel

# Direction cardinale → vecteur (x=Est, y=Nord) ; cohérent avec l'éditeur.
_ORIENT_DIR: dict[Orientation, tuple[float, float]] = {
    Orientation.N: (0.0, 1.0), Orientation.NE: (0.7, 0.7), Orientation.E: (1.0, 0.0),
    Orientation.SE: (0.7, -0.7), Orientation.S: (0.0, -1.0), Orientation.SW: (-0.7, -0.7),
    Orientation.W: (-1.0, 0.0), Orientation.NW: (-0.7, 0.7),
}

# Couleurs par label (lisibilité, pas normatif).
_LABEL_COLOR: dict[RoomLabel, str] = {
    RoomLabel.SEJOUR: "#cfe8cf",
    RoomLabel.CHAMBRE: "#cfe0f5",
    RoomLabel.CUISINE: "#f5e6cf",
    RoomLabel.SDB: "#cfeef0",
    RoomLabel.WC: "#e6cff5",
    RoomLabel.CIRCULATION: "#eeeeee",
    RoomLabel.BUREAU: "#f5cfd6",
    RoomLabel.TECHNIQUE: "#dddddd",
    RoomLabel.AUTRE: "#f0f0f0",
}


def render_plan_png(building: Building) -> bytes:
    """Rend le plan reconstruit (un sous-graphe par niveau) en PNG.

    Chaque pièce est dessinée depuis son ``polygon``, colorée par label, annotée
    (id, label, surface) ; les pièces sans polygone sont ignorées (rien à tracer).
    """
    import matplotlib

    matplotlib.use("Agg")  # backend sans affichage
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon

    rooms = [r for r in building.rooms if r.polygon and len(r.polygon) >= 3]
    levels = sorted({r.level for r in rooms}) or [0]

    fig, axes = plt.subplots(1, len(levels), figsize=(5 * len(levels), 5), squeeze=False)
    for ax, level in zip(axes[0], levels, strict=True):
        ax.set_title(f"Niveau {level}")
        ax.set_aspect("equal")
        ax.axis("off")
        for room in (r for r in rooms if r.level == level):
            color = _LABEL_COLOR.get(room.label, "#f0f0f0")
            ax.add_patch(MplPolygon(room.polygon, closed=True, facecolor=color, edgecolor="#333"))
            xs = [p[0] for p in room.polygon]
            ys = [p[1] for p in room.polygon]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            ax.text(
                cx,
                cy,
                f"{room.label.value}\n{room.area_m2:.1f} m²",
                ha="center",
                va="center",
                fontsize=8,
            )
            # Ouvrants : un trait bleu placé sur la FAÇADE correspondante (par
            # orientation), comme dans l'éditeur — pas tous au même bord.
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            rw, rh = (maxx - minx) or 1.0, (maxy - miny) or 1.0
            by_ori: dict[Orientation, list[Opening]] = {}
            for op in room.openings:
                by_ori.setdefault(op.orientation, []).append(op)
            for ori, ops in by_ori.items():
                dx, dy = _ORIENT_DIR.get(ori, (0.0, -1.0))
                ex, ey = cx + dx * rw / 2, cy + dy * rh / 2  # point milieu de la façade
                tx, ty = -dy, dx  # tangente le long du mur
                for k, _op in enumerate(ops):
                    off = (k - (len(ops) - 1) / 2) * 0.7
                    bx, by = ex + tx * off, ey + ty * off
                    ax.plot(
                        [bx - tx * 0.3, bx + tx * 0.3],
                        [by - ty * 0.3, by + ty * 0.3],
                        color="#1a73e8",
                        lw=3,
                        solid_capstyle="round",
                    )
        ax.relim()
        ax.autoscale_view()

    # Flèche Nord (+y).
    fig.text(0.01, 0.95, "N ↑", fontsize=11, weight="bold")
    legend = [
        mpatches.Patch(color=c, label=lbl.value)
        for lbl, c in _LABEL_COLOR.items()
        if any(r.label is lbl for r in rooms)
    ]
    if legend:
        fig.legend(handles=legend, loc="lower center", ncol=min(len(legend), 6), fontsize=8)

    buf = io.BytesIO()
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


def render_plan_data_uri(building: Building) -> str:
    """Plan reconstruit en data-URI base64 (pour l'embarquer dans le rapport HTML)."""
    png = render_plan_png(building)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


# Segment = paire de points en mètres ((x0, y0), (x1, y1)).
Segment = tuple[tuple[float, float], tuple[float, float]]


def render_segments_background(
    segments: list[Segment],
    *,
    max_px: int = 1600,
    ppm_cap: float = 300.0,
    max_segments: int = 300_000,
) -> tuple[bytes, int, int, float]:
    """Rend des segments CAO (en mètres) en image de fond pour l'éditeur de tracé.

    Sert au **tracé universel** (§10.3) : un DXF (déjà à l'échelle, en mètres) est
    affiché en fond, l'ingénieur trace les pièces dessus. L'image est dimensionnée
    pour que la conversion px→m de l'éditeur (``x*mpp``, ``(H−y)*mpp``) soit exacte :
    origine en bas-gauche du bbox, échelle uniforme.

    Returns:
        ``(png, w_px, h_px, m_per_px)``. ``m_per_px`` est exact (issu du DXF) — pas
        besoin de calibrer, contrairement au PDF.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    if len(segments) > max_segments:
        segments = segments[:max_segments]  # garde-fou perf (vrais A0 ~500k segments)

    xs = [p[0] for s in segments for p in s]
    ys = [p[1] for s in segments for p in s]
    if not xs:
        raise ValueError("Aucun segment vectoriel à afficher (DXF vide ?).")
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w_m = max(maxx - minx, 0.1)
    h_m = max(maxy - miny, 0.1)

    ppm = min(max_px / max(w_m, h_m), ppm_cap)  # pixels par mètre
    w_px = max(int(round(w_m * ppm)), 1)
    h_px = max(int(round(h_m * ppm)), 1)
    m_per_px = 1.0 / ppm

    # Translate origine bbox → (0,0) (les surfaces/orientations sont invariantes).
    segs = [((a[0] - minx, a[1] - miny), (b[0] - minx, b[1] - miny)) for a, b in segments]

    dpi = 100.0
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0.0, w_m)
    ax.set_ylim(0.0, h_m)
    ax.set_aspect("auto")  # le figsize colle déjà au ratio des données → échelle uniforme
    ax.axis("off")
    ax.add_collection(LineCollection(segs, colors="#9aa6b2", linewidths=0.5))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    return buf.getvalue(), w_px, h_px, m_per_px
