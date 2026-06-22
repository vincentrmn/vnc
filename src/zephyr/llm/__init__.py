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
from typing import Any

from zephyr.schemas import StudyResult

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
1. Verdict et pourquoi (disqualifiants / conditions s'il y en a).
2. Thermique : pénalité de chauffage VNC vs VMC, surchauffe.
3. ROI : ordre de grandeur (CAPEX, économie actualisée, break-even), driver principal.
4. Réserves : ce qui reste à valider / vérifier.

Pas de jargon non expliqué. Pas de markdown lourd. Ton sobre et factuel.
"""


def _study_to_payload(result: StudyResult) -> dict[str, Any]:
    """Extrait les chiffres clés du `StudyResult` pour le narratif (rien d'autre)."""
    payload: dict[str, Any] = {
        "verdict": result.verdict.value,
        "disqualifiants": result.disqualifiers,
        "conditions": result.conditions,
    }
    if result.thermal is not None:
        t = result.thermal
        payload["thermique"] = {
            "penalite_chauffage_kwh_an": round(t.heating_penalty_kwh_per_year),
            "penalite_chauffage_eur_an": round(t.heating_penalty_eur_per_year),
            "heures_surchauffe": round(t.overheating_hours),
            "note": "pénalité calculée mais directionnelle (non calée finement sur STD)",
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
    response = client.messages.create(
        model=MODEL_NARRATIVE,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": messages}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def label_room(context: str) -> str:
    """Étiquette sémantique d'une pièce (séjour, SDB, circulation…).

    Raises:
        NotImplementedError: labelling LLM différé (Phase 3 utilise des mots-clés).
    """
    raise NotImplementedError("llm.label_room — labelling LLM différé (mots-clés en attendant)")
