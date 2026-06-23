"""Module `rules` — **moteur de score d'aptitude VNC** (déterministe).

Décision produit : ~95 % des bâtiments sont éligibles à la VNC (le principe est
universel). L'utile n'est donc pas un verdict binaire mais un **score** (0–100)
décomposé en critères, chacun noté en déterministe, avec des **recommandations**
d'amélioration. Les vrais blocages (air non admissible, occupation incompatible)
restent des *drapeaux* contextuels qui pilotent le verdict.

Critères (pondérations par défaut, surchargeables) :
  - **Ventilation** (35) : traversant (idéal) ou châssis hauts ≥ 1,5 m (tirage
    mono-façade, suffisant à défaut) ; pénalise les plans trop profonds.
  - **Vitrage** (20) : ratio surface vitrée / surface au sol dans la bonne bande.
  - **Inertie** (25) : masse lue de la composition des parois (CPE).
  - **Isolation** (20) : niveau d'isolation (U) — bien isolé = +.

Les ouvrants (nombre/surface/motorisation) ne sont **pas** un critère : c'est
notre dimensionnement → un poste de CAPEX dans le ROI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from zephyr.schemas import (
    Building,
    EnvelopeData,
    InertiaClass,
    ScoreCriterion,
    SiteContext,
    StudyResult,
    Verdict,
    VNCScore,
)

# Seuils profondeur / HSP (CLAUDE.md §4).
DEPTH_RATIO_SINGLE_SIDED = 2.5
DEPTH_RATIO_CROSS = 5.0

# Hauteur de châssis à partir de laquelle le tirage mono-façade est exploitable.
TALL_SASH_M = 1.5

# Bande optimale de ratio vitrage / surface au sol.
GLAZING_LOW = 0.15
GLAZING_HIGH = 0.25

# Notes d'inertie par classe (free-cooling nocturne + amortissement).
_INERTIA_SCORE: dict[InertiaClass, float] = {
    InertiaClass.LOURDE: 100.0,
    InertiaClass.MOYENNE: 60.0,
    InertiaClass.LEGERE: 25.0,
}


@dataclass
class ScoreWeights:
    """Pondérations des critères (somme libre ; normalisées au calcul)."""

    ventilation: float = 35.0
    vitrage: float = 20.0
    inertie: float = 25.0
    isolation: float = 20.0


@dataclass
class _SiteFlags:
    hard: list[str] = field(default_factory=list)  # drapeaux durs → NO_GO
    soft: list[str] = field(default_factory=list)  # réserves → CONDITIONNEL


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "E"


def _building_sash_height(building: Building) -> float | None:
    """Hauteur libre maximale des châssis ouvrants (m), si renseignée dans les baies."""
    heights: list[float] = []
    for room in building.rooms:
        for op in room.openings:
            if op.openable and op.head_height_m is not None:
                heights.append(max(op.head_height_m - op.sill_height_m, 0.0))
    return max(heights) if heights else None


def _ventilation_criterion(
    building: Building, sash_height_m: float | None, weight: float
) -> ScoreCriterion:
    """Note la capacité géométrique à ventiler naturellement (traversant / châssis)."""
    total_area = building.total_floor_area_m2 or 1.0
    through_area = 0.0
    single_tall_area = 0.0
    single_low_area = 0.0
    interior_area = 0.0
    credited = 0.0
    tall = sash_height_m is not None and sash_height_m >= TALL_SASH_M

    for room in building.rooms:
        a = room.area_m2
        exposed = bool(room.exterior_wall_orientations) or bool(room.openings)
        if not exposed:
            interior_area += a
            credit = 0.0
        elif room.is_through:
            through_area += a
            credit = 1.0
        elif tall:
            single_tall_area += a
            credit = 0.6
        else:
            single_low_area += a
            credit = 0.3
        # Pénalité de plan trop profond (la VNC ne balaie plus le fond).
        ratio = room.depth_to_height_ratio
        if ratio is not None:
            limit = DEPTH_RATIO_CROSS if room.is_through else DEPTH_RATIO_SINGLE_SIDED
            if ratio > limit:
                credit *= 0.5
        credited += a * credit

    score = 100.0 * credited / total_area

    def pct(x: float) -> str:
        return f"{100.0 * x / total_area:.0f}%"

    detail = (
        f"{pct(through_area)} traversant, {pct(single_tall_area)} mono-façade châssis hauts, "
        f"{pct(single_low_area)} mono-façade bas, {pct(interior_area)} aveugle"
    )
    reco: str | None = None
    if score < 70:
        if not tall:
            reco = (
                "Hauteur de châssis non confirmée / < 1,5 m : viser des ouvrants ≥ 1,5 m "
                "pour activer le tirage mono-façade, et créer des transferts d'air vers "
                "les pièces aveugles/profondes."
            )
        else:
            reco = (
                "Améliorer le balayage : transferts d'air vers les pièces aveugles, "
                "ouvrants traversants là où c'est possible."
            )
    return ScoreCriterion(
        key="ventilation",
        label="Ventilation (traversant / châssis)",
        score=round(score, 1),
        weight=weight,
        detail=detail,
        recommendation=reco,
    )


def _glazing_criterion(building: Building, envelope: EnvelopeData, weight: float) -> ScoreCriterion:
    """Note le ratio surface vitrée / surface au sol (bande optimale)."""
    area = building.total_floor_area_m2 or 1.0
    if envelope.glazing_to_floor_ratio is not None:
        ratio = envelope.glazing_to_floor_ratio
        src = "CPE/saisie"
    else:
        glazing = sum(op.area_m2 for r in building.rooms for op in r.openings)
        ratio = glazing / area
        src = "baies du plan (hauteur supposée)"

    if GLAZING_LOW <= ratio <= GLAZING_HIGH:
        score = 100.0
    elif ratio < GLAZING_LOW:
        score = max(0.0, 100.0 * ratio / GLAZING_LOW)
    else:  # trop vitré
        score = max(0.0, 100.0 - 250.0 * (ratio - GLAZING_HIGH))

    reco: str | None = None
    if ratio > GLAZING_HIGH:
        reco = (
            f"Vitrage élevé ({ratio:.0%} > {GLAZING_HIGH:.0%}) : risque de surchauffe et de "
            "déperditions → protections solaires (sud/ouest), voire réduction des surfaces vitrées."
        )
    elif ratio < GLAZING_LOW:
        reco = (
            f"Vitrage faible ({ratio:.0%} < {GLAZING_LOW:.0%}) : peu d'apports/lumière → "
            "augmenter les surfaces ouvrantes utiles au tirage et à l'éclairage naturel."
        )
    return ScoreCriterion(
        key="vitrage",
        label="Vitrage (surface vitrée / surface au sol)",
        score=round(score, 1),
        weight=weight,
        detail=f"ratio vitrage/plancher = {ratio:.0%} (source : {src})",
        recommendation=reco,
    )


def _inertia_criterion(building: Building, weight: float) -> ScoreCriterion:
    """Note l'inertie (masse) — lourde = stockage de fraîcheur nocturne + amortissement."""
    cls = building.inertia_class
    score = _INERTIA_SCORE.get(cls, 60.0)
    reco = None
    if cls is not InertiaClass.LOURDE:
        reco = (
            f"Inertie {cls.value} : free-cooling nocturne moins efficace → renforcer la "
            "surventilation nocturne et les protections solaires (risque de surchauffe l'été)."
        )
    return ScoreCriterion(
        key="inertie",
        label="Inertie / masse (composition des parois)",
        score=round(score, 1),
        weight=weight,
        detail=f"classe d'inertie : {cls.value} (lue du CPE / composition des parois)",
        recommendation=reco,
    )


def _insulation_criterion(envelope: EnvelopeData, weight: float) -> ScoreCriterion:
    """Note le niveau d'isolation (U murs + vitrages) — bien isolé = +."""
    u_wall = envelope.u_wall_w_m2k
    u_win = envelope.u_window_w_m2k
    if u_wall is None and u_win is None:
        return ScoreCriterion(
            key="isolation",
            label="Isolation (niveau d'isolation)",
            score=60.0,
            weight=weight,
            detail="U non renseignés (CPE manquant) — note neutre par défaut",
            recommendation="Renseigner le CPE (U murs/vitrages) pour fiabiliser le bilan.",
        )

    def wall_score(u: float) -> float:
        # 0,15 W/m²K → 100 ; 1,0 W/m²K → ~0 (linéaire borné).
        return max(0.0, min(100.0, 100.0 * (1.0 - (u - 0.15) / 0.85)))

    def win_score(u: float) -> float:
        # 0,8 W/m²K → 100 ; 2,5 W/m²K → ~0.
        return max(0.0, min(100.0, 100.0 * (1.0 - (u - 0.8) / 1.7)))

    parts: list[float] = []
    bits: list[str] = []
    if u_wall is not None:
        parts.append(wall_score(u_wall) * 0.7)
        bits.append(f"U mur {u_wall:.2f}")
    if u_win is not None:
        parts.append(win_score(u_win) * 0.3)
        bits.append(f"Uw {u_win:.2f}")
    wsum = (0.7 if u_wall is not None else 0.0) + (0.3 if u_win is not None else 0.0)
    score = sum(parts) / wsum if wsum else 60.0
    reco = None
    if score < 60:
        reco = (
            "Enveloppe peu isolée : l'appoint de chauffage (sans récupération VNC) pèsera "
            "davantage → l'isolation est le premier levier du bilan."
        )
    return ScoreCriterion(
        key="isolation",
        label="Isolation (niveau d'isolation)",
        score=round(score, 1),
        weight=weight,
        detail=" ; ".join(bits) + " W/m²K",
        recommendation=reco,
    )


def _site_flags(site: SiteContext) -> _SiteFlags:
    flags = _SiteFlags()
    if site.pollution_high:
        flags.hard.append(
            "Pollution/pollen élevés : air extérieur peu admissible sans filtration — "
            "VNC pure compromise."
        )
    if not site.occupancy_compatible:
        flags.hard.append("Occupation incompatible avec une ventilation naturelle pilotée.")
    if site.exterior_noise_high:
        flags.soft.append(
            "Bruit extérieur excessif : prévoir des ouvrants acoustiques / ventilation décalée."
        )
    if site.ground_floor_security_risk:
        flags.soft.append(
            "Risque d'intrusion au RdC : sécuriser les ouvrants (grilles, impostes, détection)."
        )
    return flags


def score_building(
    building: Building, envelope: EnvelopeData, weights: ScoreWeights | None = None
) -> VNCScore:
    """Calcule le score d'aptitude VNC (sans le contexte de site)."""
    w = weights or ScoreWeights()
    sash = envelope.sash_height_m if envelope.sash_height_m is not None else _building_sash_height(
        building
    )
    criteria = [
        _ventilation_criterion(building, sash, w.ventilation),
        _glazing_criterion(building, envelope, w.vitrage),
        _inertia_criterion(building, w.inertie),
        _insulation_criterion(envelope, w.isolation),
    ]
    wsum = sum(c.weight for c in criteria) or 1.0
    global_score = sum(c.score * c.weight for c in criteria) / wsum
    # Recommandations priorisées par poids × déficit.
    ranked = sorted(
        (c for c in criteria if c.recommendation),
        key=lambda c: c.weight * (100.0 - c.score),
        reverse=True,
    )
    recommendations = [c.recommendation for c in ranked if c.recommendation]
    return VNCScore(
        global_score=round(global_score, 1),
        grade=_grade(global_score),
        criteria=criteria,
        recommendations=recommendations,
    )


def evaluate_vnc(
    building: Building,
    envelope: EnvelopeData | None = None,
    site: SiteContext | None = None,
    weights: ScoreWeights | None = None,
) -> StudyResult:
    """Évalue l'aptitude VNC : score + drapeaux de site → `StudyResult` (sans ROI).

    Le ROI est branché en aval par `study.compute_study`.
    """
    envelope = envelope or EnvelopeData()
    site = site or SiteContext()
    score = score_building(building, envelope, weights)
    flags = _site_flags(site)
    score.flags = flags.hard + flags.soft

    if flags.hard:
        verdict = Verdict.NO_GO
    elif flags.soft or score.global_score < 50:
        verdict = Verdict.CONDITIONNEL
    else:
        verdict = Verdict.GO

    # Réserves = drapeaux souples + recommandations d'amélioration.
    conditions = flags.soft + score.recommendations
    return StudyResult(
        verdict=verdict,
        score=score,
        disqualifiers=flags.hard,
        conditions=conditions,
        assumptions={
            "regles": "moteur de score d'aptitude VNC (déterministe)",
            "score_global": f"{score.global_score:.0f}/100 (note {score.grade})",
            "ponderations": "ventilation/vitrage/inertie/isolation",
            "seuil_profondeur_simple_face": f"{DEPTH_RATIO_SINGLE_SIDED}× HSP",
            "seuil_chassis_haut_m": f"{TALL_SASH_M}",
        },
    )
