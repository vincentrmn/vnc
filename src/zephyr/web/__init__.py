"""Module `web` — pages HTML du produit (landing, formulaire, résultats).

Pages rendues en **fonctions pures** (chaînes HTML), comme le module `report` :
testables sans serveur, servies par FastAPI (`app/web.py`). Aucune dépendance de
templating — HTML/CSS auto-portés (les rendus sont des fichiers autonomes).

Design : teal = déterministe (notre signature), corail = accents. Sobre, lisible,
orienté décision. Toujours le disclaimer « pré-étude, non opposable ».
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from datetime import datetime

from zephyr.schemas import (
    Building,
    CalcLine,
    InertiaClass,
    Opening,
    Orientation,
    Room,
    RoomLabel,
    StudyResult,
    Verdict,
)

_SILL_M = 0.9  # allège par défaut (m) ; hauteur de châssis = head − sill

# --- Jeu d'icônes (Lucide, ISC) -------------------------------------------------
# Icônes vectorielles minimalistes mono-couleur (trait), inlinées (pas de dépendance
# runtime : rendu instantané + thème via `currentColor` + fonctionne dans le PDF
# WeasyPrint où aucun JS ne tourne). Cf. CLAUDE.md §5 (toujours la meilleure lib
# spécialisée). Contenu interne SVG repris verbatim de lucide-static.
_ICONS: dict[str, str] = {
    "moon": '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "ruler": '<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z"/><path d="m14.5 12.5 2-2"/><path d="m11.5 9.5 2-2"/><path d="m8.5 6.5 2-2"/><path d="m17.5 15.5 2-2"/>',
    "building": '<path d="M10 12h4"/><path d="M10 8h4"/><path d="M14 21v-3a2 2 0 0 0-4 0v3"/><path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"/><path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
    "file": '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "pencil": '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    "hardhat": '<path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"/><path d="M14 6a6 6 0 0 1 6 6v3"/><path d="M4 15v-3a6 6 0 0 1 6-6"/><rect x="2" y="15" width="20" height="4" rx="1"/>',
    "pin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "rect": '<path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="M21 19a2 2 0 0 1-2 2"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h1"/><path d="M14 3h1"/><path d="M14 21h1"/><path d="M3 9v1"/><path d="M21 9v1"/><path d="M3 14v1"/><path d="M21 14v1"/>',
    "spline": '<circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><path d="M5 17A12 12 0 0 1 17 5"/>',
    "magnet": '<path d="m12 15 4 4"/><path d="M2.352 10.648a1.205 1.205 0 0 0 0 1.704l2.296 2.296a1.205 1.205 0 0 0 1.704 0l6.029-6.029a1 1 0 1 1 3 3l-6.029 6.029a1.205 1.205 0 0 0 0 1.704l2.296 2.296a1.205 1.205 0 0 0 1.704 0l6.365-6.367A1 1 0 0 0 8.716 4.282z"/><path d="m5 8 4 4"/>',
    "window": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 4v4"/><path d="M2 8h20"/><path d="M6 4v4"/>',
    "download": '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
    "refresh": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "maximize": '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "bulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "sheet": '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/>',
    "save": '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "wind": '<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>',
    "thermometer": '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "external-link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
}

# Logo korr OFFICIEL (fichier Drive « Korr Logo Positif NBKG SVG.svg »), recadré sur
# le seul wordmark « korr. » (baseline « intelligence for the built world » retirée).
# `currentColor` → reprend la couleur de marque (var(--primary)) et s'adapte au thème.
_KORR_LOGO = (
    '<svg class="korr-logo" viewBox="26 -1 292.2 104.5" xmlns="http://www.w3.org/2000/svg" '
    'fill="currentColor" role="img" aria-label="korr">'
    '<path d="M27.14,0h21.37v55.23l23.81-27.54h24.82l-28.83,32.71,31.27,39.59h-24.1l-20.94-26.68-6.02,6.46v20.23h-21.37V0Z"/>'
    '<path d="M137.6,25.53c22.24,0,40.17,16.93,40.17,38.3s-17.93,38.3-40.17,38.3-40.17-16.93-40.17-38.3,17.79-38.3,40.17-38.3ZM137.6,84.69c11.54,0,20.7-9.16,20.7-20.86s-9.17-20.86-20.7-20.86-20.7,9.32-20.7,20.86,9.01,20.86,20.7,20.86Z"/>'
    '<path d="M188.95,27.69h21.37v9.9c3.3-7.32,11.05-11.48,20.94-11.48,2.01,0,4.45.29,5.6.43v20.08c-2.01-.43-4.45-.72-7.17-.72-12.19,0-19.37,7.03-19.37,18.79v35.29h-21.37V27.69Z"/>'
    '<path d="M247.62,27.69h21.37v9.9c3.3-7.32,11.05-11.48,20.94-11.48,2.01,0,4.45.29,5.6.43v20.08c-2.01-.43-4.45-.72-7.17-.72-12.19,0-19.37,7.03-19.37,18.79v35.29h-21.37V27.69Z"/>'
    '<rect x="295.53" y="4.92" width="21.63" height="21.63"/>'
    '<rect x="126.78" y="53.02" width="21.63" height="21.63"/>'
    '<circle cx="306.35" cy="89.17" r="10.82"/></svg>'
)


def _icon(name: str, size: int = 16) -> str:
    """SVG inline d'une icône Lucide (trait `currentColor`, donc thème-aware)."""
    inner = _ICONS[name]
    return (
        f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{inner}</svg>'
    )


def _info(text: str) -> str:
    """Petit « i » souligné qui révèle une explication au survol / focus."""
    t = html.escape(text)
    return f'<span class="info" tabindex="0" role="note" aria-label="{t}">i<span class="tip">{t}</span></span>'


def _parse_orientations(text: str) -> list[Orientation]:
    """Parse une liste d'orientations « S, W » → [S, W] (valeurs inconnues ignorées)."""
    out: list[Orientation] = []
    valid = {o.value for o in Orientation}
    for tok in text.replace(";", ",").split(","):
        t = tok.strip().upper()
        if t in valid and Orientation(t) not in out:
            out.append(Orientation(t))
    return out


def building_from_form(form: Mapping[str, str]) -> Building:
    """Reconstruit un `Building` depuis le formulaire de **validation édité**.

    La géométrie immuable (id, surface, polygone) transite en champs cachés ; les
    champs éditables (label, niveau, orientations, châssis) sont relus tels que
    corrigés par l'ingénieur. Fonction pure → testable sans serveur.
    """
    n = int(form.get("n_rooms", "0") or "0")
    rooms: list[Room] = []
    for i in range(n):
        rid = form.get(f"r{i}_id", f"room_{i}")
        area = float(form.get(f"r{i}_area", "0") or "0")
        height = float(form.get(f"r{i}_height", "2.6") or "2.6")
        level = int(float(form.get(f"r{i}_level", "0") or "0"))
        label = RoomLabel(form.get(f"r{i}_label", "autre") or "autre")
        try:
            poly = [(float(x), float(y)) for x, y in json.loads(form.get(f"r{i}_polygon", "[]"))]
        except (ValueError, TypeError):
            poly = []
        orients = _parse_orientations(form.get(f"r{i}_orient", ""))

        openings: list[Opening] = []
        for j in range(int(form.get(f"r{i}_nslots", "0") or "0")):
            facade = (form.get(f"r{i}_o{j}_facade", "") or "").strip().upper()
            if facade not in {o.value for o in Orientation}:
                continue  # slot vide / supprimé
            oarea = float(form.get(f"r{i}_o{j}_area", "1.5") or "1.5")
            sash_raw = form.get(f"r{i}_o{j}_sash", "") or ""
            head = _SILL_M + float(sash_raw) if sash_raw.strip() else None
            openings.append(
                Opening(
                    id=f"{rid}_w{j}",
                    area_m2=max(oarea, 0.1),
                    orientation=Orientation(facade),
                    sill_height_m=_SILL_M,
                    head_height_m=head,
                    openable=bool(form.get(f"r{i}_o{j}_openable")),
                )
            )

        rooms.append(
            Room(
                id=rid,
                label=label,
                area_m2=max(area, 0.01),
                height_m=height,
                level=level,
                polygon=poly,
                exterior_wall_orientations=orients,
                openings=openings,
            )
        )
    inertia = InertiaClass(form.get("inertia", "lourde") or "lourde")
    return Building(id="dxf", rooms=rooms, inertia_class=inertia)

# --------------------------------------------------------------------------- #
# Design system (CSS auto-porté, lignes courtes pour le linter)
# --------------------------------------------------------------------------- #
_CSS = """
/* ============================================================================
   CHARTE ZÉPHYR — design tokens (source de vérité unique). DA : SaaS épuré,
   palette KORR (vert forêt #3a5b42 + neutres), Helvetica Neue, 8pt. Clair+sombre.
   Voir DESIGN.md. Ne pas écrire de hex en dur dans les composants : utiliser les
   variables ci-dessous.
   ========================================================================== */
:root {
  /* Couleurs — marque KORR */
  --bg: #fbfbf6;            /* fond appli (blanc cassé chaud) */
  --surface: #ffffff;       /* cartes */
  --surface-2: #f3f4ef;     /* surfaces secondaires, pistes */
  --ink: #141513;           /* texte principal */
  --muted: #5d6c7b;         /* texte secondaire (gris froid KORR) */
  --faint: #909a93;         /* texte tertiaire / placeholders */
  --line: #e6e7e1;          /* bordures, séparateurs */
  --primary: #3a5b42;       /* vert KORR — actions */
  --primary-strong: #2b4632;/* hover / pressé */
  --primary-soft: #eaf0ea;  /* fonds teintés */
  --on-primary: #ffffff;
  --danger: #c0392b; --danger-soft: #fdeeec;
  --warn: #9a6b00; --warn-soft: #fbf3df; --warn-line: #ecd9a8;
  --ring: rgba(58,91,66,.40);
  --shadow-1: 0 1px 2px rgba(20,21,19,.04), 0 1px 3px rgba(20,21,19,.07);
  --shadow-2: 0 6px 24px rgba(20,21,19,.10);
  /* Notes A→E */
  --a: #1f9254; --b: #2f8f7a; --c: #c79a00; --d: #cf6b30; --e: #c0392b;
  /* Espacements (8pt) */
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 48px; --s8: 64px;
  /* Rayons */
  --r1: 8px; --r2: 12px; --r3: 16px; --pill: 999px;
  /* Alias rétro-compat (ancien nommage) */
  --teal: var(--primary); --teal-d: var(--primary-strong); --coral: var(--danger);
  --card: var(--surface);
}
:root[data-theme="dark"] {
  --bg: #121212;
  --surface: #1b1c19;
  --surface-2: #232420;
  --ink: #f1f1ec;
  --muted: #a3aea7;
  --faint: #79847d;
  --line: #2d2f2a;
  --primary: #84b58c;       /* vert éclairci pour fond sombre */
  --primary-strong: #9ec8a4;
  --primary-soft: #1f2620;
  --on-primary: #10140f;
  --danger: #e06a5d; --danger-soft: #2a1c1a;
  --warn: #e0b257; --warn-soft: #2a2418; --warn-line: #4a3f24;
  --ring: rgba(132,181,140,.45);
  --shadow-1: 0 1px 2px rgba(0,0,0,.4); --shadow-2: 0 8px 28px rgba(0,0,0,.5);
}
* { box-sizing: border-box; }
html { color-scheme: light dark; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  line-height: 1.55; -webkit-font-smoothing: antialiased;
}
a { color: var(--primary-strong); text-decoration: none; }
a:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; border-radius: 4px; }
h1, h2, h3 { letter-spacing: -.02em; }
.wrap { max-width: 980px; margin: 0 auto; padding: 0 var(--s5); }
.wrap.wide { max-width: 1500px; }
nav { padding: var(--s4) 0; }
.nav-inner { display: flex; align-items: center; justify-content: space-between; }
.brand { display: inline-flex; align-items: center; gap: .5rem; font-weight: 700;
  letter-spacing: -.03em; font-size: 1.3rem; color: var(--ink); }
.brand:hover { text-decoration: none; }
.brand .brand-x { color: var(--muted); font-weight: 400; margin: 0 .05rem; }
.brand .brand-name { color: var(--ink); }
.brand .dot-g { color: var(--primary); }
.korr-logo { height: .9em; width: auto; display: inline-block; vertical-align: -.12em;
  color: var(--primary); }
.btn .korr-logo { height: .95em; }
.nav-right { display: flex; align-items: center; gap: var(--s3); }
.theme-toggle {
  display: inline-grid; place-items: center; width: 2.1rem; height: 2.1rem;
  border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: var(--r1); cursor: pointer; font-size: 1rem; line-height: 1;
}
.theme-toggle:hover { border-color: var(--primary); }
/* Boutons */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: .4rem;
  background: var(--primary); color: var(--on-primary); font-weight: 600;
  padding: .6rem 1.1rem; border-radius: var(--r1); border: 1px solid var(--primary);
  cursor: pointer; font: inherit; font-weight: 600; line-height: 1.2;
  transition: background .15s ease, border-color .15s ease, transform .05s ease;
}
.btn:hover { background: var(--primary-strong); border-color: var(--primary-strong); text-decoration: none; }
.btn:active { transform: translateY(1px); }
.btn.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
.btn.ghost:hover { background: var(--primary-soft); border-color: var(--primary); color: var(--primary-strong); }
.btn.sm { padding: .35rem .7rem; font-size: .85rem; }
/* Hero / landing */
.hero { padding: var(--s8) 0 var(--s6); }
.hero h1 { font-size: 2.7rem; line-height: 1.08; letter-spacing: -.04em; margin: 0 0 var(--s3); }
.hero p.lead { font-size: 1.2rem; color: var(--muted); max-width: 640px; }
.kicker {
  display: inline-block; font-size: .78rem; font-weight: 700; letter-spacing: .03em;
  text-transform: uppercase; color: var(--primary-strong);
  background: var(--primary-soft); padding: .3rem .7rem; border-radius: var(--pill); margin-bottom: var(--s4);
}
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s4); margin: var(--s6) 0; }
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r2);
  padding: var(--s5); box-shadow: var(--shadow-1);
}
.card h3 { margin: .2rem 0 .4rem; font-size: 1.05rem; }
.card .n {
  display: inline-grid; place-items: center; width: 1.8rem; height: 1.8rem;
  background: var(--primary); color: var(--on-primary); border-radius: 50%; font-weight: 700; font-size: .9rem;
}
.crit-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--s3); margin: var(--s4) 0; }
.disclaimer {
  background: var(--warn-soft); border: 1px solid var(--warn-line); border-radius: var(--r1);
  padding: .7rem .9rem; font-size: .9rem; color: var(--warn); margin: var(--s5) 0;
}
footer { color: var(--muted); font-size: .85rem; padding: var(--s6) 0 var(--s6);
  border-top: 1px solid var(--line); margin-top: var(--s8); }
.site-footer { display: flex; gap: var(--s4); align-items: center; justify-content: space-between; }
.site-footer a { color: var(--muted); }
.site-footer a:hover { color: var(--primary); }
/* Résultats */
.result-head { display: flex; gap: var(--s5); align-items: center; flex-wrap: wrap; margin: var(--s4) 0; }
.gauge { flex: 0 0 auto; }
.badge { display: inline-block; padding: .3rem .8rem; border-radius: var(--r1); color: #fff;
  font-weight: 700; font-size: .9rem; }
.bars { margin: var(--s4) 0; }
.bar-row { display: grid; grid-template-columns: 1fr 200px 44px; gap: .7rem;
  align-items: center; padding: .4rem 0; border-bottom: 1px solid var(--line); }
.bar-row .lab { font-weight: 600; font-size: .92rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.track { background: var(--surface-2); border-radius: var(--pill); height: .55rem; overflow: hidden; }
.fill { height: 100%; border-radius: var(--pill); }
.bar-row .val { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }
/* Critère dépliable : détail par pièce/poste + calcul de la note */
.crit { border-bottom: 1px solid var(--line); }
.crit > summary { list-style: none; cursor: pointer; border-bottom: 0; }
.crit > summary::-webkit-details-marker { display: none; }
.crit > summary .lab::before { content: '▸'; color: var(--muted); margin-right: .4rem;
  display: inline-block; transition: transform .15s; }
.crit[open] > summary .lab::before { transform: rotate(90deg); }
.crit-detail { padding: .2rem 0 .9rem 1.1rem; }
.crit-summary { font-size: .88rem; color: var(--ink); margin: .2rem 0 .5rem; }
.crit-scale { font-size: .82rem; color: var(--muted); margin: .55rem 0 .2rem; }
.crit-list { margin: .15rem 0 .6rem; padding-left: 1.1rem; }
.crit-list li { margin: .12rem 0; }
ul.crit-list.crit-summary { color: var(--ink); font-size: .88rem; }
.crit-scale + ul.crit-list { color: var(--muted); font-size: .82rem; }
.crit-formula { font-size: .84rem; font-weight: 600; color: var(--ink); margin: .4rem 0 0; }
table.bd { width: 100%; border-collapse: collapse; font-size: .82rem; margin: .2rem 0; }
table.bd th { text-align: left; color: var(--muted); font-weight: 700; font-size: .7rem;
  text-transform: uppercase; letter-spacing: .03em; padding: .3rem .45rem; border-bottom: 1px solid var(--line); }
table.bd td { padding: .3rem .45rem; border-bottom: 1px solid var(--line); }
table.bd td:not(:first-child) { font-variant-numeric: tabular-nums; }
.reco { background: var(--primary-soft); border-left: 3px solid var(--primary); padding: .7rem .9rem;
  border-radius: var(--r1); margin: .5rem 0; }
.flag { background: var(--danger-soft); border-left: 3px solid var(--danger); padding: .7rem .9rem;
  border-radius: var(--r1); margin: .5rem 0; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s3); margin: var(--s4) 0; }
.kpi { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r1);
  padding: .9rem; box-shadow: var(--shadow-1); }
.kpi .k { color: var(--muted); font-size: .82rem; }
.kpi .v { font-size: 1.35rem; font-weight: 700; letter-spacing: -.02em; }
/* Formulaires — ciblage par type (les champs des cartes sont liés par form="…", pas imbriqués) */
form label { display: block; font-weight: 600; font-size: .9rem; margin: .8rem 0 .2rem; }
input[type=text], input[type=number], input[type=search], input[type=email], input[type=tel],
select, textarea { width: 100%; padding: .5rem .6rem; box-sizing: border-box;
  border: 1px solid var(--line); border-radius: var(--r1); font: inherit; font-size: .92rem;
  background: var(--surface-2); color: var(--ink); transition: border-color .12s, box-shadow .12s; }
input[type=text]:hover, input[type=number]:hover, select:hover, textarea:hover { border-color: var(--faint); }
/* Sélecteurs épurés : flèche custom (pas de combo natif « noir et gros ») */
select { appearance: none; -webkit-appearance: none; -moz-appearance: none;
  padding-right: 2rem; cursor: pointer;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%235d6c7b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='m6 9 6 6 6-6'/></svg>");
  background-repeat: no-repeat; background-position: right .6rem center; }
input::placeholder { color: var(--faint); }
input:focus, select:focus, textarea:focus { border-color: var(--primary); outline: none;
  background: var(--surface); box-shadow: 0 0 0 3px var(--ring); }
/* Cases à cocher / radios : cases standard du navigateur, teintées à la marque */
input[type=checkbox], input[type=radio] { accent-color: var(--primary); width: 1.05em; height: 1.05em;
  cursor: pointer; vertical-align: -.12em; flex: none; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 var(--s4); }
/* En-tête de la page config : titre + reprise discrète */
.form-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap; }
.resume { position: relative; }
.resume > summary { cursor: pointer; color: var(--ink); font-size: .9rem; font-weight: 600;
  list-style: none; display: inline-flex; align-items: center; gap: .4rem;
  border: 1px solid var(--line); border-radius: var(--r1); padding: .55rem 1rem;
  background: var(--surface); transition: border-color .15s, background .15s, color .15s; }
.resume > summary::-webkit-details-marker { display: none; }
.resume > summary:hover, .resume[open] > summary { color: var(--primary-strong);
  border-color: var(--primary); background: var(--primary-soft); }
/* Panneau flottant : s'ouvre par-dessus, ne décale aucun contenu */
.resume-form { position: absolute; right: 0; top: 1.8rem; z-index: 30; width: max-content; max-width: 340px;
  display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--r1); padding: .7rem .8rem;
  box-shadow: 0 10px 28px rgba(0,0,0,.16); }
/* Ligne d'upload + action séparée du cadre */
/* Bloc upload : sélection de fichier sur une ligne, action (Extraire) en dessous */
.upload-row { display: flex; flex-direction: column; align-items: flex-start; gap: .6rem; }
.filefield { display: inline-flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.filefield .filename { color: var(--muted); font-size: .88rem; }
/* Bouton de sélection de fichier : vert pâle discret */
.filebtn { background: var(--primary-soft); color: var(--primary-strong); border: 1px solid var(--primary-soft);
  border-radius: var(--r1); padding: .45rem .9rem; font: inherit; font-weight: 600; cursor: pointer; }
.filebtn:hover { background: var(--primary); color: var(--on-primary); }
.check { display: flex; align-items: center; gap: .5rem; margin: .5rem 0; }
.check input { width: auto; }
.winrow { display: flex; gap: .5rem; align-items: center; margin: .3rem 0; flex-wrap: wrap; }
.winrow select, .winrow input { padding: .35rem .4rem; }
/* Éditeur de validation (SVG) */
.editor { display: grid; grid-template-columns: 1.4fr 1fr; gap: var(--s4); align-items: start; }
.editor svg { width: 100%; height: 520px; display: block; background: #fff;
  border: 1px solid var(--line); border-radius: var(--r1); }
#panel { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r1);
  padding: var(--s4); position: sticky; top: 1rem; }
#panel label { display: block; font-weight: 600; font-size: .85rem; margin: .6rem 0 .2rem; }
#panel select, #panel input[type=number] { width: 100%; padding: .4rem; border: 1px solid var(--line);
  border-radius: var(--r1); font: inherit; background: var(--surface); color: var(--ink); }
.chips { display: flex; flex-wrap: wrap; gap: .3rem; }
.chip { display: inline-flex; align-items: center; gap: .2rem; font-size: .82rem; font-weight: 500;
  border: 1px solid var(--line); border-radius: var(--pill); padding: .15rem .5rem; cursor: pointer;
  color: var(--ink); }
.chip input { width: auto; }
.badge-ok { background: var(--primary); color: var(--on-primary); font-size: .72rem; padding: .1rem .45rem;
  border-radius: .35rem; }
.levelbar { display: flex; gap: .4rem; margin: .4rem 0; flex-wrap: wrap; }
.levelbar button { border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  border-radius: var(--r1); padding: .35rem .8rem; cursor: pointer; font: inherit; font-weight: 600; }
.levelbar button.active { background: var(--primary); color: var(--on-primary); border-color: var(--primary); }
.tracebar { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; margin: .6rem 0; }
.tracebar .btn { padding: .4rem .8rem; }
#plan image { image-rendering: auto; }
@media (max-width: 760px) { .editor { grid-template-columns: 1fr; } }
h2.sec { margin: var(--s6) 0 .4rem; padding-bottom: .3rem; border-bottom: 2px solid var(--line); font-size: 1.3rem; }
table.kv { border-collapse: collapse; width: 100%; }
table.kv td { border-bottom: 1px solid var(--line); padding: .35rem .2rem; }
table.kv td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) {
  .steps, .crit-grid, .kpis, .form-grid { grid-template-columns: 1fr; }
  .hero h1 { font-size: 2rem; }
  .hero-xl .display { white-space: normal; }
}
/* Page config : cartes, uploaders, toggle segmenté */
.card > h2 { display: flex; align-items: center; gap: .5rem; font-size: 1.15rem; margin: 0 0 .2rem; }
.card .sub { color: var(--muted); font-size: .9rem; margin: 0 0 var(--s4); }
.field { margin: .8rem 0; }
.field > .lab { font-weight: 600; font-size: .92rem; margin-bottom: .35rem; }
.field .hint { color: var(--muted); font-size: .82rem; margin: .35rem 0 0; }
.hint { color: var(--muted); font-size: .82rem; }
.hint.err { display: inline-flex; align-items: center; gap: .45rem; color: var(--danger);
  font-weight: 600; font-size: .84rem; background: var(--danger-soft);
  border: 1px solid var(--danger); border-radius: var(--pill); padding: .35rem .75rem;
  vertical-align: middle; }
.hint.err::before { content: '!'; display: inline-flex; align-items: center; justify-content: center;
  width: 1.05rem; height: 1.05rem; flex: none; border-radius: 50%; background: var(--danger);
  color: #fff; font-size: .72rem; font-weight: 700; }
.uploader { border: 1.5px dashed var(--line); border-radius: var(--r1); padding: 1rem 1.1rem;
  background: var(--surface-2); }
.uploader + .uploader { margin-top: .8rem; }
input[type=file] { width: 100%; font: inherit; color: var(--muted); border: 0; padding: 0; background: none; }
input[type=file]::file-selector-button {
  background: var(--primary-soft); color: var(--primary-strong); border: 1px solid var(--primary);
  border-radius: var(--r1); padding: .45rem .9rem; font-weight: 600; cursor: pointer; margin-right: .8rem;
}
input[type=file]::file-selector-button:hover { background: var(--primary); color: var(--on-primary); }
.seg { display: inline-flex; gap: .2rem; background: var(--surface-2); border: 1px solid var(--line);
  border-radius: var(--pill); padding: .2rem; }
.seg label { padding: .35rem .9rem; cursor: pointer; font-weight: 600; font-size: .88rem;
  color: var(--muted); border-radius: var(--pill); user-select: none; transition: background .12s, color .12s; }
.seg label.on { background: var(--surface); color: var(--ink); box-shadow: var(--shadow-1); }
.seg input { position: absolute; opacity: 0; pointer-events: none; }
/* Éditeur de tracé (Konva) : plan + palette fixés à l'écran, liste de pièces qui défile seule */
.trace-head { margin-bottom: .4rem; }
/* Menus dépliants d'explication : ampoule + cadre jaune pâle pour ressortir */
.explain { background: #fdf6e3; border: 1px solid #efdfa6; border-radius: var(--r1);
  padding: .5rem .9rem; margin: .8rem 0; }
.explain > summary { cursor: pointer; font-weight: 600; font-size: .92rem; list-style: none;
  display: inline-flex; align-items: center; gap: .45rem; color: var(--ink); }
.explain > summary::-webkit-details-marker { display: none; }
.explain > summary .ic { color: #c79400; flex: none; }
.explain ol, .explain ul, .explain p, .explain table { margin: .5rem 0 .2rem; }
.explain ol { padding-left: 1.2rem; line-height: 1.7; font-size: .9rem; }
.explain li { margin: .15rem 0; }
.explain li b { color: var(--ink); }
:root[data-theme="dark"] .explain { background: #29260f; border-color: #4a4320; }
.howto { margin: .4rem 0 .6rem; }
kbd { font: 600 .78rem/1 'Helvetica Neue', Arial, sans-serif; background: var(--surface);
  border: 1px solid var(--line); border-bottom-width: 2px; border-radius: .35rem;
  padding: .12rem .4rem; color: var(--ink); white-space: nowrap; }
.trace-layout { display: grid; grid-template-columns: 1fr 360px; gap: var(--s4); align-items: start; }
.trace-canvas-wrap { position: sticky; top: .6rem; }
.stage-mode { min-height: 1.6rem; margin-bottom: .4rem; font-weight: 700; font-size: .9rem;
  display: flex; align-items: center; gap: .45rem; padding: .45rem .7rem; border-radius: var(--r1);
  background: var(--primary-soft); color: var(--primary-strong); border: 1px solid var(--primary); }
.stage-mode.empty { background: var(--surface-2); color: var(--muted); font-weight: 400;
  border-color: var(--line); }
#stage { width: 100%; height: calc(100vh - 7rem); min-height: 420px; background: #fff;
  border: 1px solid var(--line); border-radius: var(--r2); overflow: hidden; touch-action: none;
  box-shadow: var(--shadow-1); }
.trace-side { position: sticky; top: .6rem; height: calc(100vh - 4.5rem);
  display: flex; flex-direction: column; gap: .6rem; }
/* Onglets Outils / Pièces : on bascule sans scroller */
.side-tabs { display: flex; gap: .3rem; background: var(--surface-2); border: 1px solid var(--line);
  border-radius: var(--pill); padding: .2rem; flex: none; }
.side-tabs button { flex: 1; border: 0; background: none; cursor: pointer; font: inherit;
  font-weight: 600; font-size: .88rem; color: var(--muted); padding: .35rem .6rem; border-radius: var(--pill); }
.side-tabs button.active { background: var(--surface); color: var(--ink); box-shadow: var(--shadow-1); }
.side-tabs .cnt { display: inline-grid; place-items: center; min-width: 1.2rem; height: 1.2rem;
  padding: 0 .3rem; margin-left: .2rem; background: var(--primary); color: var(--on-primary);
  border-radius: var(--pill); font-size: .72rem; }
.palette { flex: 1; min-height: 0; overflow-y: auto; }
.roomlist-wrap { flex: 1; min-height: 0; overflow-y: auto; }
#roomlist { display: flex; flex-direction: column; gap: .5rem; }
#roomlist .empty { color: var(--muted); font-size: .9rem; }
.palette { flex: none; display: flex; flex-direction: column; gap: .7rem;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r2); padding: .9rem;
  box-shadow: var(--shadow-1); }
.pgroup { display: flex; flex-direction: column; gap: .4rem; padding-bottom: .6rem; border-bottom: 1px solid var(--line); }
.pgroup:last-of-type { border-bottom: 0; padding-bottom: 0; }
.ptitle { font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 700; }
.palette .btn { width: 100%; text-align: center; padding: .5rem .7rem; }
.palette .btn.active { background: var(--primary); color: var(--on-primary); border-color: var(--primary);
  box-shadow: inset 0 0 0 2px rgba(255,255,255,.30); }
.palette .row { display: flex; gap: .35rem; }
.palette .row .btn { flex: 1; }
.palette .lbl { font-size: .82rem; font-weight: 600; color: var(--muted); }
.palette .chk { display: flex; align-items: center; gap: .4rem; font-size: .85rem; font-weight: 600; color: var(--ink); cursor: pointer; }
.palette .chk input { width: auto; }
/* Sélecteur de niveau : petits boutons sur une ligne (RDC / R+1 …) */
.levelsel { display: flex; gap: .3rem; flex-wrap: nowrap; overflow-x: auto; padding-bottom: .15rem; }
.levelsel button { flex: none; border: 1px solid var(--line); background: var(--surface);
  color: var(--ink); border-radius: var(--r1); padding: .25rem .6rem; cursor: pointer;
  font: inherit; font-weight: 600; font-size: .82rem; }
.levelsel button.active { background: var(--primary); color: var(--on-primary); border-color: var(--primary); }
.roomlist-wrap { flex: 1; min-height: 0; overflow-y: auto; padding-right: .3rem; }
.room-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r1);
  padding: .6rem .7rem; margin: .45rem 0; box-sizing: border-box; max-width: 100%; }
/* Sélection : bordure + ombre interne (l'outline était rognée par le conteneur scrollable) */
.room-card.sel { border-color: var(--primary); box-shadow: inset 0 0 0 2px var(--primary); }
.room-head { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; min-width: 0; }
.room-head select { padding: .2rem; flex: 0 1 auto; min-width: 0; max-width: 100%; }
/* Validation au tracé d'une pièce : modale centrée (suit l'écran, jamais coincée au scroll) */
.trace-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.28); z-index: 59; }
.trace-pop { position: fixed; left: 50%; top: 50%; transform: translate(-50%, -50%);
  z-index: 60; background: var(--surface); border: 1px solid var(--primary);
  border-radius: var(--r1); padding: .8rem .9rem; box-shadow: 0 12px 40px rgba(0,0,0,.28);
  display: flex; flex-direction: column; gap: .5rem; min-width: 240px; }
.trace-pop .tp-t { font-size: .85rem; font-weight: 700; color: var(--ink); }
.trace-pop .tp-sel { padding: .4rem .5rem; border: 1px solid var(--line); border-radius: var(--r1);
  font: inherit; background: var(--surface-2); color: var(--ink); }
.trace-pop .tp-row { display: flex; gap: .5rem; }
/* Toast tutoriel (1re pièce) + pulsation de l'onglet Pièces */
.trace-toast { position: fixed; left: 50%; top: 1.2rem; transform: translateX(-50%); z-index: 200;
  max-width: 380px; background: var(--primary); color: var(--on-primary); padding: .85rem 1.1rem;
  border-radius: var(--r1); box-shadow: 0 14px 40px rgba(0,0,0,.3); font-size: .9rem; line-height: 1.45;
  animation: toastIn .25s ease-out; }
.trace-toast b { color: var(--on-primary); }
.trace-toast .tt-x { display: inline-block; margin-top: .5rem; background: var(--on-primary);
  color: var(--primary); border: 0; border-radius: var(--r1); padding: .3rem .8rem; font: inherit;
  font-weight: 700; cursor: pointer; }
@keyframes toastIn { from { opacity: 0; transform: translate(-50%, -8px); }
  to { opacity: 1; transform: translate(-50%, 0); } }
.side-tabs button.pulse { animation: pulseTab 1s ease-in-out 0s 5; }
@keyframes pulseTab { 0%,100% { box-shadow: 0 0 0 0 var(--ring); background: var(--surface); color: var(--ink); }
  50% { box-shadow: 0 0 0 5px var(--ring); background: var(--primary); color: var(--on-primary); } }
.room-no { display: inline-grid; place-items: center; width: 1.5rem; height: 1.5rem;
  background: var(--primary); color: var(--on-primary); border-radius: 50%; font-size: .8rem; font-weight: 700; }
.room-head .grow { flex: 1; }
.nivlbl { font-size: .78rem; color: var(--muted); }
.room-sec { margin-top: .5rem; }
.room-seclbl { display: block; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
  color: var(--muted); font-weight: 700; margin-bottom: .25rem; }
.wintab { width: 100%; border-collapse: collapse; font-size: .8rem; }
.wintab th { text-align: left; font-weight: 600; color: var(--muted); font-size: .72rem; padding: .1rem .2rem; }
.wintab td { padding: .12rem .2rem; }
.wintab .wref { font-weight: 700; color: var(--primary); white-space: nowrap; }
.wintab select[data-wf="facade"] { width: 64px; padding: .15rem; }
.wintab tr.wprot td { padding-bottom: .5rem; border-bottom: 1px solid var(--line); }
.wprot-lbl { color: var(--muted); font-size: .72rem; margin-right: .45rem; }
.wprot-sel { width: auto; min-width: 60%; padding: .15rem; }
.iconbtn { border: 1px solid var(--line); background: var(--surface); color: var(--muted); cursor: pointer;
  border-radius: .35rem; padding: .15rem .35rem; font-size: .8rem; line-height: 0; }
.iconbtn:hover { color: var(--danger); border-color: var(--danger); }
/* Icônes Lucide inline : trait currentColor, alignées au texte */
.ic { display: inline-block; vertical-align: -.15em; }
h2 .ic { vertical-align: -.12em; margin-right: .45rem; color: var(--primary-strong); }
.sec-head .ic { vertical-align: -.1em; }
.btn.mini { padding: .25rem .6rem; font-size: .82rem; margin-top: .4rem; }
@media (max-width: 980px) {
  .trace-layout { grid-template-columns: 1fr; }
  .trace-canvas-wrap, .trace-side { position: static; max-height: none; }
  #stage { height: 62vh; }
}
/* Landing & résultats — registre éditorial (moins "SaaS générique") */
.eyebrow { display: flex; align-items: center; gap: .5rem; font-size: .72rem; font-weight: 700;
  letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.eyebrow .dot { width: .45rem; height: .45rem; border-radius: 50%; background: var(--primary); }
.hero-xl { padding: var(--s8) 0 var(--s7); }
.display { font-size: clamp(2.5rem, 6.5vw, 5rem); line-height: 1.02; letter-spacing: -.045em;
  font-weight: 700; margin: var(--s4) 0; max-width: 16ch; }
.display em { font-style: normal; color: var(--primary); }
.hero-xl .display { white-space: nowrap; }
.lead-xl { font-size: 1.2rem; color: var(--muted); max-width: 52ch; line-height: 1.5; }
.hero-xl .lead-xl { max-width: none; }
.cta-row { display: flex; gap: .8rem; flex-wrap: wrap; margin-top: var(--s5); }
.rule { border: 0; border-top: 1px solid var(--line); margin: 0; }
.sec-head { display: flex; align-items: baseline; gap: .8rem; margin: var(--s7) 0 var(--s4); }
.sec-head .idx { font-size: .8rem; font-weight: 700; color: var(--primary); letter-spacing: .1em; }
.sec-head h2 { font-size: clamp(1.4rem, 3vw, 2rem); margin: 0; letter-spacing: -.03em; }
.process { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--line); }
.proc { padding: var(--s5) var(--s4) var(--s5) 0; border-bottom: 1px solid var(--line); }
.proc + .proc { border-left: 1px solid var(--line); padding-left: var(--s4); }
.proc .num { font-size: 1.6rem; font-weight: 700; color: var(--primary); letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; }
.proc h3 { margin: .5rem 0 .3rem; font-size: 1.1rem; }
.proc p { margin: 0; color: var(--muted); font-size: .95rem; }
.pillars { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s5); margin-top: var(--s2); }
.pillar .ic { color: var(--primary); }
.pillar h3 { margin: .7rem 0 .35rem; font-size: 1.15rem; letter-spacing: -.01em; }
.pillar p { margin: 0; color: var(--muted); font-size: .95rem; line-height: 1.55; }
.note-muted { color: var(--muted); font-size: .9rem; margin-top: var(--s5); max-width: 60ch; }
.crit-list-v { border-top: 1px solid var(--line); margin-top: var(--s2); }
.crit-item { display: grid; grid-template-columns: auto 1fr; gap: var(--s4); align-items: start;
  padding: var(--s4) 0; border-bottom: 1px solid var(--line); }
.crit-item .ic { color: var(--primary); margin-top: .15rem; }
.crit-item .t { font-weight: 600; font-size: 1.08rem; }
.crit-item .d { color: var(--muted); font-size: .95rem; line-height: 1.5; margin-top: .15rem; }
.video-ph { margin: var(--s6) 0 0; aspect-ratio: 16 / 9; width: 100%; border-radius: var(--r2);
  border: 1px dashed var(--line); background: var(--surface-2); display: flex;
  align-items: center; justify-content: center; gap: .6rem; color: var(--muted); }
.video-ph .ic { color: var(--muted); }
.spec { border-top: 1px solid var(--line); margin-top: var(--s2); }
.spec-row { display: grid; grid-template-columns: 1fr auto; gap: .4rem 1.5rem;
  padding: 1rem 0; border-bottom: 1px solid var(--line); align-items: baseline; }
.spec-row .t { font-weight: 600; font-size: 1.05rem; }
.spec-row .w { font-variant-numeric: tabular-nums; color: var(--primary); font-weight: 700; text-align: right; }
.spec-row .d { grid-column: 1 / -1; color: var(--muted); font-size: .92rem; margin-top: -.1rem; }
/* Résultats — note (cercle) + verdict sur une même ligne, conclusion en dessous */
.score-hero { display: flex; align-items: center; gap: var(--s4); flex-wrap: wrap;
  padding: var(--s4) 0 var(--s3); }
.score-hero .verdict-title { font-size: clamp(1.5rem, 3.4vw, 2.2rem); margin: 0; letter-spacing: -.03em; }
/* Conclusion : points forts / points de vigilance */
.concl { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: .8rem;
  margin: 0 0 var(--s5); padding-bottom: var(--s5); border-bottom: 1px solid var(--line); }
.concl-col { border: 1px solid var(--line); border-radius: var(--r1); padding: .6rem .8rem;
  font-size: .9rem; background: var(--surface); }
.concl-col > div { margin: .15rem 0; }
.concl-h { font-weight: 700; display: flex; align-items: center; gap: .4rem; margin-bottom: .3rem !important; }
.concl-col.good { border-left: 3px solid var(--ok, #1a9d5a); }
.concl-col.good .concl-h { color: #1a9d5a; }
.concl-col.bad { border-left: 3px solid var(--danger); }
.concl-col.bad .concl-h { color: var(--danger); }
.result-actions { margin: 0 0 1.4rem; padding: .7rem .9rem; background: var(--surface-2);
  border: 1px solid var(--line); border-radius: var(--r1); }
.result-actions .ra-lbl { font-size: .72rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .05em; color: var(--muted); margin-bottom: .5rem; }
.result-actions .ra-btns { display: flex; gap: .6rem; flex-wrap: wrap; }
.hyp-grp { margin: .9rem 0 .2rem; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em;
  color: var(--muted); font-weight: 700; }
/* Bandeau « estimation rapide » */
.quick-banner { display: flex; align-items: flex-start; gap: .5rem; background: #fdf6e3;
  border: 1px solid #efdfa6; border-radius: var(--r1); padding: .7rem .9rem; margin: 0 0 1.2rem;
  font-size: .9rem; line-height: 1.45; }
.quick-banner .ic { color: #c79400; flex: none; margin-top: .1rem; }
:root[data-theme="dark"] .quick-banner { background: #29260f; border-color: #4a4320; }
.explain table.kv td { font-size: .85rem; }
/* Bilan : séparateur discret entre les colonnes VMC et VNC */
.cost-cols > div:nth-child(2) { border-left: 1px solid var(--line); padding-left: var(--s4); }
@media (max-width: 720px) { .cost-cols > div:nth-child(2) { border-left: 0; padding-left: 0; } }
@media (max-width: 720px) {
  .process { grid-template-columns: 1fr; }
  .proc + .proc { border-left: 0; padding-left: 0; }
  .pillars { grid-template-columns: 1fr; gap: var(--s4); }
  .score-hero { grid-template-columns: 1fr; }
}
/* ROI à livre ouvert : chaque poste = ligne dépliable (formule + montant dessous) */
.costlist { margin: .2rem 0 .6rem; }
.costrow { border-bottom: 1px solid var(--line); }
.costrow > summary { display: flex; justify-content: space-between; align-items: baseline;
  gap: 1rem; padding: .42rem .2rem; cursor: pointer; list-style: none; }
.costrow > summary::-webkit-details-marker { display: none; }
.costrow > summary::before { content: '▸'; color: var(--muted); font-size: .7rem;
  margin-right: .4rem; display: inline-block; transition: transform .15s; }
.costrow[open] > summary::before { transform: rotate(90deg); }
.costrow .lbl { flex: 1; }
.costrow .amt { font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
.costrow .formula { color: var(--muted); font-size: .82rem; line-height: 1.45;
  padding: 0 .2rem .5rem 1.25rem; font-family: 'Helvetica Neue', Arial, sans-serif; }
.costrow.total { display: flex; justify-content: space-between; padding: .5rem .2rem;
  font-weight: 700; border-bottom: none; border-top: 2px solid var(--line); }
/* Graphe VAN (Chart.js) : conteneur à hauteur fixe (maintainAspectRatio:false) */
.vanchart { position: relative; height: 300px; margin: .6rem 0 .2rem; background: var(--surface);
  border: 1px solid var(--line); border-radius: .6rem; padding: .6rem .6rem .2rem; }
/* Info-bulle : petit rond avec un « i » dedans */
.info { display: inline-flex; align-items: center; justify-content: center; width: 1.15em; height: 1.15em;
  font-size: .7rem; font-style: normal; font-weight: 700; line-height: 1; text-decoration: none;
  color: var(--muted); border: 1.5px solid var(--muted); border-radius: 50%;
  cursor: help; position: relative; margin-left: .35rem; vertical-align: middle; }
.info:hover { color: var(--primary-strong); border-color: var(--primary-strong); }
.info .tip { position: absolute; bottom: 145%; left: 50%; transform: translateX(-50%);
  background: var(--ink); color: var(--bg); padding: .5rem .65rem; border-radius: .45rem; width: 240px;
  font: 400 .78rem/1.45 'Helvetica Neue', Arial, sans-serif; font-style: normal; text-align: left;
  text-decoration: none; letter-spacing: 0; opacity: 0; visibility: hidden; transition: opacity .12s;
  z-index: 50; box-shadow: 0 6px 18px rgba(0,0,0,.22); pointer-events: none; }
.info:hover .tip, .info:focus .tip { opacity: 1; visibility: visible; }
/* Barre d'actions en tête de résultats + hypothèses éditables */
.hyp { background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--r1);
  padding: .4rem .9rem; margin: .8rem 0; }
.hyp > summary { cursor: pointer; font-weight: 600; font-size: .92rem; }
.hyp .form-grid { margin-top: .6rem; }
/* Page styleguide */
.sg-swatch { display: inline-block; width: 64px; height: 64px; border-radius: var(--r1);
  border: 1px solid var(--line); vertical-align: middle; margin-right: .5rem; }
.sg-row { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; margin: .5rem 0; }
.sg-icons { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: .5rem; }
.sg-icon { display: flex; flex-direction: column; align-items: center; gap: .4rem;
  padding: .8rem .4rem; border: 1px solid var(--line); border-radius: var(--r1);
  background: var(--surface); color: var(--ink); }
.sg-icon code { font-size: .72rem; color: var(--muted); }
/* Impression / export PDF : la page telle quelle, en clair, dépliants ouverts.
   On force le rendu couleur, on masque le chrome interactif, on évite les coupures. */
@media print {
  nav, footer, .result-actions, .theme-toggle, .resume, .cta-row, .no-print { display: none !important; }
  body { background: #fff !important; color: #111 !important;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  main.wrap, main.wrap.wide { max-width: 100% !important; padding: 0 !important; }
  a { color: inherit !important; text-decoration: none !important; }
  details > summary { list-style: none; }
  details > summary::-webkit-details-marker { display: none; }
  .card, details, .crit, .kpi, .concl-col, table, .bar-row { break-inside: avoid; }
  h1, h2, h3 { break-after: avoid; }
}
"""

_DISCLAIMER = (
    "Pré-étude / aide à la décision. Ce document n'est pas une étude thermique "
    "opposable : les résultats sont des ordres de grandeur et exposent leurs hypothèses."
)

_VERDICT = {
    Verdict.GO: ("Bon candidat VNC", "#1a9d5a"),
    Verdict.CONDITIONNEL: ("Éligible, sous réserves", "#d9a400"),
    Verdict.NO_GO: ("Cas particulier", "#c0392b"),
}

_GRADE_COLOR = {"A": "#1a9d5a", "B": "#0e9aa7", "C": "#d9a400", "D": "#e07b39", "E": "#c0392b"}


_THEME_INIT = (
    "(function(){try{var t=localStorage.getItem('zephyr-theme')||"
    "(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');"
    "document.documentElement.setAttribute('data-theme',t);}catch(e){}})();"
)
_THEME_TOGGLE_JS = (
    "var ICON_SUN='" + _icon("sun", 18) + "',ICON_MOON='" + _icon("moon", 18) + "';"
    "function paintTheme(){var b=document.getElementById('themebtn');if(!b){return;}"
    "b.innerHTML=document.documentElement.getAttribute('data-theme')==='dark'?ICON_SUN:ICON_MOON;}"
    "function toggleTheme(){var r=document.documentElement,"
    "n=r.getAttribute('data-theme')==='dark'?'light':'dark';"
    "r.setAttribute('data-theme',n);try{localStorage.setItem('zephyr-theme',n);}catch(e){}paintTheme();}"
    "document.addEventListener('DOMContentLoaded',paintTheme);"
)


# Favicon : carré vert KORR avec « Z » (SVG inline, base64).
_FAVICON_B64 = (
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qg"
    "d2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzNhNWI0MiIvPjx0ZXh0IHg9IjE2IiB5PSIyMyIg"
    "Zm9udC1mYW1pbHk9IkhlbHZldGljYSBOZXVlLEhlbHZldGljYSxBcmlhbCxzYW5zLXNlcmlmIiBmb250LXNpemU9"
    "IjIwIiBmb250LXdlaWdodD0iNzAwIiBmaWxsPSIjZmZmZmZmIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj5aPC90ZXh0"
    "Pjwvc3ZnPg=="
)


def _layout(title: str, body: str, *, cta: bool = True, wide: bool = False) -> str:
    """Gabarit commun (nav + contenu + footer). `wide` élargit le conteneur (tracé).

    L'onglet navigateur affiche toujours « Zéphyr » ; `title` reste pour la lisibilité
    des appels (et un éventuel usage futur).
    """
    nav_cta = '<a class="btn" href="/etude">Lancer une étude !</a>' if cta else ""
    wrap_cls = "wrap wide" if wide else "wrap"
    korr_btn = (
        '<a class="btn ghost sm" href="https://korr.lu" target="_blank" rel="noopener" '
        f'aria-label="Site korr">{_KORR_LOGO} {_icon("external-link", 14)}</a>'
    )
    toggle = (
        '<button type="button" class="theme-toggle" id="themebtn" onclick="toggleTheme()" '
        f'title="Thème clair / sombre" aria-label="Basculer le thème">{_icon("moon", 18)}</button>'
    )
    return f"""<!DOCTYPE html><html lang="fr" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zéphyr</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{_FAVICON_B64}">
<script>{_THEME_INIT}</script>
<style>{_CSS}</style></head><body>
<nav><div class="{wrap_cls} nav-inner">
<a class="brand" href="/">{_KORR_LOGO}<span class="brand-x">×</span><span class="brand-name">Zéphyr<span class="dot-g">.</span></span></a>
<div class="nav-right">{toggle}{korr_btn}{nav_cta}</div></div></nav>
<main class="{wrap_cls}">{body}</main>
<footer class="wrap site-footer"><span>© {datetime.now().year} korr</span></footer>
<script>{_THEME_TOGGLE_JS}</script>
</body></html>"""


def render_styleguide() -> str:
    """Charte visible (/styleguide) : tokens, typo, boutons, composants. Respecte le thème."""
    swatches = [
        ("bg", "--bg"), ("surface", "--surface"), ("surface-2", "--surface-2"),
        ("ink", "--ink"), ("muted", "--muted"), ("line", "--line"),
        ("primary", "--primary"), ("primary-strong", "--primary-strong"),
        ("primary-soft", "--primary-soft"), ("danger", "--danger"), ("warn", "--warn"),
    ]
    sw = "".join(
        f'<div class="sg-row"><span class="sg-swatch" style="background:var({var})"></span>'
        f"<code>{var}</code> <span class=\"hint\">{name}</span></div>"
        for name, var in swatches
    )
    grades = "".join(
        f'<span class="badge" style="background:var(--{g.lower()})">{g}</span> '
        for g in ["a", "b", "c", "d", "e"]
    )
    icons = "".join(
        f'<div class="sg-icon">{_icon(name, 22)}<code>{name}</code></div>'
        for name in _ICONS
    )
    body = f"""
<h1>Charte Zéphyr</h1>
<p class="sub">Système de design (DA KORR : vert #3a5b42, Helvetica Neue, 8pt).
Tous les écrans s'appuient sur ces tokens. Bascule clair/sombre en haut à droite.</p>

<h2 class="sec">Couleurs</h2>
<div class="crit-grid"><div>{sw}</div>
<div><p class="hint">Notes A→E</p><p>{grades}</p>
<p class="hint" style="margin-top:1rem">Tons sémantiques</p>
<div class="reco">Recommandation (primary-soft)</div>
<div class="flag">Alerte / drapeau (danger-soft)</div>
<div class="disclaimer">Disclaimer (warn-soft)</div></div></div>

<h2 class="sec">Typographie — Helvetica Neue</h2>
<h1 style="margin:.2rem 0">Titre H1 — aptitude VNC</h1>
<h2 style="margin:.2rem 0">Titre H2 — bilan financier</h2>
<h3 style="margin:.2rem 0">Titre H3 — détail</h3>
<p>Corps de texte : un paragraphe lisible, gris d'encre sur fond clair.</p>
<p class="hint">Texte secondaire (muted / hint).</p>

<h2 class="sec">Boutons</h2>
<div class="sg-row">
  <button class="btn">Action primaire</button>
  <button class="btn ghost">Secondaire</button>
  <button class="btn sm">Petit</button>
  <span class="badge-ok">badge</span>
  <label class="chip"><input type="checkbox"> chip</label>
</div>

<h2 class="sec">Icônes — Lucide (trait, mono-couleur)</h2>
<p class="hint">Jeu minimaliste inliné (couleur héritée via <code>currentColor</code>, donc
thème-aware et rendu dans le PDF). <code>_icon("nom")</code> dans les pages.</p>
<div class="sg-icons">{icons}</div>

<h2 class="sec">Cartes & champs</h2>
<div class="crit-grid">
  <div class="card"><h3>Carte</h3><p class="hint">Surface, bordure, ombre douce.</p>
    <label>Champ</label><input type="text" placeholder="saisie…"></div>
  <div class="kpis" style="grid-template-columns:repeat(2,1fr)">
    <div class="kpi"><div class="k">KPI</div><div class="v">739 m²</div></div>
    <div class="kpi"><div class="k">VAN</div><div class="v">12 k€</div></div>
  </div>
</div>
"""
    return _layout("Zéphyr — charte", body, cta=False)


def render_landing() -> str:
    """Landing page : le concept (confort/sobriété/pérennité) puis la méthode."""
    pillars = [
        ("sun", "Confort", "Un air sain et une température stable toute l'année grâce à "
         "la ventilation naturelle contrôlée, l'inertie du bâtiment et un pilotage intelligent."),
        ("bulb", "Sobriété", "Pas de ventilation mécanique, peu ou pas de chauffage. "
         "Moins de machines à entretenir, moins de pannes, moins de dépendance."),
        ("building", "Pérennité", "Moins d'équipement à financer puis à remplacer. "
         "Un bâtiment simple, qui dure et coûte moins sur la durée."),
    ]
    pillars_html = "".join(
        f'<div class="pillar">{_icon(ic, 24)}<h3>{html.escape(t)}</h3>'
        f"<p>{html.escape(d)}</p></div>"
        for ic, t, d in pillars
    )
    steps = [
        ("01", "Configurez votre bâtiment", "Déposez vos plans (DXF ou PDF) et votre "
         "passeport énergétique. Zéphyr analyse automatiquement le CPE."),
        ("02", "Tracez, on mesure !", "Tracez rapidement les pièces importantes : "
         "Zéphyr s'occupe de l'analyse."),
        ("03", "Le bilan", "Une note instructive sur le potentiel du bâtiment, des "
         "pistes d'amélioration et les gains financiers de l'opération."),
    ]
    steps_html = "".join(
        f'<div class="proc"><div class="num">{n}</div><h3>{html.escape(t)}</h3>'
        f"<p>{html.escape(d)}</p></div>"
        for n, t, d in steps
    )
    crits = [
        ("wind", "Ventilation", "La capacité du bâtiment à renouveler l'air "
         "naturellement, par tirage thermique et circulation entre les façades."),
        ("thermometer", "Inertie", "La masse des parois, qui amortit les variations "
         "de température et restitue la fraîcheur stockée pendant la nuit."),
        ("shield", "Isolation", "Le niveau d'isolation de l'enveloppe : moins de "
         "déperditions, donc un besoin de chauffage réduit."),
        ("window", "Vitrage", "La proportion de surfaces vitrées : suffisante pour "
         "l'éclairage naturel, sans provoquer de surchauffe."),
        ("sun", "Protections solaires", "La présence de protections (stores, "
         "brise-soleil, casquettes) limitant les apports solaires en été."),
    ]
    crit_html = "".join(
        f'<div class="crit-item">{_icon(ic, 26)}<div><div class="t">{html.escape(t)}</div>'
        f'<div class="d">{html.escape(d)}</div></div></div>'
        for ic, t, d in crits
    )
    body = f"""
<section class="hero-xl">
  <h1 class="display">Créer un <em>meilleur</em> bâti.</h1>
  <p class="lead-xl">Nous pouvons concevoir des bâtiments qui restent sains et tempérés
  toute l'année presque sans équipement : leur masse, leur isolation et des ouvrants
  pilotés suffisent. Moins de machines à installer et à entretenir, peu ou pas de
  chauffage. Zéphyr estime si votre projet en est capable, et les gains associés.</p>
  <div class="cta-row">
    <a class="btn" href="/etude">Lancer une étude</a>
    <a class="btn ghost" href="#methode">Comment ça marche ?</a>
  </div>
  <div class="video-ph">{_icon("play", 22)} Vidéo à venir</div>
</section>
<hr class="rule">
<section>
  <div class="sec-head"><span class="idx">{_icon("arrow-right", 18)}</span><h2>L'idée</h2></div>
  <div class="pillars">{pillars_html}</div>
</section>
<section id="methode">
  <div class="sec-head"><span class="idx">{_icon("arrow-right", 18)}</span><h2>Comment ça marche ?</h2></div>
  <div class="process">{steps_html}</div>
</section>
<section style="margin-bottom:12rem">
  <div class="sec-head"><span class="idx">{_icon("arrow-right", 18)}</span><h2>Ce qu'on évalue</h2></div>
  <div class="crit-list-v">{crit_html}</div>
</section>
"""
    return _layout("Zéphyr — pré-étude de confort naturel", body)


def render_error(message: str) -> str:
    """Page d'erreur simple (ex. PDF scanné refusé, fichier illisible)."""
    body = (
        '<h1>Fichier non exploitable</h1>'
        f'<div class="disclaimer">{_icon("alert")} {html.escape(message)}</div>'
        f'<p><a class="btn" href="/etude">{_icon("arrow-left")} Revenir à la configuration</a></p>'
    )
    return _layout("Zéphyr — erreur", body, cta=False)


# Bascule CPE / saisie manuelle (choix exclusif) — vanilla, validé par node --check.
_CONFIG_JS = """
(function(){
  function sync(){
    var r=document.querySelector('input[name=cpe_mode]:checked'), m=r?r.value:'cpe';
    // Ne cibler QUE le toggle CPE (pas .modeseg, qui partage la classe .seg).
    Array.prototype.forEach.call(document.querySelectorAll('.seg:not(.modeseg) label'), function(l){
      l.classList.toggle('on', l.querySelector('input').value===m);
    });
    var up=document.getElementById('cpe-upload'), env=document.getElementById('envelope-block'),
        hint=document.getElementById('cpe-hint'), ex=window.__CPE_EXTRACTED__;
    if(up){ up.style.display = (m==='cpe')?'':'none'; }
    if(hint){ hint.style.display = (m==='cpe' && !ex)?'':'none'; }
    if(env){ env.style.display = (m==='manual' || (m==='cpe' && ex))?'':'none'; }
  }
  function curMode(){
    var r=document.querySelector('input[name=etude_mode]:checked');
    return r?r.value:'complete';
  }
  function hasPlan(){
    var d=document.getElementById('in-dxf'), f=document.getElementById('in-floors');
    return (d && d.files && d.files.length) || (f && f.files && f.files.length);
  }
  function syncMode(){
    var rapide=curMode()==='rapide';
    Array.prototype.forEach.call(document.querySelectorAll('.modeseg label'), function(l){
      l.classList.toggle('on', l.querySelector('input').value===curMode());
    });
    var plan=document.getElementById('card-plan'), est=document.getElementById('card-estim');
    if(plan){ plan.style.display=rapide?'none':''; }
    if(est){ est.style.display=rapide?'':'none'; }
    var mh=document.getElementById('mode-hint');
    if(mh){ mh.textContent=rapide
      ? "Rapide : quelques estimations, sans plan ni traçage, pour un résultat indicatif (tendance)."
      : "Complète : import d'un plan puis traçage des pièces, pour une analyse fine pièce par pièce."; }
    gate();
  }
  function markCpe(){ window.__CPE_TOUCHED__=true; gate(); }
  function gate(){
    var btn=document.getElementById('go-btn'), hint=document.getElementById('go-hint');
    var planOk=(curMode()==='rapide') || hasPlan();
    var cpeOk=!!window.__CPE_TOUCHED__;
    var ok=planOk && cpeOk;
    if(btn){ btn.disabled=!ok; }
    if(hint){
      if(ok){ hint.style.display='none'; hint.classList.remove('err'); }
      else {
        hint.style.display=''; hint.classList.add('err');
        hint.textContent = !planOk
          ? "Importez d'abord un plan."
          : "Renseignez le passeport énergétique.";
      }
    }
  }
  // Remplace le bouton natif (texte abrégé selon l'OS) par un libellé clair en français.
  function enhanceFiles(){
    Array.prototype.forEach.call(document.querySelectorAll('input[type=file]'), function(inp){
      if(inp.dataset.enh){ return; } inp.dataset.enh='1';
      var wrap=document.createElement('span'); wrap.className='filefield';
      var btn=document.createElement('button'); btn.type='button'; btn.className='filebtn';
      btn.textContent=inp.multiple?'Sélectionner des fichiers':'Sélectionner un fichier';
      var nm=document.createElement('span'); nm.className='filename'; nm.textContent='Aucun fichier choisi';
      inp.parentNode.insertBefore(wrap, inp); wrap.appendChild(btn); wrap.appendChild(nm); wrap.appendChild(inp);
      inp.style.display='none';
      btn.addEventListener('click', function(){ inp.click(); });
      inp.addEventListener('change', function(){
        nm.textContent = inp.files.length ? (inp.files.length>1 ? (inp.files.length+' fichiers') : inp.files[0].name) : 'Aucun fichier choisi';
      });
    });
  }
  document.addEventListener('DOMContentLoaded', function(){
    // Une extraction réussie (page rechargée) compte comme une action sur la carte CPE.
    if(window.__CPE_EXTRACTED__){ window.__CPE_TOUCHED__=true; }
    Array.prototype.forEach.call(document.querySelectorAll('input[name=cpe_mode]'), function(r){
      r.addEventListener('change', function(){ sync(); markCpe(); });
    });
    var cpe=document.getElementById('in-cpe');
    if(cpe){ cpe.addEventListener('change', markCpe); }
    var eb=document.getElementById('envelope-block');
    if(eb){ eb.addEventListener('input', markCpe); eb.addEventListener('change', markCpe); }
    var d=document.getElementById('in-dxf'), f=document.getElementById('in-floors');
    if(d){ d.addEventListener('change', gate); }
    if(f){ f.addEventListener('change', gate); }
    Array.prototype.forEach.call(document.querySelectorAll('input[name=etude_mode]'), function(r){
      r.addEventListener('change', syncMode);
    });
    // L'extraction CPE recharge la page : on embarque la config courante (mode + estimations)
    // pour la restaurer (sinon retour en « complète » et perte des saisies).
    var cf=document.getElementById('cpe-form');
    if(cf){ cf.addEventListener('submit', function(){
      var snap={}, mf=document.getElementById('mainform');
      if(mf){ Array.prototype.forEach.call(mf.elements, function(el){
        if(!el.name){ return; }
        if(el.type==='radio'||el.type==='checkbox'){ if(el.checked){ snap[el.name]=el.value; } }
        else { snap[el.name]=el.value; }
      }); }
      var h=document.getElementById('cfg_snapshot'); if(h){ h.value=JSON.stringify(snap); }
    }); }
    enhanceFiles(); sync(); syncMode();
  });
})();
"""


def render_study_form(
    prefill: Mapping[str, str] | None = None, *, cpe_banner: str = "", cpe_extracted: bool = False
) -> str:
    """Page 1 — configuration & plans : tout ce qui ne se lit pas sur les plans.

    `prefill` pré-remplit l'enveloppe (issue d'un CPE extrait, par ex.) ; l'ingénieur
    valide/corrige avant de continuer (human-in-the-loop). `cpe_banner` affiche le
    bilan de l'extraction CPE (valeurs trouvées + provenance, ou message d'erreur).
    """
    p = dict(prefill or {})

    def v(key: str, default: str) -> str:
        return html.escape(str(p.get(key, default)))

    def select(name: str, options: list[tuple[str, str]], default: str) -> str:
        cur = str(p.get(name, default))
        opts = "".join(
            f'<option value="{val}"{" selected" if val == cur else ""}>{lbl}</option>'
            for val, lbl in options
        )
        return f'<select name="{name}" form="mainform">{opts}</select>'

    inertia_sel = select(
        "inertia",
        [("lourde", "Lourde (béton / maçonnerie)"), ("moyenne", "Moyenne"),
         ("legere", "Légère (ossature)")],
        "lourde",
    )
    nature_sel = select(
        "nature", [("neuf", "Construction neuve"), ("renovation", "Rénovation")], "neuf"
    )
    ptype_sel = select(
        "project_type",
        [("logement", "Logement"), ("bureau", "Bureau"), ("mixte", "Mixte"),
         ("scolaire", "Scolaire")],
        "mixte",
    )
    chauffage_sel = select(
        "chauffage",
        [("pac", "Pompe à chaleur"), ("gaz", "Gaz"), ("electrique", "Électrique"),
         ("reseau", "Réseau de chaleur"), ("fioul", "Fioul"), ("bois", "Bois / pellets")],
        "pac",
    )
    ecs_sel = select(
        "ecs",
        [("thermodynamique", "Ballon thermodynamique"), ("ballon_elec", "Ballon électrique"),
         ("gaz", "Gaz"), ("solaire", "Solaire thermique"), ("chauffage", "Couplé au chauffage")],
        "thermodynamique",
    )
    chassis_sel = select(
        "chassis_material",
        [("pvc", "PVC"), ("alu", "Aluminium"), ("bois", "Bois"), ("mixte", "Bois/alu")],
        "pvc",
    )
    depth_sel = select("q_depth", [("compact", "Compactes"), ("profond", "Profondes")], "compact")
    solar_sel = select(
        "q_solar",
        [("aucune", "Aucune"), ("partielle", "Partielle (stores int.)"),
         ("bonne", "Bonne (stores ext. / brise-soleil)")],
        "partielle",
    )
    extracted = cpe_extracted
    cpe_manual = str(p.get("cpe_mode", "cpe")) == "manual"
    mode = str(p.get("etude_mode", "complete"))
    rapide_ck = " checked" if mode == "rapide" else ""
    complete_ck = "" if mode == "rapide" else " checked"
    body = f"""
<div class="form-head">
  <h1>Nouvelle étude</h1>
  <details class="resume">
    <summary>{_icon("history")} Reprendre une étude</summary>
    <form method="post" action="/etude/reprendre" enctype="multipart/form-data" class="resume-form">
      <input type="file" name="study" accept=".json,application/json">
      <button class="btn" type="submit">Reprendre</button>
    </form>
  </details>
</div>

<!-- Formulaire principal (vide) : les champs des cartes y sont rattachés via form="mainform". -->
<form id="mainform" method="post" action="/etude" enctype="multipart/form-data"></form>

<div class="seg modeseg" role="tablist" style="margin:1rem 0 .3rem">
  <label class="{"on" if mode != "rapide" else ""}"><input type="radio" name="etude_mode" value="complete" form="mainform"{complete_ck}> Étude complète</label>
  <label class="{"on" if mode == "rapide" else ""}"><input type="radio" name="etude_mode" value="rapide" form="mainform"{rapide_ck}> Étude rapide</label>
</div>
<p class="hint" id="mode-hint" style="margin:0 0 1rem"></p>

<div class="card" id="card-plan" style="margin:1.2rem 0">
  <h2>{_icon("ruler", 20)}Plan</h2>
  <p class="sub">Plan vectoriel (DXF ou PDF) servant de fond pour tracer les pièces.
  Un PDF scanné n'est pas lu.</p>
  <div class="field">
    <div class="lab">Plan unique (DXF, ou PDF A0 avec tous les niveaux)</div>
    <input type="file" name="dxf" accept=".dxf,.pdf" form="mainform" id="in-dxf">
  </div>
  <div class="field" style="margin-bottom:0">
    <div class="lab">Ou un PDF par niveau, du bas vers le haut (1<sup>er</sup> fichier = RdC)</div>
    <input type="file" name="floor_pdfs" accept=".pdf" multiple form="mainform" id="in-floors">
  </div>
</div>

<div class="card" id="card-estim" style="margin:1.2rem 0;display:none">
  <h2>{_icon("ruler", 20)}Ventilation &amp; vitrage (estimation)</h2>
  <p class="sub">En mode rapide, ces quelques estimations remplacent le tracé. La hauteur des
  châssis et le taux de vitrage se règlent dans « Passeport énergétique ».</p>
  <div class="form-grid">
    <div class="field"><div class="lab">Surface totale (m²)</div>
      <input type="number" name="area" value="{v("area", "800")}" step="10" form="mainform"></div>
    <div class="field"><div class="lab">Nombre de niveaux</div>
      <input type="number" name="levels" value="{v("levels", "2")}" min="1" form="mainform"></div>
    <div class="field"><div class="lab">Part de surface traversante (%)</div>
      <input type="number" name="q_through" value="{v("q_through", "40")}" min="0" max="100" step="5" form="mainform"></div>
    <div class="field"><div class="lab">Pièces plutôt…</div>{depth_sel}</div>
    <div class="field"><div class="lab">Protections solaires (façades exposées)</div>{solar_sel}</div>
  </div>
</div>

<div class="card" style="margin:1.2rem 0">
  <h2>{_icon("file", 20)}Passeport énergétique</h2>
  <div class="seg" role="tablist">
    <label class="{"" if cpe_manual else "on"}"><input type="radio" name="cpe_mode" value="cpe"{"" if cpe_manual else " checked"}> Upload du passeport</label>
    <label class="{"on" if cpe_manual else ""}"><input type="radio" name="cpe_mode" value="manual"{" checked" if cpe_manual else ""}> Saisie à la main</label>
  </div>

  <div id="cpe-upload" style="margin-top:1rem">
    <form method="post" action="/etude/cpe" enctype="multipart/form-data" class="upload-row" id="cpe-form">
      <input type="hidden" name="cfg_snapshot" id="cfg_snapshot">
      <input type="file" name="cpe" accept=".pdf" id="in-cpe">
      <button class="btn" type="submit">Extraire</button>
    </form>
  </div>
  {cpe_banner}

  <div id="envelope-block" style="margin-top:1rem">
    <div class="form-grid">
      <div class="field"><div class="lab">U murs (W/m²K)</div>
        <input type="number" name="u_wall" value="{v("u_wall", "0.20")}" step="0.01" form="mainform"></div>
      <div class="field"><div class="lab">Uw vitrage (W/m²K)</div>
        <input type="number" name="u_window" value="{v("u_window", "0.9")}" step="0.1" form="mainform"></div>
      <div class="field"><div class="lab">Taux de surface vitrée</div>
        <input type="number" name="glazing" value="{v("glazing", "0.15")}" step="0.01" form="mainform"></div>
      <div class="field"><div class="lab">Hauteur des châssis par défaut (m)</div>
        <input type="number" name="sash" value="{v("sash", "1.5")}" step="0.1" form="mainform"></div>
      <div class="field"><div class="lab">Perméabilité n50 (vol/h)</div>
        <input type="number" name="n50" value="{v("n50", "1.5")}" step="0.1" form="mainform"></div>
      <div class="field"><div class="lab">Inertie (parois)</div>{inertia_sel}</div>
    </div>
  </div>
</div>

<div class="card" style="margin:1.2rem 0">
  <h2>{_icon("hardhat", 20)}Projet</h2>
  <div class="form-grid">
    <div class="field"><div class="lab">Nature</div>{nature_sel}</div>
    <div class="field"><div class="lab">Type de projet</div>{ptype_sel}</div>
    <div class="field"><div class="lab">Type de chauffage</div>{chauffage_sel}</div>
    <div class="field"><div class="lab">Eau chaude sanitaire (ECS)</div>{ecs_sel}</div>
    <div class="field"><div class="lab">Matériau des châssis</div>{chassis_sel}</div>
    <div class="field"><div class="lab">Localisation (climat)</div>
      <input type="text" name="location" value="{v("location", "Luxembourg")}" form="mainform"></div>
  </div>
</div>

<div class="card" style="margin:1.2rem 0">
  <h2>{_icon("pin", 20)}Contexte du site</h2>
  <label class="check"><input type="checkbox" name="noise" form="mainform"> Bruit extérieur excessif</label>
  <label class="check"><input type="checkbox" name="pollution" form="mainform"> Pollution ou pollen élevés</label>
  <label class="check"><input type="checkbox" name="security" form="mainform"> Risque de sécurité au RdC</label>
</div>

<p style="margin:1.4rem 0">
  <button class="btn" type="submit" form="mainform" id="go-btn" disabled>Continuer {_icon("arrow-right")}</button>
  <span id="go-hint" class="hint" style="margin-left:.6rem">Importez d'abord un plan pour continuer.</span>
</p>

<script>window.__CPE_EXTRACTED__={"true" if extracted else "false"};</script>
<script>{_CONFIG_JS}</script>
"""
    return _layout("Zéphyr — nouvelle étude", body, cta=False)


def render_cpe_banner(extraction: object | None, *, message: str = "") -> str:
    """Bandeau récapitulatif de l'extraction CPE (valeurs + provenance, ou message)."""
    if extraction is None:
        return f'<div class="flag">{html.escape(message)}</div>' if message else ""
    labels = {
        "u_wall_w_m2k": "U murs", "u_roof_w_m2k": "U toiture",
        "u_floor_w_m2k": "U plancher", "u_window_w_m2k": "Uw vitrage",
        "air_permeability_ach50": "n50", "glazing_to_floor_ratio": "Ratio vitrage",
        "inertia_class": "Inertie", "floor_area_m2": "Surface réf.",
        "construction_year": "Année",
    }
    sources = getattr(extraction, "sources", {}) or {}
    rows = []
    for key, lab in labels.items():
        val = getattr(extraction, key, None)
        if val is None:
            continue
        shown = val.value if hasattr(val, "value") else val
        src = sources.get(key, "")
        src_html = (
            f'<small style="color:var(--muted)"> : « {html.escape(str(src)[:80])} »</small>'
            if src else ""
        )
        rows.append(f"<li><b>{lab}</b> : {html.escape(str(shown))}{src_html}</li>")
    notes = getattr(extraction, "notes", []) or []
    if not rows:
        return (
            '<div class="flag">CPE lu, mais aucune valeur d\'enveloppe vérifiable n\'a '
            "été extraite. Saisissez les champs à la main.</div>"
        )
    notes_html = (
        '<p style="color:var(--muted);font-size:.85rem;margin:.4rem 0 0">'
        + "<br>".join(html.escape(n) for n in notes)
        + "</p>"
    ) if notes else ""
    return (
        '<div class="reco"><b>CPE extrait</b> : valeurs posées dans le formulaire '
        "(vérifiées dans le texte source ; à valider) :"
        f'<ul style="margin:.4rem 0">{"".join(rows)}</ul>{notes_html}</div>'
    )


def _orient_select(name: str, selected: str, *, empty: bool = False) -> str:
    opts = ['<option value="">(non précisé)</option>'] if empty else []
    for o in Orientation:
        sel = " selected" if o.value == selected else ""
        opts.append(f'<option value="{o.value}"{sel}>{o.value}</option>')
    return f'<select name="{name}" style="width:auto">{"".join(opts)}</select>'


def _room_edit_block(idx: int, room: object) -> str:
    """Bloc éditable d'une pièce : label, niveau, orientations, châssis."""
    rid = getattr(room, "id", f"room_{idx}")
    area = getattr(room, "area_m2", 0.0)
    height = getattr(room, "height_m", 2.6)
    level = getattr(room, "level", 0)
    label = getattr(getattr(room, "label", None), "value", "autre")
    polygon = list(getattr(room, "polygon", []) or [])
    orients = ", ".join(o.value for o in getattr(room, "exterior_wall_orientations", []))
    openings = list(getattr(room, "openings", []) or [])

    label_opts = "".join(
        f'<option value="{rl.value}"{" selected" if rl.value == label else ""}>{rl.value}</option>'
        for rl in RoomLabel
    )
    # Châssis existants + 2 emplacements vides (ajout sans JS).
    n_slots = len(openings) + 2
    win_rows = []
    for j in range(n_slots):
        op = openings[j] if j < len(openings) else None
        facade = getattr(getattr(op, "orientation", None), "value", "") if op else ""
        oarea = f"{op.area_m2:.1f}" if op else ""
        sash = ""
        if op is not None and op.head_height_m is not None:
            sash = f"{max(op.head_height_m - op.sill_height_m, 0.0):.1f}"
        openable = "checked" if (op is None or op.openable) else ""
        win_rows.append(
            '<div class="winrow">'
            f"{_orient_select(f'r{idx}_o{j}_facade', facade, empty=True)}"
            f'<input type="number" step="0.1" placeholder="m²" name="r{idx}_o{j}_area" '
            f'value="{oarea}" style="width:80px">'
            f'<input type="number" step="0.1" placeholder="H châssis" name="r{idx}_o{j}_sash" '
            f'value="{sash}" style="width:90px">'
            f'<label class="check" style="margin:0"><input type="checkbox" '
            f'name="r{idx}_o{j}_openable" {openable}> ouvrable</label>'
            "</div>"
        )

    poly_json = html.escape(json.dumps([[round(x, 3), round(y, 3)] for x, y in polygon]))
    return f"""
<div class="card" style="margin:.6rem 0">
  <input type="hidden" name="r{idx}_id" value="{html.escape(str(rid))}">
  <input type="hidden" name="r{idx}_area" value="{area:.2f}">
  <input type="hidden" name="r{idx}_height" value="{height:.2f}">
  <input type="hidden" name="r{idx}_polygon" value="{poly_json}">
  <input type="hidden" name="r{idx}_nslots" value="{n_slots}">
  <div class="form-grid">
    <div><label>Pièce <code>{html.escape(str(rid))}</code> — label</label>
      <select name="r{idx}_label">{label_opts}</select></div>
    <div><label>Surface / niveau</label>
      <div style="display:flex;gap:.5rem;align-items:center">
        <span style="color:var(--muted)">{area:.1f} m²</span>
        <input type="number" name="r{idx}_level" value="{level}" style="width:70px"></div></div>
    <div style="grid-column:1/3"><label>Façades extérieures (orientations, ex. « S, W »)</label>
      <input type="text" name="r{idx}_orient" value="{html.escape(orients)}"
        placeholder="ex. S, W"></div>
  </div>
  <label style="margin-top:.6rem">Châssis (façade, m², hauteur châssis m, ouvrable)</label>
  {"".join(win_rows)}
</div>"""


def _rooms_table(building: object) -> str:
    rooms = getattr(building, "rooms", [])
    rows = []
    for r in rooms:
        orients = ", ".join(o.value for o in r.exterior_wall_orientations) or "aucune"
        wins = ", ".join(o.orientation.value for o in r.openings) or "aucun"
        label = getattr(r.label, "value", str(r.label))
        through = f'{_icon("check")} oui' if r.is_through else "non"
        rows.append(
            "<tr>"
            f"<td style='text-align:left'>{html.escape(r.id)}</td>"
            f"<td style='text-align:left'>{html.escape(label)}</td>"
            f"<td>{r.area_m2:.1f}</td><td>{r.level}</td>"
            f"<td style='text-align:left'>{html.escape(orients)}</td>"
            f"<td style='text-align:left'>{html.escape(wins)}</td>"
            f"<td style='text-align:left'>{through}</td></tr>"
        )
    head = (
        "<tr><th style='text-align:left'>pièce</th><th style='text-align:left'>label</th>"
        "<th>m²</th><th>niv.</th><th style='text-align:left'>façades</th>"
        "<th style='text-align:left'>châssis (façade)</th>"
        "<th style='text-align:left'>traversant</th></tr>"
    )
    return f"<table class='kv'>{head}{''.join(rows)}</table>"


_LABEL_COLORS: dict[str, str] = {
    "sejour": "#cfe8cf", "chambre": "#cfe0f5", "cuisine": "#f5e6cf", "sdb": "#cfeef0",
    "wc": "#e6cff5", "circulation": "#eeeeee", "bureau": "#f5cfd6", "technique": "#dddddd",
    "autre": "#f0f0f0",
}

# Éditeur de plan interactif (vanilla JS). Pas d'f-string : accolades JS littérales.
_VALIDATION_JS = """
var B = window.BUILDING, COLORS = window.LABEL_COLORS || {};
var ORS = ["N","NE","E","SE","S","SW","W","NW"];
var ORDIR = {N:[0,1],NE:[0.7,0.7],E:[1,0],SE:[0.7,-0.7],S:[0,-1],SW:[-0.7,-0.7],W:[-1,0],NW:[-0.7,0.7]};
var LABELS = ["sejour","chambre","cuisine","sdb","wc","circulation","bureau","technique","autre"];
var sel = -1;
var lvl = Math.min.apply(null, B.rooms.map(function(r){return r.level;}));
function through(r){ return new Set(r.exterior_wall_orientations).size >= 2; }
function fmt(n){ return Math.round(n*10)/10; }
function levels(){
  var ls = Array.from(new Set(B.rooms.map(function(r){return r.level;}))).sort(function(a,b){return a-b;});
  var bar = document.getElementById('levelbar');
  if(ls.length<=1){ bar.innerHTML=''; return; }
  bar.innerHTML = ls.map(function(l){return '<button type="button" class="'+(l===lvl?'active':'')+'" data-l="'+l+'">Niveau '+l+'</button>';}).join('');
  Array.prototype.forEach.call(bar.querySelectorAll('button'), function(b){ b.onclick=function(){ lvl=parseInt(b.dataset.l); sel=-1; render(); panel(); }; });
}
var SVGNS = 'http://www.w3.org/2000/svg';
function svgEl(tag, attrs){
  var e = document.createElementNS(SVGNS, tag);
  for(var k in attrs){ e.setAttribute(k, attrs[k]); }
  return e;
}
function render(){
  var svg = document.getElementById('plan');
  while(svg.firstChild){ svg.removeChild(svg.firstChild); }
  var rooms = B.rooms.filter(function(r){return r.level===lvl && r.polygon && r.polygon.length>=3;});
  var xs=[], ys=[];
  rooms.forEach(function(r){ r.polygon.forEach(function(p){xs.push(p[0]); ys.push(p[1]);}); });
  levels();
  if(!xs.length){ syncHidden(); return; }
  var minx=Math.min.apply(null,xs), maxx=Math.max.apply(null,xs);
  var miny=Math.min.apply(null,ys), maxy=Math.max.apply(null,ys), pad=0.6;
  svg.setAttribute('viewBox',(minx-pad)+' '+(miny-pad)+' '+((maxx-minx)+2*pad)+' '+((maxy-miny)+2*pad));
  svg.setAttribute('preserveAspectRatio','xMidYMid meet');
  function fy(y){ return (miny+maxy)-y; }
  B.rooms.forEach(function(r,i){
    if(r.level!==lvl || !r.polygon || r.polygon.length<3) return;
    var pts = r.polygon.map(function(p){return p[0]+','+fy(p[1]);}).join(' ');
    var thru = through(r);
    var stroke = (i===sel) ? '#08313a' : (thru ? '#0e9aa7' : '#999');
    var sw = (i===sel) ? 0.14 : (thru ? 0.10 : 0.05);
    var pg = svgEl('polygon', {points:pts, fill:(COLORS[r.label]||'#eee'),
      stroke:stroke, 'stroke-width':sw});
    pg.style.cursor = 'pointer';
    pg.addEventListener('click', (function(idx){ return function(){ sel=idx; render(); panel(); }; })(i));
    svg.appendChild(pg);
    var rxs = r.polygon.map(function(p){return p[0];}), rys = r.polygon.map(function(p){return p[1];});
    var dminx=Math.min.apply(null,rxs), dmaxx=Math.max.apply(null,rxs);
    var dminy=Math.min.apply(null,rys), dmaxy=Math.max.apply(null,rys);
    var dcx=(dminx+dmaxx)/2, dcy=(dminy+dmaxy)/2, rw=dmaxx-dminx, rh=dmaxy-dminy;
    var t1 = svgEl('text', {x:dcx, y:fy(dcy), 'text-anchor':'middle', 'font-size':0.45, fill:'#222'});
    t1.textContent = r.label;
    var t2 = svgEl('text', {x:dcx, y:fy(dcy)+0.5, 'text-anchor':'middle', 'font-size':0.32, fill:'#666'});
    t2.textContent = fmt(r.area_m2) + ' m\\u00b2';
    svg.appendChild(t1); svg.appendChild(t2);
    // Façades extérieures : lettres d'orientation placées vers la bonne direction.
    (r.exterior_wall_orientations||[]).forEach(function(o){
      var d = ORDIR[o]; if(!d) return;
      var mx = dcx + d[0]*0.40*rw, my = dcy + d[1]*0.40*rh;
      var tm = svgEl('text', {x:mx, y:fy(my), 'text-anchor':'middle', 'font-size':0.34,
        fill:'#0e9aa7', 'font-weight':'700'});
      tm.textContent = o;
      svg.appendChild(tm);
    });
    // Châssis : barres sur la façade correspondante (bleu = ouvrable, gris = fixe).
    var byOri = {};
    (r.openings||[]).forEach(function(op){ if(ORDIR[op.orientation]){ (byOri[op.orientation]=byOri[op.orientation]||[]).push(op); } });
    Object.keys(byOri).forEach(function(o){
      var d=ORDIR[o], ux=d[0], uy=d[1], tnx=-uy, tny=ux;
      var epx=dcx+ux*(rw/2), epy=dcy+uy*(rh/2), list=byOri[o];
      list.forEach(function(op,k){
        var off=(k-(list.length-1)/2)*0.7, bx=epx+tnx*off, by=epy+tny*off, half=0.28;
        var ln=svgEl('line', {x1:bx-tnx*half, y1:fy(by-tny*half), x2:bx+tnx*half, y2:fy(by+tny*half),
          stroke:(op.openable?'#1a73e8':'#9aa3ad'), 'stroke-width':0.18, 'stroke-linecap':'round'});
        svg.appendChild(ln);
      });
    });
  });
  syncHidden();
}
function panel(){
  var p = document.getElementById('panel'), r = B.rooms[sel];
  if(!r){ p.innerHTML='<p style="color:#888">Cliquez une pièce sur le plan pour la corriger.</p>'; return; }
  var labOpts = LABELS.map(function(l){return '<option value="'+l+'"'+(l===r.label?' selected':'')+'>'+l+'</option>';}).join('');
  var orChips = ORS.map(function(o){return '<label class="chip"><input type="checkbox" data-or="'+o+'"'+(r.exterior_wall_orientations.indexOf(o)>=0?' checked':'')+'>'+o+'</label>';}).join('');
  var wins = (r.openings||[]).map(function(op,j){
    var sash = (op.head_height_m!=null)?fmt(op.head_height_m-(op.sill_height_m!=null?op.sill_height_m:0.9)):'';
    var fOpts = [''].concat(ORS).map(function(o){return '<option value="'+o+'"'+(o===op.orientation?' selected':'')+'>'+(o||'\\u2014')+'</option>';}).join('');
    return '<div class="winrow"><select data-w="'+j+'" data-f="facade">'+fOpts+'</select>'+
      '<input data-w="'+j+'" data-f="area" type="number" step="0.1" value="'+(op.area_m2!=null?op.area_m2:'')+'" style="width:70px" placeholder="m\\u00b2">'+
      '<input data-w="'+j+'" data-f="sash" type="number" step="0.1" value="'+sash+'" style="width:80px" placeholder="H">'+
      '<label class="chip"><input data-w="'+j+'" data-f="openable" type="checkbox"'+(op.openable?' checked':'')+'>ouvr.</label>'+
      '<button type="button" data-del="'+j+'">\\u2715</button></div>';
  }).join('');
  p.innerHTML = '<h3 style="margin-top:0">'+r.id+'</h3>'+
    '<label>Label</label><select id="p-label">'+labOpts+'</select>'+
    '<label>Niveau</label><input id="p-level" type="number" value="'+r.level+'">'+
    '<label>Façades extérieures</label><div class="chips">'+orChips+'</div>'+
    '<label>Châssis '+(through(r)?'<span class="badge-ok">traversant</span>':'<span style="color:#888;font-size:.8rem">mono-façade</span>')+'</label>'+
    '<div id="p-wins">'+wins+'</div>'+
    '<button type="button" id="p-add" class="btn ghost" style="margin-top:.5rem">+ Ajouter</button>';
  wire();
}
function wire(){
  var r = B.rooms[sel];
  document.getElementById('p-label').onchange=function(e){ r.label=e.target.value; render(); panel(); };
  document.getElementById('p-level').onchange=function(e){ r.level=parseInt(e.target.value||'0'); render(); };
  Array.prototype.forEach.call(document.querySelectorAll('#panel [data-or]'), function(c){ c.onchange=function(e){
    var o=e.target.dataset.or, s=new Set(r.exterior_wall_orientations);
    if(e.target.checked){ s.add(o); } else { s.delete(o); }
    r.exterior_wall_orientations=Array.from(s); render(); panel();
  };});
  Array.prototype.forEach.call(document.querySelectorAll('#panel [data-w]'), function(el){ el.onchange=function(){
    var j=parseInt(el.dataset.w), f=el.dataset.f, op=r.openings[j];
    if(f==='facade'){ op.orientation=el.value; }
    else if(f==='area'){ op.area_m2=parseFloat(el.value||'1.5'); }
    else if(f==='sash'){ var v=parseFloat(el.value); op.sill_height_m=(op.sill_height_m!=null?op.sill_height_m:0.9); op.head_height_m=isNaN(v)?null:(op.sill_height_m+v); }
    else if(f==='openable'){ op.openable=el.checked; }
    render(); syncHidden();
  };});
  Array.prototype.forEach.call(document.querySelectorAll('#panel [data-del]'), function(b){ b.onclick=function(){ r.openings.splice(parseInt(b.dataset.del),1); render(); panel(); syncHidden(); };});
  document.getElementById('p-add').onclick=function(){
    if(!r.openings){ r.openings=[]; }
    r.openings.push({id:r.id+'_w'+r.openings.length, kind:'window', orientation:(r.exterior_wall_orientations[0]||'S'), area_m2:1.5, sill_height_m:0.9, head_height_m:2.2, openable:true, free_area_ratio:0.5});
    render(); panel(); syncHidden();
  };
}
function syncHidden(){
  var clean = JSON.parse(JSON.stringify(B));
  clean.rooms.forEach(function(r){ r.openings = (r.openings||[]).filter(function(o){ return ORS.indexOf(o.orientation)>=0 && o.area_m2>0; }); });
  document.getElementById('building_json').value = JSON.stringify(clean);
}
document.addEventListener('DOMContentLoaded', function(){ render(); panel(); });
"""


# Éditeur de TRACÉ : plan en fond + tracé des pièces au clic (vanilla JS).
_TRACING_JS = """
var ICON_X='<svg class="ic" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
var T=window.TRACE, floors=T.floors, fi=0, multi=floors.length>1;
var ORS=["N","NE","E","SE","S","SW","W","NW"];
// Affichage cardinal en français (la valeur stockée reste le code Orientation : W, SW, NW).
var ORF={N:"N",NE:"NE",E:"E",SE:"SE",S:"S",SW:"SO",W:"O",NW:"NO"};
var ORDIR={N:[0,1],NE:[0.7,0.7],E:[1,0],SE:[0.7,-0.7],S:[0,-1],SW:[-0.7,-0.7],W:[-1,0],NW:[-0.7,0.7]};
// (valeur RoomLabel, libellé affiché avec majuscules + accents)
var LABELS=[["sejour","Séjour"],["salle_a_manger","Salle à manger"],["chambre","Chambre"],
  ["cuisine","Cuisine"],["sdb","Salle de bain"],["wc","WC"],["entree","Entrée"],
  ["circulation","Circulation / couloir"],["bureau","Bureau"],["buanderie","Buanderie"],
  ["cellier","Cellier"],["dressing","Dressing"],["garage","Garage"],
  ["technique","Local technique"],["autre","Autre"]];
var LABMAP={}; LABELS.forEach(function(p){ LABMAP[p[0]]=p[1]; });
// (valeur SolarProtection, libellé) — protection solaire d'un châssis.
var PROT=[["aucune","Aucune"],["store_interieur","Store int."],["volet","Volet"],
  ["naturelle","Masque/végé."],["casquette","Casquette"],["store_exterieur","Store ext."],
  ["brise_soleil","Brise-soleil"]];
var COLORS={sejour:"#cfe8cf",salle_a_manger:"#d7ecd0",chambre:"#cfe0f5",cuisine:"#f5e6cf",
  sdb:"#cfeef0",wc:"#e6cff5",entree:"#efe7d6",circulation:"#eeeeee",bureau:"#f5cfd6",
  buanderie:"#d6eef0",cellier:"#e8e2d2",dressing:"#efd9e8",garage:"#dcdcdc",technique:"#dddddd",autre:"#f0f0f0"};
var inertiaEl=document.querySelector('input[name=inertia]');
var B={id:"pdf", name:null, rooms:[], inertia_class:(inertiaEl?inertiaEl.value:"lourde"), num_levels:1, total_height_m:null, location:null, epw_path:null};
var sel=-1, mode="idle", draft=[], calib=[], winDrag=null, rectDrag=null, lastSash=1.5, curLvl=0;
// Niveaux créés par l'utilisateur (persistants même sans pièce) — clé = numéro de niveau.
var availLvls={0:true};
var stage, bgLayer, shapeLayer, bg=null, lastDist=0;
function F(){ return floors[fi]; }
function MPP(){ return F().mpp; }
function HH(){ return F().h; }
function toM(x,y){ return [x*MPP(), (HH()-y)*MPP()]; }
function toPx(mx,my){ return [mx/MPP(), HH()-my/MPP()]; }
function area(poly){ var s=0; for(var i=0;i<poly.length;i++){ var a=poly[i], b=poly[(i+1)%poly.length]; s+=a[0]*b[1]-b[0]*a[1]; } return Math.abs(s)/2; }
function through(r){ return new Set(r.exterior_wall_orientations).size>=2; }
function fmt(n){ return Math.round(n*10)/10; }
function centroidM(r){ var x=0,y=0,n=r.polygon.length||1; r.polygon.forEach(function(p){x+=p[0];y+=p[1];}); return [x/n,y/n]; }
function nearestOri(dx,dy){ var best="N",bd=-1e9,L=Math.hypot(dx,dy)||1; dx/=L; dy/=L; ORS.forEach(function(o){ var d=ORDIR[o],dot=dx*d[0]+dy*d[1]; if(dot>bd){bd=dot;best=o;} }); return best; }
function sc(p){ return p/stage.scaleX(); }
function pm(m){ return m/MPP(); }
function markF(){ var e=document.getElementById("t-mark"); return e?(parseFloat(e.value)||1):1; }
function snapOn(){ var e=document.getElementById("t-snap"); return e?e.checked:false; }

// Magnétisme : accroche un point (px-image) à un sommet proche, sinon aligne x/y.
function allVerts(skipRoom, skipVi){
  var v=[]; B.rooms.forEach(function(r,ri){ if(multi && r.level!==F().level){ return; }
    r.polygon.forEach(function(m,vi){ if(ri===skipRoom && vi===skipVi){ return; } v.push(toPx(m[0],m[1])); }); });
  return v;
}
function snapPx(p, skipRoom, skipVi){
  if(!snapOn()){ return p; }
  var th=sc(12), vs=allVerts(skipRoom,skipVi), best=null, bd=th;
  vs.forEach(function(q){ var d=Math.hypot(q[0]-p[0],q[1]-p[1]); if(d<bd){ bd=d; best=[q[0],q[1]]; } });
  if(best){ return best; }
  var x=p[0], y=p[1];
  vs.forEach(function(q){ if(Math.abs(q[0]-p[0])<th){ x=q[0]; } if(Math.abs(q[1]-p[1])<th){ y=q[1]; } });
  return [x,y];
}

function fitStage(){
  var c=stage.container(); stage.width(c.clientWidth); stage.height(c.clientHeight);
  var f=F(), s=Math.min(stage.width()/f.w, stage.height()/f.h)*0.97;
  if(!(s>0)){ s=1; }
  stage.scale({x:s,y:s});
  stage.position({x:(stage.width()-f.w*s)/2, y:(stage.height()-f.h*s)/2});
}
function loadBg(){
  var f=F(), im=new Image();
  im.onload=function(){ if(bg){bg.destroy();} bg=new Konva.Image({image:im,x:0,y:0,width:f.w,height:f.h,listening:false}); bgLayer.add(bg); bgLayer.batchDraw(); };
  im.src=f.image_uri;
}
function applyFloor(){ if(bg){bg.destroy();bg=null;} loadBg(); fitStage(); }
function goToLevel(lv){ for(var k=0;k<floors.length;k++){ if(floors[k].level===lv){ fi=k; applyFloor(); return true; } } return false; }
function levelLabel(lv){ return lv===0?"RDC":(lv>0?("R+"+lv):("S"+(-lv))); }
function levelsel(){
  var el=document.getElementById("levelsel"); if(!el){ return; }
  var lvls;
  if(multi){ lvls=floors.map(function(f){ return f.level; }); }
  else {
    var s={}; s[curLvl]=1; B.rooms.forEach(function(r){ s[r.level]=1; });
    Object.keys(availLvls).forEach(function(k){ s[parseInt(k)]=1; });  // niveaux créés persistent
    lvls=Object.keys(s).map(Number).sort(function(a,b){ return a-b; });
  }
  var cur=multi?F().level:curLvl;
  var h=lvls.map(function(lv){ return '<button type="button" class="'+(lv===cur?"active":"")+'" data-lv="'+lv+'">'+levelLabel(lv)+'</button>'; }).join("");
  if(!multi){ var mx=Math.max.apply(null,lvls); h+='<button type="button" data-add="'+(mx+1)+'" title="Ajouter un niveau">+</button>'; }
  el.innerHTML=h;
  Array.prototype.forEach.call(el.querySelectorAll("[data-lv]"),function(b){ b.onclick=function(){ var lv=parseInt(b.dataset.lv); if(multi){ goToLevel(lv); sel=-1; } else { curLvl=lv; } render(); }; });
  var add=el.querySelector("[data-add]"); if(add){ add.onclick=function(){ var nv=parseInt(add.dataset.add); availLvls[nv]=true; curLvl=nv; levelsel(); }; }
}
function ptr(){ return stage.getRelativePointerPosition(); }

function polyPxPoints(r){ var a=[]; r.polygon.forEach(function(m){ var p=toPx(m[0],m[1]); a.push(p[0],p[1]); }); return a; }

function render(){
  if(!stage){ return; }
  shapeLayer.destroyChildren();
  levelsel();
  var selGrp=null;
  B.rooms.forEach(function(r,i){
    if(multi && r.level!==F().level){ return; }
    if(!r.polygon || r.polygon.length<2){ return; }
    var xs=[], ys=[]; r.polygon.forEach(function(m){ var p=toPx(m[0],m[1]); xs.push(p[0]); ys.push(p[1]); });
    var seld=(i===sel);
    var grp=seld?new Konva.Group({draggable:(mode==="idle")}):null;
    var poly=new Konva.Line({points:polyPxPoints(r), closed:true, fill:(COLORS[r.label]||"#eee"), opacity:0.45,
      stroke:(seld?"#08313a":(through(r)?"#0e9aa7":"#555")), strokeWidth:(seld?2.4:1.4), strokeScaleEnabled:false});
    if(seld){
      grp.add(poly);
      grp.on("dragstart",function(){ stage.container().style.cursor="grabbing"; });
      grp.on("dragend",function(){
        var ox=grp.x(), oy=grp.y();
        if(ox||oy){
          r.polygon=r.polygon.map(function(m){ var p=toPx(m[0],m[1]); return toM(p[0]+ox,p[1]+oy); });
          (r.openings||[]).forEach(function(op){ if(op._seg){ op._seg=[[op._seg[0][0]+ox,op._seg[0][1]+oy],[op._seg[1][0]+ox,op._seg[1][1]+oy]]; } });
        }
        grp.position({x:0,y:0}); render();
      });
      shapeLayer.add(grp); selGrp=grp;
      r.polygon.forEach(function(m,vi){ var p=toPx(m[0],m[1]);
        var h=new Konva.Circle({x:p[0],y:p[1],radius:sc(5),fill:"#fff",stroke:"#08313a",strokeWidth:sc(1.5),draggable:true});
        h.on("dragmove",function(){ var q=snapPx([h.x(),h.y()],i,vi); h.x(q[0]); h.y(q[1]); r.polygon[vi]=toM(q[0],q[1]); poly.points(polyPxPoints(r)); r.area_m2=Math.max(area(r.polygon),0.01); shapeLayer.batchDraw(); });
        h.on("dragend",function(){ render(); });
        h.on("mouseenter",function(){ stage.container().style.cursor="move"; });
        grp.add(h);
      });
    } else {
      poly.on("click tap",function(e){ if(mode==="idle"){ e.cancelBubble=true; sel=i; render(); } });
      poly.on("mouseenter",function(){ if(mode==="idle"){ stage.container().style.cursor="pointer"; } });
      poly.on("mouseleave",function(){ stage.container().style.cursor=(mode==="idle"?"grab":"crosshair"); });
      shapeLayer.add(poly);
    }
    var cx=xs.reduce(function(a,b){return a+b;},0)/xs.length, cy=ys.reduce(function(a,b){return a+b;},0)/ys.length;
    var t1=new Konva.Text({x:cx,y:cy,text:(LABMAP[r.label]||r.label),fontSize:pm(0.5),fontFamily:"Helvetica Neue, Arial, sans-serif",fontStyle:"600",fill:"#111",listening:false});
    t1.offsetX(t1.width()/2); t1.offsetY(t1.height()/2+pm(0.32)); shapeLayer.add(t1);
    var t2=new Konva.Text({x:cx,y:cy,text:fmt(r.area_m2)+" m², "+levelLabel(r.level),fontSize:pm(0.34),fontFamily:"Helvetica Neue, Arial, sans-serif",fill:"#444",listening:false});
    t2.offsetX(t2.width()/2); t2.offsetY(t2.height()/2-pm(0.32)); shapeLayer.add(t2);
    var minx=Math.min.apply(null,xs),maxx=Math.max.apply(null,xs),miny=Math.min.apply(null,ys),maxy=Math.max.apply(null,ys);
    var dcx=(minx+maxx)/2,dcy=(miny+maxy)/2,rw=maxx-minx,rh=maxy-miny;
    (r.exterior_wall_orientations||[]).forEach(function(o){ var d=ORDIR[o]; if(!d){ return; }
      var mx=dcx+d[0]*0.4*rw, my=dcy-d[1]*0.4*rh;
      var tt=new Konva.Text({x:mx,y:my,text:(ORF[o]||o),fontSize:pm(0.42),fontStyle:"700",fontFamily:"Helvetica Neue, Arial, sans-serif",fill:"#0e9aa7",listening:false});
      tt.offsetX(tt.width()/2); tt.offsetY(tt.height()/2); shapeLayer.add(tt);
    });
    (r.openings||[]).forEach(function(op,k){
      var seg=op._seg; if(!seg){ return; }
      var ln=new Konva.Line({points:[seg[0][0],seg[0][1],seg[1][0],seg[1][1]], stroke:(op.openable?"#1a73e8":"#9aa3ad"), strokeWidth:pm(0.09), lineCap:"round", listening:false});
      shapeLayer.add(ln);
      // Référence du châssis (C1, C2…) posée juste à l'extérieur de la façade.
      var wmx=(seg[0][0]+seg[1][0])/2, wmy=(seg[0][1]+seg[1][1])/2;
      var wox=wmx-dcx, woy=wmy-dcy, wol=Math.hypot(wox,woy)||1;
      var ct=new Konva.Text({x:wmx+wox/wol*pm(0.55), y:wmy+woy/wol*pm(0.55), text:"C"+(k+1),
        fontSize:pm(0.32), fontStyle:"700", fontFamily:"Helvetica Neue, Arial, sans-serif",
        fill:"#1a73e8", listening:false});
      ct.offsetX(ct.width()/2); ct.offsetY(ct.height()/2); shapeLayer.add(ct);
    });
  });
  if(selGrp){ selGrp.moveToTop(); }  // pièce sélectionnée toujours au-dessus (contour visible)
  if(draft.length){
    var dp=[]; draft.forEach(function(p){ dp.push(p[0],p[1]); });
    shapeLayer.add(new Konva.Line({points:dp, stroke:"#e8590c", strokeWidth:sc(2*markF()), dash:[sc(6*markF()),sc(4*markF())], listening:false}));
    draft.forEach(function(p){ shapeLayer.add(new Konva.Circle({x:p[0],y:p[1],radius:sc(4*markF()),fill:"#e8590c",listening:false})); });
  }
  if(rectDrag){ var a=rectDrag.a,b=rectDrag.b;
    shapeLayer.add(new Konva.Line({points:[a[0],a[1],b[0],a[1],b[0],b[1],a[0],b[1]], closed:true, stroke:"#e8590c", strokeWidth:sc(2*markF()), dash:[sc(6*markF()),sc(4*markF())], listening:false})); }
  if(winDrag){ shapeLayer.add(new Konva.Line({points:[winDrag.a[0],winDrag.a[1],winDrag.b[0],winDrag.b[1]], stroke:"#1a73e8", strokeWidth:pm(0.12), dash:[sc(6),sc(4)], lineCap:"round", listening:false})); }
  if(calib.length===1){ shapeLayer.add(new Konva.Circle({x:calib[0][0],y:calib[0][1],radius:sc(5),fill:"#c0392b",listening:false})); }
  shapeLayer.batchDraw();
  updateScaleInfo();
  roomlist(); syncHidden();
}
function updateScaleInfo(){
  var si=document.getElementById("scaleinfo"); if(!si){ return; }
  // Échelle du PLAN (constante, indépendante du zoom) : mètres réels par pixel d'image
  // rapportés à la taille physique d'un pixel CSS à 96 dpi (≈ 0,2646 mm).
  var ratio=MPP()/0.0002645833;
  si.textContent=ratio>0?("Échelle du plan ≈ 1/"+Math.round(ratio)):"";
}

var MODE_BANNER={
  rect:"Glissez en diagonale pour tracer un rectangle. Échap pour quitter.",
  draw:"Cliquez les coins ; re-cliquez le 1er point ou « Terminer la pièce ». Échap pour quitter.",
  window:"Glissez le long de la façade de la pièce sélectionnée. Échap pour quitter.",
  calibrate:"Cliquez deux points d'une cote connue. Échap pour quitter."
};
var MODEBTN={draw:"t-draw", rect:"t-rect", window:"t-win", calibrate:"t-cal"};
function setBanner(){
  var el=document.getElementById("modebanner"); if(!el){ return; }
  if(mode==="idle"){ el.className="stage-mode empty"; el.textContent="Survolez une pièce pour la sélectionner, ou choisissez un outil."; }
  else { el.className="stage-mode"; el.textContent=MODE_BANNER[mode]||""; }
}
function updateFinishBtn(){ var b=document.getElementById("t-finish"); if(b){ b.style.display=(mode==="draw"&&draft.length>0)?"":"none"; } }
function setMode(m){ mode=m; draft=[]; calib=[]; winDrag=null; rectDrag=null;
  if(stage){ stage.draggable(m==="idle"); stage.container().style.cursor=(m==="idle"?"grab":"crosshair"); }
  Object.keys(MODEBTN).forEach(function(k){ var b=document.getElementById(MODEBTN[k]); if(b){ b.classList.toggle("active", k===m); } });
  setBanner(); updateFinishBtn(); render();
}
function evClient(e){
  var ev=e&&e.evt; if(ev){ if(ev.clientX!=null){ return [ev.clientX,ev.clientY]; }
    if(ev.changedTouches&&ev.changedTouches[0]){ return [ev.changedTouches[0].clientX,ev.changedTouches[0].clientY]; } }
  var rect=stage.container().getBoundingClientRect(); return [rect.left+rect.width/2, rect.top+90];
}
function curLevel(){ return multi?F().level:curLvl; }
var firstRoomNotified=false;
function updateRoomsCount(){ var c=document.getElementById("rooms-count"); if(c){ c.textContent=B.rooms.length; } }
function showSide(which){
  var tools=document.getElementById("panel-tools"), rooms=document.getElementById("panel-rooms");
  var bt=document.getElementById("tab-tools"), br=document.getElementById("tab-rooms");
  var r=(which==="rooms");
  if(tools){ tools.style.display=r?"none":""; } if(rooms){ rooms.style.display=r?"":"none"; }
  if(bt){ bt.classList.toggle("active",!r); } if(br){ br.classList.toggle("active",r); }
}
function notifyFirstRoom(){
  if(firstRoomNotified){ return; } firstRoomNotified=true;
  var br=document.getElementById("tab-rooms"); if(br){ br.classList.add("pulse"); }
  var t=document.createElement("div"); t.className="trace-toast";
  t.innerHTML='<b>Première pièce ajoutée.</b><br>Retrouvez et modifiez toutes vos pièces dans '+
    'l\\'onglet <b>« Pièces »</b>, à droite. <button type="button" class="tt-x">Compris</button>';
  document.body.appendChild(t);
  var close=function(){ if(t.parentNode){ t.parentNode.removeChild(t); } if(br){ br.classList.remove("pulse"); } };
  var x=t.querySelector(".tt-x"); if(x){ x.addEventListener("click", close); }
  setTimeout(close, 9000);
}
function addRoom(poly){
  B.rooms.push({id:"r"+B.rooms.length, name:null, label:"autre", level:curLevel(), polygon:poly,
    area_m2:Math.max(area(poly),0.01), height_m:2.6, openings:[], exterior_wall_orientations:[], is_occupied:true, is_wet_room:false});
  sel=B.rooms.length-1;
  notifyFirstRoom();
}
function finishRoom(e){
  if(mode!=="draw" || draft.length<3){ setMode("idle"); return; }
  addRoom(draft.map(function(p){ return toM(p[0],p[1]); }));
  var pt=evClient(e); setMode("idle"); showRoomPopup(sel, pt[0], pt[1]);
}
function finishRect(e){
  if(!rectDrag){ return; }
  var a=rectDrag.a, b=rectDrag.b;
  if(Math.abs(a[0]-b[0])<4 || Math.abs(a[1]-b[1])<4){ rectDrag=null; render(); return; }
  var corners=[[a[0],a[1]],[b[0],a[1]],[b[0],b[1]],[a[0],b[1]]].map(function(p){ return toM(p[0],p[1]); });
  rectDrag=null; addRoom(corners); render();   // on reste en mode rect (tracer plusieurs pièces)
  var pt=evClient(e); showRoomPopup(sel, pt[0], pt[1]);
}
// Bulle de validation d'une pièce qui vient d'être tracée (nommer / valider / supprimer).
function showRoomPopup(i, x, y){
  var r=B.rooms[i]; if(!r){ return; }
  // Modale centrée + fond : reste toujours visible à l'écran (plus de bulle coincée au scroll).
  var back=document.createElement("div"); back.className="trace-backdrop";
  var pop=document.createElement("div"); pop.className="trace-pop";
  var opts=LABELS.map(function(p){ return '<option value="'+p[0]+'"'+(p[0]===r.label?" selected":"")+">"+p[1]+"</option>"; }).join("");
  pop.innerHTML='<div class="tp-t">Pièce tracée : '+fmt(r.area_m2)+' m²</div>'+
    '<select class="tp-sel">'+opts+'</select>'+
    '<div class="tp-row"><button type="button" class="btn sm tp-ok">Valider</button>'+
    '<button type="button" class="btn ghost sm tp-del">Supprimer</button></div>';
  document.body.appendChild(back); document.body.appendChild(pop);
  var selEl=pop.querySelector(".tp-sel");
  function close(){ if(pop.parentNode){ pop.parentNode.removeChild(pop); } if(back.parentNode){ back.parentNode.removeChild(back); } }
  selEl.onchange=function(){ r.label=selEl.value; render(); };
  pop.querySelector(".tp-ok").onclick=function(){ r.label=selEl.value; close(); render(); };
  pop.querySelector(".tp-del").onclick=function(){ var idx=B.rooms.indexOf(r); if(idx>=0){ B.rooms.splice(idx,1); } sel=-1; close(); render(); };
  back.onclick=function(){ r.label=selEl.value; close(); render(); };  // clic dehors = valider
  selEl.focus();
}
function addWindow(a,b){
  if(Math.hypot(a[0]-b[0],a[1]-b[1])<3){ return null; }
  var r=B.rooms[sel]; if(!r){ return null; }
  var ma=toM(a[0],a[1]), mb=toM(b[0],b[1]);
  var lenM=Math.hypot(ma[0]-mb[0],ma[1]-mb[1]);
  var c=centroidM(r), ex=mb[0]-ma[0], ey=mb[1]-ma[1], nx=-ey, ny=ex;
  var ox=(ma[0]+mb[0])/2-c[0], oy=(ma[1]+mb[1])/2-c[1];
  if(nx*ox+ny*oy<0){ nx=-nx; ny=-ny; }
  var o=nearestOri(nx,ny), h=lastSash, w=Math.max(lenM,0.1);
  var op={id:r.id+"_w"+r.openings.length, kind:"window", orientation:o,
    area_m2:Math.max(w*h,0.1), sill_height_m:0.9, head_height_m:0.9+h,
    openable:true, free_area_ratio:0.5, solar_protection:"aucune", _w:w, _h:h, _seg:[a,b]};
  r.openings.push(op);
  if(r.exterior_wall_orientations.indexOf(o)<0){ r.exterior_wall_orientations.push(o); }
  return {ri:sel, oi:r.openings.length-1};
}
function winRecalc(op){ op.area_m2=Math.max((op._w||0.1)*(op._h||1.5),0.1); op.sill_height_m=0.9; op.head_height_m=0.9+(op._h||1.5); }
function setWinWidth(op,w){
  w=Math.max(w,0.05); var old=op._w||w; op._w=w; winRecalc(op);
  if(op._seg && old>0){ var a=op._seg[0],b=op._seg[1],mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2,k=w/old;
    op._seg=[[mx+(a[0]-mx)*k,my+(a[1]-my)*k],[mx+(b[0]-mx)*k,my+(b[1]-my)*k]]; }
}
function showHeightPopup(ref, x, y){
  var r=B.rooms[ref.ri], op=r&&r.openings[ref.oi]; if(!op){ return; }
  var pop=document.createElement("div");
  pop.style.cssText="position:fixed;z-index:50;background:#fff;border:1px solid #0e9aa7;border-radius:.5rem;padding:.5rem .6rem;box-shadow:0 4px 16px rgba(0,0,0,.18);font:inherit";
  pop.style.left=Math.min(x,window.innerWidth-250)+"px"; pop.style.top=(y+8)+"px";
  pop.style.minWidth="220px";
  var cur=op.solar_protection||"aucune";
  var popts=PROT.map(function(p){ return '<option value="'+p[0]+'"'+(p[0]===cur?" selected":"")+">"+p[1]+"</option>"; }).join("");
  pop.innerHTML='<div style="font-size:.8rem;font-weight:600;margin-bottom:.2rem">Hauteur du châssis (m)</div>'+
    '<input type="number" step="0.1" value="'+fmt(op._h)+'" style="width:100%;padding:.3rem;box-sizing:border-box">'+
    '<div style="font-size:.8rem;font-weight:600;margin:.5rem 0 .2rem">Protection solaire</div>'+
    '<select class="hp-prot" style="width:100%;padding:.3rem;box-sizing:border-box">'+popts+'</select>'+
    '<div style="margin-top:.6rem;text-align:right"><button type="button" class="btn" style="padding:.3rem .8rem">OK</button></div>';
  document.body.appendChild(pop);
  var inp=pop.querySelector("input"), psel=pop.querySelector(".hp-prot"), ok=pop.querySelector("button");
  function commit(){ var v=parseFloat(inp.value); if(v>0){ op._h=v; lastSash=v; winRecalc(op); }
    op.solar_protection=psel.value; if(pop.parentNode){ pop.parentNode.removeChild(pop); } render(); }
  ok.onclick=commit;
  inp.onkeydown=function(e){ if(e.key==="Enter"){ commit(); } else if(e.key==="Escape"){ if(pop.parentNode){ pop.parentNode.removeChild(pop); } } };
  inp.focus(); inp.select();
}
function roomlist(){
  var d=document.getElementById("roomlist"); if(!d){ return; }
  if(!B.rooms.length){ d.innerHTML='<p class="empty">Aucune pièce tracée pour l\\'instant.</p>'; updateRoomsCount(); return; }
  // Pièces les plus récentes en haut (on parcourt les index à l'envers).
  var order=[]; for(var qi=B.rooms.length-1;qi>=0;qi--){ order.push(qi); }
  d.innerHTML=order.map(function(i){
    var r=B.rooms[i];
    var lab=LABELS.map(function(l){ return '<option value="'+l[0]+'"'+(l[0]===r.label?" selected":"")+">"+l[1]+"</option>"; }).join("");
    var chips=ORS.map(function(o){ return '<label class="chip"><input type="checkbox" data-i="'+i+'" data-or="'+o+'"'+(r.exterior_wall_orientations.indexOf(o)>=0?" checked":"")+">"+(ORF[o]||o)+"</label>"; }).join("");
    var wins=(r.openings||[]).map(function(op,j){
      var fopts=ORS.map(function(o){ return '<option value="'+o+'"'+(o===op.orientation?" selected":"")+">"+(ORF[o]||o)+"</option>"; }).join("");
      var cur=op.solar_protection||"aucune";
      var popts=PROT.map(function(p){ return '<option value="'+p[0]+'"'+(p[0]===cur?" selected":"")+">"+p[1]+"</option>"; }).join("");
      return '<tr>'+
        '<td class="wref">C'+(j+1)+'</td>'+
        '<td><select data-wi="'+i+'" data-wj="'+j+'" data-wf="facade">'+fopts+'</select></td>'+
        '<td><input data-wi="'+i+'" data-wj="'+j+'" data-wf="w" type="number" step="0.1" value="'+fmt(op._w!=null?op._w:0)+'" style="width:54px;padding:.15rem"></td>'+
        '<td><input data-wi="'+i+'" data-wj="'+j+'" data-wf="h" type="number" step="0.1" value="'+fmt(op._h!=null?op._h:0)+'" style="width:54px;padding:.15rem"></td>'+
        '<td style="color:var(--muted)">'+fmt(op.area_m2)+'</td>'+
        '<td><button type="button" data-wdel="'+i+"_"+j+'" class="iconbtn" title="supprimer">'+ICON_X+'</button></td></tr>'+
        '<tr class="wprot"><td></td><td colspan="5"><span class="wprot-lbl">Protection</span>'+
          '<select class="wprot-sel" data-wi="'+i+'" data-wj="'+j+'" data-wf="prot">'+popts+'</select></td></tr>';
    }).join("");
    var wintable=wins?('<table class="wintab"><tr><th>Réf.</th><th>Façade</th><th>l</th><th>h</th><th>m²</th><th></th></tr>'+wins+"</table>"):'<div style="font-size:.8rem;color:var(--faint)">Aucun châssis</div>';
    return '<div class="room-card'+(i===sel?" sel":"")+'" data-sel="'+i+'">'+
      '<div class="room-head">'+
        '<span class="room-no">'+(i+1)+'</span>'+
        '<button type="button" data-del="'+i+'" class="iconbtn" title="Supprimer la pièce">'+ICON_X+'</button>'+
        '<select data-lab="'+i+'">'+lab+'</select>'+
        '<b>'+fmt(r.area_m2)+' m²</b>'+
        (through(r)?'<span class="badge-ok">traversant</span>':'')+
        '<span class="grow"></span>'+
        '<label class="nivlbl">Niveau <input data-lvl="'+i+'" type="number" value="'+r.level+'" style="width:42px;padding:.15rem"></label>'+
      '</div>'+
      '<div class="room-sec"><span class="room-seclbl">Façades</span><div class="chips">'+chips+'</div></div>'+
      '<div class="room-sec"><span class="room-seclbl">Châssis</span>'+wintable+
        '<button type="button" data-pick="'+i+'" class="btn ghost mini">+ Ajouter</button></div>'+
    "</div>";
  }).join("");
  Array.prototype.forEach.call(d.querySelectorAll("[data-sel]"),function(c){ c.onclick=function(e){ if(e.target.closest("select,input,button,label")){ return; } sel=parseInt(c.dataset.sel); if(multi){ goToLevel(B.rooms[sel].level); } render(); }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-pick]"),function(b){ b.onclick=function(){ sel=parseInt(b.dataset.pick); if(multi){ goToLevel(B.rooms[sel].level); } setMode("window"); }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-lab]"),function(s){ s.onchange=function(){ B.rooms[parseInt(s.dataset.lab)].label=s.value; render(); }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-lvl]"),function(n){ n.onchange=function(){ B.rooms[parseInt(n.dataset.lvl)].level=parseInt(n.value)||0; render(); }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-del]"),function(b){ b.onclick=function(){ B.rooms.splice(parseInt(b.dataset.del),1); sel=-1; render(); }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-or]"),function(c){ c.onchange=function(){ var r=B.rooms[parseInt(c.dataset.i)],o=c.dataset.or,st=new Set(r.exterior_wall_orientations); if(c.checked){ st.add(o); } else { st.delete(o); } r.exterior_wall_orientations=Array.from(st); render(); }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-wf]"),function(el){ el.onchange=function(){
    var rm=B.rooms[parseInt(el.dataset.wi)], op=rm.openings[parseInt(el.dataset.wj)];
    if(el.dataset.wf==="facade"){ op.orientation=el.value; if(rm.exterior_wall_orientations.indexOf(el.value)<0){ rm.exterior_wall_orientations.push(el.value); } render(); return; }
    if(el.dataset.wf==="prot"){ op.solar_protection=el.value; render(); return; }
    var v=parseFloat(el.value); if(!(v>0)){ return; }
    if(el.dataset.wf==="w"){ setWinWidth(op,v); } else { op._h=v; lastSash=v; winRecalc(op); }
    render();
  }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-wdel]"),function(b){ b.onclick=function(){ var p=b.dataset.wdel.split("_"); B.rooms[parseInt(p[0])].openings.splice(parseInt(p[1]),1); render(); }; });
  updateRoomsCount();
}
function syncHidden(){
  var ls=B.rooms.map(function(r){ return r.level; });
  B.num_levels=B.rooms.length?(Math.max.apply(null,ls)-Math.min.apply(null,ls)+1):1;
  var el=document.getElementById("building_json"); if(el){ el.value=JSON.stringify(B); }
}
function zoomBy(factor){
  var old=stage.scaleX(), ns=Math.max(0.02,Math.min(50,old*factor));
  var p={x:stage.width()/2,y:stage.height()/2}, mp={x:(p.x-stage.x())/old,y:(p.y-stage.y())/old};
  stage.scale({x:ns,y:ns}); stage.position({x:p.x-mp.x*ns,y:p.y-mp.y*ns}); render();
}
function onWheel(e){
  e.evt.preventDefault(); var old=stage.scaleX(), p=stage.getPointerPosition();
  var mp={x:(p.x-stage.x())/old,y:(p.y-stage.y())/old};
  var ns=e.evt.deltaY>0?old/1.12:old*1.12; ns=Math.max(0.02,Math.min(50,ns));
  stage.scale({x:ns,y:ns}); stage.position({x:p.x-mp.x*ns,y:p.y-mp.y*ns}); render();
}
function multiTouch(e){ return e.evt.touches && e.evt.touches.length>1; }
function onDown(e){
  if(multiTouch(e)){ return; }
  if(mode==="window" && sel>=0){ var p=ptr(); winDrag={a:[p.x,p.y],b:[p.x,p.y]}; }
  else if(mode==="rect"){ var q=snapPx([ptr().x,ptr().y]); rectDrag={a:q,b:q}; }
}
function onMove(e){
  if(multiTouch(e)){ return; }
  if(winDrag){ var p=ptr(); winDrag.b=[p.x,p.y]; render(); }
  else if(rectDrag){ var q=snapPx([ptr().x,ptr().y]); rectDrag.b=q; render(); }
}
function onUp(e){
  if(winDrag){ var ref=addWindow(winDrag.a,winDrag.b); winDrag=null; render();
    if(ref){ var ev=e.evt, cx=ev.clientX!=null?ev.clientX:(ev.changedTouches?ev.changedTouches[0].clientX:200), cy=ev.clientY!=null?ev.clientY:(ev.changedTouches?ev.changedTouches[0].clientY:200); showHeightPopup(ref,cx,cy); }
    return;
  }
  if(rectDrag){ finishRect(e); }
}
function onClick(e){
  if(mode==="draw"){ var p=ptr(), q=snapPx([p.x,p.y]);
    // Re-cliquer près du 1er point ferme automatiquement la pièce.
    if(draft.length>=3){ var f0=draft[0]; if(Math.hypot(q[0]-f0[0],q[1]-f0[1])<sc(10*markF())){ finishRoom(e); return; } }
    draft.push(q); updateFinishBtn(); render();
  }
  else if(mode==="calibrate"){ var qc=ptr(); calib.push([qc.x,qc.y]);
    if(calib.length===2){ var dpx=Math.hypot(calib[0][0]-calib[1][0],calib[0][1]-calib[1][1]); var real=parseFloat(prompt("Longueur reelle de ce segment, en metres ?","5")); if(real>0 && dpx>0){ F().mpp=real/dpx; } setMode("idle"); }
    else { render(); }
  }
}
function onTouchMove(e){
  var t=e.evt.touches; if(!t || t.length<2){ return; }
  e.evt.preventDefault();
  if(stage.isDragging()){ stage.stopDrag(); }
  var rect=stage.container().getBoundingClientRect();
  var c={x:(t[0].clientX+t[1].clientX)/2-rect.left, y:(t[0].clientY+t[1].clientY)/2-rect.top};
  var dist=Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY);
  if(!lastDist){ lastDist=dist; return; }
  var old=stage.scaleX(), mp={x:(c.x-stage.x())/old,y:(c.y-stage.y())/old};
  var ns=Math.max(0.02,Math.min(50,old*(dist/lastDist)));
  stage.scale({x:ns,y:ns}); stage.position({x:c.x-mp.x*ns,y:c.y-mp.y*ns}); stage.batchDraw();
  lastDist=dist;
}
function initStage(){
  stage=new Konva.Stage({container:"stage", width:10, height:10, draggable:true});
  bgLayer=new Konva.Layer({listening:false}); shapeLayer=new Konva.Layer();
  stage.add(bgLayer); stage.add(shapeLayer);
  stage.on("wheel",onWheel);
  stage.on("mousedown touchstart",onDown);
  stage.on("mousemove",onMove);
  stage.on("touchmove",function(e){ if(multiTouch(e)){ onTouchMove(e); } else { onMove(e); } });
  stage.on("mouseup touchend",function(e){ lastDist=0; onUp(e); });
  stage.on("click tap",onClick);
  stage.container().style.cursor="grab";
}
document.addEventListener("DOMContentLoaded",function(){
  if(!window.Konva){ var s=document.getElementById("stage"); if(s){ s.innerHTML='<p style="padding:1rem;color:#c0392b">Konva non charge (verifie le reseau).</p>'; } return; }
  initStage();
  document.getElementById("t-draw").onclick=function(){ setMode(mode==="draw"?"idle":"draw"); };
  document.getElementById("t-rect").onclick=function(){ setMode(mode==="rect"?"idle":"rect"); };
  document.getElementById("t-finish").onclick=function(){ finishRoom(); };
  document.getElementById("t-cal").onclick=function(){ setMode(mode==="calibrate"?"idle":"calibrate"); };
  document.getElementById("t-win").onclick=function(){
    if(sel<0){ var el=document.getElementById("modebanner"); if(el){ el.className="stage-mode"; el.textContent="Sélectionnez d'abord une pièce (sur le plan ou via « + Ajouter »), puis tracez sur sa façade."; } return; }
    setMode(mode==="window"?"idle":"window");
  };
  var tt=document.getElementById("tab-tools"), tr=document.getElementById("tab-rooms");
  if(tt){ tt.onclick=function(){ showSide("tools"); }; }
  if(tr){ tr.onclick=function(){ showSide("rooms"); }; }
  document.getElementById("t-zin").onclick=function(){ zoomBy(1.25); };
  document.getElementById("t-zout").onclick=function(){ zoomBy(0.8); };
  document.getElementById("t-zreset").onclick=function(){ fitStage(); render(); };
  document.getElementById("t-mark").oninput=function(){ render(); };
  document.addEventListener("keydown",function(e){ if(e.key==="Escape" && mode!=="idle"){ setMode("idle"); } });
  var se=document.querySelector('input[name=sash]'); if(se){ var sv=parseFloat(se.value); if(sv>0){ lastSash=sv; } }
  window.addEventListener("resize",function(){ fitStage(); render(); });
  setBanner(); applyFloor(); render();
});
"""


# Rose des vents (overlay statique, coin du cadre) — N = +y (convention de l'app).
_COMPASS_SVG = """
<svg width="78" height="78" viewBox="0 0 78 78" aria-label="rose des vents"
  style="position:absolute;top:10px;right:10px;width:78px;height:78px;
  background:rgba(255,255,255,.85);border:1px solid var(--line);border-radius:50%;pointer-events:none">
  <circle cx="39" cy="39" r="36" fill="none" stroke="#cbd5e1" stroke-width="1"/>
  <polygon points="39,7 33,39 45,39" fill="#c0392b"/>
  <polygon points="39,71 33,39 45,39" fill="#9aa3ad"/>
  <polygon points="7,39 39,33 39,45" fill="#cbd5e1"/>
  <polygon points="71,39 39,33 39,45" fill="#cbd5e1"/>
  <text x="39" y="20" text-anchor="middle" font-size="11" font-weight="700" fill="#c0392b">N</text>
  <text x="39" y="68" text-anchor="middle" font-size="9" fill="#5b6b80">S</text>
  <text x="70" y="42" text-anchor="middle" font-size="9" fill="#5b6b80">E</text>
  <text x="8" y="42" text-anchor="middle" font-size="9" fill="#5b6b80">O</text>
</svg>
"""


# Export d'une étude (sauvegarde/reprise sans BDD) — partagé par les deux éditeurs.
_STUDY_IO_JS = """
function downloadStudy(){
  if(window.syncHidden){ try{ syncHidden(); }catch(e){} }
  var form=document.getElementById('valform'), cfg={};
  Array.prototype.forEach.call(form.querySelectorAll('[name]'), function(el){
    if(el.name!=='building_json'){ cfg[el.name]=(el.type==='checkbox')?(el.checked?'on':''):el.value; }
  });
  var bj=(document.getElementById('building_json')||{}).value||'';
  var data={zephyr_study:1, config:cfg, building_json:bj};
  var blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='etude-zephyr.json'; document.body.appendChild(a); a.click(); a.remove();
}
"""


# Page de résultats : enregistrer le projet (JSON) + export Excel (CSV) côté client.
_RESULTS_JS = """
function downloadProject(){
  var form=document.getElementById('valform'), cfg={};
  if(form){ Array.prototype.forEach.call(form.querySelectorAll('[name]'), function(el){
    if(el.name!=='building_json'){ cfg[el.name]=(el.type==='checkbox')?(el.checked?'on':''):el.value; }
  }); }
  var bj=(document.getElementById('building_json')||{}).value||'';
  var data={zephyr_study:1, config:cfg, building_json:bj};
  var blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='projet-zephyr.json'; document.body.appendChild(a); a.click(); a.remove();
}
// PDF = téléchargement 1 clic. Le serveur imprime la page de résultats elle-même
// via Chromium headless (même design, graphes, dépliants ouverts) et renvoie le PDF
// en pièce jointe. On poste le formulaire dans une iframe cachée → pas de navigation.
function exportPdf(){
  var f=document.getElementById('valform'); if(!f){ return; }
  var ifr=document.getElementById('pdf-sink');
  if(!ifr){ ifr=document.createElement('iframe'); ifr.id='pdf-sink'; ifr.name='pdf-sink';
    ifr.style.display='none'; document.body.appendChild(ifr); }
  var act=f.getAttribute('action'), tgt=f.getAttribute('target');
  f.setAttribute('action','/etude/rapport'); f.setAttribute('target','pdf-sink');
  f.submit();
  if(act){ f.setAttribute('action',act); } else { f.removeAttribute('action'); }
  if(tgt){ f.setAttribute('target',tgt); } else { f.removeAttribute('target'); }
}
function exportCsv(){
  var el=document.getElementById('calc-data');
  if(!el){ alert("L'export Excel détaillé n'est disponible qu'en étude complète."); return; }
  var rows=[]; try { rows=JSON.parse(el.textContent); } catch(e){ rows=[]; }
  var SEC={capex_vmc:'CAPEX VMC',capex_vnc:'CAPEX VNC',opex_vmc:'OPEX VMC (an 1)',
    opex_vnc:'OPEX VNC (an 1)',penalite:'Pénalité',synthese:'Synthèse'};
  var out=[['Section','Poste','Détail du calcul','Montant (EUR)']];
  rows.forEach(function(r){
    var val=Math.round(Number(r.value)||0);
    var formula=(''+(r.formula||'')).replace(/\\u00a0/g,' ').replace(/\\s+/g,' ').trim();
    out.push([SEC[r.section]||r.section, r.label, formula, val]);
  });
  var csv=out.map(function(row){ return row.map(function(c){
    return '"'+(''+c).replace(/"/g,'""')+'"'; }).join(';'); }).join('\\r\\n');
  var blob=new Blob(['\\ufeff'+csv],{type:'text/csv;charset=utf-8'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='bilan-vnc.csv'; document.body.appendChild(a); a.click(); a.remove();
}
"""


def render_tracing(floors: list[dict[str, object]], hidden_fields: str) -> str:
    """Éditeur de **tracé** : plan(s) en fond, l'ingénieur trace les pièces au clic.

    `floors` = liste de niveaux ``{level, image_uri, w, h, mpp}`` (un seul élément
    pour un plan/planche A0 unique ; plusieurs pour un PDF par étage). La mesure
    vient des clics calibrés (échelle par niveau), pas d'une lecture du raster.
    Produit un `building_json` (polygones en mètres) → mêmes résultats.
    """
    data = json.dumps({"floors": floors})
    body = f"""
<div class="trace-head">
  <h1 style="margin-bottom:.2rem">Tracer le plan</h1>
  <details class="howto explain" open>
    <summary>{_icon("bulb")} Comment tracer</summary>
    <ol>
      <li><b>Objectif</b> : délimiter chaque pièce et poser ses châssis ; le code en
      déduit surfaces, façades et espaces traversants.</li>
      <li><b>Tracer une pièce</b> : bouton <b>Rectangle</b> puis glisser en diagonale,
      ou <b>Point par point</b> puis cliquer les coins (re-cliquer le 1<sup>er</sup>
      point ferme la pièce). Une bulle s'ouvre pour valider et nommer la pièce.</li>
      <li><b>Façades &amp; châssis</b> : sélectionner une pièce, bouton <b>Châssis</b>,
      puis glisser le long d'une façade (longueur = largeur ; une bulle demande la hauteur).</li>
      <li><b>Naviguer</b> : <kbd>molette</kbd> zoom, glisser = déplacer le plan,
      <kbd>Échap</kbd> quitte l'outil en cours.</li>
      <li><b>Inutile de tracer</b> WC, salle de bain, circulation, garage, sous-sols :
      concentrez-vous sur les <b>pièces de vie et bureaux</b> (les locaux de service
      ne comptent pas dans les notes ventilation / vitrage).</li>
    </ol>
  </details>
</div>
<div class="trace-layout">
  <div class="trace-canvas-wrap">
    <div class="stage-mode empty" id="modebanner">Sélectionnez un outil pour commencer.</div>
    <div style="position:relative">
      <div id="stage"></div>
      {_COMPASS_SVG}
    </div>
  </div>
  <aside class="trace-side">
    <div class="side-tabs">
      <button type="button" id="tab-tools" class="active">Outils</button>
      <button type="button" id="tab-rooms">Pièces <span id="rooms-count" class="cnt">0</span></button>
    </div>
    <div class="palette" id="panel-tools">
      <div class="pgroup">
        <div class="ptitle">Niveau des nouvelles pièces</div>
        <div class="levelsel" id="levelsel"></div>
      </div>
      <div class="pgroup">
        <div class="ptitle">Pièces</div>
        <button type="button" class="btn ghost" id="t-rect">{_icon("rect")} Rectangle</button>
        <button type="button" class="btn ghost" id="t-draw">{_icon("spline")} Point par point</button>
        <button type="button" class="btn ghost" id="t-finish" style="display:none">{_icon("check")} Terminer la pièce</button>
        <label class="chk"><input type="checkbox" id="t-snap" checked> {_icon("magnet")} Magnétisme</label>
      </div>
      <div class="pgroup">
        <div class="ptitle">Châssis</div>
        <button type="button" class="btn ghost" id="t-win">{_icon("window")} Tracer un châssis</button>
        <span class="lbl" style="font-weight:400">Sélectionnez une pièce, puis glissez sur sa façade.</span>
      </div>
      <div class="pgroup">
        <div class="ptitle">Vue</div>
        <div class="row">
          <button type="button" class="btn ghost" id="t-zout" title="Dézoomer">−</button>
          <button type="button" class="btn ghost" id="t-zin" title="Zoomer">+</button>
          <button type="button" class="btn ghost" id="t-zreset" title="Vue entière">{_icon("maximize")}</button>
        </div>
        <label class="lbl" title="Grosseur des repères de tracé">Taille des repères
          <input type="range" id="t-mark" min="0.5" max="4" step="0.5" value="1" style="width:100%"></label>
      </div>
      <div class="pgroup">
        <div class="ptitle">Échelle</div>
        <button type="button" class="btn ghost" id="t-cal">{_icon("ruler")} Calibrer l'échelle</button>
        <span id="scaleinfo" class="lbl" style="font-weight:400"></span>
      </div>
    </div>
    <div class="roomlist-wrap" id="panel-rooms" style="display:none"><div id="roomlist"></div></div>
  </aside>
</div>
<form id="valform" method="post" action="/etude/resultat" onsubmit="syncHidden()">
  {hidden_fields}
  <input type="hidden" name="building_json" id="building_json">
  <p style="margin-top:1.2rem">
    <a class="btn ghost" href="/etude">{_icon("arrow-left")} Config</a>
    <button type="button" class="btn ghost" onclick="downloadStudy()">{_icon("download")} Télécharger l'étude</button>
    <button class="btn" type="submit">Confirmer &amp; calculer {_icon("arrow-right")}</button>
  </p>
</form>
<script src="https://unpkg.com/konva@9/konva.min.js"></script>
<script>window.TRACE={data};</script>
<script>{_TRACING_JS}</script>
<script>{_STUDY_IO_JS}</script>"""
    return _layout("Zéphyr — tracé du plan", body, cta=False, wide=True)


def render_validation(building: Building, hidden_fields: str, warnings: list[str]) -> str:
    """Page 2 — validation humaine de la géométrie (§2.8).

    Éditeur de plan **interactif** (clic sur une pièce → label, façades, châssis,
    traversant live) quand les pièces ont des polygones ; sinon repli sur un
    formulaire de saisie pièce par pièce.
    """
    rooms = building.rooms
    has_poly = any(r.polygon for r in rooms)
    warn_html = "".join(f'<div class="flag">{html.escape(w)}</div>' for w in warnings)
    total = sum(r.area_m2 for r in rooms)
    n_labelled = sum(1 for r in rooms if r.label.value not in ("", "autre"))
    n_windows = sum(len(r.openings) for r in rooms)
    n_through = sum(1 for r in rooms if r.is_through)
    chips = (
        '<div class="kpis">'
        f'<div class="kpi"><div class="k">Pièces</div><div class="v">{len(rooms)}</div></div>'
        f'<div class="kpi"><div class="k">Labellisées</div>'
        f'<div class="v">{n_labelled}/{len(rooms)}</div></div>'
        f'<div class="kpi"><div class="k">Châssis</div><div class="v">{n_windows}</div></div>'
        f'<div class="kpi"><div class="k">Traversantes</div>'
        f'<div class="v">{n_through}/{len(rooms)}</div></div>'
        "</div>"
    )

    if has_poly:
        data = building.model_dump_json()
        colors = json.dumps(_LABEL_COLORS)
        core = f"""
<p class="lead" style="color:var(--muted)">Cliquez une pièce sur le plan pour
corriger son <b>label</b>, ses <b>façades</b> et ses <b>châssis</b>. Le
<b>traversant</b> se recalcule en direct. ({len(rooms)} pièce(s), {total:.0f} m²)</p>
{chips}{warn_html}
<form id="valform" method="post" action="/etude/resultat" onsubmit="syncHidden()">
  {hidden_fields}
  <input type="hidden" name="building_json" id="building_json">
  <div class="editor">
    <div><div class="levelbar" id="levelbar"></div><svg id="plan"></svg></div>
    <div id="panel"></div>
  </div>
  <p style="margin-top:1.2rem">
    <a class="btn ghost" href="/etude">{_icon("arrow-left")} Config</a>
    <button type="button" class="btn ghost" onclick="downloadStudy()">{_icon("download")} Télécharger l'étude</button>
    <button class="btn" type="submit">Confirmer &amp; calculer {_icon("arrow-right")}</button>
  </p>
</form>
<script>window.BUILDING={data};window.LABEL_COLORS={colors};</script>
<script>{_VALIDATION_JS}</script>
<script>{_STUDY_IO_JS}</script>"""
    else:
        edit_blocks = "".join(_room_edit_block(i, r) for i, r in enumerate(rooms))
        core = f"""
<p class="lead" style="color:var(--muted)">Pièces lues ({len(rooms)}, {total:.0f} m²)
sans polygones ; saisissez/validez façades et châssis pièce par pièce (§2.8).</p>
{chips}{warn_html}
<form method="post" action="/etude/resultat">
  {hidden_fields}
  <input type="hidden" name="n_rooms" value="{len(rooms)}">
  {edit_blocks}
  <p style="margin-top:1.4rem">
    <a class="btn ghost" href="/etude">{_icon("arrow-left")} Config</a>
    <button class="btn" type="submit">Confirmer &amp; calculer {_icon("arrow-right")}</button>
  </p>
</form>"""

    body = f"<h1>Validation de la géométrie</h1>{core}"
    return _layout("Zéphyr — validation géométrie", body, cta=False)


def _gauge_svg(score: float, grade: str) -> str:
    """Jauge circulaire (donut) du score global."""
    color = _GRADE_COLOR.get(grade, "#0e9aa7")
    r = 52.0
    circ = 2 * 3.14159 * r
    filled = circ * max(0.0, min(1.0, score / 100.0))
    return f"""<svg class="gauge" width="140" height="140" viewBox="0 0 140 140">
  <circle cx="70" cy="70" r="{r}" fill="none" stroke="#eef2f6" stroke-width="14"/>
  <circle cx="70" cy="70" r="{r}" fill="none" stroke="{color}" stroke-width="14"
    stroke-linecap="round" stroke-dasharray="{filled:.1f} {circ:.1f}"
    transform="rotate(-90 70 70)"/>
  <text x="70" y="82" text-anchor="middle" font-size="38" font-weight="800"
    fill="{color}">{score:.0f}</text>
</svg>"""


def _cap(text: str) -> str:
    """Majuscule en début de phrase (laisse les chiffres / sigles intacts)."""
    return text[:1].upper() + text[1:] if text else text


def _breakdown_table(bd: object) -> str:
    """Tableau du détail d'un critère (par pièce / par poste) + calcul de la note."""
    rows = getattr(bd, "rows", None)
    if not rows:
        return ""
    cols = getattr(bd, "columns", []) or []
    head = (
        "<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr>" if cols else ""
    )
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    formula = getattr(bd, "formula", None)
    fhtml = f'<p class="crit-formula">{html.escape(formula)}</p>' if formula else ""
    return f'<table class="bd">{head}{body}</table>{fhtml}'


def _criteria_bars(result: StudyResult) -> str:
    if result.score is None:
        return ""
    rows = []
    for c in result.score.criteria:
        color = (
            "#1a9d5a" if c.score >= 75 else "#d9a400" if c.score >= 50 else "#e07b39"
        )
        bar = (
            f'<div class="lab">{html.escape(c.label)}</div>'
            f'<div class="track"><div class="fill" style="width:{c.score:.0f}%;'
            f'background:{color}"></div></div>'
            f'<div class="val">{c.score:.0f}</div>'
        )
        table = _breakdown_table(c.breakdown)
        # Détail (« résultats ») : puces si disponibles, sinon phrase.
        pts = getattr(c, "detail_points", None) or []
        if pts:
            items = "".join(f"<li>{html.escape(_cap(p))}</li>" for p in pts)
            detail = f'<ul class="crit-list crit-summary">{items}</ul>'
        elif c.detail:
            detail = f'<p class="crit-summary">{html.escape(_cap(c.detail))}</p>'
        else:
            detail = ""
        # Barème : ligne d'intro + puces si disponibles.
        spts = getattr(c, "scale_points", None) or []
        if spts:
            sitems = "".join(f"<li>{html.escape(_cap(p))}</li>" for p in spts)
            lead = (
                f'<p class="crit-scale"><b>Barème :</b> {html.escape(c.scale)}</p>'
                if c.scale else '<p class="crit-scale"><b>Barème</b></p>'
            )
            scale = f'{lead}<ul class="crit-list">{sitems}</ul>'
        elif c.scale:
            scale = f'<p class="crit-scale"><b>Barème :</b> {html.escape(c.scale)}</p>'
        else:
            scale = ""
        if table or scale or detail:
            rows.append(
                f'<details class="crit"><summary class="bar-row">{bar}</summary>'
                f'<div class="crit-detail">{detail}{scale}{table}</div></details>'
            )
        else:
            rows.append(f'<div class="bar-row">{bar}</div>')
    return '<div class="bars">' + "".join(rows) + "</div>"


_VAN_CHART_JS = """
(function(){
  if(!window.Chart){
    var el=document.getElementById('vanchart');
    if(el){ el.outerHTML='<p style="color:#c0392b;padding:1rem">Graphe indisponible '+
      '(Chart.js non chargé, vérifie le réseau).</p>'; }
    return;
  }
  var src=document.getElementById('van-data');
  if(!src){ return; }
  var cfg=JSON.parse(src.textContent);
  var data=cfg.cumulative, be=cfg.break_even;
  var labels=data.map(function(_,i){ return 'An '+i; });
  var fmt=function(v){ return Math.round(v).toLocaleString('fr-FR')+' \\u20ac'; };
  // Ligne de zéro (seuil de rentabilité) en pointillés.
  var zeroLine={ id:'zeroLine', afterDatasetsDraw:function(c){
    var ya=c.scales.y; if(!ya){ return; }
    var y=ya.getPixelForValue(0); var a=c.chartArea; var ctx=c.ctx;
    ctx.save(); ctx.strokeStyle='#94a3b8'; ctx.setLineDash([5,4]); ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(a.left,y); ctx.lineTo(a.right,y); ctx.stroke(); ctx.restore();
  }};
  new Chart(document.getElementById('vanchart'),{
    type:'line',
    data:{ labels:labels, datasets:[{
      label:'VAN cumulée (économie VNC)', data:data,
      borderColor:'#0e9aa7', backgroundColor:'rgba(14,154,167,.12)',
      borderWidth:2.5, fill:false, tension:.15,
      pointRadius:data.map(function(_,i){ return i===be?5:2.5; }),
      pointHoverRadius:6,
      pointBackgroundColor:data.map(function(_,i){ return i===be?'#1a9d5a':'#0e9aa7'; })
    }]},
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{ mode:'index', intersect:false },
      plugins:{
        legend:{ display:false },
        tooltip:{ callbacks:{
          title:function(it){ return it[0].label+(it[0].dataIndex===be?' (seuil de rentabilité)':''); },
          label:function(c){ return 'VAN cumulée : '+fmt(c.parsed.y); }
        }}
      },
      scales:{
        x:{ title:{ display:true, text:'Année' }, grid:{ display:false } },
        y:{ title:{ display:true, text:'VAN cumulée (\\u20ac)' },
            ticks:{ callback:function(v){ return fmt(v); } },
            grid:{ color:'rgba(148,163,184,.18)' } }
      }
    },
    plugins:[zeroLine]
  });
})();
"""


def _van_chart(cumulative: list[float], break_even: int | None) -> str:
    """Graphe VAN cumulée via Chart.js (axes, échelle, ligne de zéro, break-even).

    Lib spécialisée chargée par CDN (même approche que Konva pour le tracé, cf.
    CLAUDE.md §5). Les données transitent par un bloc JSON ; le JS reste statique
    (validable par ``node --check``).
    """
    if not cumulative:
        return ""
    payload = json.dumps(
        {"cumulative": [round(v, 2) for v in cumulative], "break_even": break_even}
    )
    return (
        '<div class="vanchart"><canvas id="vanchart"></canvas></div>'
        f'<script type="application/json" id="van-data">{payload}</script>'
        '<script src="https://unpkg.com/chart.js@4/dist/chart.umd.min.js"></script>'
        f"<script>{_VAN_CHART_JS}</script>"
    )


_GRADE_LEGEND = "A ≥ 80, B ≥ 65, C ≥ 50, D ≥ 35, E < 35"


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def _cost_block(title: str, lines: list[CalcLine]) -> str:
    """Bloc de coûts : un poste par ligne **dépliable** (clic → formule + nombres dessous)."""
    rows = []
    for ln in lines:
        rows.append(
            '<details class="costrow">'
            f'<summary><span class="lbl">{html.escape(ln.label)}</span>'
            f'<span class="amt">{_eur(ln.value_eur)}</span></summary>'
            f'<div class="formula">{html.escape(ln.formula)}'
            f'{(" : " + html.escape(ln.note)) if ln.note else ""}</div></details>'
        )
    total = sum(ln.value_eur for ln in lines)
    rows.append(
        '<div class="costrow total"><span class="lbl">Total</span>'
        f'<span class="amt">{_eur(total)}</span></div>'
    )
    return (
        f"<h4 style='margin:.6rem 0 .2rem'>{html.escape(title)}</h4>"
        f"<div class='costlist'>{''.join(rows)}</div>"
    )


def _score_legend(result: StudyResult) -> str:
    if result.score is None:
        return ""
    items = "".join(
        f"<tr><td>{html.escape(c.label)}</td>"
        f"<td style='text-align:left'>{html.escape(c.scale or 'n.c.')}</td></tr>"
        for c in result.score.criteria
    )
    return (
        f"<details class='explain'><summary>{_icon('bulb')} Comment le score est-il calculé ?"
        "</summary>"
        "<p style='color:var(--muted);font-size:.85rem'>Le score global est la "
        "<b>moyenne pondérée</b> des quatre critères ci-dessous. Chaque critère est noté de 0 à "
        f"100 selon une règle simple (colonne de droite). Notes : {_GRADE_LEGEND}.</p>"
        f"<table class='kv'>{items}</table></details>"
    )


_SENS_LABELS = {
    "price_elec_eur_kwh": "Prix de l'électricité",
    "wacc": "Taux d'actualisation (WACC)",
    "vnc_m2_per_ouvrant": "Densité d'ouvrants",
    "bos_subscription_eur_per_point_year": "Abonnement BOS",
    "heating_penalty_eur_per_year": "Pénalité de chauffage",
    "inflation": "Inflation",
}


def _tornado(result: StudyResult) -> str:
    # Masqué pour l'instant (décision produit) : on ne montre plus « ce qui fait varier
    # le résultat » (sensibilité/tornado). Le câblage ROI reste en place ; on rebranchera
    # l'affichage ici le jour voulu.
    return ""


def _tendance(score: float) -> tuple[str, str]:
    """Tendance d'aptitude (mode rapide) : Favorable / À étudier / Défavorable."""
    if score >= 65:
        return "Favorable", "#1a9d5a"
    if score >= 45:
        return "À étudier", "#d9a400"
    return "Défavorable", "#c0392b"


def _financial_quick(result: StudyResult) -> str:
    """Bilan financier **allégé** (mode rapide) : ordres de grandeur, pas de détail."""
    r = result.roi
    if r is None:
        return ""
    npv = r.npv_delta_eur
    if npv > 0:
        tlab, tcol = "plutôt favorable", "#1a9d5a"
    elif npv > -r.capex_vnc_eur * 0.1:
        tlab, tcol = "à l'équilibre", "#d9a400"
    else:
        tlab, tcol = "plutôt défavorable", "#c0392b"
    rng = ""
    if r.npv_delta_range is not None:
        rng = (
            '<div style="font-size:.72rem;color:var(--muted)">fourchette large '
            f"{_eur(r.npv_delta_range.low)} … {_eur(r.npv_delta_range.high)}</div>"
        )
    kpis = '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="k">{k}{_info(t)}</div><div class="v">{v}</div>{sub}</div>'
        for k, v, sub, t in [
            ("CAPEX VMC (ordre de grandeur)", _eur(r.capex_vmc_eur), "",
             "Investissement VMC double-flux estimé (ratios €/m²)."),
            ("CAPEX VNC (ordre de grandeur)", _eur(r.capex_vnc_eur), "",
             "Investissement VNC estimé."),
            ("VAN économie VNC (indicative)", _eur(npv), rng,
             "Économie actualisée VNC vs VMC. En mode rapide, fourchette volontairement large."),
        ]
    ) + "</div>"
    return (
        "<h2 class='sec'>Bilan financier — estimation</h2>"
        f'<p style="margin:.2rem 0 .6rem">Tendance économique : '
        f'<b style="color:{tcol}">{tlab}</b>.</p>'
        f"{kpis}"
        "<p style='color:var(--muted);font-size:.85rem;margin:.6rem 0'>Chiffres en "
        "<b>ordre de grandeur</b> : le mode rapide ne détaille pas les postes. Pour un bilan "
        "complet (CAPEX/OPEX détaillés, hypothèses éditables, sensibilité), lancez une "
        "<b>étude complète</b> avec les plans.</p>"
    )


def _financial_section(result: StudyResult, hyp_html: str = "") -> str:
    """Bilan financier détaillé (façon comparatif Excel VNC vs VMC).

    ``hyp_html`` (hypothèses éditables) est inséré **juste avant les calculs** (CAPEX/OPEX).
    """
    r = result.roi
    if r is None:
        return ""
    be = f"an {r.break_even_year}" if r.break_even_year is not None else "hors horizon"

    def _sub(txt: str) -> str:
        return f'<div style="font-size:.72rem;color:var(--muted);font-weight:400">{txt}</div>'

    van_sub = ""
    if r.npv_delta_range is not None:
        van_sub = _sub(f"P10–P90 {_eur(r.npv_delta_range.low)} … {_eur(r.npv_delta_range.high)}")
    be_sub = ""
    if r.break_even_range is not None:
        h = r.horizon_years
        lo, hi = r.break_even_range.low, r.break_even_range.high
        lo_s = "hors" if lo > h else f"an {lo:.0f}"
        hi_s = "hors" if hi > h else f"an {hi:.0f}"
        be_sub = _sub(f"P10–P90 {lo_s} … {hi_s}")
    proba = r.assumptions.get("proba_van_favorable", "")
    proba_sub = _sub("probabilité VNC gagnante") if proba else ""
    kpis = '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="k">{html.escape(k)}{_info(tip)}</div>'
        f'<div class="v">{v}</div>{sub}</div>'
        for k, v, sub, tip in [
            ("CAPEX VNC", _eur(r.capex_vnc_eur), "",
             "Investissement initial de la solution VNC (ouvrants motorisés, capteurs, "
             "plateforme BOS, câblage, mise en service), aléas +10 % inclus."),
            ("VAN économie VNC", _eur(r.npv_delta_eur), van_sub,
             "Valeur Actuelle Nette de l'économie VNC = coûts VMC − coûts VNC, actualisée au "
             "coût du capital (WACC) sur l'horizon. Positive ⇒ la VNC est l'option la moins chère."),
            ("Break-even", be, be_sub,
             "Année où l'économie VNC cumulée et actualisée devient positive "
             "(retour sur investissement)."),
            ("VNC favorable", proba or "n.c.", proba_sub,
             "Probabilité, sur un tirage Monte-Carlo des hypothèses sensibles, que la VAN "
             "soit positive."),
        ]
    ) + "</div>"

    def _sec(name: str) -> list[CalcLine]:
        return [ln for ln in r.calc_lines if ln.section == name]

    openbook = (
        "<p style='color:var(--muted);font-size:.85rem;margin:.2rem 0 .6rem'>Chaque poste est "
        "<b>dépliable</b> : clic → la formule et les nombres du calcul. Montants aléas inclus "
        "(+10 %). OPEX an 1 avant inflation.</p>"
    )
    capex = (
        "<h3>CAPEX (investissement, aléas inclus)</h3>"
        f"{openbook}"
        '<div class="crit-grid cost-cols">'
        f"<div>{_cost_block('VMC double-flux', _sec('capex_vmc'))}</div>"
        f"<div>{_cost_block('VNC', _sec('capex_vnc'))}</div>"
        "</div>"
    )
    opex = (
        "<h3>OPEX annuel (an 1, avant inflation)</h3>"
        '<div class="crit-grid cost-cols">'
        f"<div>{_cost_block('VMC double-flux', _sec('opex_vmc'))}</div>"
        f"<div>{_cost_block('VNC', _sec('opex_vnc'))}</div>"
        "</div>"
    )
    tco_tip = (
        "TCO (Total Cost of Ownership) : somme NON actualisée de tous les coûts sur l'horizon "
        "(CAPEX initial + OPEX annuels inflatés + renouvellements), par solution. "
        "Contrairement à la VAN, il n'actualise pas et ne pondère pas le temps."
    )
    synth = (
        "<h3>Synthèse sur "
        f"{r.horizon_years} ans</h3><table class='kv'>"
        f"<tr><td>TCO non actualisé VMC{_info(tco_tip)}</td>"
        f"<td>{_eur(r.tco_vmc_undiscounted_eur)}</td></tr>"
        f"<tr><td>TCO non actualisé VNC{_info(tco_tip)}</td>"
        f"<td>{_eur(r.tco_vnc_undiscounted_eur)}</td></tr>"
        f"<tr><td>VAN cumulée économie VNC (actualisée)"
        f"{_info('Économie VNC actualisée au WACC : coûts VMC − coûts VNC. Positive ⇒ VNC gagnante.')}"
        f"</td><td>{_eur(r.npv_delta_eur)}</td></tr>"
        f"<tr><td>Break-even{_info('Année du retour sur investissement (économie cumulée actualisée ≥ 0).')}"
        f"</td><td>{be}</td></tr></table>"
    )
    warns = ""
    if r.warnings:
        warns = (
            f"<details class='explain'><summary>{_icon('bulb')} Avertissements méthodologiques"
            "</summary><ul>"
            + "".join(f"<li>{html.escape(w)}</li>" for w in r.warnings)
            + "</ul></details>"
        )
    return (
        "<h2 class='sec'>Bilan financier : VNC vs VMC double-flux</h2>"
        f"{kpis}{_van_chart(r.npv_delta_cumulative_eur, r.break_even_year)}"
        "<p style='color:var(--muted);font-size:.85rem;margin:.4rem 0 1rem'>VAN cumulée de "
        "l'économie VNC (coûts VMC − coûts VNC), actualisée, année par année. Le point vert "
        "marque le seuil de rentabilité ; la fourchette P10–P90 (KPI) vient d'un tirage "
        "Monte-Carlo sur les hypothèses sensibles.</p>"
        f"{hyp_html}{capex}{opex}{synth}{_tornado(result)}{warns}"
    )


# Hypothèses ROI éditables (source unique : sert au formulaire ET à l'application serveur).
# (groupe, attribut ROIParameters, libellé, pas, entier ?)
ROI_OVERRIDE_FIELDS: list[tuple[str, str, str, str, bool]] = [
    ("Finance", "price_elec_eur_kwh", "Prix électricité (€/kWh)", "0.01", False),
    ("Finance", "wacc", "Taux d'actualisation WACC (ex. 0,06)", "0.005", False),
    ("Finance", "inflation", "Inflation OPEX (ex. 0,025)", "0.005", False),
    ("Finance", "horizon_years", "Horizon (ans)", "1", True),
    ("Finance", "contingency_rate", "Provision aléas (ex. 0,10)", "0.01", False),
    ("CAPEX VMC (€/m²)", "vmc_centrales_eur_m2", "Centrales + récupérateurs", "1", False),
    ("CAPEX VMC (€/m²)", "vmc_reseau_gaines_eur_m2", "Réseau de gaines", "1", False),
    ("CAPEX VMC (€/m²)", "vmc_pose_cvc_eur_m2", "Pose CVC", "1", False),
    ("CAPEX VMC (€/m²)", "vmc_regulation_eur_m2", "Régulation", "1", False),
    ("CAPEX VMC (€/m²)", "vmc_etancheite_eur_m2", "Étanchéité", "1", False),
    ("CAPEX VMC (€/m²)", "vmc_etudes_eur_m2", "Études", "1", False),
    ("CAPEX VMC (€/m²)", "vmc_commissioning_eur_m2", "Commissioning", "1", False),
    ("CAPEX VNC", "vnc_price_per_ouvrant_eur", "Prix par ouvrant (€)", "10", False),
    ("CAPEX VNC", "vnc_price_per_capteur_eur", "Prix par capteur (€)", "10", False),
    ("CAPEX VNC", "vnc_price_station_meteo_eur", "Station météo (€)", "50", False),
    ("CAPEX VNC", "vnc_bos_platform_eur", "Plateforme BOS (€)", "100", False),
    ("CAPEX VNC", "vnc_cablage_eur_m2", "Câblage (€/m²)", "1", False),
    ("CAPEX VNC", "vnc_extraction_humide_eur", "Extraction pièces humides (€)", "100", False),
    ("CAPEX VNC", "vnc_std_engineering_eur", "STD + ingénierie (€)", "100", False),
    ("CAPEX VNC", "vnc_commissioning_hypercare_eur", "Commissioning + hypercare (€)", "100", False),
    ("OPEX annuel", "vmc_ach", "VMC : renouvellement d'air (vol/h)", "0.1", False),
    ("OPEX annuel", "vmc_sfp_wh_m3", "VMC : SFP ventilateurs (Wh/m³)", "0.05", False),
    ("OPEX annuel", "vmc_operating_hours_year", "VMC : heures de marche / an", "100", False),
    ("OPEX annuel", "vmc_maintenance_eur_m2_year", "VMC : maintenance (€/m²/an)", "0.1", False),
    ("OPEX annuel", "vnc_actuator_energy_kwh_year", "VNC : énergie actionneurs (kWh/an)", "10", False),
    ("OPEX annuel", "vnc_maintenance_eur_m2_year", "VNC : maintenance (€/m²/an)", "0.1", False),
    ("OPEX annuel", "bos_subscription_eur_per_point_year", "Abonnement BOS (€/pt/an)", "1", False),
    ("OPEX annuel", "wet_extraction_opex_eur_year", "Extraction humide (€/an)", "100", False),
    ("Quantités", "vnc_m2_per_ouvrant", "Surface couverte par ouvrant (m²)", "1", False),
    ("Quantités", "num_ouvrants_override", "Nombre d'ouvrants imposé", "1", True),
]


def _hypotheses_form(result: StudyResult, building: object | None, cfg: Mapping[str, str]) -> str:
    """Hypothèses ROI éditables (recalcul serveur) + données pour les exports.

    Le `<form id="valform">` porte aussi `building_json` + la config : les boutons
    d'action en tête (Enregistrer / Export) le lisent par id même s'il est plus bas.
    Toutes les valeurs des calculs sont modifiables (source `ROI_OVERRIDE_FIELDS`).
    """
    from zephyr.roi import ROIParameters

    p = ROIParameters()
    c = dict(cfg or {})
    bjson = building.model_dump_json() if isinstance(building, Building) else ""
    hidden = "".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(str(v))}">'
        for k, v in c.items()
        if not k.startswith("ovr_") and k != "building_json"
    )

    lines = result.roi.calc_lines if result.roi else []
    calc = json.dumps(
        [
            {"section": ln.section, "label": ln.label, "formula": ln.formula,
             "value": round(ln.value_eur)}
            for ln in lines
        ]
    )
    groups: dict[str, list[str]] = {}
    for group, attr, label, step, _is_int in ROI_OVERRIDE_FIELDS:
        default = c.get("ovr_" + attr, getattr(p, attr, ""))
        if default is None:
            default = ""
        ph = ' placeholder="auto"' if attr == "num_ouvrants_override" else ""
        groups.setdefault(group, []).append(
            f'<div class="field"><div class="lab">{html.escape(label)}</div>'
            f'<input type="number" step="{step}" name="ovr_{attr}" '
            f'value="{html.escape(str(default))}"{ph}></div>'
        )
    sections = "".join(
        f'<h5 class="hyp-grp">{html.escape(g)}</h5><div class="form-grid">{"".join(items)}</div>'
        for g, items in groups.items()
    )
    return (
        '<form id="valform" method="post" action="/etude/resultat">'
        f"{hidden}"
        f'<input type="hidden" name="building_json" id="building_json" value="{html.escape(bjson)}">'
        '<details class="hyp"><summary>Ajuster les hypothèses du calcul (prix, taux, quantités)</summary>'
        '<p class="hint" style="margin:.4rem 0">Chaque nombre utilisé dans le bilan est modifiable. '
        'Recalculez ensuite : tout est régénéré côté serveur. « Enregistrer le projet » (en haut) '
        'sauvegarde aussi vos hypothèses.</p>'
        f"{sections}"
        f'<button type="submit" class="btn no-print" style="margin-top:.8rem">{_icon("refresh")} Recalculer le bilan</button>'
        "</details></form>"
        f'<script type="application/json" id="calc-data">{calc}</script>'
        f"<script>{_RESULTS_JS}</script>"
    )


def _results_actions() -> str:
    """Encadré « Export » (titre + options dessous) ; lit le formulaire par id, plus bas."""
    return (
        '<div class="result-actions">'
        '<div class="ra-lbl">Export</div>'
        '<div class="ra-btns">'
        f'<button type="button" class="btn ghost sm" onclick="exportCsv()">{_icon("sheet")} Excel</button>'
        f'<button type="button" class="btn ghost sm" onclick="exportPdf()">{_icon("file")} PDF</button>'
        f'<button type="button" class="btn ghost sm" onclick="downloadProject()">{_icon("save")} Projet (JSON)</button>'
        "</div></div>"
    )


def render_results(
    result: StudyResult, *, building: object | None = None, cfg: Mapping[str, str] | None = None
) -> str:
    """Page de résultats : score + critères + recos + bilan financier."""
    _vlabel, vcolor = _VERDICT[result.verdict]
    s = result.score
    gauge = _gauge_svg(s.global_score, s.grade) if s else ""

    recos = ""
    if s and s.recommendations:
        recos = "<h2 class='sec'>Pistes d'amélioration</h2>" + "".join(
            f'<div class="reco">{html.escape(r)}</div>' for r in s.recommendations
        )

    # Conclusion : points faibles (drapeaux + critères < 50) et points forts (critères ≥ 75),
    # en phrases courtes (pas de tirets cadratins).
    good_phrases = {
        "ventilation": "Bonne capacité de ventilation naturelle",
        "vitrage": "Taux de vitrage maîtrisé, peu de surchauffe",
        "inertie": "Forte inertie, bon stockage de fraîcheur",
        "isolation": "Enveloppe bien isolée",
    }
    bad_phrases = {
        "ventilation": "Ventilation naturelle limitée (peu de traversant)",
        "vitrage": "Vitrage trop important ou absent",
        "inertie": "Inertie faible, free-cooling moins efficace",
        "isolation": "Enveloppe peu isolée, appoint de chauffage notable",
    }
    bad: list[str] = list(s.flags) if s else []
    good: list[str] = []
    if s:
        for c in sorted(s.criteria, key=lambda c: c.score):
            if c.score < 50:
                bad.append(f"{bad_phrases.get(c.key, c.label)} ({c.score:.0f}/100)")
        for c in sorted(s.criteria, key=lambda c: c.score, reverse=True):
            if c.score >= 75:
                good.append(f"{good_phrases.get(c.key, c.label)} ({c.score:.0f}/100)")
    concl_blocks = ""
    if good:
        concl_blocks += (
            f'<div class="concl-col good"><div class="concl-h">{_icon("check")} Points forts</div>'
            + "".join(f"<div>{html.escape(g)}</div>" for g in good) + "</div>"
        )
    if bad:
        concl_blocks += (
            f'<div class="concl-col bad"><div class="concl-h">{_icon("alert")} Points de vigilance</div>'
            + "".join(f"<div>{html.escape(b)}</div>" for b in bad) + "</div>"
        )
    concl = f'<div class="concl">{concl_blocks}</div>' if concl_blocks else ""

    plan = ""
    rooms = getattr(building, "rooms", []) if building is not None else []
    if building is not None and any(getattr(r, "polygon", None) for r in rooms):
        try:
            from zephyr.viz import render_plan_data_uri

            uri = render_plan_data_uri(building)  # type: ignore[arg-type]
            plan = (
                "<h2 class='sec'>Plan reconstruit</h2>"
                f"<img src='{uri}' alt='plan' style='max-width:100%;border:1px solid #e6ebf1;"
                "border-radius:.5rem'>"
            )
        except Exception:  # pragma: no cover - matplotlib absent
            plan = ""

    quick = result.mode == "rapide"
    # Le titre reflète l'APTITUDE (la note), pas l'éligibilité de site : un bâtiment qui
    # score 80 est un bon candidat même si un drapeau de site (pollution…) impose une réserve,
    # laquelle apparaît alors dans « Points de vigilance ». En rapide : une « tendance ».
    if quick and s:
        tlab, bordc = _tendance(s.global_score)
        title = f"Tendance : {tlab}"
    else:
        title = {
            "A": "Excellent candidat à la VNC",
            "B": "Bon candidat à la VNC",
            "C": "Candidat correct à la VNC",
            "D": "Aptitude à la VNC limitée",
            "E": "Peu adapté à la VNC",
        }.get(s.grade, "Aptitude à la VNC") if s else "Aptitude à la VNC"
        bordc = _GRADE_COLOR.get(s.grade, vcolor) if s else vcolor

    banner = ""
    if quick:
        banner = (
            f'<div class="quick-banner">{_icon("bulb")}<div><b>Estimation rapide.</b> '
            "Résultat indicatif calculé à partir de quelques données saisies (sans plan). "
            "Pour une analyse fine pièce par pièce et un bilan financier détaillé, lancez "
            'une <a href="/etude">étude complète</a> avec les plans.</div></div>'
        )

    actions = "" if quick else _results_actions()
    fin = _financial_quick(result) if quick else _financial_section(
        result, _hypotheses_form(result, building, cfg or {})
    )
    body = f"""
<div class="score-hero">
  {gauge}
  <h1 class="verdict-title" style="border-left:4px solid {bordc};padding-left:.7rem">{html.escape(title)}</h1>
</div>
{banner}
{concl}
{actions}
<h2 class="sec">Détail par critère</h2>
{_criteria_bars(result)}
{_score_legend(result)}
{recos}
{plan}
{fin}
<div class="disclaimer">{_icon("alert")} {html.escape(_DISCLAIMER)}</div>
<p><a class="btn ghost" href="/etude">{_icon("refresh")} Nouvelle étude</a></p>
"""
    return _layout("Zéphyr — résultats", body, cta=False)
