"""Module `report` — génération du rapport (HTML, PDF optionnel) (Phase 4).

Assemble verdict + ROI + explications en un rapport lisible et exportable. Toute
sortie expose ses hypothèses et son incertitude ; jamais de chiffre orphelin
(CLAUDE.md §12). Ce n'est **jamais** une étude opposable (§11).

Le HTML est généré en pur stdlib (aucune dépendance requise). La conversion PDF
via WeasyPrint est **optionnelle** : si le paquet n'est pas installé, on écrit le
HTML et on le signale.
"""

from __future__ import annotations

import html
from pathlib import Path

from zephyr.schemas import StudyResult, Verdict

_VERDICT_LABEL = {
    Verdict.GO: ("GO", "#1a7f37"),
    Verdict.CONDITIONNEL: ("CONDITIONNEL", "#9a6700"),
    Verdict.NO_GO: ("NO-GO", "#b42318"),
}

_DISCLAIMER = (
    "Pré-étude / aide à la décision interne. Ce document n'est PAS une étude "
    "thermique opposable. Les résultats sont des ordres de grandeur, exposant "
    "leurs hypothèses et leur incertitude."
)

# Icône d'alerte (Lucide « triangle-alert », ISC) inlinée — le PDF (WeasyPrint)
# n'exécute aucun JS, donc l'icône doit être présente dans le HTML rendu.
_ALERT_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-.12em" aria-hidden="true">'
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
    '<path d="M12 9v4"/><path d="M12 17h.01"/></svg>'
)


def _li(items: list[str]) -> str:
    if not items:
        return "<li><em>aucun</em></li>"
    return "".join(f"<li>{html.escape(x)}</li>" for x in items)


def _kv_table(d: dict[str, str]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k, v in d.items()
    )
    return f"<table>{rows}</table>"


def _score_table(result: StudyResult) -> str:
    """Tableau du score d'aptitude VNC : note globale + détail par critère + recos."""
    if result.score is None:
        return ""
    s = result.score
    head = "<tr><th>critère</th><th>note /100</th><th>poids</th><th>détail</th></tr>"
    rows = []
    for c in s.criteria:
        rows.append(
            "<tr>"
            f"<td>{html.escape(c.label)}</td>"
            f"<td>{c.score:.0f}</td>"
            f"<td>{c.weight:.0f}</td>"
            f"<td style='text-align:left'>{html.escape(c.detail)}</td>"
            "</tr>"
        )
    recos = ""
    if s.recommendations:
        recos = "<h3>Recommandations d'amélioration</h3><ul>" + _li(s.recommendations) + "</ul>"
    flags = ""
    if s.flags:
        flags = "<h3>Points de vigilance (site)</h3><ul>" + _li(s.flags) + "</ul>"
    return (
        f"<p><b>Score d'aptitude VNC : {s.global_score:.0f}/100 "
        f"(note {html.escape(s.grade)})</b></p>"
        "<table class='zones'>" + head + "".join(rows) + "</table>" + recos + flags
    )


def render_report_html(
    result: StudyResult,
    *,
    building: object | None = None,
    title: str = "Pré-étude VNC — Zéphyr",
) -> str:
    """Construit le rapport au format HTML (chaîne).

    Si ``building`` (un `Building`) est fourni et que matplotlib est disponible,
    le plan reconstruit est embarqué.
    """
    label, color = _VERDICT_LABEL[result.verdict]

    plan_html = ""
    rooms = getattr(building, "rooms", []) if building is not None else []
    has_polygons = any(getattr(r, "polygon", None) for r in rooms)
    if building is not None and has_polygons:
        try:
            from zephyr.viz import render_plan_data_uri

            uri = render_plan_data_uri(building)  # type: ignore[arg-type]
            plan_html = (
                "<h2>Géométrie reconstruite</h2>"
                f"<img src='{uri}' alt='plan' style='max-width:100%;border:1px solid #eee'>"
                "<p style='font-size:.85rem;color:#777'>Orientations/ouvrants estimés — "
                "à valider par l'ingénieur (§2.8).</p>"
            )
        except Exception:  # pragma: no cover - matplotlib absent
            plan_html = ""

    score_html = _score_table(result)

    penalty_html = ""
    if result.heating_penalty is not None:
        p = result.heating_penalty
        penalty_html = "<h2>Surcoût de chauffage VNC (déterministe, degrés-jours)</h2>" + _kv_table(
            {
                "Pénalité de chauffage VNC vs VMC DF": (
                    f"{p.kwh_per_year:.0f} kWh/an (≈ {p.eur_per_year:.0f} €/an)"
                ),
                "Degrés-jours de chauffe (base 18 °C)": f"{p.heating_degree_days:.0f} °C·j",
            }
        ) + (
            "<p style='font-size:.85rem;color:#777'>Surcoût = pertes de ventilation non "
            "récupérées par la VNC (la VMC DF récupère ~80 %), atténuées par la commande "
            "à la demande. Calcul déterministe en degrés-jours, sans STD.</p>"
        )

    roi_html = "<p><em>Non calculé.</em></p>"
    if result.roi is not None:
        r = result.roi
        be = f"an {r.break_even_year}" if r.break_even_year is not None else "au-delà de l'horizon"
        roi_html = _kv_table(
            {
                "CAPEX VNC": f"{r.capex_vnc_eur:,.0f} €",
                "CAPEX VMC DF": f"{r.capex_vmc_eur:,.0f} €",
                "VAN économie VNC (actualisée)": f"{r.npv_delta_eur:,.0f} €",
                "Break-even": be,
                "Horizon": f"{r.horizon_years} ans",
            }
        )
        tornado = sorted(r.sensitivity, key=lambda e: e.swing, reverse=True)
        if tornado:
            bars = "".join(
                f"<tr><td>{html.escape(e.parameter)}</td>"
                f"<td style='text-align:right'>{e.swing:,.0f} €</td></tr>"
                for e in tornado
            )
            roi_html += f"<h3>Sensibilité (tornado)</h3><table>{bars}</table>"
        if r.warnings:
            roi_html += f"<h3>Avertissements méthodologiques</h3><ul>{_li(r.warnings)}</ul>"

    narrative = ""
    if result.narrative:
        narrative = f"<h2>Synthèse</h2><p>{html.escape(result.narrative)}</p>"

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
 body {{ font-family: system-ui, sans-serif; max-width: 820px; margin: 2rem auto; color:#1c1c1c; }}
 h1 {{ margin-bottom: .2rem; }}
 .verdict {{ display:inline-block; padding:.3rem .8rem; border-radius:.4rem; color:#fff;
            font-weight:700; background:{color}; }}
 .disclaimer {{ background:#fff8e6; border:1px solid #f0d999; padding:.6rem .8rem;
               border-radius:.4rem; font-size:.9rem; }}
 table {{ border-collapse: collapse; width:100%; margin:.5rem 0; }}
 td {{ border-bottom:1px solid #eee; padding:.35rem .5rem; }}
 td:last-child {{ text-align:right; font-variant-numeric: tabular-nums; }}
 h2 {{ margin-top:1.6rem; border-bottom:2px solid #eee; padding-bottom:.2rem; }}
 footer {{ margin-top:2rem; color:#777; font-size:.8rem; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="verdict">VERDICT&nbsp;: {label}</p>
<p class="disclaimer">{_ALERT_SVG} {html.escape(_DISCLAIMER)}</p>
{narrative}
{plan_html}
<h2>Aptitude à la VNC (score)</h2>{score_html}
{penalty_html}
<h2>ROI — VNC vs VMC double-flux</h2>{roi_html}
<h2>Hypothèses</h2>{_kv_table(result.assumptions)}
<footer>Généré par Zéphyr — moteur de pré-étude VNC. Pré-étude non opposable.</footer>
</body></html>"""


def render_report(
    result: StudyResult, output_path: str | Path, *, building: object | None = None
) -> Path:
    """Génère le rapport. Écrit du HTML ; tente un PDF si WeasyPrint est dispo.

    Renvoie le chemin réellement écrit (``.pdf`` si possible, sinon ``.html``).
    """
    output_path = Path(output_path)
    html_text = render_report_html(result, building=building)

    if output_path.suffix.lower() == ".pdf":
        try:
            from weasyprint import HTML

            HTML(string=html_text).write_pdf(str(output_path))
            return output_path
        except Exception:
            # WeasyPrint absent ou libs système manquantes → repli HTML.
            output_path = output_path.with_suffix(".html")

    output_path.write_text(html_text, encoding="utf-8")
    return output_path
