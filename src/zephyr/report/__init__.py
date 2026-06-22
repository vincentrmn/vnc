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


def _li(items: list[str]) -> str:
    if not items:
        return "<li><em>aucun</em></li>"
    return "".join(f"<li>{html.escape(x)}</li>" for x in items)


def _kv_table(d: dict[str, str]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k, v in d.items()
    )
    return f"<table>{rows}</table>"


def _zones_table(result: StudyResult) -> str:
    """Tableau thermique par pièce : températures saisonnières + CO₂."""
    if result.thermal is None or not result.thermal.zones:
        return ""
    head = (
        "<tr><th>pièce</th><th>label</th><th>m²</th><th>T° libre min/max</th>"
        "<th>h&lt;18°C</th><th>h&gt;26°C</th><th>chauffage kWh/an</th>"
        "<th>froid kWh/an</th><th>CO₂ moy/max ppm</th><th>h&gt;1000</th></tr>"
    )
    rows = []
    for z in result.thermal.zones:
        co2_h = z.co2_hours_above_1000 or 0.0
        rows.append(
            "<tr>"
            f"<td>{html.escape(z.zone_id)}</td>"
            f"<td>{html.escape(z.label or '')}</td>"
            f"<td>{z.area_m2 or 0:.0f}</td>"
            f"<td>{z.top_min_c}/{z.top_max_c}</td>"
            f"<td>{z.hours_below_comfort:.0f}</td>"
            f"<td>{z.overheating_hours:.0f}</td>"
            f"<td>{z.heating_need_kwh or 0:.0f}</td>"
            f"<td>{z.cooling_need_kwh or 0:.0f}</td>"
            f"<td>{z.co2_mean_ppm}/{z.co2_max_ppm}</td>"
            f"<td>{co2_h:.0f}</td>"
            "</tr>"
        )
    return (
        "<h3>Détail par pièce (températures libres, besoins, CO₂)</h3>"
        "<table class='zones'>" + head + "".join(rows) + "</table>"
        "<p style='font-size:.85rem;color:#777'>T° <b>libre</b> = VNC en marche mais "
        "sans chauffage ni froid actifs (révèle la dérive réelle). h&lt;18 °C → besoin de "
        "chaud ; h&gt;26 °C → surchauffe/besoin de froid. Chauffage/froid = énergie pour "
        "tenir les consignes (froid résiduel <i>après</i> night-cooling). CO₂ = modèle "
        "d'équilibre (occupation × débit).</p>"
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

    thermal_html = "<p><em>Non calculé.</em></p>"
    if result.thermal is not None:
        t = result.thermal
        thermal_html = _kv_table(
            {
                "Besoin de chauffage VNC": f"{t.heating_need_kwh_per_year:.0f} kWh/an",
                "Besoin de froid actif (après night-cooling)": (
                    f"{t.cooling_need_kwh_per_year:.0f} kWh/an"
                ),
                "Pénalité de chauffage VNC vs VMC DF": (
                    f"{t.heating_penalty_kwh_per_year:.0f} kWh/an "
                    f"(≈ {t.heating_penalty_eur_per_year:.0f} €/an)"
                ),
                "Heures < 18 °C (pire pièce, libre)": f"{t.hours_below_comfort:.0f} h/an",
                "Heures > 26 °C (pire pièce, libre)": f"{t.overheating_hours:.0f} h/an",
                "Bénéfice night-cooling": f"{t.night_cooling_benefit_kwh:.0f} kWh/an",
            }
        ) + _zones_table(result)

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
<p class="disclaimer">⚠️ {html.escape(_DISCLAIMER)}</p>
{narrative}
{plan_html}
<h2>Faisabilité</h2>
<h3>Disqualifiants</h3><ul>{_li(result.disqualifiers)}</ul>
<h3>Conditions</h3><ul>{_li(result.conditions)}</ul>
<h2>Screen thermique</h2>{thermal_html}
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
