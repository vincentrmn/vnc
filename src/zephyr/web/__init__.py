"""Module `web` — pages HTML du produit (landing, formulaire, résultats).

Pages rendues en **fonctions pures** (chaînes HTML), comme le module `report` :
testables sans serveur, servies par FastAPI (`app/web.py`). Aucune dépendance de
templating — HTML/CSS auto-portés (les rendus sont des fichiers autonomes).

Design : teal = déterministe (notre signature), corail = accents. Sobre, lisible,
orienté décision. Toujours le disclaimer « pré-étude, non opposable ».
"""

from __future__ import annotations

import html

from zephyr.schemas import StudyResult, Verdict

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
    """Formulaire d'étude (saisie paramétrique + dépôt DXF optionnel)."""
    body = """
<h1>Nouvelle étude</h1>
<p class="lead" style="color:var(--muted)">Renseignez le bâtiment (ou déposez un
plan DXF), l'enveloppe (CPE) et le contexte. Tout est modifiable ensuite.</p>
<form method="post" action="/etude" enctype="multipart/form-data">
  <h2 class="sec">Plans & bâtiment</h2>
  <label>Plan DXF (optionnel)</label>
  <input type="file" name="dxf" accept=".dxf">
  <div class="form-grid">
    <div><label>Type de projet</label>
      <select name="project_type">
        <option value="logement">Logement</option>
        <option value="bureau">Bureau</option>
        <option value="mixte" selected>Mixte</option>
        <option value="scolaire">Scolaire</option>
      </select></div>
    <div><label>Surface ventilée (m²)</label>
      <input type="number" name="area" value="1200" step="10"></div>
    <div><label>Niveaux</label><input type="number" name="levels" value="2" min="1"></div>
    <div><label>Inertie (composition parois)</label>
      <select name="inertia">
        <option value="lourde" selected>Lourde</option>
        <option value="moyenne">Moyenne</option>
        <option value="legere">Légère</option>
      </select></div>
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
  </div>
  <h2 class="sec">Contexte du site</h2>
  <label class="check"><input type="checkbox" name="noise"> Bruit extérieur excessif</label>
  <label class="check"><input type="checkbox" name="pollution"> Pollution / pollen élevés</label>
  <label class="check"><input type="checkbox" name="security"> Risque de sécurité au RdC</label>
  <p style="margin-top:1.4rem"><button class="btn" type="submit">Calculer l'étude</button></p>
</form>
"""
    return _layout("Zéphyr — nouvelle étude", body, cta=False)


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
            '<div class="bar-row">'
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

    kpis = ""
    van_svg = ""
    if result.roi is not None:
        r = result.roi
        be = f"an {r.break_even_year}" if r.break_even_year is not None else "hors horizon"
        pen = result.heating_penalty.eur_per_year if result.heating_penalty else 0.0
        cells = [
            ("CAPEX VNC", f"{r.capex_vnc_eur:,.0f} €"),
            ("VAN économie VNC", f"{r.npv_delta_eur:,.0f} €"),
            ("Break-even", be),
            ("Pénalité chauffage", f"{pen:,.0f} €/an"),
        ]
        kpis = '<div class="kpis">' + "".join(
            f'<div class="kpi"><div class="k">{html.escape(k)}</div>'
            f'<div class="v">{html.escape(v)}</div></div>'
            for k, v in cells
        ) + "</div>"
        van_svg = _van_svg(r.npv_delta_cumulative_eur)

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
{recos}
{plan}
<h2 class="sec">Bilan financier — VNC vs VMC double-flux</h2>
{kpis}
{van_svg}
<p style="color:var(--muted);font-size:.85rem;margin-top:.6rem">VAN cumulée de
l'économie VNC (coûts VMC − coûts VNC), actualisée, année par année.</p>
<div class="disclaimer">⚠️ {html.escape(_DISCLAIMER)}</div>
<p><a class="btn ghost" href="/etude">↺ Nouvelle étude</a></p>
"""
    return _layout("Zéphyr — résultats", body, cta=False)
