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
:root {
  --ink: #14233a; --muted: #5b6b80; --line: #e6ebf1;
  --teal: #0e9aa7; --teal-d: #0b7a85; --coral: #ff6b6b;
  --bg: #f7f9fb; --card: #ffffff;
  --a: #1a9d5a; --b: #0e9aa7; --c: #d9a400; --d: #e07b39; --e: #c0392b;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  line-height: 1.55;
}
a { color: var(--teal-d); text-decoration: none; }
.wrap { max-width: 980px; margin: 0 auto; padding: 0 1.2rem; }
nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.2rem; max-width: 980px; margin: 0 auto;
}
.brand { font-weight: 800; letter-spacing: -.02em; font-size: 1.25rem; }
.brand span { color: var(--teal); }
.btn {
  display: inline-block; background: var(--teal); color: #fff; font-weight: 600;
  padding: .6rem 1.1rem; border-radius: .5rem; border: 0; cursor: pointer;
}
.btn:hover { background: var(--teal-d); }
.btn.ghost { background: transparent; color: var(--teal-d); border: 1px solid var(--teal); }
.hero { padding: 3rem 0 2rem; }
.hero h1 { font-size: 2.5rem; line-height: 1.1; letter-spacing: -.03em; margin: 0 0 .6rem; }
.hero p.lead { font-size: 1.2rem; color: var(--muted); max-width: 640px; }
.kicker {
  display: inline-block; font-size: .8rem; font-weight: 700; color: var(--teal-d);
  background: #e6f6f7; padding: .25rem .6rem; border-radius: 1rem; margin-bottom: 1rem;
}
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 2.2rem 0; }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: .8rem;
  padding: 1.1rem 1.2rem;
}
.card h3 { margin: .2rem 0 .4rem; font-size: 1.05rem; }
.card .n {
  display: inline-grid; place-items: center; width: 1.7rem; height: 1.7rem;
  background: var(--teal); color: #fff; border-radius: 50%; font-weight: 700; font-size: .9rem;
}
.crit-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: .8rem; margin: 1rem 0; }
.disclaimer {
  background: #fff8e6; border: 1px solid #f0d999; border-radius: .5rem;
  padding: .7rem .9rem; font-size: .9rem; color: #6b5800; margin: 1.5rem 0;
}
footer { color: var(--muted); font-size: .85rem; padding: 2rem 0 3rem; }
/* Résultats */
.result-head { display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap; margin: 1rem 0; }
.gauge { flex: 0 0 auto; }
.badge {
  display: inline-block; padding: .3rem .8rem; border-radius: .4rem; color: #fff;
  font-weight: 700; font-size: .9rem;
}
.bars { margin: 1rem 0; }
.bar-row { display: grid; grid-template-columns: 220px 1fr 48px; gap: .7rem;
  align-items: center; padding: .45rem 0; border-bottom: 1px solid var(--line); }
.bar-row .lab { font-weight: 600; font-size: .92rem; }
.bar-row .lab small { display: block; font-weight: 400; color: var(--muted); font-size: .8rem; }
.track { background: #eef2f6; border-radius: 1rem; height: .7rem; overflow: hidden; }
.fill { height: 100%; border-radius: 1rem; }
.bar-row .val { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }
.reco { background: #f0faf8; border-left: 3px solid var(--teal); padding: .6rem .9rem;
  border-radius: .3rem; margin: .5rem 0; }
.flag { background: #fff4f0; border-left: 3px solid var(--coral); padding: .6rem .9rem;
  border-radius: .3rem; margin: .5rem 0; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: .8rem; margin: 1rem 0; }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: .6rem;
  padding: .8rem .9rem; }
.kpi .k { color: var(--muted); font-size: .82rem; }
.kpi .v { font-size: 1.3rem; font-weight: 700; letter-spacing: -.02em; }
form label { display: block; font-weight: 600; font-size: .9rem; margin: .8rem 0 .2rem; }
form input, form select { width: 100%; padding: .5rem .6rem; border: 1px solid var(--line);
  border-radius: .45rem; font: inherit; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 1rem; }
.check { display: flex; align-items: center; gap: .5rem; margin: .5rem 0; }
.check input { width: auto; }
.winrow { display: flex; gap: .5rem; align-items: center; margin: .3rem 0; flex-wrap: wrap; }
.winrow select, .winrow input { padding: .35rem .4rem; }
.editor { display: grid; grid-template-columns: 1.4fr 1fr; gap: 1rem; align-items: start; }
.editor svg { width: 100%; height: 520px; display: block; background: #fff;
  border: 1px solid var(--line); border-radius: .6rem; }
#panel { background: var(--card); border: 1px solid var(--line); border-radius: .6rem;
  padding: 1rem; position: sticky; top: 1rem; }
#panel label { display: block; font-weight: 600; font-size: .85rem; margin: .6rem 0 .2rem; }
#panel select, #panel input[type=number] { width: 100%; padding: .4rem; border: 1px solid var(--line);
  border-radius: .4rem; font: inherit; }
.chips { display: flex; flex-wrap: wrap; gap: .3rem; }
.chip { display: inline-flex; align-items: center; gap: .2rem; font-size: .82rem; font-weight: 500;
  border: 1px solid var(--line); border-radius: 1rem; padding: .15rem .5rem; cursor: pointer; }
.chip input { width: auto; }
.badge-ok { background: #1a9d5a; color: #fff; font-size: .72rem; padding: .1rem .4rem;
  border-radius: .3rem; }
.levelbar { display: flex; gap: .4rem; margin: .4rem 0; }
.levelbar button { border: 1px solid var(--teal); background: #fff; color: var(--teal-d);
  border-radius: .4rem; padding: .3rem .7rem; cursor: pointer; }
.levelbar button.active { background: var(--teal); color: #fff; }
@media (max-width: 760px) { .editor { grid-template-columns: 1fr; } }
h2.sec { margin: 2rem 0 .4rem; padding-bottom: .3rem; border-bottom: 2px solid var(--line); }
table.kv { border-collapse: collapse; width: 100%; }
table.kv td { border-bottom: 1px solid var(--line); padding: .35rem .2rem; }
table.kv td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) {
  .steps, .crit-grid, .kpis, .form-grid { grid-template-columns: 1fr; }
  .hero h1 { font-size: 2rem; }
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


def _layout(title: str, body: str, *, cta: bool = True) -> str:
    """Gabarit commun (nav + contenu + footer)."""
    nav_cta = '<a class="btn" href="/etude">Lancer une étude</a>' if cta else ""
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>
<nav><div class="brand">Zéphyr<span>.</span></div>{nav_cta}</nav>
<main class="wrap">{body}</main>
<footer class="wrap">Zéphyr — pré-étude de faisabilité VNC. {html.escape(_DISCLAIMER)}</footer>
</body></html>"""


def render_landing() -> str:
    """Landing page : proposition de valeur + comment ça marche + critères."""
    steps = [
        ("1", "Déposez vos plans", "Un export DXF + quelques infos du CPE (parois, isolation)."),
        ("2", "Score d'aptitude VNC", "Traversant, vitrage, inertie, isolation — noté, expliqué."),
        ("3", "Bilan financier", "VNC vs VMC double-flux : CAPEX, VAN, break-even, sensibilité."),
    ]
    steps_html = "".join(
        f'<div class="card"><span class="n">{n}</span><h3>{html.escape(t)}</h3>'
        f"<p>{html.escape(d)}</p></div>"
        for n, t, d in steps
    )
    crits = [
        ("Ventilation", "Traversant idéal ; sinon châssis ≥ 1,5 m (tirage mono-façade)."),
        ("Vitrage", "Ratio surface vitrée / surface au sol dans la bonne bande."),
        ("Inertie", "Masse lue de la composition des parois (free-cooling nocturne)."),
        ("Isolation", "Niveau d'isolation — moins de pertes, meilleur bilan."),
    ]
    crit_html = "".join(
        f'<div class="card"><h3>{html.escape(t)}</h3><p>{html.escape(d)}</p></div>'
        for t, d in crits
    )
    body = f"""
<section class="hero">
  <span class="kicker">Ventilation Naturelle Contrôlée · pré-étude déterministe</span>
  <h1>Pré-qualifiez la VNC<br>en quelques minutes.</h1>
  <p class="lead">Des plans, le CPE, et Zéphyr vous donne un score d'aptitude à la
  ventilation naturelle, des pistes d'amélioration, et le bilan financier face à
  une VMC double-flux. Sans simulation lourde — du calcul déterministe.</p>
  <p style="margin-top:1.4rem">
    <a class="btn" href="/etude">Lancer une étude</a>
    <a class="btn ghost" href="#methode">Comment ça marche</a>
  </p>
</section>
<section id="methode"><h2 class="sec">Comment ça marche</h2>
  <div class="steps">{steps_html}</div></section>
<section><h2 class="sec">Ce qu'on évalue</h2>
  <div class="crit-grid">{crit_html}</div></section>
<div class="disclaimer">⚠️ {html.escape(_DISCLAIMER)}</div>
"""
    return _layout("Zéphyr — pré-étude VNC", body)


def render_study_form() -> str:
    """Page 1 — configuration & plans : tout ce qui ne se lit pas sur les plans."""
    body = """
<h1>Nouvelle étude — configuration</h1>
<p class="lead" style="color:var(--muted)">Déposez les plans (DXF) et renseignez ce
qu'un plan ne porte pas : nature du projet, matériaux/CPE, contexte. On lit la
géométrie du DXF ; vous la validez à l'étape suivante.</p>
<form method="post" action="/etude" enctype="multipart/form-data">
  <h2 class="sec">Plans</h2>
  <label>Plan DXF vectorisé (optionnel — sinon saisie paramétrique)</label>
  <input type="file" name="dxf" accept=".dxf">

  <h2 class="sec">Projet (non lisible des plans)</h2>
  <div class="form-grid">
    <div><label>Nature</label>
      <select name="nature">
        <option value="neuf" selected>Construction neuve</option>
        <option value="renovation">Rénovation</option>
      </select></div>
    <div><label>Type de projet</label>
      <select name="project_type">
        <option value="logement">Logement</option>
        <option value="bureau">Bureau</option>
        <option value="mixte" selected>Mixte</option>
        <option value="scolaire">Scolaire</option>
      </select></div>
    <div><label>Localisation (climat)</label>
      <input type="text" name="location" value="Luxembourg" placeholder="ville, pays"></div>
    <div><label>Angle du Nord (° ; 0 = +y du plan)</label>
      <input type="number" name="north" value="0" step="5"></div>
    <div><label>Inertie (composition des parois — CPE)</label>
      <select name="inertia">
        <option value="lourde" selected>Lourde (béton / maçonnerie)</option>
        <option value="moyenne">Moyenne</option>
        <option value="legere">Légère (ossature)</option>
      </select></div>
    <div><label>Surface ventilée (m²) — si pas de DXF</label>
      <input type="number" name="area" value="1200" step="10"></div>
    <div><label>Niveaux — si pas de DXF</label>
      <input type="number" name="levels" value="2" min="1"></div>
  </div>

  <h2 class="sec">Enveloppe (CPE)</h2>
  <div class="form-grid">
    <div><label>U murs (W/m²K)</label>
      <input type="number" name="u_wall" value="0.20" step="0.01"></div>
    <div><label>Uw vitrage (W/m²K)</label>
      <input type="number" name="u_window" value="0.9" step="0.1"></div>
    <div><label>Ratio vitrage / surface au sol</label>
      <input type="number" name="glazing" value="0.18" step="0.01"></div>
    <div><label>Hauteur des châssis (m)</label>
      <input type="number" name="sash" value="1.6" step="0.1"></div>
    <div><label>Perméabilité à l'air n50 (vol/h)</label>
      <input type="number" name="n50" value="1.5" step="0.1"></div>
  </div>

  <h2 class="sec">Contexte du site</h2>
  <label class="check"><input type="checkbox" name="noise"> Bruit extérieur excessif</label>
  <label class="check"><input type="checkbox" name="pollution"> Pollution / pollen élevés</label>
  <label class="check"><input type="checkbox" name="security"> Risque de sécurité au RdC</label>
  <label class="check"><input type="checkbox" name="occ_incompatible">
    Occupation incompatible (hôpital, process…)</label>

  <p style="margin-top:1.4rem"><button class="btn" type="submit">Continuer →</button></p>
</form>
"""
    return _layout("Zéphyr — nouvelle étude", body, cta=False)


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
    syncHidden();
  };});
  Array.prototype.forEach.call(document.querySelectorAll('#panel [data-del]'), function(b){ b.onclick=function(){ r.openings.splice(parseInt(b.dataset.del),1); panel(); syncHidden(); };});
  document.getElementById('p-add').onclick=function(){
    if(!r.openings){ r.openings=[]; }
    r.openings.push({id:r.id+'_w'+r.openings.length, kind:'window', orientation:(r.exterior_wall_orientations[0]||'S'), area_m2:1.5, sill_height_m:0.9, head_height_m:2.2, openable:true, free_area_ratio:0.5});
    panel(); syncHidden();
  };
}
function syncHidden(){
  var clean = JSON.parse(JSON.stringify(B));
  clean.rooms.forEach(function(r){ r.openings = (r.openings||[]).filter(function(o){ return ORS.indexOf(o.orientation)>=0 && o.area_m2>0; }); });
  document.getElementById('building_json').value = JSON.stringify(clean);
}
document.addEventListener('DOMContentLoaded', function(){ render(); panel(); });
"""


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
    <button class="btn" type="submit">Confirmer &amp; calculer →</button>
  </p>
</form>
<script>window.BUILDING={data};window.LABEL_COLORS={colors};</script>
<script>{_VALIDATION_JS}</script>"""
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
    pen = result.heating_penalty.eur_per_year if result.heating_penalty else 0.0
    kpis = '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="k">{html.escape(k)}</div><div class="v">{v}</div></div>'
        for k, v in [
            ("CAPEX VNC", _eur(r.capex_vnc_eur)),
            ("VAN économie VNC", _eur(r.npv_delta_eur)),
            ("Break-even", be),
            ("Pénalité chauffage", f"{_eur(pen)}/an"),
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
        "l'économie VNC (coûts VMC − coûts VNC), actualisée, année par année.</p>"
        f"{capex}{opex}{synth}{_tornado(result)}{warns}"
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

    body = f"""
<div class="result-head">
  {gauge}
  <div>
    <span class="badge" style="background:{vcolor}">{html.escape(vlabel)}</span>
    <h1 style="margin:.5rem 0 0">Aptitude à la VNC</h1>
    <p style="color:var(--muted);margin:.2rem 0 0">Score déterministe sur 4 critères
    pondérés. Détail et leviers ci-dessous.</p>
  </div>
</div>
{flags}
<h2 class="sec">Détail par critère</h2>
{_criteria_bars(result)}
{_score_legend(result)}
{recos}
{plan}
{_financial_section(result)}
<div class="disclaimer">⚠️ {html.escape(_DISCLAIMER)}</div>
<p><a class="btn ghost" href="/etude">↺ Nouvelle étude</a></p>
"""
    return _layout("Zéphyr — résultats", body, cta=False)
