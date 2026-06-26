"""Tests de l'analyse de sensibilité ROI (tornado + Sobol)."""

from __future__ import annotations

from zephyr.roi import ROIParameters, tornado
from zephyr.roi.sensitivity import HEATING_PENALTY_KEY, sobol_indices

P = ROIParameters()
PENALTY = 4000.0


def test_tornado_covers_reference_drivers() -> None:
    """Les 5 drivers §6 sont présents dans le tornado."""
    bars = tornado(P, heating_penalty_eur_per_year=PENALTY)
    names = {b.parameter for b in bars}
    assert {
        "price_elec_eur_kwh",
        "wacc",
        "vnc_m2_per_ouvrant",
        "bos_subscription_eur_per_point_year",
        HEATING_PENALTY_KEY,
    } <= names


def test_tornado_sorted_by_swing_desc() -> None:
    bars = tornado(P, heating_penalty_eur_per_year=PENALTY)
    swings = [b.swing for b in bars]
    assert swings == sorted(swings, reverse=True)
    assert all(b.swing >= 0 for b in bars)


def test_heating_penalty_has_real_effect() -> None:
    bars = {b.parameter: b for b in tornado(P, heating_penalty_eur_per_year=PENALTY)}
    assert bars[HEATING_PENALTY_KEY].swing > 0


def test_sobol_indices_smoke() -> None:
    """SALib tourne et renvoie un S1 par driver (sensibilité globale, §6)."""
    s1 = sobol_indices(P, heating_penalty_eur_per_year=PENALTY, n_samples=16)
    assert HEATING_PENALTY_KEY in s1
    assert len(s1) == 5


def test_monte_carlo_percentiles_ordered() -> None:
    """Monte-Carlo : P10 ≤ P50 ≤ P90 sur la VAN, proba dans [0,1]."""
    from zephyr.roi import ROIParameters
    from zephyr.roi.sensitivity import monte_carlo

    mc = monte_carlo(ROIParameters(), heating_penalty_eur_per_year=4000.0, n=120, seed=1)
    assert mc["npv_p10"] <= mc["npv_p50"] <= mc["npv_p90"]
    assert 0.0 <= mc["prob_favorable"] <= 1.0
