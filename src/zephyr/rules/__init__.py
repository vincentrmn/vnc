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
    ScoreBreakdown,
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

# Vitrage : « plus c'est bas, mieux c'est » (moins de surchauffe / déperditions).
# 100 jusqu'à 1/8 (12,5 %), décroissance linéaire jusqu'au maximum 20 %, plancher 20 au-delà.
GLAZING_OPTIMAL = 0.125  # 1/8 du ratio surface vitrée / surface de la pièce
GLAZING_MAX = 0.20  # au-delà : trop vitré
GLAZING_FLOOR_SCORE = 20.0

# Libellés FR des pièces (affichage du détail par critère).
_ROOM_FR: dict[str, str] = {
    "sejour": "Séjour", "salle_a_manger": "Salle à manger", "chambre": "Chambre",
    "cuisine": "Cuisine", "sdb": "Salle de bain", "wc": "WC", "entree": "Entrée",
    "circulation": "Circulation", "bureau": "Bureau", "buanderie": "Buanderie",
    "cellier": "Cellier", "dressing": "Dressing", "garage": "Garage",
    "technique": "Local technique", "autre": "Autre",
}


def _room_fr(room: object) -> str:
    name = getattr(room, "name", None)
    if name:  # nom explicite (ex. zones agrégées du mode rapide)
        return str(name)
    val = getattr(getattr(room, "label", None), "value", "autre")
    return _ROOM_FR.get(val, val.capitalize())


# Pièces de vie (le critère vitrage ne porte que sur elles ; « autre » = ex. salle de jeu).
_LIVING_LABELS = {"sejour", "salle_a_manger", "chambre", "cuisine", "bureau", "autre"}


def _is_living(room: object) -> bool:
    return getattr(getattr(room, "label", None), "value", "autre") in _LIVING_LABELS


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
    """Note la capacité géométrique à ventiler naturellement (traversant / châssis).

    Ne juge que les **pièces de vie** : les pièces de service (WC, sdb, circulation,
    technique…) ne pénalisent pas la note (les pièces humides ont une extraction
    dédiée, hors VNC) — elles restent affichées comme « non comptées » pour la
    transparence.
    """
    through_area = 0.0
    single_tall_area = 0.0
    single_low_area = 0.0
    interior_area = 0.0
    credited = 0.0
    tall = sash_height_m is not None and sash_height_m >= TALL_SASH_M
    rows: list[list[str]] = []
    living = [r for r in building.rooms if _is_living(r)]
    counted = living or list(building.rooms)  # garde-fou : aucune pièce de vie → tout compte
    counted_ids = {id(r) for r in counted}
    living_area = sum(r.area_m2 for r in counted) or 1.0

    for room in building.rooms:
        a = room.area_m2
        n_open = len(room.openings)
        n_fac = len(room.exterior_wall_orientations)
        if id(room) not in counted_ids:
            # Pièce de service : affichée mais non comptée dans la note.
            rows.append([_room_fr(room), f"{a:.1f}", str(n_fac), str(n_open),
                         "Service", "non comptée"])
            continue
        exposed = bool(room.exterior_wall_orientations) or bool(room.openings)
        if not exposed:
            interior_area += a
            credit = 0.0
            kind = "Aveugle"
        elif room.is_through:
            through_area += a
            credit = 1.0
            kind = "Traversante"
        elif tall:
            single_tall_area += a
            credit = 0.6
            kind = f"Mono-façade, châssis ≥ {TALL_SASH_M:g} m"
        else:
            single_low_area += a
            credit = 0.2  # plancher : exposé mais ni traversant ni châssis haut
            kind = "Mono-façade basse"
        base_pts = credit * 100.0
        # Pénalité de plan trop profond (la VNC ne balaie plus le fond).
        deep = False
        ratio = room.depth_to_height_ratio
        if ratio is not None:
            limit = DEPTH_RATIO_CROSS if room.is_through else DEPTH_RATIO_SINGLE_SIDED
            if ratio > limit:
                credit *= 0.5
                deep = True
        credited += a * credit
        pts = f"{base_pts:.0f}" + (" × 0,5 (profonde)" if deep else "")
        rows.append([_room_fr(room), f"{a:.1f}", str(n_fac), str(n_open), kind, pts])

    score = 100.0 * credited / living_area
    through_pct = 100.0 * through_area / living_area

    def pct(x: float) -> str:
        return f"{100.0 * x / living_area:.0f}%"

    detail = (
        f"{through_pct:.0f}% de la surface traversante, "
        f"{pct(single_tall_area)} mono-façade châssis ≥ {TALL_SASH_M:g} m, "
        f"{pct(single_low_area)} mono-façade bas, {pct(interior_area)} aveugle"
    )
    reco: str | None = None
    if score < 70:
        if not tall:
            reco = (
                "Hauteur de châssis non confirmée ou < 1,5 m : viser des ouvrants ≥ 1,5 m "
                "pour activer le tirage mono-façade, et créer des transferts d'air vers "
                "les pièces aveugles ou profondes."
            )
        else:
            reco = (
                "Améliorer le balayage : transferts d'air vers les pièces aveugles, "
                "ouvrants traversants là où c'est possible."
            )
    breakdown = ScoreBreakdown(
        columns=["Pièce", "Surface m²", "Façades", "Châssis", "Type", "Points/100"],
        rows=rows,
        formula=(
            "Note = Σ(surface × points) ÷ surface des pièces de vie = "
            f"{credited:.0f} ÷ {living_area:.0f} = {score:.0f}/100 "
            "(pièces de service exclues)"
        ),
    )
    return ScoreCriterion(
        key="ventilation",
        label="Ventilation (traversant / châssis)",
        score=round(score, 1),
        weight=weight,
        detail=detail,
        scale=(
            f"Au prorata des surfaces des pièces de vie : traversante 100, châssis ≥ "
            f"{TALL_SASH_M:g} m 60, mono-façade basse 20, aveugle 0 (note divisée par 2 si la "
            "pièce est trop profonde). Pièces de service (WC, sdb, circulation…) non comptées."
        ),
        recommendation=reco,
        breakdown=breakdown,
    )


def _glazing_score(ratio: float) -> float:
    """Note de vitrage (0–100) pour un taux donné : plus c'est bas, mieux c'est."""
    if ratio <= GLAZING_OPTIMAL:
        return 100.0
    if ratio >= GLAZING_MAX:
        return GLAZING_FLOOR_SCORE
    frac = (ratio - GLAZING_OPTIMAL) / (GLAZING_MAX - GLAZING_OPTIMAL)
    return 100.0 - (100.0 - GLAZING_FLOOR_SCORE) * frac


def _glazing_criterion(building: Building, envelope: EnvelopeData, weight: float) -> ScoreCriterion:
    """Note le taux de surface vitrée : plus il est bas, mieux c'est (surchauffe/déperditions)."""
    # On ne raisonne que sur les pièces de vie (le service borgne ne doit pas compter).
    living = [r for r in building.rooms if _is_living(r) and r.area_m2 > 0]
    target = living or [r for r in building.rooms if r.area_m2 > 0]
    has_openings = any(r.openings for r in target)
    scale_txt = (
        f"Plus le taux est bas, mieux c'est : ≤ {GLAZING_OPTIMAL:.1%} (1/8) = 100, "
        f"décroissance linéaire jusqu'au maximum {GLAZING_MAX:.0%}, "
        f"plancher {GLAZING_FLOOR_SCORE:.0f} au-delà. Sans châssis tracé : 0."
    )

    # Priorité au MESURÉ : si des châssis sont tracés, on note CHAQUE pièce de vie
    # (taux de la pièce → note de la pièce), puis on agrège au prorata de la surface.
    # Le ratio du CPE n'est utilisé qu'en repli (aucun châssis tracé) ; sinon note nulle.
    if has_openings:
        rows: list[list[str]] = []
        weighted = 0.0
        living_area = 0.0
        worst: tuple[float, str] | None = None
        for r in target:
            g = sum(op.area_m2 for op in r.openings)
            rr = g / r.area_m2
            rs = _glazing_score(rr)
            weighted += rs * r.area_m2
            living_area += r.area_m2
            rows.append([_room_fr(r), f"{g:.1f}", f"{r.area_m2:.1f}", f"{rr:.1%}", f"{rs:.0f}"])
            if rr > GLAZING_MAX and (worst is None or rr > worst[0]):
                worst = (rr, _room_fr(r))
        score = weighted / living_area if living_area else 100.0
        glaz_tot = sum(sum(op.area_m2 for op in r.openings) for r in target)
        ratio = glaz_tot / living_area if living_area else 0.0
        src = "châssis tracés (mesuré par pièce de vie)"
        reco = (
            f"{worst[1]} : taux de vitrage {worst[0]:.0%} (> {GLAZING_MAX:.0%}) — risque de "
            "surchauffe/déperditions ; protections solaires ou réduction des surfaces vitrées."
        ) if worst else None
        breakdown = ScoreBreakdown(
            columns=["Pièce", "Châssis m²", "Surface m²", "Taux", "Note"],
            rows=rows,
            formula=(
                "Note = moyenne des notes pièces pondérée par surface = "
                f"{score:.0f}/100 (pièces de vie uniquement ; taux moyen {ratio:.1%})."
            ),
        )
        return ScoreCriterion(
            key="vitrage", label="Vitrage (taux de surface vitrée)",
            score=round(score, 1), weight=weight,
            detail=f"taux de vitrage moyen (pièces de vie) = {ratio:.0%} (source : {src})",
            scale=scale_txt, recommendation=reco, breakdown=breakdown,
        )

    if envelope.glazing_to_floor_ratio is not None:
        ratio = envelope.glazing_to_floor_ratio
        score = _glazing_score(ratio)
        reco = (
            f"Taux de vitrage élevé ({ratio:.0%} > {GLAZING_MAX:.0%}) : risque de surchauffe et "
            "de déperditions ; protections solaires (sud/ouest) ou réduction des surfaces vitrées."
        ) if ratio > GLAZING_MAX else None
        return ScoreCriterion(
            key="vitrage", label="Vitrage (taux de surface vitrée)",
            score=round(score, 1), weight=weight,
            detail=f"taux de vitrage / plancher = {ratio:.0%} (source : CPE ou saisie)",
            scale=scale_txt, recommendation=reco,
            breakdown=ScoreBreakdown(
                columns=["Élément", "Valeur"],
                rows=[["Taux de vitrage", f"{ratio:.1%}"], ["Source", "CPE ou saisie"],
                      ["Note", f"{score:.0f}/100"]],
                formula=f"Note depuis le taux déclaré {ratio:.1%} → {score:.0f}/100.",
            ),
        )

    return ScoreCriterion(
        key="vitrage", label="Vitrage (taux de surface vitrée)",
        score=0.0, weight=weight,
        detail="aucun châssis tracé (taux de vitrage = 0)",
        scale=scale_txt,
        recommendation=(
            "Aucun châssis n'a été tracé : ajouter les ouvrants sur les façades pour "
            "permettre la ventilation naturelle et l'éclairage."
        ),
        breakdown=ScoreBreakdown(
            columns=["Élément", "Valeur"],
            rows=[["Châssis tracés", "aucun"], ["Note", "0/100"]],
            formula="Sans châssis tracé, le taux de vitrage n'est pas exploitable : note = 0.",
        ),
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
    fr = {
        InertiaClass.LOURDE: "Lourde", InertiaClass.MOYENNE: "Moyenne",
        InertiaClass.LEGERE: "Légère",
    }
    rows = [
        [fr.get(c, c.value) + (" (retenue)" if c is cls else ""), f"{_INERTIA_SCORE[c]:.0f}/100"]
        for c in (InertiaClass.LOURDE, InertiaClass.MOYENNE, InertiaClass.LEGERE)
    ]
    return ScoreCriterion(
        key="inertie",
        label="Inertie / masse (composition des parois)",
        score=round(score, 1),
        weight=weight,
        detail=f"classe d'inertie : {cls.value} (lue du CPE / composition des parois)",
        scale="Lourde = 100, moyenne = 60, légère = 25 (stockage de fraîcheur nocturne).",
        recommendation=reco,
        breakdown=ScoreBreakdown(
            columns=["Classe d'inertie", "Note"],
            rows=rows,
            formula=f"Classe retenue : {fr.get(cls, cls.value).lower()} → {score:.0f}/100.",
        ),
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
            detail="U non renseignés (CPE manquant) : note neutre par défaut",
            scale="U mur 0,15 → 100 jusqu'à 1,0 → 0 (poids 70 %) ; Uw 0,8 → 100 jusqu'à 2,5 → 0.",
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
    rows: list[list[str]] = []
    if u_wall is not None:
        ws = wall_score(u_wall)
        parts.append(ws * 0.7)
        bits.append(f"U mur {u_wall:.2f}")
        rows.append([f"Murs (U = {u_wall:.2f})", f"{ws:.0f}/100", "70 %"])
    if u_win is not None:
        vs = win_score(u_win)
        parts.append(vs * 0.3)
        bits.append(f"Uw {u_win:.2f}")
        rows.append([f"Vitrages (Uw = {u_win:.2f})", f"{vs:.0f}/100", "30 %"])
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
        scale="U mur 0,15→100 jusqu'à 1,0→0 (poids 70 %) ; Uw 0,8→100 jusqu'à 2,5→0 (30 %).",
        recommendation=reco,
        breakdown=ScoreBreakdown(
            columns=["Paroi", "Sous-note", "Poids"],
            rows=rows,
            formula=f"Note = moyenne pondérée des sous-notes = {score:.0f}/100.",
        ),
    )


def _site_flags(site: SiteContext) -> _SiteFlags:
    flags = _SiteFlags()
    if site.pollution_high:
        flags.hard.append(
            "Pollution ou pollen élevés : air extérieur peu admissible sans filtration ; "
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
