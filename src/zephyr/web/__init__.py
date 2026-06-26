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

from zephyr.schemas import (
    Building,
    InertiaClass,
    Opening,
    Orientation,
    ROIResult,
    Room,
    RoomLabel,
    StudyResult,
    Verdict,
)

_SILL_M = 0.9  # allège par défaut (m) ; hauteur de châssis = head − sill


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
nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--s4) var(--s5); max-width: 1500px; margin: 0 auto;
}
.brand { font-weight: 700; letter-spacing: -.03em; font-size: 1.3rem; color: var(--ink); }
.brand span { color: var(--primary); }
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
footer { color: var(--muted); font-size: .85rem; padding: var(--s6) 0 var(--s7);
  border-top: 1px solid var(--line); margin-top: var(--s7); }
/* Résultats */
.result-head { display: flex; gap: var(--s5); align-items: center; flex-wrap: wrap; margin: var(--s4) 0; }
.gauge { flex: 0 0 auto; }
.badge { display: inline-block; padding: .3rem .8rem; border-radius: var(--r1); color: #fff;
  font-weight: 700; font-size: .9rem; }
.bars { margin: var(--s4) 0; }
.bar-row { display: grid; grid-template-columns: 220px 1fr 48px; gap: .7rem;
  align-items: center; padding: .45rem 0; border-bottom: 1px solid var(--line); }
.bar-row .lab { font-weight: 600; font-size: .92rem; }
.bar-row .lab small { display: block; font-weight: 400; color: var(--muted); font-size: .8rem; }
.track { background: var(--surface-2); border-radius: var(--pill); height: .7rem; overflow: hidden; }
.fill { height: 100%; border-radius: var(--pill); }
.bar-row .val { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }
.reco { background: var(--primary-soft); border-left: 3px solid var(--primary); padding: .7rem .9rem;
  border-radius: var(--r1); margin: .5rem 0; }
.flag { background: var(--danger-soft); border-left: 3px solid var(--danger); padding: .7rem .9rem;
  border-radius: var(--r1); margin: .5rem 0; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s3); margin: var(--s4) 0; }
.kpi { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r1);
  padding: .9rem; box-shadow: var(--shadow-1); }
.kpi .k { color: var(--muted); font-size: .82rem; }
.kpi .v { font-size: 1.35rem; font-weight: 700; letter-spacing: -.02em; }
/* Formulaires */
form label { display: block; font-weight: 600; font-size: .9rem; margin: .8rem 0 .2rem; }
form input, form select, form textarea { width: 100%; padding: .55rem .65rem;
  border: 1px solid var(--line); border-radius: var(--r1); font: inherit;
  background: var(--surface); color: var(--ink); }
form input::placeholder { color: var(--faint); }
form input:focus, form select:focus { border-color: var(--primary); outline: none;
  box-shadow: 0 0 0 3px var(--ring); }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 var(--s4); }
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
}
/* Page config : cartes, uploaders, toggle segmenté */
.card > h2 { display: flex; align-items: center; gap: .5rem; font-size: 1.15rem; margin: 0 0 .2rem; }
.card .sub { color: var(--muted); font-size: .9rem; margin: 0 0 var(--s4); }
.field { margin: .8rem 0; }
.field > .lab { font-weight: 600; font-size: .92rem; margin-bottom: .35rem; }
.field .hint { color: var(--muted); font-size: .82rem; margin: .35rem 0 0; }
.hint { color: var(--muted); font-size: .82rem; }
.uploader { border: 1.5px dashed var(--line); border-radius: var(--r1); padding: 1rem 1.1rem;
  background: var(--surface-2); }
.uploader + .uploader { margin-top: .8rem; }
input[type=file] { width: 100%; font: inherit; color: var(--muted); border: 0; padding: 0; background: none; }
input[type=file]::file-selector-button {
  background: var(--primary-soft); color: var(--primary-strong); border: 1px solid var(--primary);
  border-radius: var(--r1); padding: .45rem .9rem; font-weight: 600; cursor: pointer; margin-right: .8rem;
}
input[type=file]::file-selector-button:hover { background: var(--primary); color: var(--on-primary); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: var(--r1); overflow: hidden; }
.seg label { padding: .5rem 1rem; cursor: pointer; font-weight: 600; color: var(--muted); user-select: none; }
.seg label + label { border-left: 1px solid var(--line); }
.seg label.on { background: var(--primary); color: var(--on-primary); }
.seg input { position: absolute; opacity: 0; pointer-events: none; }
/* Éditeur de tracé (Konva) : grand plan collant à gauche, palette + liste à droite */
.trace-layout { display: grid; grid-template-columns: 1fr 360px; gap: var(--s4); align-items: start; }
.trace-canvas-wrap { position: sticky; top: .6rem; }
#stage { width: 100%; height: 84vh; background: #fff; border: 1px solid var(--line);
  border-radius: var(--r2); overflow: hidden; touch-action: none; box-shadow: var(--shadow-1); }
.trace-side { position: sticky; top: .6rem; max-height: calc(100vh - 1.2rem);
  overflow-y: auto; display: flex; flex-direction: column; gap: .8rem; padding-right: .25rem; }
.palette { display: flex; flex-direction: column; gap: .6rem;
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
.palette #hint { color: var(--warn); font-weight: 600; font-size: .85rem; min-height: 1rem; }
.room-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r1);
  padding: .6rem .7rem; margin: .45rem 0; }
.room-card.sel { outline: 2px solid var(--primary); }
.room-head { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
.room-head select { padding: .2rem; }
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
.iconbtn { border: 1px solid var(--line); background: var(--surface); color: var(--muted); cursor: pointer;
  border-radius: .35rem; padding: .1rem .4rem; font-size: .8rem; }
.iconbtn:hover { color: var(--danger); border-color: var(--danger); }
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
.lead-xl { font-size: 1.2rem; color: var(--muted); max-width: 52ch; line-height: 1.5; }
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
.spec { border-top: 1px solid var(--line); margin-top: var(--s2); }
.spec-row { display: grid; grid-template-columns: 1fr auto; gap: .4rem 1.5rem;
  padding: 1rem 0; border-bottom: 1px solid var(--line); align-items: baseline; }
.spec-row .t { font-weight: 600; font-size: 1.05rem; }
.spec-row .w { font-variant-numeric: tabular-nums; color: var(--primary); font-weight: 700; text-align: right; }
.spec-row .d { grid-column: 1 / -1; color: var(--muted); font-size: .92rem; margin-top: -.1rem; }
/* Résultats — score en grand */
.score-hero { display: grid; grid-template-columns: auto 1fr; gap: var(--s5); align-items: center;
  padding: var(--s4) 0 var(--s6); border-bottom: 1px solid var(--line); margin-bottom: var(--s5); }
.score-hero .big { display: flex; align-items: baseline; gap: .3rem; }
.score-hero .big .n { font-size: clamp(3.5rem, 11vw, 6.5rem); font-weight: 700; line-height: .85;
  letter-spacing: -.05em; }
.score-hero .big .slash { font-size: 1.4rem; color: var(--faint); }
.score-hero h1 { font-size: clamp(1.5rem, 3.4vw, 2.2rem); margin: .3rem 0 .4rem; letter-spacing: -.03em; }
@media (max-width: 720px) {
  .process { grid-template-columns: 1fr; }
  .proc + .proc { border-left: 0; padding-left: 0; }
  .score-hero { grid-template-columns: 1fr; }
}
/* ROI à livre ouvert : table des formules */
table.calc { border-collapse: collapse; width: 100%; font-size: .85rem; margin: .2rem 0 .8rem; }
table.calc th { text-align: left; color: var(--muted); font-size: .72rem; text-transform: uppercase;
  letter-spacing: .04em; border-bottom: 1px solid var(--line); padding: .3rem .3rem; }
table.calc td { border-bottom: 1px solid var(--line); padding: .35rem .3rem; vertical-align: top; }
table.calc td:last-child { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; font-weight: 600; }
table.calc td.formula { color: var(--muted); font-family: 'Helvetica Neue', Arial, sans-serif; }
/* Page styleguide */
.sg-swatch { display: inline-block; width: 64px; height: 64px; border-radius: var(--r1);
  border: 1px solid var(--line); vertical-align: middle; margin-right: .5rem; }
.sg-row { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; margin: .5rem 0; }
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
    "function toggleTheme(){var r=document.documentElement,"
    "n=r.getAttribute('data-theme')==='dark'?'light':'dark';"
    "r.setAttribute('data-theme',n);try{localStorage.setItem('zephyr-theme',n);}catch(e){}"
    "var b=document.getElementById('themebtn');if(b){b.textContent=n==='dark'?'☀️':'🌙';}}"
    "document.addEventListener('DOMContentLoaded',function(){var b=document.getElementById('themebtn');"
    "if(b){b.textContent=document.documentElement.getAttribute('data-theme')==='dark'?'☀️':'🌙';}});"
)


def _layout(title: str, body: str, *, cta: bool = True, wide: bool = False) -> str:
    """Gabarit commun (nav + contenu + footer). `wide` élargit le conteneur (tracé)."""
    nav_cta = '<a class="btn" href="/etude">Lancer une étude</a>' if cta else ""
    wrap_cls = "wrap wide" if wide else "wrap"
    toggle = (
        '<button type="button" class="theme-toggle" id="themebtn" onclick="toggleTheme()" '
        'title="Thème clair / sombre" aria-label="Basculer le thème">🌙</button>'
    )
    return f"""<!DOCTYPE html><html lang="fr" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script>{_THEME_INIT}</script>
<style>{_CSS}</style></head><body>
<nav><div class="brand">Zéphyr<span>.</span></div>
<div class="nav-right">{toggle}{nav_cta}</div></nav>
<main class="{wrap_cls}">{body}</main>
<footer class="wrap">Zéphyr — pré-étude de faisabilité VNC. {html.escape(_DISCLAIMER)}</footer>
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
    """Landing page : proposition de valeur + comment ça marche + critères."""
    steps = [
        ("01", "Déposez le plan & le CPE", "DXF ou PDF vectoriel ; le passeport "
         "énergétique pré-remplit l'enveloppe (U, n50, inertie)."),
        ("02", "Tracez, on mesure", "Pièces, châssis, façades sur le plan en fond. "
         "Le code calcule surfaces et traversant — pas de vision, pas d'à-peu-près."),
        ("03", "Score + bilan", "Aptitude VNC notée et expliquée, puis le bilan "
         "financier face à une VMC double-flux."),
    ]
    steps_html = "".join(
        f'<div class="proc"><div class="num">{n}</div><h3>{html.escape(t)}</h3>'
        f"<p>{html.escape(d)}</p></div>"
        for n, t, d in steps
    )
    crits = [
        ("Ventilation", "35", "Traversant idéal ; sinon châssis ≥ 1,5 m (tirage mono-façade)."),
        ("Inertie", "25", "Masse lue de la composition des parois — free-cooling nocturne."),
        ("Vitrage", "20", "Ratio surface vitrée / surface au sol, dans la bonne bande."),
        ("Isolation", "20", "Niveau d'isolation : moins de pertes, meilleur bilan."),
    ]
    crit_html = "".join(
        f'<div class="spec-row"><div class="t">{html.escape(t)}</div>'
        f'<div class="w">{w}</div><div class="d">{html.escape(d)}</div></div>'
        for t, w, d in crits
    )
    body = f"""
<section class="hero-xl">
  <div class="eyebrow"><span class="dot"></span> Pré-étude déterministe · Ventilation Naturelle Contrôlée</div>
  <h1 class="display">La VNC, <em>pré-qualifiée</em> en quelques minutes.</h1>
  <p class="lead-xl">Un plan, le CPE, et Zéphyr rend un score d'aptitude à la
  ventilation naturelle, des leviers d'amélioration, et le bilan financier face à
  une VMC double-flux. Du calcul déterministe — aucune simulation boîte noire.</p>
  <div class="cta-row">
    <a class="btn" href="/etude">Lancer une étude</a>
    <a class="btn ghost" href="#methode">Comment ça marche</a>
  </div>
</section>
<hr class="rule">
<section id="methode">
  <div class="sec-head"><span class="idx">→</span><h2>Comment ça marche</h2></div>
  <div class="process">{steps_html}</div>
</section>
<section>
  <div class="sec-head"><span class="idx">→</span><h2>Ce qu'on évalue</h2></div>
  <p class="lead-xl" style="margin-bottom:var(--s2)">Quatre critères pondérés (poids
  sur 100), notés en déterministe avec barème et recommandation.</p>
  <div class="spec">{crit_html}</div>
</section>
<div class="disclaimer">⚠️ {html.escape(_DISCLAIMER)}</div>
"""
    return _layout("Zéphyr — pré-étude VNC", body)


def render_error(message: str) -> str:
    """Page d'erreur simple (ex. PDF scanné refusé, fichier illisible)."""
    body = (
        '<h1>Fichier non exploitable</h1>'
        f'<div class="disclaimer">⚠️ {html.escape(message)}</div>'
        '<p><a class="btn" href="/etude">← Revenir à la configuration</a></p>'
    )
    return _layout("Zéphyr — erreur", body, cta=False)


# Bascule CPE / saisie manuelle (choix exclusif) — vanilla, validé par node --check.
_CONFIG_JS = """
(function(){
  function sync(){
    var r=document.querySelector('input[name=cpe_mode]:checked'), m=r?r.value:'cpe';
    Array.prototype.forEach.call(document.querySelectorAll('.seg label'), function(l){
      l.classList.toggle('on', l.querySelector('input').value===m);
    });
    var up=document.getElementById('cpe-upload'), env=document.getElementById('envelope-block'),
        hint=document.getElementById('cpe-hint'), ex=window.__CPE_EXTRACTED__;
    if(up){ up.style.display = (m==='cpe')?'':'none'; }
    if(hint){ hint.style.display = (m==='cpe' && !ex)?'':'none'; }
    if(env){ env.style.display = (m==='manual' || (m==='cpe' && ex))?'':'none'; }
  }
  document.addEventListener('DOMContentLoaded', function(){
    Array.prototype.forEach.call(document.querySelectorAll('input[name=cpe_mode]'), function(r){
      r.addEventListener('change', sync);
    });
    sync();
  });
})();
"""


def render_study_form(
    prefill: Mapping[str, str] | None = None, *, cpe_banner: str = ""
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
    extracted = bool(p)
    body = f"""
<h1>Nouvelle étude</h1>
<p class="lead" style="color:var(--muted);max-width:680px">Importez un plan à
tracer, renseignez l'enveloppe (depuis un CPE ou à la main) et le projet. On
calcule ensuite le score d'aptitude VNC et le bilan financier.</p>

<!-- Formulaire principal (vide) : les champs des cartes y sont rattachés via form="mainform". -->
<form id="mainform" method="post" action="/etude" enctype="multipart/form-data"></form>

<div class="card" style="margin:1.2rem 0">
  <h2>📐 Plan &amp; tracé</h2>
  <p class="sub">Le plan sert de fond pour tracer les pièces et les châssis à
  l'étape suivante. Format vectoriel uniquement (un PDF scanné n'est pas lu).</p>
  <div class="uploader">
    <div class="field" style="margin:0">
      <div class="lab">Plan unique — DXF ou PDF A0 (tous les niveaux sur une planche)</div>
      <input type="file" name="dxf" accept=".dxf,.pdf" form="mainform">
    </div>
  </div>
  <div class="uploader">
    <div class="field" style="margin:0">
      <div class="lab">…ou un PDF par étage</div>
      <input type="file" name="floor_pdfs" accept=".pdf" multiple form="mainform">
      <p class="hint">Ordre d'import = niveau (1<sup>er</sup> = RdC). Prioritaire sur
      le plan unique ; vous basculez de niveau dans l'éditeur.</p>
    </div>
  </div>
  <p class="hint">Sans plan, l'étude reste possible en paramétrique (surface plus bas).</p>
</div>

<div class="card" style="margin:1.2rem 0">
  <h2>🏢 Enveloppe</h2>
  <p class="sub">D'où viennent les valeurs (U, n50, inertie…) ?</p>
  <div class="seg" role="tablist">
    <label class="on"><input type="radio" name="cpe_mode" value="cpe" checked> 📄 J'ai un CPE</label>
    <label><input type="radio" name="cpe_mode" value="manual"> ✍️ Saisie manuelle</label>
  </div>

  <div id="cpe-upload" class="uploader" style="margin-top:1rem">
    <div class="field" style="margin:0">
      <div class="lab">Passeport énergétique (PDF vectoriel)</div>
      <form method="post" action="/etude/cpe" enctype="multipart/form-data"
        style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
        <input type="file" name="cpe" accept=".pdf">
        <button class="btn" type="submit">Extraire</button>
      </form>
      <p class="hint">Les valeurs sont vérifiées dans le texte source puis posées
      ci-dessous — vous validez ou corrigez chacune.</p>
    </div>
  </div>
  <p id="cpe-hint" class="hint" style="margin-top:.8rem">Téléchargez votre CPE pour
  pré-remplir l'enveloppe, ou passez en « Saisie manuelle ».</p>
  {cpe_banner}

  <div id="envelope-block" style="margin-top:1rem">
    <div class="form-grid">
      <div class="field"><div class="lab">U murs (W/m²K)</div>
        <input type="number" name="u_wall" value="{v("u_wall", "0.20")}" step="0.01" form="mainform"></div>
      <div class="field"><div class="lab">Uw vitrage (W/m²K)</div>
        <input type="number" name="u_window" value="{v("u_window", "0.9")}" step="0.1" form="mainform"></div>
      <div class="field"><div class="lab">Ratio vitrage / surface au sol</div>
        <input type="number" name="glazing" value="{v("glazing", "0.18")}" step="0.01" form="mainform"></div>
      <div class="field"><div class="lab">Hauteur des châssis par défaut (m)</div>
        <input type="number" name="sash" value="{v("sash", "1.5")}" step="0.1" form="mainform"></div>
      <div class="field"><div class="lab">Perméabilité n50 (vol/h)</div>
        <input type="number" name="n50" value="{v("n50", "1.5")}" step="0.1" form="mainform"></div>
      <div class="field"><div class="lab">Inertie (parois)</div>{inertia_sel}</div>
    </div>
  </div>
</div>

<div class="card" style="margin:1.2rem 0">
  <h2>🏗️ Projet</h2>
  <div class="form-grid">
    <div class="field"><div class="lab">Nature</div>{nature_sel}</div>
    <div class="field"><div class="lab">Type de projet</div>{ptype_sel}</div>
    <div class="field"><div class="lab">Type de chauffage</div>{chauffage_sel}</div>
    <div class="field"><div class="lab">Eau chaude sanitaire (ECS)</div>{ecs_sel}</div>
    <div class="field"><div class="lab">Matériau des châssis</div>{chassis_sel}</div>
    <div class="field"><div class="lab">Localisation (climat)</div>
      <input type="text" name="location" value="{v("location", "Luxembourg")}" form="mainform"></div>
    <div class="field"><div class="lab">Angle du Nord (°, 0 = haut du plan)</div>
      <input type="number" name="north" value="{v("north", "0")}" step="5" form="mainform"></div>
    <div class="field"><div class="lab">Surface (m²) — facultatif, recoupée au tracé</div>
      <input type="number" name="area" value="{v("area", "1200")}" step="10" form="mainform"></div>
    <div class="field"><div class="lab">Niveaux — si pas de plan</div>
      <input type="number" name="levels" value="{v("levels", "2")}" min="1" form="mainform"></div>
  </div>
</div>

<div class="card" style="margin:1.2rem 0">
  <h2>📍 Contexte du site</h2>
  <label class="check"><input type="checkbox" name="noise" form="mainform"> Bruit extérieur excessif</label>
  <label class="check"><input type="checkbox" name="pollution" form="mainform"> Pollution / pollen élevés</label>
  <label class="check"><input type="checkbox" name="security" form="mainform"> Risque de sécurité au RdC</label>
  <label class="check"><input type="checkbox" name="occ_incompatible" form="mainform">
    Occupation incompatible (hôpital, process…)</label>
</div>

<p style="margin:1.4rem 0"><button class="btn" type="submit" form="mainform">Continuer →</button></p>

<div class="card" style="margin:1.2rem 0;background:#f7faf9">
  <h2>↩️ Reprendre une étude</h2>
  <p class="sub">Vous avez déjà téléchargé une étude (fichier .json) ? Rechargez-la
  pour repartir de votre géométrie et de votre config.</p>
  <div class="uploader">
    <form method="post" action="/etude/reprendre" enctype="multipart/form-data"
      style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
      <input type="file" name="study" accept=".json,application/json">
      <button class="btn ghost" type="submit">Reprendre</button>
    </form>
  </div>
</div>

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
            f'<small style="color:var(--muted)"> — « {html.escape(str(src)[:80])} »</small>'
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
        '<div class="reco"><b>CPE extrait</b> — valeurs posées dans le formulaire '
        "(vérifiées dans le texte source ; à valider) :"
        f'<ul style="margin:.4rem 0">{"".join(rows)}</ul>{notes_html}</div>'
    )


def _orient_select(name: str, selected: str, *, empty: bool = False) -> str:
    opts = ['<option value="">—</option>'] if empty else []
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
  <label style="margin-top:.6rem">Châssis (façade · m² · hauteur châssis m · ouvrable)</label>
  {"".join(win_rows)}
</div>"""


def _rooms_table(building: object) -> str:
    rooms = getattr(building, "rooms", [])
    rows = []
    for r in rooms:
        orients = ", ".join(o.value for o in r.exterior_wall_orientations) or "—"
        wins = ", ".join(o.orientation.value for o in r.openings) or "—"
        label = getattr(r.label, "value", str(r.label))
        through = "✅ oui" if r.is_through else "— non"
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
    '<button type="button" id="p-add" class="btn ghost" style="margin-top:.5rem">+ châssis</button>';
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
var T=window.TRACE, floors=T.floors, fi=0, multi=floors.length>1;
var ORS=["N","NE","E","SE","S","SW","W","NW"];
var ORDIR={N:[0,1],NE:[0.7,0.7],E:[1,0],SE:[0.7,-0.7],S:[0,-1],SW:[-0.7,-0.7],W:[-1,0],NW:[-0.7,0.7]};
var LABELS=["sejour","chambre","cuisine","sdb","wc","circulation","bureau","technique","autre"];
var COLORS={sejour:"#cfe8cf",chambre:"#cfe0f5",cuisine:"#f5e6cf",sdb:"#cfeef0",wc:"#e6cff5",circulation:"#eeeeee",bureau:"#f5cfd6",technique:"#dddddd",autre:"#f0f0f0"};
var inertiaEl=document.querySelector('input[name=inertia]');
var B={id:"pdf", name:null, rooms:[], inertia_class:(inertiaEl?inertiaEl.value:"lourde"), num_levels:1, total_height_m:null, location:null, epw_path:null};
var sel=-1, mode="idle", draft=[], calib=[], winDrag=null, rectDrag=null, lastSash=1.5;
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
function floorbar(){
  var bar=document.getElementById("floorbar"); if(!bar){ return; }
  if(!multi){ bar.innerHTML=""; return; }
  bar.innerHTML=floors.map(function(f,k){ return '<button type="button" class="'+(k===fi?"active":"")+'" data-fi="'+k+'">Niveau '+f.level+"</button>"; }).join("");
  Array.prototype.forEach.call(bar.querySelectorAll("button"),function(b){ b.onclick=function(){ fi=parseInt(b.dataset.fi); sel=-1; applyFloor(); render(); }; });
}
function ptr(){ return stage.getRelativePointerPosition(); }

function polyPxPoints(r){ var a=[]; r.polygon.forEach(function(m){ var p=toPx(m[0],m[1]); a.push(p[0],p[1]); }); return a; }

function render(){
  if(!stage){ return; }
  shapeLayer.destroyChildren();
  floorbar();
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
      shapeLayer.add(grp);
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
    var t1=new Konva.Text({x:cx,y:cy,text:r.label,fontSize:pm(0.5),fontFamily:"Helvetica Neue, Arial, sans-serif",fontStyle:"600",fill:"#111",listening:false});
    t1.offsetX(t1.width()/2); t1.offsetY(t1.height()/2+pm(0.32)); shapeLayer.add(t1);
    var t2=new Konva.Text({x:cx,y:cy,text:fmt(r.area_m2)+" m² · N"+r.level,fontSize:pm(0.34),fontFamily:"Helvetica Neue, Arial, sans-serif",fill:"#444",listening:false});
    t2.offsetX(t2.width()/2); t2.offsetY(t2.height()/2-pm(0.32)); shapeLayer.add(t2);
    var minx=Math.min.apply(null,xs),maxx=Math.max.apply(null,xs),miny=Math.min.apply(null,ys),maxy=Math.max.apply(null,ys);
    var dcx=(minx+maxx)/2,dcy=(miny+maxy)/2,rw=maxx-minx,rh=maxy-miny;
    (r.exterior_wall_orientations||[]).forEach(function(o){ var d=ORDIR[o]; if(!d){ return; }
      var mx=dcx+d[0]*0.4*rw, my=dcy-d[1]*0.4*rh;
      var tt=new Konva.Text({x:mx,y:my,text:o,fontSize:pm(0.42),fontStyle:"700",fontFamily:"Helvetica Neue, Arial, sans-serif",fill:"#0e9aa7",listening:false});
      tt.offsetX(tt.width()/2); tt.offsetY(tt.height()/2); shapeLayer.add(tt);
    });
    (r.openings||[]).forEach(function(op,k){
      var seg=op._seg; if(!seg){ return; }
      var ln=new Konva.Line({points:[seg[0][0],seg[0][1],seg[1][0],seg[1][1]], stroke:(op.openable?"#1a73e8":"#9aa3ad"), strokeWidth:pm(0.09), lineCap:"round"});
      ln.on("click tap",function(e){ if(mode==="idle"){ e.cancelBubble=true; B.rooms[i].openings.splice(k,1); render(); } });
      shapeLayer.add(ln);
    });
  });
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
  var si=document.getElementById("scaleinfo"); if(si){ si.textContent="Echelle ~ "+(MPP()*1000).toFixed(1)+" mm/px"; }
  roomlist(); syncHidden();
}

var HINTS={draw:"Cliquez les coins de la piece, puis Terminer.",rect:"Glissez pour tracer un rectangle (pièce).",calibrate:"Cliquez deux points d'une cote connue.",window:"Glissez le long de la facade de la piece selectionnee (longueur = largeur)."};
var MODEBTN={draw:"t-draw", rect:"t-rect", window:"t-win", calibrate:"t-cal"};
function setMode(m){ mode=m; draft=[]; calib=[]; winDrag=null; rectDrag=null;
  if(stage){ stage.draggable(m==="idle"); stage.container().style.cursor=(m==="idle"?"grab":"crosshair"); }
  Object.keys(MODEBTN).forEach(function(k){ var b=document.getElementById(MODEBTN[k]); if(b){ b.classList.toggle("active", k===m); } });
  var hi=document.getElementById("hint"); if(hi){ hi.textContent=m==="idle"?"":((HINTS[m]||"")+" — Échap pour quitter."); }
  render();
}
function curLevel(){ if(multi){ return F().level; } var e=document.getElementById("t-level"); return e?(parseInt(e.value)||0):0; }
function addRoom(poly){
  B.rooms.push({id:"r"+B.rooms.length, name:null, label:"autre", level:curLevel(), polygon:poly,
    area_m2:Math.max(area(poly),0.01), height_m:2.6, openings:[], exterior_wall_orientations:[], is_occupied:true, is_wet_room:false});
  sel=B.rooms.length-1;
}
function finishRoom(){
  if(mode!=="draw" || draft.length<3){ setMode("idle"); return; }
  addRoom(draft.map(function(p){ return toM(p[0],p[1]); })); setMode("idle");
}
function finishRect(){
  if(!rectDrag){ return; }
  var a=rectDrag.a, b=rectDrag.b;
  if(Math.abs(a[0]-b[0])<4 || Math.abs(a[1]-b[1])<4){ rectDrag=null; render(); return; }
  var corners=[[a[0],a[1]],[b[0],a[1]],[b[0],b[1]],[a[0],b[1]]].map(function(p){ return toM(p[0],p[1]); });
  rectDrag=null; addRoom(corners); render();   // on reste en mode rect (tracer plusieurs pièces)
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
    openable:true, free_area_ratio:0.5, _w:w, _h:h, _seg:[a,b]};
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
  pop.style.left=Math.min(x,window.innerWidth-180)+"px"; pop.style.top=(y+8)+"px";
  pop.innerHTML='<div style="font-size:.8rem;font-weight:600;margin-bottom:.2rem">Hauteur du chassis (m)</div>'+
    '<input type="number" step="0.1" value="'+fmt(op._h)+'" style="width:90px;padding:.3rem"> '+
    '<button type="button" class="btn" style="padding:.3rem .6rem">OK</button>';
  document.body.appendChild(pop);
  var inp=pop.querySelector("input"), ok=pop.querySelector("button");
  function commit(){ var v=parseFloat(inp.value); if(v>0){ op._h=v; lastSash=v; winRecalc(op); } if(pop.parentNode){ pop.parentNode.removeChild(pop); } render(); }
  ok.onclick=commit;
  inp.onkeydown=function(e){ if(e.key==="Enter"){ commit(); } else if(e.key==="Escape"){ if(pop.parentNode){ pop.parentNode.removeChild(pop); } } };
  inp.focus(); inp.select();
}
function roomlist(){
  var d=document.getElementById("roomlist"); if(!d){ return; }
  if(!B.rooms.length){ d.innerHTML='<p style="color:var(--muted);font-size:.9rem">Aucune piece tracee. Choisis "Rectangle" ou "Tracer une piece".</p>'; return; }
  d.innerHTML='<div class="ptitle" style="margin:.2rem 0 .4rem">Pieces ('+B.rooms.length+')</div>'+B.rooms.map(function(r,i){
    var lab=LABELS.map(function(l){ return '<option value="'+l+'"'+(l===r.label?" selected":"")+">"+l+"</option>"; }).join("");
    var chips=ORS.map(function(o){ return '<label class="chip"><input type="checkbox" data-i="'+i+'" data-or="'+o+'"'+(r.exterior_wall_orientations.indexOf(o)>=0?" checked":"")+">"+o+"</label>"; }).join("");
    var wins=(r.openings||[]).map(function(op,j){
      var fopts=ORS.map(function(o){ return '<option value="'+o+'"'+(o===op.orientation?" selected":"")+">"+o+"</option>"; }).join("");
      return '<tr><td><select data-wi="'+i+'" data-wj="'+j+'" data-wf="facade">'+fopts+'</select></td>'+
        '<td><input data-wi="'+i+'" data-wj="'+j+'" data-wf="w" type="number" step="0.1" value="'+fmt(op._w!=null?op._w:0)+'" style="width:54px;padding:.15rem"></td>'+
        '<td><input data-wi="'+i+'" data-wj="'+j+'" data-wf="h" type="number" step="0.1" value="'+fmt(op._h!=null?op._h:0)+'" style="width:54px;padding:.15rem"></td>'+
        '<td style="color:var(--muted)">'+fmt(op.area_m2)+'</td>'+
        '<td><button type="button" data-wdel="'+i+"_"+j+'" class="iconbtn">✕</button></td></tr>';
    }).join("");
    var wintable=wins?('<table class="wintab"><tr><th>facade</th><th>l</th><th>h</th><th>m²</th><th></th></tr>'+wins+"</table>"):'<div style="font-size:.8rem;color:var(--faint)">aucun chassis</div>';
    return '<div class="room-card'+(i===sel?" sel":"")+'" data-sel="'+i+'">'+
      '<div class="room-head">'+
        '<span class="room-no">'+(i+1)+'</span>'+
        '<select data-lab="'+i+'">'+lab+'</select>'+
        '<b>'+fmt(r.area_m2)+' m²</b>'+
        (through(r)?'<span class="badge-ok">traversant</span>':'')+
        '<span class="grow"></span>'+
        '<label class="nivlbl">niv.<input data-lvl="'+i+'" type="number" value="'+r.level+'" style="width:42px;padding:.15rem"></label>'+
        '<button type="button" data-del="'+i+'" class="iconbtn" title="supprimer">✕</button>'+
      '</div>'+
      '<div class="room-sec"><span class="room-seclbl">Facades</span><div class="chips">'+chips+'</div></div>'+
      '<div class="room-sec"><span class="room-seclbl">Chassis</span>'+wintable+
        '<button type="button" data-pick="'+i+'" class="btn ghost mini">+ chassis</button></div>'+
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
    var v=parseFloat(el.value); if(!(v>0)){ return; }
    if(el.dataset.wf==="w"){ setWinWidth(op,v); } else { op._h=v; lastSash=v; winRecalc(op); }
    render();
  }; });
  Array.prototype.forEach.call(d.querySelectorAll("[data-wdel]"),function(b){ b.onclick=function(){ var p=b.dataset.wdel.split("_"); B.rooms[parseInt(p[0])].openings.splice(parseInt(p[1]),1); render(); }; });
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
  if(rectDrag){ finishRect(); }
}
function onClick(e){
  if(mode==="draw"){ var p=ptr(); draft.push(snapPx([p.x,p.y])); render(); }
  else if(mode==="calibrate"){ var q=ptr(); calib.push([q.x,q.y]);
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
  document.getElementById("t-finish").onclick=finishRoom;
  document.getElementById("t-cal").onclick=function(){ setMode(mode==="calibrate"?"idle":"calibrate"); };
  document.getElementById("t-win").onclick=function(){
    if(sel<0){ var hi=document.getElementById("hint"); if(hi){ hi.textContent="Selectionne une piece (sur le plan ou via + chassis), puis trace sur sa facade."; } return; }
    setMode(mode==="window"?"idle":"window");
  };
  document.getElementById("t-zin").onclick=function(){ zoomBy(1.25); };
  document.getElementById("t-zout").onclick=function(){ zoomBy(0.8); };
  document.getElementById("t-zreset").onclick=function(){ fitStage(); render(); };
  document.getElementById("t-mark").oninput=function(){ render(); };
  document.addEventListener("keydown",function(e){ if(e.key==="Escape" && mode!=="idle"){ setMode("idle"); } });
  if(multi){ var lw=document.getElementById("t-levelwrap"); if(lw){ lw.style.display="none"; } }
  var se=document.querySelector('input[name=sash]'); if(se){ var sv=parseFloat(se.value); if(sv>0){ lastSash=sv; } }
  window.addEventListener("resize",function(){ fitStage(); render(); });
  applyFloor(); render();
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


def render_tracing(floors: list[dict[str, object]], hidden_fields: str) -> str:
    """Éditeur de **tracé** : plan(s) en fond, l'ingénieur trace les pièces au clic.

    `floors` = liste de niveaux ``{level, image_uri, w, h, mpp}`` (un seul élément
    pour un plan/planche A0 unique ; plusieurs pour un PDF par étage). La mesure
    vient des clics calibrés (échelle par niveau), pas d'une lecture du raster.
    Produit un `building_json` (polygones en mètres) → mêmes résultats.
    """
    data = json.dumps({"floors": floors})
    multi = len(floors) > 1
    level_help = (
        "Plusieurs niveaux : bascule de plan avec les boutons « Niveau » ; "
        "les pièces tracées prennent le niveau affiché."
        if multi
        else "Plusieurs plans sur la planche (RdC, étage…) ? Règle le <b>niveau</b> "
        "avant de tracer ; chaque pièce garde le sien."
    )
    body = f"""
<h1 style="margin-bottom:.2rem">Tracer le plan</h1>
<p class="sub" style="max-width:820px"><b>Rectangle</b> : glisse en diagonale pour
créer une pièce. <b>Point par point</b> : clique les coins puis « Terminer ».
Sélectionne une pièce pour <b>déplacer</b> son corps ou <b>tirer ses coins</b> ;
trace ses châssis sur la façade (glisser = largeur, une bulle demande la hauteur).
Le <b>magnétisme</b> accroche aux coins voisins. Molette / pincer = zoom, glisser =
déplacer le plan, <b>Échap</b> quitte l'outil. {level_help}</p>
<div class="levelbar" id="floorbar"></div>
<div class="trace-layout">
  <div class="trace-canvas-wrap">
    <div style="position:relative">
      <div id="stage"></div>
      {_COMPASS_SVG}
    </div>
  </div>
  <aside class="trace-side">
    <div class="palette">
      <div class="pgroup">
        <div class="ptitle">Pièces</div>
        <button type="button" class="btn ghost" id="t-rect">▭ Tracer un rectangle</button>
        <button type="button" class="btn ghost" id="t-draw">✏️ Tracer (point par point)</button>
        <button type="button" class="btn ghost" id="t-finish">✓ Terminer la pièce</button>
        <label class="chk"><input type="checkbox" id="t-snap" checked> 🧲 Magnétisme</label>
        <label class="lbl" id="t-levelwrap">Niveau des nouvelles pièces
          <input type="number" id="t-level" value="0" style="width:100%;padding:.3rem;margin-top:.2rem"></label>
      </div>
      <div class="pgroup">
        <div class="ptitle">Châssis</div>
        <button type="button" class="btn ghost" id="t-win">🪟 Tracer un châssis</button>
        <span class="lbl" style="font-weight:400">Sélectionne une pièce, puis glisse sur sa façade.</span>
      </div>
      <div class="pgroup">
        <div class="ptitle">Échelle &amp; vue</div>
        <button type="button" class="btn ghost" id="t-cal">📏 Calibrer l'échelle</button>
        <div class="row">
          <button type="button" class="btn ghost" id="t-zout" title="Dézoomer">−</button>
          <button type="button" class="btn ghost" id="t-zin" title="Zoomer">+</button>
          <button type="button" class="btn ghost" id="t-zreset" title="Vue entière">⤢</button>
        </div>
        <label class="lbl" title="Grosseur des repères de tracé">Taille des repères
          <input type="range" id="t-mark" min="0.5" max="4" step="0.5" value="1" style="width:100%"></label>
        <span id="scaleinfo" style="color:var(--muted);font-size:.8rem"></span>
      </div>
      <span id="hint"></span>
    </div>
    <div id="roomlist"></div>
  </aside>
</div>
<form id="valform" method="post" action="/etude/resultat" onsubmit="syncHidden()">
  {hidden_fields}
  <input type="hidden" name="building_json" id="building_json">
  <p style="margin-top:1.2rem">
    <a class="btn ghost" href="/etude">← Config</a>
    <button type="button" class="btn ghost" onclick="downloadStudy()">💾 Télécharger l'étude</button>
    <button class="btn" type="submit">Confirmer &amp; calculer →</button>
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
    <a class="btn ghost" href="/etude">← Config</a>
    <button type="button" class="btn ghost" onclick="downloadStudy()">💾 Télécharger l'étude</button>
    <button class="btn" type="submit">Confirmer &amp; calculer →</button>
  </p>
</form>
<script>window.BUILDING={data};window.LABEL_COLORS={colors};</script>
<script>{_VALIDATION_JS}</script>
<script>{_STUDY_IO_JS}</script>"""
    else:
        edit_blocks = "".join(_room_edit_block(i, r) for i, r in enumerate(rooms))
        core = f"""
<p class="lead" style="color:var(--muted)">Pièces lues ({len(rooms)}, {total:.0f} m²)
sans polygones — saisissez/validez façades et châssis pièce par pièce (§2.8).</p>
{chips}{warn_html}
<form method="post" action="/etude/resultat">
  {hidden_fields}
  <input type="hidden" name="n_rooms" value="{len(rooms)}">
  {edit_blocks}
  <p style="margin-top:1.4rem">
    <a class="btn ghost" href="/etude">← Config</a>
    <button class="btn" type="submit">Confirmer &amp; calculer →</button>
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
  <text x="70" y="66" text-anchor="middle" font-size="30" font-weight="800"
    fill="#14233a">{score:.0f}</text>
  <text x="70" y="90" text-anchor="middle" font-size="13" fill="#5b6b80">/ 100 · {grade}</text>
</svg>"""


def _criteria_bars(result: StudyResult) -> str:
    if result.score is None:
        return ""
    rows = []
    for c in result.score.criteria:
        color = (
            "#1a9d5a" if c.score >= 75 else "#d9a400" if c.score >= 50 else "#e07b39"
        )
        rows.append(
            f'<div class="bar-row" title="{html.escape(c.scale or "")}">'
            f'<div class="lab">{html.escape(c.label)}<small>{html.escape(c.detail)}</small></div>'
            f'<div class="track"><div class="fill" style="width:{c.score:.0f}%;'
            f'background:{color}"></div></div>'
            f'<div class="val">{c.score:.0f}</div></div>'
        )
    return '<div class="bars">' + "".join(rows) + "</div>"


def _van_svg(cumulative: list[float]) -> str:
    """Mini-graphe SVG de la VAN cumulée (économie VNC) année par année."""
    if not cumulative:
        return ""
    w, h, pad = 640, 180, 28
    n = len(cumulative)
    lo, hi = min(cumulative), max(cumulative)
    span = (hi - lo) or 1.0

    def x(i: int) -> float:
        return pad + (w - 2 * pad) * i / max(n - 1, 1)

    def y(v: float) -> float:
        return pad + (h - 2 * pad) * (1 - (v - lo) / span)

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(cumulative))
    zero = y(0.0) if lo < 0 < hi else None
    zero_line = (
        f'<line x1="{pad}" y1="{zero:.1f}" x2="{w - pad}" y2="{zero:.1f}" '
        'stroke="#cbd5e1" stroke-dasharray="4 4"/>'
        if zero is not None
        else ""
    )
    return f"""<svg width="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="none"
  style="background:#fff;border:1px solid var(--line);border-radius:.6rem">
  {zero_line}
  <polyline fill="none" stroke="#0e9aa7" stroke-width="2.5" points="{pts}"/>
</svg>"""


_GRADE_LEGEND = "A ≥ 80 · B ≥ 65 · C ≥ 50 · D ≥ 35 · E < 35"

_CAPEX_VMC_LABELS = {
    "centrales_recuperateurs": "Centrales + récupérateurs",
    "reseau_gaines": "Réseau de gaines",
    "pose_cvc": "Pose CVC",
    "regulation": "Régulation",
    "etancheite": "Étanchéité",
    "etudes": "Études",
    "commissioning": "Commissioning",
}
_CAPEX_VNC_LABELS = {
    "ouvrants_motorises": "Ouvrants motorisés",
    "capteurs_4en1": "Capteurs 4-en-1",
    "station_meteo": "Station météo",
    "plateforme_bos": "Plateforme BOS",
    "cablage": "Câblage",
    "extraction_humide": "Extraction pièces humides",
    "std_ingenierie": "STD + ingénierie",
    "commissioning_hypercare": "Commissioning + hypercare",
}
_OPEX_VMC_LABELS = {
    "energie_ventilateurs": "Énergie ventilateurs",
    "maintenance_filtres": "Maintenance (filtres)",
    "extraction_humide": "Extraction pièces humides",
}
_OPEX_VNC_LABELS = {
    "energie_actionneurs": "Énergie actionneurs",
    "maintenance_ouvrants_capteurs": "Maintenance ouvrants/capteurs",
    "abonnement_bos": "Abonnement BOS",
    "extraction_humide": "Extraction pièces humides",
    "penalite_chauffage": "Pénalité de chauffage (vs récup VMC)",
}


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def _cost_table(title: str, breakdown: dict[str, float], labels: dict[str, str]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(labels.get(k, k))}</td><td>{_eur(v)}</td></tr>"
        for k, v in breakdown.items()
    )
    total = sum(breakdown.values())
    return (
        f"<h4 style='margin:.6rem 0 .2rem'>{html.escape(title)}</h4>"
        f"<table class='kv'>{rows}"
        f"<tr><td><b>Total</b></td><td><b>{_eur(total)}</b></td></tr></table>"
    )


def _score_legend(result: StudyResult) -> str:
    if result.score is None:
        return ""
    items = "".join(
        f"<tr><td>{html.escape(c.label)}</td>"
        f"<td style='text-align:left'>{html.escape(c.scale or '—')}</td></tr>"
        for c in result.score.criteria
    )
    return (
        "<details style='margin:.6rem 0'><summary style='cursor:pointer;font-weight:600'>"
        "Comment le score est calculé (échelle)</summary>"
        f"<p style='color:var(--muted);font-size:.88rem'>Note globale = moyenne pondérée des "
        f"critères. Lettres : {_GRADE_LEGEND}.</p>"
        f"<table class='kv'>{items}</table></details>"
    )


def _tornado(result: StudyResult) -> str:
    if result.roi is None or not result.roi.sensitivity:
        return ""
    entries = sorted(result.roi.sensitivity, key=lambda e: e.swing, reverse=True)
    top = entries[0].swing or 1.0
    rows = []
    for e in entries:
        w = 100.0 * e.swing / top
        rows.append(
            '<div class="bar-row">'
            f'<div class="lab">{html.escape(e.parameter)}</div>'
            f'<div class="track"><div class="fill" style="width:{w:.0f}%;'
            'background:#0e9aa7"></div></div>'
            f'<div class="val">{_eur(e.swing)}</div></div>'
        )
    return (
        "<h2 class='sec'>Sensibilité (tornado)</h2>"
        "<p style='color:var(--muted);font-size:.88rem'>Effet de chaque paramètre sur la VAN — "
        "jamais un point unique (CLAUDE.md §6).</p>"
        '<div class="bars">' + "".join(rows) + "</div>"
    )


def _financial_section(result: StudyResult) -> str:
    """Bilan financier détaillé (façon comparatif Excel VNC vs VMC)."""
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
        f'<div class="kpi"><div class="k">{html.escape(k)}</div><div class="v">{v}</div>{sub}</div>'
        for k, v, sub in [
            ("CAPEX VNC", _eur(r.capex_vnc_eur), ""),
            ("VAN économie VNC", _eur(r.npv_delta_eur), van_sub),
            ("Break-even", be, be_sub),
            ("VNC favorable", proba or "—", proba_sub),
        ]
    ) + "</div>"

    capex = (
        "<h3>CAPEX (investissement, aléas inclus)</h3>"
        '<div class="crit-grid">'
        f"<div>{_cost_table('VMC double-flux', r.capex_vmc_breakdown, _CAPEX_VMC_LABELS)}</div>"
        f"<div>{_cost_table('VNC', r.capex_vnc_breakdown, _CAPEX_VNC_LABELS)}</div>"
        "</div>"
    )
    opex = (
        "<h3>OPEX annuel (an 1, avant inflation)</h3>"
        '<div class="crit-grid">'
        f"<div>{_cost_table('VMC double-flux', r.opex_vmc_breakdown, _OPEX_VMC_LABELS)}</div>"
        f"<div>{_cost_table('VNC', r.opex_vnc_breakdown, _OPEX_VNC_LABELS)}</div>"
        "</div>"
    )
    synth = (
        "<h3>Synthèse sur "
        f"{r.horizon_years} ans</h3><table class='kv'>"
        f"<tr><td>TCO non actualisé VMC</td><td>{_eur(r.tco_vmc_undiscounted_eur)}</td></tr>"
        f"<tr><td>TCO non actualisé VNC</td><td>{_eur(r.tco_vnc_undiscounted_eur)}</td></tr>"
        f"<tr><td>VAN cumulée économie VNC (actualisée)</td><td>{_eur(r.npv_delta_eur)}</td></tr>"
        f"<tr><td>Break-even</td><td>{be}</td></tr></table>"
    )
    warns = ""
    if r.warnings:
        warns = (
            "<details style='margin:.6rem 0'><summary style='cursor:pointer;font-weight:600'>"
            "Avertissements méthodologiques</summary><ul>"
            + "".join(f"<li>{html.escape(w)}</li>" for w in r.warnings)
            + "</ul></details>"
        )
    return (
        "<h2 class='sec'>Bilan financier — VNC vs VMC double-flux</h2>"
        f"{kpis}{_van_svg(r.npv_delta_cumulative_eur)}"
        "<p style='color:var(--muted);font-size:.85rem;margin:.4rem 0 1rem'>VAN cumulée de "
        "l'économie VNC (coûts VMC − coûts VNC), actualisée, année par année. La fourchette "
        "P10–P90 vient d'un tirage Monte-Carlo sur les hypothèses sensibles.</p>"
        f"{capex}{opex}{synth}{_calc_detail(r)}{_tornado(result)}{warns}"
    )


def _calc_detail(r: ROIResult) -> str:
    """ROI « à livre ouvert » : chaque poste avec sa formule (valeurs substituées) et son montant."""
    if not r.calc_lines:
        return ""
    sections = [
        ("capex_vmc", "CAPEX VMC double-flux"), ("capex_vnc", "CAPEX VNC"),
        ("opex_vmc", "OPEX VMC — an 1"), ("opex_vnc", "OPEX VNC — an 1"),
    ]
    blocks = []
    for key, title in sections:
        rows = "".join(
            f"<tr><td>{html.escape(line.label)}</td>"
            f"<td class='formula'>{html.escape(line.formula)}</td>"
            f"<td>{_eur(line.value_eur)}</td></tr>"
            for line in r.calc_lines
            if line.section == key
        )
        if rows:
            blocks.append(
                f"<h4 style='margin:.8rem 0 .2rem'>{title}</h4>"
                "<table class='calc'><tr><th>poste</th><th>formule</th><th>montant</th></tr>"
                f"{rows}</table>"
            )
    return (
        "<details style='margin:.8rem 0'><summary style='cursor:pointer;font-weight:600'>"
        "Calcul détaillé (à livre ouvert) — chaque poste, sa formule, son montant</summary>"
        "<p style='color:var(--muted);font-size:.85rem;margin:.4rem 0'>Montants aléas inclus "
        "(+10 %). OPEX an 1 avant inflation ; les flux sont ensuite inflatés et actualisés.</p>"
        + "".join(blocks) + "</details>"
    )


def render_results(result: StudyResult, *, building: object | None = None) -> str:
    """Page de résultats : score + critères + recos + bilan financier."""
    vlabel, vcolor = _VERDICT[result.verdict]
    s = result.score
    gauge = _gauge_svg(s.global_score, s.grade) if s else ""

    recos = ""
    if s and s.recommendations:
        recos = "<h2 class='sec'>Pistes d'amélioration</h2>" + "".join(
            f'<div class="reco">{html.escape(r)}</div>' for r in s.recommendations
        )
    flags = ""
    if s and s.flags:
        flags = "".join(f'<div class="flag">{html.escape(f)}</div>' for f in s.flags)

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

    big = ""
    if s is not None:
        big = (
            '<div class="big"><span class="n">'
            f'{s.global_score:.0f}</span><span class="slash">/ 100</span>'
            f'<span class="slash" style="margin-left:.5rem;font-weight:700;color:var(--ink)">'
            f'{html.escape(s.grade)}</span></div>'
        )
    body = f"""
<div class="score-hero">
  {gauge}
  <div>
    <div class="eyebrow"><span class="dot"></span> Aptitude VNC</div>
    {big}
    <h1>Aptitude à la VNC</h1>
    <span class="badge" style="background:{vcolor}">{html.escape(vlabel)}</span>
    <p class="hint" style="margin-top:.6rem;max-width:52ch">Score déterministe sur 4
    critères pondérés (ventilation, inertie, vitrage, isolation). Détail, leviers et
    bilan financier ci-dessous.</p>
  </div>
</div>
{flags}
<div class="sec-head"><span class="idx">01</span><h2>Détail par critère</h2></div>
{_criteria_bars(result)}
{_score_legend(result)}
{recos}
{plan}
{_financial_section(result)}
<div class="disclaimer">⚠️ {html.escape(_DISCLAIMER)}</div>
<p><a class="btn ghost" href="/etude">↺ Nouvelle étude</a></p>
"""
    return _layout("Zéphyr — résultats", body, cta=False)
