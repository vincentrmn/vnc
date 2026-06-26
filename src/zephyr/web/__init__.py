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
  font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  line-height: 1.55;
}
a { color: var(--teal-d); text-decoration: none; }
.wrap { max-width: 980px; margin: 0 auto; padding: 0 1.2rem; }
.wrap.wide { max-width: 1500px; }
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
.tracebar { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; margin: .6rem 0; }
.tracebar .btn { padding: .4rem .8rem; }
#plan image { image-rendering: auto; }
@media (max-width: 760px) { .editor { grid-template-columns: 1fr; } }
h2.sec { margin: 2rem 0 .4rem; padding-bottom: .3rem; border-bottom: 2px solid var(--line); }
table.kv { border-collapse: collapse; width: 100%; }
table.kv td { border-bottom: 1px solid var(--line); padding: .35rem .2rem; }
table.kv td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) {
  .steps, .crit-grid, .kpis, .form-grid { grid-template-columns: 1fr; }
  .hero h1 { font-size: 2rem; }
}
/* Page config : cartes, uploaders, toggle segmenté */
.card > h2 { display: flex; align-items: center; gap: .5rem; font-size: 1.15rem; margin: 0 0 .2rem; }
.card .sub { color: var(--muted); font-size: .9rem; margin: 0 0 1rem; }
.field { margin: .8rem 0; }
.field > .lab { font-weight: 600; font-size: .92rem; margin-bottom: .35rem; }
.field .hint { color: var(--muted); font-size: .82rem; margin: .35rem 0 0; }
.uploader {
  border: 1.5px dashed #cdd9e3; border-radius: .6rem; padding: 1rem 1.1rem; background: #fbfdfe;
}
.uploader + .uploader { margin-top: .8rem; }
input[type=file] {
  width: 100%; font: inherit; color: var(--muted); border: 0; padding: 0; background: none;
}
input[type=file]::file-selector-button {
  background: #eef6f7; color: var(--teal-d); border: 1px solid var(--teal);
  border-radius: .45rem; padding: .45rem .9rem; font-weight: 600; cursor: pointer;
  margin-right: .8rem;
}
input[type=file]::file-selector-button:hover { background: var(--teal); color: #fff; }
.seg { display: inline-flex; border: 1px solid var(--teal); border-radius: .55rem; overflow: hidden; }
.seg label { padding: .5rem 1rem; cursor: pointer; font-weight: 600; color: var(--teal-d);
  user-select: none; }
.seg label + label { border-left: 1px solid var(--teal); }
.seg label.on { background: var(--teal); color: #fff; }
.seg input { position: absolute; opacity: 0; pointer-events: none; }
/* Éditeur de tracé : grand plan (Konva) collant à gauche, palette + liste à droite */
.trace-layout { display: grid; grid-template-columns: 1fr 360px; gap: 1rem; align-items: start; }
.trace-canvas-wrap { position: sticky; top: .6rem; }
#stage { width: 100%; height: 84vh; background: #fff; border: 1px solid var(--line);
  border-radius: .6rem; overflow: hidden; touch-action: none; }
.trace-side { position: sticky; top: .6rem; max-height: calc(100vh - 1.2rem);
  overflow-y: auto; display: flex; flex-direction: column; gap: .8rem; padding-right: .25rem; }
.palette { display: flex; flex-direction: column; gap: .6rem;
  background: var(--card); border: 1px solid var(--line); border-radius: .7rem; padding: .9rem; }
.pgroup { display: flex; flex-direction: column; gap: .4rem; padding-bottom: .6rem;
  border-bottom: 1px solid var(--line); }
.pgroup:last-of-type { border-bottom: 0; padding-bottom: 0; }
.ptitle { font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
  color: var(--muted); font-weight: 700; }
.palette .btn { width: 100%; text-align: center; padding: .5rem .7rem; }
.palette .btn.active { background: var(--teal); color: #fff; border-color: var(--teal);
  box-shadow: inset 0 0 0 2px rgba(255,255,255,.35); }
.palette .row { display: flex; gap: .35rem; }
.palette .row .btn { flex: 1; }
.palette .lbl { font-size: .82rem; font-weight: 600; color: var(--muted); }
.palette #hint { color: #e8590c; font-weight: 600; font-size: .85rem; min-height: 1rem; }
/* Carte pièce dans la liste */
.room-card { background: var(--card); border: 1px solid var(--line); border-radius: .6rem;
  padding: .6rem .7rem; margin: .45rem 0; }
.room-card.sel { outline: 2px solid var(--teal); }
.room-head { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
.room-head select { padding: .2rem; }
.room-no { display: inline-grid; place-items: center; width: 1.5rem; height: 1.5rem;
  background: var(--teal); color: #fff; border-radius: 50%; font-size: .8rem; font-weight: 700; }
.room-head .grow { flex: 1; }
.nivlbl { font-size: .78rem; color: var(--muted); }
.room-sec { margin-top: .5rem; }
.room-seclbl { display: block; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
  color: var(--muted); font-weight: 700; margin-bottom: .25rem; }
.wintab { width: 100%; border-collapse: collapse; font-size: .8rem; }
.wintab th { text-align: left; font-weight: 600; color: var(--muted); font-size: .72rem; padding: .1rem .2rem; }
.wintab td { padding: .12rem .2rem; }
.iconbtn { border: 1px solid var(--line); background: #fff; color: var(--muted); cursor: pointer;
  border-radius: .35rem; padding: .1rem .4rem; font-size: .8rem; }
.iconbtn:hover { color: var(--coral); border-color: var(--coral); }
.btn.mini { padding: .25rem .6rem; font-size: .82rem; margin-top: .4rem; }
@media (max-width: 980px) {
  .trace-layout { grid-template-columns: 1fr; }
  .trace-canvas-wrap, .trace-side { position: static; max-height: none; }
  #stage { height: 62vh; }
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


def _layout(title: str, body: str, *, cta: bool = True, wide: bool = False) -> str:
    """Gabarit commun (nav + contenu + footer). `wide` élargit le conteneur (tracé)."""
    nav_cta = '<a class="btn" href="/etude">Lancer une étude</a>' if cta else ""
    wrap_cls = "wrap wide" if wide else "wrap"
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Inter:wght@400;500;600;700;800&display=swap">'
    )
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>{fonts}<style>{_CSS}</style></head><body>
<nav><div class="brand">Zéphyr<span>.</span></div>{nav_cta}</nav>
<main class="{wrap_cls}">{body}</main>
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
var sel=-1, mode="idle", draft=[], calib=[], winDrag=null, lastSash=1.5;
var stage, bgLayer, shapeLayer, bg=null;
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
function sc(p){ return p/stage.scaleX(); }   // px ecran -> unites contenu (taille constante)
function pm(m){ return m/MPP(); }            // metres -> px-image (taille physique)
function markF(){ var e=document.getElementById("t-mark"); return e?(parseFloat(e.value)||1):1; }

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

function render(){
  if(!stage){ return; }
  shapeLayer.destroyChildren();
  floorbar();
  B.rooms.forEach(function(r,i){
    if(multi && r.level!==F().level){ return; }
    if(!r.polygon || r.polygon.length<2){ return; }
    var pts=[], xs=[], ys=[];
    r.polygon.forEach(function(m){ var p=toPx(m[0],m[1]); pts.push(p[0],p[1]); xs.push(p[0]); ys.push(p[1]); });
    var poly=new Konva.Line({points:pts, closed:true, fill:(COLORS[r.label]||"#eee"), opacity:0.45,
      stroke:(i===sel?"#08313a":(through(r)?"#0e9aa7":"#555")), strokeWidth:(i===sel?2.4:1.4), strokeScaleEnabled:false});
    poly.on("click tap",function(e){ if(mode==="idle"){ e.cancelBubble=true; sel=i; render(); } });
    poly.on("mouseenter",function(){ if(mode==="idle"){ stage.container().style.cursor="pointer"; } });
    poly.on("mouseleave",function(){ stage.container().style.cursor=(mode==="idle"?"grab":"crosshair"); });
    shapeLayer.add(poly);
    var cx=xs.reduce(function(a,b){return a+b;},0)/xs.length, cy=ys.reduce(function(a,b){return a+b;},0)/ys.length;
    var t1=new Konva.Text({x:cx,y:cy,text:r.label,fontSize:pm(0.5),fontFamily:"Inter, sans-serif",fontStyle:"600",fill:"#111",listening:false});
    t1.offsetX(t1.width()/2); t1.offsetY(t1.height()/2+pm(0.32)); shapeLayer.add(t1);
    var t2=new Konva.Text({x:cx,y:cy,text:fmt(r.area_m2)+" m² · N"+r.level,fontSize:pm(0.34),fontFamily:"Inter, sans-serif",fill:"#444",listening:false});
    t2.offsetX(t2.width()/2); t2.offsetY(t2.height()/2-pm(0.32)); shapeLayer.add(t2);
    var minx=Math.min.apply(null,xs),maxx=Math.max.apply(null,xs),miny=Math.min.apply(null,ys),maxy=Math.max.apply(null,ys);
    var dcx=(minx+maxx)/2,dcy=(miny+maxy)/2,rw=maxx-minx,rh=maxy-miny;
    (r.exterior_wall_orientations||[]).forEach(function(o){ var d=ORDIR[o]; if(!d){ return; }
      var mx=dcx+d[0]*0.4*rw, my=dcy-d[1]*0.4*rh;
      var tt=new Konva.Text({x:mx,y:my,text:o,fontSize:pm(0.42),fontStyle:"700",fontFamily:"Inter, sans-serif",fill:"#0e9aa7",listening:false});
      tt.offsetX(tt.width()/2); tt.offsetY(tt.height()/2); shapeLayer.add(tt);
    });
    (r.openings||[]).forEach(function(op,k){
      var seg=op._seg; if(!seg){ return; }
      var ln=new Konva.Line({points:[seg[0][0],seg[0][1],seg[1][0],seg[1][1]], stroke:(op.openable?"#1a73e8":"#9aa3ad"), strokeWidth:pm(0.09), lineCap:"round"});
      ln.on("click tap",function(e){ if(mode==="idle"){ e.cancelBubble=true; B.rooms[i].openings.splice(k,1); render(); } });
      shapeLayer.add(ln);
    });
    if(i===sel){
      r.polygon.forEach(function(m,vi){ var p=toPx(m[0],m[1]);
        var h=new Konva.Circle({x:p[0],y:p[1],radius:sc(5),fill:"#fff",stroke:"#08313a",strokeWidth:sc(1.5),draggable:true});
        h.on("dragmove",function(){
          r.polygon[vi]=toM(h.x(),h.y());
          var np=[]; r.polygon.forEach(function(mm){ var q=toPx(mm[0],mm[1]); np.push(q[0],q[1]); });
          poly.points(np); r.area_m2=Math.max(area(r.polygon),0.01); shapeLayer.batchDraw();
        });
        h.on("dragend",function(){ render(); });
        h.on("mouseenter",function(){ stage.container().style.cursor="move"; });
        shapeLayer.add(h);
      });
    }
  });
  if(draft.length){
    var dp=[]; draft.forEach(function(p){ dp.push(p[0],p[1]); });
    shapeLayer.add(new Konva.Line({points:dp, stroke:"#e8590c", strokeWidth:sc(2*markF()), dash:[sc(6*markF()),sc(4*markF())], listening:false}));
    draft.forEach(function(p){ shapeLayer.add(new Konva.Circle({x:p[0],y:p[1],radius:sc(4*markF()),fill:"#e8590c",listening:false})); });
  }
  if(winDrag){ shapeLayer.add(new Konva.Line({points:[winDrag.a[0],winDrag.a[1],winDrag.b[0],winDrag.b[1]], stroke:"#1a73e8", strokeWidth:pm(0.12), dash:[sc(6),sc(4)], lineCap:"round", listening:false})); }
  if(calib.length===1){ shapeLayer.add(new Konva.Circle({x:calib[0][0],y:calib[0][1],radius:sc(5),fill:"#c0392b",listening:false})); }
  shapeLayer.batchDraw();
  var si=document.getElementById("scaleinfo"); if(si){ si.textContent="Echelle ~ "+(MPP()*1000).toFixed(1)+" mm/px"; }
  roomlist(); syncHidden();
}

var HINTS={draw:"Cliquez les coins de la piece, puis Terminer.",calibrate:"Cliquez deux points d'une cote connue.",window:"Glissez le long de la facade de la piece selectionnee (longueur = largeur)."};
var MODEBTN={draw:"t-draw", window:"t-win", calibrate:"t-cal"};
function setMode(m){ mode=m; draft=[]; calib=[]; winDrag=null;
  if(stage){ stage.draggable(m==="idle"); stage.container().style.cursor=(m==="idle"?"grab":"crosshair"); }
  Object.keys(MODEBTN).forEach(function(k){ var b=document.getElementById(MODEBTN[k]); if(b){ b.classList.toggle("active", k===m); } });
  var hi=document.getElementById("hint"); if(hi){ hi.textContent=m==="idle"?"":((HINTS[m]||"")+" — Échap pour quitter."); }
  render();
}
function curLevel(){ if(multi){ return F().level; } var e=document.getElementById("t-level"); return e?(parseInt(e.value)||0):0; }
function finishRoom(){
  if(mode!=="draw" || draft.length<3){ setMode("idle"); return; }
  var poly=draft.map(function(p){ return toM(p[0],p[1]); });
  B.rooms.push({id:"r"+B.rooms.length, name:null, label:"autre", level:curLevel(), polygon:poly,
    area_m2:Math.max(area(poly),0.01), height_m:2.6, openings:[], exterior_wall_orientations:[], is_occupied:true, is_wet_room:false});
  sel=B.rooms.length-1; setMode("idle");
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
  if(!B.rooms.length){ d.innerHTML='<p style="color:#888;font-size:.9rem">Aucune piece tracee. Clique "Tracer une piece".</p>'; return; }
  d.innerHTML='<div class="ptitle" style="margin:.2rem 0 .4rem">Pieces ('+B.rooms.length+')</div>'+B.rooms.map(function(r,i){
    var lab=LABELS.map(function(l){ return '<option value="'+l+'"'+(l===r.label?" selected":"")+">"+l+"</option>"; }).join("");
    var chips=ORS.map(function(o){ return '<label class="chip"><input type="checkbox" data-i="'+i+'" data-or="'+o+'"'+(r.exterior_wall_orientations.indexOf(o)>=0?" checked":"")+">"+o+"</label>"; }).join("");
    var wins=(r.openings||[]).map(function(op,j){
      var fopts=ORS.map(function(o){ return '<option value="'+o+'"'+(o===op.orientation?" selected":"")+">"+o+"</option>"; }).join("");
      return '<tr><td><select data-wi="'+i+'" data-wj="'+j+'" data-wf="facade">'+fopts+'</select></td>'+
        '<td><input data-wi="'+i+'" data-wj="'+j+'" data-wf="w" type="number" step="0.1" value="'+fmt(op._w!=null?op._w:0)+'" style="width:54px;padding:.15rem"></td>'+
        '<td><input data-wi="'+i+'" data-wj="'+j+'" data-wf="h" type="number" step="0.1" value="'+fmt(op._h!=null?op._h:0)+'" style="width:54px;padding:.15rem"></td>'+
        '<td style="color:#888">'+fmt(op.area_m2)+'</td>'+
        '<td><button type="button" data-wdel="'+i+"_"+j+'" class="iconbtn">✕</button></td></tr>';
    }).join("");
    var wintable=wins?('<table class="wintab"><tr><th>facade</th><th>l</th><th>h</th><th>m²</th><th></th></tr>'+wins+"</table>"):'<div style="font-size:.8rem;color:#aaa">aucun chassis</div>';
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
function onDown(e){ if(mode==="window" && sel>=0){ var p=ptr(); winDrag={a:[p.x,p.y],b:[p.x,p.y]}; } }
function onMove(e){ if(winDrag){ var p=ptr(); winDrag.b=[p.x,p.y]; render(); } }
function onUp(e){
  if(winDrag){ var ref=addWindow(winDrag.a,winDrag.b); winDrag=null; render();
    if(ref){ var ev=e.evt, cx=ev.clientX!=null?ev.clientX:(ev.changedTouches?ev.changedTouches[0].clientX:200), cy=ev.clientY!=null?ev.clientY:(ev.changedTouches?ev.changedTouches[0].clientY:200); showHeightPopup(ref,cx,cy); }
  }
}
function onClick(e){
  if(mode==="draw"){ var p=ptr(); draft.push([p.x,p.y]); render(); }
  else if(mode==="calibrate"){ var q=ptr(); calib.push([q.x,q.y]);
    if(calib.length===2){ var dpx=Math.hypot(calib[0][0]-calib[1][0],calib[0][1]-calib[1][1]); var real=parseFloat(prompt("Longueur reelle de ce segment, en metres ?","5")); if(real>0 && dpx>0){ F().mpp=real/dpx; } setMode("idle"); }
    else { render(); }
  }
}
function initStage(){
  stage=new Konva.Stage({container:"stage", width:10, height:10, draggable:true});
  bgLayer=new Konva.Layer({listening:false}); shapeLayer=new Konva.Layer();
  stage.add(bgLayer); stage.add(shapeLayer);
  stage.on("wheel",onWheel);
  stage.on("mousedown touchstart",onDown);
  stage.on("mousemove touchmove",onMove);
  stage.on("mouseup touchend",onUp);
  stage.on("click tap",onClick);
  stage.container().style.cursor="grab";
}
document.addEventListener("DOMContentLoaded",function(){
  if(!window.Konva){ var s=document.getElementById("stage"); if(s){ s.innerHTML='<p style="padding:1rem;color:#c0392b">Konva non charge (verifie le reseau).</p>'; } return; }
  initStage();
  document.getElementById("t-draw").onclick=function(){ setMode(mode==="draw"?"idle":"draw"); };
  document.getElementById("t-finish").onclick=finishRoom;
  document.getElementById("t-cal").onclick=function(){ setMode(mode==="calibrate"?"idle":"calibrate"); };
  document.addEventListener("keydown",function(e){ if(e.key==="Escape" && mode!=="idle"){ setMode("idle"); } });
  document.getElementById("t-win").onclick=function(){
    if(sel<0){ var hi=document.getElementById("hint"); if(hi){ hi.textContent="Selectionne une piece (sur le plan ou via + chassis), puis trace sur sa facade."; } return; }
    setMode(mode==="window"?"idle":"window");
  };
  document.getElementById("t-zin").onclick=function(){ zoomBy(1.25); };
  document.getElementById("t-zout").onclick=function(){ zoomBy(0.8); };
  document.getElementById("t-zreset").onclick=function(){ fitStage(); render(); };
  document.getElementById("t-mark").oninput=function(){ render(); };
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
<p class="sub" style="max-width:760px">Trace chaque pièce (clique ses coins puis
« Terminer »), nomme-la et coche ses façades — la surface est calculée via
l'échelle. Sélectionne une pièce puis trace ses châssis sur la façade (le glisser
donne la largeur, une bulle demande la hauteur). Molette = zoom, glisser = déplacer.
{level_help}</p>
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
        <button type="button" class="btn ghost" id="t-draw">✏️ Tracer une pièce</button>
        <button type="button" class="btn ghost" id="t-finish">✓ Terminer la pièce</button>
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
