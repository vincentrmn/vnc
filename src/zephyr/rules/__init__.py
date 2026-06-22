"""Module `rules` — moteur déterministe de faisabilité VNC.

Rend un verdict **go / no-go / conditionnel** avec disqualifiants explicites
(CLAUDE.md §4). Chaque règle porte son seuil et son explication. Le verdict est :

- **NO_GO** si au moins un *disqualifiant dur* (la VNC ne peut pas fonctionner ou
  est inacceptable) ;
- **CONDITIONNEL** si pas de disqualifiant dur mais au moins une *condition* (la
  VNC est possible moyennant une mesure / vérification) ;
- **GO** sinon.

Seuils de profondeur de plan (§4) : profondeur > ~2,5 × HSP en simple-face,
> ~5 × HSP en traversant → la ventilation naturelle ne balaie plus le fond.
"""

from __future__ import annotations

from dataclasses import dataclass

from zephyr.schemas import Building, SiteContext, StudyResult, ThermalResult, Verdict
from zephyr.ventilation import VentilationResult

# Seuils profondeur / HSP (CLAUDE.md §4).
DEPTH_RATIO_SINGLE_SIDED = 2.5
DEPTH_RATIO_CROSS = 5.0


@dataclass
class _Finding:
    code: str
    message: str
    hard: bool  # True → disqualifiant dur (no_go) ; False → condition (conditionnel)


def _deep_rooms(building: Building) -> list[str]:
    """Pièces trop profondes pour être balayées par la VNC (selon traversant)."""
    deep: list[str] = []
    for room in building.rooms:
        ratio = room.depth_to_height_ratio
        if ratio is None:
            continue
        limit = DEPTH_RATIO_CROSS if room.is_through else DEPTH_RATIO_SINGLE_SIDED
        if ratio > limit:
            deep.append(room.name or room.id)
    return deep


def _collect_findings(
    building: Building,
    thermal: ThermalResult | None,
    ventilation: VentilationResult | None,
    site: SiteContext,
) -> list[_Finding]:
    findings: list[_Finding] = []

    # --- Contexte de site (saisi) ---
    if site.exterior_noise_high:
        findings.append(
            _Finding(
                "bruit",
                "Bruit extérieur excessif : ouverture des fenêtres difficilement "
                "acceptable (étudier ouvrants acoustiques / ventilation décalée).",
                hard=False,
            )
        )
    if site.pollution_high:
        findings.append(
            _Finding(
                "pollution",
                "Pollution/pollen élevés : air extérieur peu admissible sans "
                "filtration — la VNC pure est compromise.",
                hard=True,
            )
        )
    if site.ground_floor_security_risk:
        findings.append(
            _Finding(
                "securite_rdc",
                "Risque d'intrusion au RdC : ouvrants ouverts à sécuriser "
                "(grilles, ouvrants en imposte, détection).",
                hard=False,
            )
        )
    if not site.occupancy_compatible:
        findings.append(
            _Finding(
                "occupation",
                "Occupation incompatible avec une ventilation naturelle pilotée.",
                hard=True,
            )
        )

    # --- Géométrie : plans trop profonds ---
    deep = _deep_rooms(building)
    if deep:
        n = len(deep)
        sample = ", ".join(deep[:5]) + ("…" if n > 5 else "")
        findings.append(
            _Finding(
                "plan_profond",
                f"{n} pièce(s) trop profonde(s) pour un balayage naturel "
                f"(> {DEPTH_RATIO_SINGLE_SIDED}× HSP en simple-face, "
                f"> {DEPTH_RATIO_CROSS}× en traversant) : {sample}.",
                hard=False,
            )
        )

    # --- Ventilation : surface d'ouvrants / exposition ---
    if ventilation is not None:
        if not ventilation.meets_hygienic:
            findings.append(
                _Finding(
                    "ouvrants_insuffisants",
                    f"Surface d'ouvrants insuffisante : {ventilation.achievable_ach:.1f} vol/h "
                    f"atteignables < {ventilation.hygienic_ach:.1f} vol/h hygiénique requis.",
                    hard=True,
                )
            )
        elif not ventilation.meets_freecool:
            findings.append(
                _Finding(
                    "freecool_limite",
                    f"Débit de free-cooling limité : {ventilation.achievable_ach:.1f} vol/h "
                    f"< {ventilation.target_freecool_ach:.1f} vol/h visés "
                    "(bénéfice de rafraîchissement passif réduit).",
                    hard=False,
                )
            )
        if ventilation.wind_flow_m3h < 0.1 * ventilation.combined_flow_m3h:
            findings.append(
                _Finding(
                    "expo_vent",
                    "Très faible contribution du vent : la VNC repose presque uniquement sur le "
                    "tirage thermique (vérifier l'exposition au vent).",
                    hard=False,
                )
            )

    # --- Thermique : surchauffe résiduelle malgré la VNC ---
    if thermal is not None and thermal.overheating_hours > 350:
        findings.append(
            _Finding(
                "surchauffe",
                f"Surchauffe résiduelle élevée malgré la VNC ({thermal.overheating_hours:.0f} h/an "
                "au-dessus du confort) : protections solaires / sur-ventilation à renforcer.",
                hard=False,
            )
        )

    return findings


def evaluate_feasibility(
    building: Building,
    thermal: ThermalResult | None = None,
    ventilation: VentilationResult | None = None,
    site: SiteContext | None = None,
) -> StudyResult:
    """Évalue la faisabilité VNC et renvoie un `StudyResult` (verdict justifié).

    `thermal` et `ventilation` sont optionnels : sans eux, seules les règles
    géométriques et de site s'appliquent (verdict partiel).
    """
    site = site or SiteContext()
    findings = _collect_findings(building, thermal, ventilation, site)

    disqualifiers = [f.message for f in findings if f.hard]
    conditions = [f.message for f in findings if not f.hard]

    if disqualifiers:
        verdict = Verdict.NO_GO
    elif conditions:
        verdict = Verdict.CONDITIONNEL
    else:
        verdict = Verdict.GO

    return StudyResult(
        verdict=verdict,
        disqualifiers=disqualifiers,
        conditions=conditions,
        thermal=thermal,
        assumptions={
            "regles": "moteur déterministe VNC (CLAUDE.md §4)",
            "seuil_profondeur_simple_face": f"{DEPTH_RATIO_SINGLE_SIDED}× HSP",
            "seuil_profondeur_traversant": f"{DEPTH_RATIO_CROSS}× HSP",
            "n_disqualifiants": str(len(disqualifiers)),
            "n_conditions": str(len(conditions)),
        },
    )
