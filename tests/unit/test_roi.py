"""Tests du module `roi` — non-régression + invariants clés (CLAUDE.md §6, §13.3).

On vérifie :
  1. les chiffres de CAPEX/OPEX (golden values, garde de non-régression) ;
  2. l'effet **obligatoire** de la pénalité de chauffage : activer le terme
     dégrade exactement la VAN de l'économie VNC du PV du flux de pénalité —
     c'est la correction vs l'Excel d'origine ;
  3. la cohérence des sorties (break-even, fourchette, TCO).
"""

from __future__ import annotations

import pytest

from zephyr.roi import ROIParameters, compute_roi

# Preset par défaut (LU/Pommerloch) : surface = 40*75 + 1200 = 4200 m².
P = ROIParameters()


def test_derived_quantities() -> None:
    assert P.total_floor_area_m2 == pytest.approx(4200.0)
    assert P.total_volume_m3 == pytest.approx(10920.0)
    assert P.num_ouvrants == 168
    assert P.num_capteurs == 84
    assert P.num_bos_points == 168 + 84 + 1


def test_capex_golden() -> None:
    r = compute_roi(P, heating_penalty_eur_per_year=0.0)
    # VMC : 135 €/m² × 4200 × 1.10
    assert r.capex_vmc_eur == pytest.approx(135 * 4200 * 1.10)
    # VNC : somme des quantités × 1.10
    expected_vnc = (168 * 1400 + 84 * 350 + 3500 + 25000 + 12 * 4200 + 18000 + 22000 + 15000) * 1.10
    assert r.capex_vnc_eur == pytest.approx(expected_vnc)


def test_opex_year1_golden() -> None:
    r = compute_roi(P, heating_penalty_eur_per_year=0.0)
    fan_kwh = 10920 * 0.5 * 0.40 * 8760 / 1000
    expected_vmc = fan_kwh * 0.28 + 2.5 * 4200 + 1500
    assert r.opex_vmc_year1_eur == pytest.approx(expected_vmc)
    expected_vnc = 200 * 0.28 + 1.5 * 4200 + 253 * 20 + 1500
    assert r.opex_vnc_year1_eur == pytest.approx(expected_vnc)


def test_heating_penalty_is_in_vnc_opex() -> None:
    penalty = 4000.0
    r = compute_roi(P, heating_penalty_eur_per_year=penalty)
    assert r.opex_vnc_breakdown["penalite_chauffage"] == penalty


def test_heating_penalty_degrades_npv_by_pv_of_stream() -> None:
    """Activer la pénalité réduit la VAN d'économie VNC du PV exact du flux."""
    penalty = 4000.0
    r0 = compute_roi(P, heating_penalty_eur_per_year=0.0)
    rp = compute_roi(P, heating_penalty_eur_per_year=penalty)

    # PV du flux de pénalité (an 1..H), inflaté puis actualisé — calculé à part.
    pv_penalty = sum(
        penalty * (1 + P.inflation) ** (y - 1) / (1 + P.wacc) ** y
        for y in range(1, P.horizon_years + 1)
    )
    # L'économie VNC (VMC − VNC) baisse de pv_penalty (la VNC coûte plus cher).
    assert r0.npv_delta_eur - rp.npv_delta_eur == pytest.approx(pv_penalty)
    assert rp.npv_delta_eur < r0.npv_delta_eur


def test_penalty_never_implicitly_zero_must_be_passed() -> None:
    """`heating_penalty_eur_per_year` est keyword-only et obligatoire (§13.3)."""
    with pytest.raises(TypeError):
        compute_roi(P)  # type: ignore[call-arg]


def test_negative_penalty_rejected() -> None:
    with pytest.raises(ValueError):
        compute_roi(P, heating_penalty_eur_per_year=-100.0)


def test_outputs_consistency() -> None:
    r = compute_roi(P, heating_penalty_eur_per_year=4000.0)
    assert len(r.npv_delta_cumulative_eur) == P.horizon_years + 1
    assert r.npv_delta_cumulative_eur[-1] == pytest.approx(r.npv_delta_eur)
    assert r.tco_vmc_undiscounted_eur > 0
    assert r.tco_vnc_undiscounted_eur > 0
    # Les breakdowns somment au total.
    assert sum(r.capex_vnc_breakdown.values()) == pytest.approx(r.capex_vnc_eur)
    assert sum(r.opex_vmc_breakdown.values()) == pytest.approx(r.opex_vmc_year1_eur)
    assert r.warnings  # avertissements méthodologiques présents


def test_optional_posts_neutral_by_default() -> None:
    """Subvention/carbone/free-cooling/TVA = 0 par défaut → calcul identique (golden)."""
    r = compute_roi(P, heating_penalty_eur_per_year=0.0)
    # Aucune ligne carbone/free-cooling parasite quand les prix sont nuls.
    assert "cout_carbone" not in r.opex_vnc_breakdown
    assert "benefice_freecooling" not in r.opex_vnc_breakdown
    assert r.capex_vmc_eur == pytest.approx(135 * 4200 * 1.10)  # part fixe VMC = 0


def test_subsidy_and_geometry_override() -> None:
    """Subvention réduit la VAN VNC (mieux) ; override d'ouvrants depuis la géométrie."""
    base = compute_roi(P, heating_penalty_eur_per_year=0.0)
    subsidized = compute_roi(
        P.model_copy(update={"subsidy_vnc_eur": 50000.0}), heating_penalty_eur_per_year=0.0
    )
    assert subsidized.npv_delta_eur > base.npv_delta_eur  # aide VNC → économie VNC ↑
    # CAPEX affiché reste brut (subvention = flux an 0, pas dans le breakdown).
    assert subsidized.capex_vnc_eur == pytest.approx(base.capex_vnc_eur)
    p2 = P.model_copy(update={"num_ouvrants_override": 10})
    assert p2.num_ouvrants == 10


def test_calc_lines_traceable() -> None:
    """Chaque poste expose une formule (ROI à livre ouvert) et somme au total."""
    r = compute_roi(P, heating_penalty_eur_per_year=4000.0)
    assert r.calc_lines and all(line.formula for line in r.calc_lines)
    capex_vnc_lines = [x for x in r.calc_lines if x.section == "capex_vnc"]
    assert sum(x.value_eur for x in capex_vnc_lines) == pytest.approx(r.capex_vnc_eur)


def test_break_even_later_with_penalty() -> None:
    """La pénalité ne peut que retarder (ou laisser inchangé) le break-even."""
    r0 = compute_roi(P, heating_penalty_eur_per_year=0.0)
    rp = compute_roi(P, heating_penalty_eur_per_year=8000.0)
    be0 = r0.break_even_year if r0.break_even_year is not None else 10**9
    bep = rp.break_even_year if rp.break_even_year is not None else 10**9
    assert bep >= be0
