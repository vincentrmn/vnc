"""Module `llm` — service transverse (labelling + narratif) (Phase 4).

Deux rôles, et seulement ceux-là (CLAUDE.md §8) :
  1. Labelling sémantique à l'ingestion (Sonnet 4.6 / Haiku 4.5).
  2. Narratif en sortie (Opus 4.8).

Interdits : mesurer une géométrie par vision, **inventer des chiffres**, remplacer
un calcul déterministe. Le narratif ne fait que *reformuler* les nombres fournis.
Prompt caching sur le bloc statique (règles) → ~90 % d'économie sur l'input répété.
`max_tokens` borné, pas de thinking (tâche de rédaction).
"""

from __future__ import annotations

import json
import os
from typing import Any, cast

from zephyr.schemas import CpeExtraction, InertiaClass, StudyResult

# Modèles de référence (CLAUDE.md §5/§8). Ne pas confondre avec l'identité du
# modèle qui exécute Claude Code.
MODEL_NARRATIVE = "claude-opus-4-8"
MODEL_LABELLING = "claude-sonnet-4-6"
MODEL_LABELLING_BULK = "claude-haiku-4-5"

# Bloc système STATIQUE → mis en cache (prompt caching). Aucune donnée variable ici.
_NARRATIVE_SYSTEM = """\
Tu es le rédacteur technique de Zéphyr, un outil de PRÉ-ÉTUDE de faisabilité de la
Ventilation Naturelle Contrôlée (VNC) dans les bâtiments.

Ta tâche : transformer des résultats chiffrés (fournis en JSON) en une synthèse
claire et honnête, en FRANÇAIS, pour un ingénieur non spécialiste de l'énergie.

RÈGLES ABSOLUES :
- N'invente AUCUN chiffre. N'utilise QUE les valeurs présentes dans le JSON. Tu
  peux les arrondir et les reformuler, jamais en créer ni en extrapoler.
- C'est une pré-étude / aide à la décision, PAS une étude opposable. Dis-le.
- Reste directionnel : parle d'ordres de grandeur, pas de précision absolue.
  Mentionne l'incertitude et le fait que les hypothèses sont exposées.
- Ne survends pas la VNC : sois équilibré (on la vend, donc on doit rester crédible).

STRUCTURE (concise, ~200-300 mots, titres courts) :
1. Aptitude VNC : score global + note, et les critères forts/faibles.
2. Recommandations d'amélioration (les plus utiles).
3. Surcoût de chauffage VNC vs VMC (déterministe, degrés-jours).
4. ROI : ordre de grandeur (CAPEX, économie actualisée, break-even), driver principal.

Pas de jargon non expliqué. Pas de markdown lourd. Ton sobre et factuel.
"""


def _study_to_payload(result: StudyResult) -> dict[str, Any]:
    """Extrait les chiffres clés du `StudyResult` pour le narratif (rien d'autre)."""
    payload: dict[str, Any] = {
        "verdict": result.verdict.value,
        "disqualifiants": result.disqualifiers,
        "conditions": result.conditions,
    }
    if result.score is not None:
        s = result.score
        payload["score"] = {
            "global_sur_100": round(s.global_score),
            "note": s.grade,
            "criteres": [
                {"critere": c.label, "note": round(c.score), "detail": c.detail}
                for c in s.criteria
            ],
            "recommandations": s.recommendations,
            "drapeaux": s.flags,
        }
    if result.heating_penalty is not None:
        p = result.heating_penalty
        payload["surcout_chauffage"] = {
            "kwh_an": round(p.kwh_per_year),
            "eur_an": round(p.eur_per_year),
            "dju_base18": round(p.heating_degree_days),
            "methode": "degrés-jours (déterministe, sans STD)",
        }
    if result.roi is not None:
        r = result.roi
        top = max(r.sensitivity, key=lambda e: e.swing).parameter if r.sensitivity else None
        payload["roi"] = {
            "capex_vnc_eur": round(r.capex_vnc_eur),
            "capex_vmc_eur": round(r.capex_vmc_eur),
            "van_economie_vnc_eur": round(r.npv_delta_eur),
            "break_even_annee": r.break_even_year,
            "horizon_ans": r.horizon_years,
            "driver_principal": top,
        }
        payload["avertissements"] = r.warnings
    return payload


def build_narrative_messages(
    result: StudyResult,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Construit (system, messages) pour le narratif. Pur, testable sans API."""
    system = [{"type": "text", "text": _NARRATIVE_SYSTEM, "cache_control": {"type": "ephemeral"}}]
    payload = _study_to_payload(result)
    user = [
        {
            "type": "text",
            "text": "Rédige la synthèse à partir de ces résultats (JSON) :\n"
            + json.dumps(payload, ensure_ascii=False, indent=2),
        }
    ]
    return system, user


def narrative_available() -> bool:
    """Le narratif est-il appelable (SDK installé + clé API présente) ?"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def write_narrative(result: StudyResult, *, max_tokens: int = 1200) -> str:
    """Rédige le narratif lisible à partir des résultats chiffrés (Opus 4.8).

    Raises:
        RuntimeError: si le SDK Anthropic ou la clé API ne sont pas disponibles.
    """
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - dépend de l'extra llm
        raise RuntimeError(
            "SDK Anthropic absent : installer l'extra 'llm' (uv sync --extra llm)."
        ) from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY absente : narratif indisponible.")

    system, messages = build_narrative_messages(result)
    client = anthropic.Anthropic()
    response = cast(Any, client).messages.create(
        model=MODEL_NARRATIVE,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": messages}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


# --------------------------------------------------------------------------- #
# Extraction CPE (hybride : règles + LLM, chiffres vérifiés verbatim)
# --------------------------------------------------------------------------- #
# Bloc système STATIQUE (mis en cache). Décrit la tâche + le contrat de sortie.
_CPE_SYSTEM = """\
Tu es un extracteur de données pour Zéphyr (pré-étude VNC). On te donne le TEXTE
BRUT d'un CPE luxembourgeois (passeport énergétique / Energiepass, bilingue
FR/DE), extrait d'un PDF — la mise en page est désordonnée (colonnes mélangées).

Ta tâche : retrouver, SI ELLES SONT PRÉSENTES, les valeurs d'enveloppe ci-dessous,
et UNIQUEMENT celles-là. Tu ne calcules rien, tu ne devines rien : tu RECOPIES ce
qui est écrit. Pour CHAQUE valeur trouvée, tu fournis aussi un court extrait du
texte (`source`) copié mot pour mot, contenant la valeur (sert de preuve).

Champs (clé JSON → sens) :
- u_wall_w_m2k : valeur U du mur extérieur (Aussenwand / mur extérieur), W/(m²K).
- u_roof_w_m2k : valeur U de la toiture (Dach), W/(m²K).
- u_floor_w_m2k : valeur U du plancher bas / radier (Bodenplatte), W/(m²K).
- u_window_w_m2k : valeur Uw des fenêtres (Fenster), W/(m²K).
- air_permeability_ach50 : n50 retenu pour le calcul (vol/h sous 50 Pa).
- glazing_to_floor_ratio : ratio surface vitrée / surface (si explicitement donné).
- inertia_class : "lourde" (béton/maçonnerie), "moyenne" ou "legere" (ossature
  bois/légère), DÉDUITE de la composition des parois ; mets en `source` les
  matériaux qui le justifient.
- floor_area_m2 : surface de référence énergétique, m².
- construction_year : année de construction (entier).

S'il y a plusieurs valeurs U pour un même type, prends la valeur U calculée
représentative (pas une couche intermédiaire). Les décimales peuvent être notées
avec une virgule (ex. 0,18) — recopie le nombre tel quel dans `source`.

Indices de nommage (CPE LU, FR/DE) : un tableau récapitulatif liste souvent les
éléments sous la forme « N Nom / U: valeur ». Correspondances :
- mur extérieur ← « Façade » (PAS « Façade ventilée » si une « Façade » simple
  existe, PAS « Mur contre non chauffé ») ; en allemand « Aussenwand ».
- toiture ← « Toiture » / « Dach » ; plancher bas ← « Radier » / « Dalle » /
  « Bodenplatte ».
- fenêtres ← « Fenster » / « fenêtre » : prends la valeur « U-Wert Fenster » (U
  de la fenêtre complète, pas du verre ni du cadre seuls). NE PRENDS PAS les
  « Porte(s) » (ce sont des portes, pas des vitrages).
- n50 ← « Luftdichtheitswert für Berechnung » / valeur n50 retenue pour le calcul.

SORTIE : un SEUL objet JSON, rien d'autre (pas de texte, pas de balises code).
Forme : {"u_wall_w_m2k": {"value": 0.18, "source": "..."}, ...}. Pour un champ
absent : null. N'INVENTE AUCUN CHIFFRE — si tu n'es pas sûr, mets null.
"""

# Champs numériques attendus (les autres : inertia_class, construction_year).
_CPE_NUMERIC = (
    "u_wall_w_m2k", "u_roof_w_m2k", "u_floor_w_m2k", "u_window_w_m2k",
    "air_permeability_ach50", "glazing_to_floor_ratio", "floor_area_m2",
)


def build_cpe_messages(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Construit (system, user) pour l'extraction CPE. Pur, testable sans API."""
    system = [{"type": "text", "text": _CPE_SYSTEM, "cache_control": {"type": "ephemeral"}}]
    user = [{"type": "text", "text": "Texte du CPE :\n" + text}]
    return system, user


def parse_cpe_response(raw: str) -> dict[str, Any]:
    """Parse la réponse JSON du modèle (tolère un éventuel bloc ```)."""
    s = raw.strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        return {}
    obj = json.loads(s[start : end + 1])
    return obj if isinstance(obj, dict) else {}


def _number_in_text(value: float, text: str) -> bool:
    """La valeur apparaît-elle telle quelle dans le texte (virgule ou point) ?

    On ne teste que des rendus **fidèles** (qui ré-évaluent à la même valeur), donc
    pas d'arrondi trompeur (0,18 ne « matche » jamais via 0,2). Anti-hallucination.
    """
    norm = text.replace(",", ".")
    for d in range(5):
        r = f"{value:.{d}f}"
        if r not in ("0", "0.0") and abs(float(r) - value) < 1e-9 and r in norm:
            return True
    return False


def verify_cpe_extraction(parsed: dict[str, Any], source_text: str) -> CpeExtraction:
    """Vérifie chaque champ proposé contre le texte source et construit l'extraction.

    Tout nombre qui n'apparaît pas **verbatim** dans le CPE est écarté (et noté) :
    le LLM ne peut pas introduire de chiffre absent (CLAUDE.md §11).
    """
    fields: dict[str, Any] = {}
    sources: dict[str, str] = {}
    notes: list[str] = []

    def _val(entry: Any) -> tuple[Any, str]:
        if isinstance(entry, dict):
            return entry.get("value"), str(entry.get("source", ""))
        return entry, ""

    for key in (*_CPE_NUMERIC, "construction_year"):
        v, src = _val(parsed.get(key))
        if v is None:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            continue
        if _number_in_text(num, source_text):
            fields[key] = int(num) if key == "construction_year" else num
            if src:
                sources[key] = src
        else:
            notes.append(f"{key}={v} écarté : valeur non retrouvée verbatim dans le CPE.")

    v, src = _val(parsed.get("inertia_class"))
    if isinstance(v, str) and v in {c.value for c in InertiaClass}:
        fields["inertia_class"] = InertiaClass(v)
        if src:
            sources["inertia_class"] = src

    return CpeExtraction(**fields, sources=sources, notes=notes)


def cpe_extraction_available() -> bool:
    """L'extraction CPE est-elle appelable (SDK + clé API) ?"""
    return narrative_available()


def extract_cpe(text: str, *, max_tokens: int = 1500) -> CpeExtraction:
    """Extrait les champs d'enveloppe d'un CPE (Sonnet 4.6) puis les vérifie.

    Hybride : extraction texte déterministe (amont) → mapping LLM → vérification
    verbatim des chiffres. Le résultat pré-remplit le formulaire (humain valide).

    Raises:
        RuntimeError: si le SDK Anthropic ou la clé API ne sont pas disponibles.
    """
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - dépend de l'extra llm
        raise RuntimeError(
            "SDK Anthropic absent : installer l'extra 'llm' (uv sync --extra llm)."
        ) from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY absente : extraction CPE indisponible.")

    system, messages = build_cpe_messages(text)
    client = anthropic.Anthropic()
    response = cast(Any, client).messages.create(
        model=MODEL_LABELLING,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": messages}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text")
    return verify_cpe_extraction(parse_cpe_response(raw), text)


def label_room(context: str) -> str:
    """Étiquette sémantique d'une pièce (séjour, SDB, circulation…).

    Raises:
        NotImplementedError: labelling LLM différé (Phase 3 utilise des mots-clés).
    """
    raise NotImplementedError("llm.label_room — labelling LLM différé (mots-clés en attendant)")
