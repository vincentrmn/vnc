"""Analyse de sensibilité du ROI — tornado (OAT) et indices de Sobol (SALib).

CLAUDE.md §6 : « Toujours afficher une analyse de sensibilité (tornado), pas un
point unique. » Drivers de référence : prix élec, WACC, nb d'ouvrants,
abonnement BOS, pénalité de chauffage.

- `tornado` : balayage *one-at-a-time* (le diagramme effectivement affiché).
- `sobol_indices` : sensibilité globale (variance) via SALib, pour aller plus
  loin quand on veut hiérarchiser les incertitudes croisées.
"""

from __future__ import annotations

import numpy as np

from zephyr.roi.engine import compute_roi
from zephyr.roi.parameters import ROIParameters
from zephyr.schemas.results import SensitivityEntry

# Nom réservé : la pénalité de chauffage n'est pas un champ de ROIParameters,
# c'est l'argument séparé de `compute_roi`.
HEATING_PENALTY_KEY = "heating_penalty_eur_per_year"


def default_tornado_specs(
    params: ROIParameters, heating_penalty_eur_per_year: float
) -> dict[str, tuple[float, float]]:
    """Bornes (low, high) par défaut pour les 5 drivers §6, autour du central."""
    return {
        "price_elec_eur_kwh": (params.price_elec_eur_kwh * 0.7, params.price_elec_eur_kwh * 1.3),
        "wacc": (max(0.0, params.wacc - 0.01), params.wacc + 0.02),
        # nb d'ouvrants via la surface couverte par ouvrant (plus dense = plus d'ouvrants).
        "vnc_m2_per_ouvrant": (params.vnc_m2_per_ouvrant * 0.8, params.vnc_m2_per_ouvrant * 1.2),
        "bos_subscription_eur_per_point_year": (
            params.bos_subscription_eur_per_point_year * 0.5,
            params.bos_subscription_eur_per_point_year * 1.5,
        ),
        HEATING_PENALTY_KEY: (
            heating_penalty_eur_per_year * 0.5,
            heating_penalty_eur_per_year * 1.5,
        ),
    }


def _npv_at(params: ROIParameters, heating_penalty: float, param_name: str, value: float) -> float:
    """VAN delta lorsque `param_name` prend `value` (les autres au central)."""
    if param_name == HEATING_PENALTY_KEY:
        return compute_roi(params, heating_penalty_eur_per_year=value).npv_delta_eur
    updated = params.model_copy(update={param_name: value})
    return compute_roi(updated, heating_penalty_eur_per_year=heating_penalty).npv_delta_eur


def tornado(
    params: ROIParameters | None = None,
    *,
    heating_penalty_eur_per_year: float,
    specs: dict[str, tuple[float, float]] | None = None,
) -> list[SensitivityEntry]:
    """Diagramme tornado OAT sur la VAN delta, trié par amplitude décroissante."""
    p = params or ROIParameters()
    specs = specs or default_tornado_specs(p, heating_penalty_eur_per_year)

    entries: list[SensitivityEntry] = []
    for name, (low, high) in specs.items():
        entries.append(
            SensitivityEntry(
                parameter=name,
                low_value=low,
                high_value=high,
                output_low=_npv_at(p, heating_penalty_eur_per_year, name, low),
                output_high=_npv_at(p, heating_penalty_eur_per_year, name, high),
            )
        )
    entries.sort(key=lambda e: e.swing, reverse=True)
    return entries


def monte_carlo(
    params: ROIParameters | None = None,
    *,
    heating_penalty_eur_per_year: float,
    specs: dict[str, tuple[float, float]] | None = None,
    n: int = 500,
    seed: int = 0,
) -> dict[str, float]:
    """Distribution de la VAN delta et du break-even par tirage Monte-Carlo.

    Échantillonne uniformément les drivers §6 dans leurs bornes (mêmes que le
    tornado) → P10/médiane/P90 de la VAN et du break-even. Tient la promesse §6
    (fourchette, pas un point unique). Renvoie un dict de percentiles.
    """
    p = params or ROIParameters()
    specs = specs or default_tornado_specs(p, heating_penalty_eur_per_year)
    names = list(specs.keys())
    rng = np.random.default_rng(seed)
    lows = np.array([specs[k][0] for k in names])
    highs = np.array([specs[k][1] for k in names])
    sample = rng.uniform(lows, highs, size=(n, len(names)))

    horizon_plus = p.horizon_years + 1
    npvs = np.empty(n)
    bes = np.empty(n)
    for i in range(n):
        row = sample[i]
        hp = heating_penalty_eur_per_year
        update = {}
        for name, val in zip(names, row, strict=True):
            if name == HEATING_PENALTY_KEY:
                hp = float(val)
            else:
                update[name] = float(val)
        pp = p.model_copy(update=update) if update else p
        r = compute_roi(pp, heating_penalty_eur_per_year=hp)
        npvs[i] = r.npv_delta_eur
        bes[i] = r.break_even_year if r.break_even_year is not None else horizon_plus
    return {
        "npv_p10": float(np.percentile(npvs, 10)),
        "npv_p50": float(np.percentile(npvs, 50)),
        "npv_p90": float(np.percentile(npvs, 90)),
        "be_p10": float(np.percentile(bes, 10)),
        "be_p50": float(np.percentile(bes, 50)),
        "be_p90": float(np.percentile(bes, 90)),
        "prob_favorable": float((npvs > 0).mean()),
    }


def sobol_indices(
    params: ROIParameters | None = None,
    *,
    heating_penalty_eur_per_year: float,
    specs: dict[str, tuple[float, float]] | None = None,
    n_samples: int = 256,
    seed: int = 0,
) -> dict[str, float]:
    """Indices de Sobol du 1er ordre (S1) sur la VAN delta, via SALib.

    Sensibilité globale par décomposition de variance — complète le tornado OAT
    quand on veut tenir compte des interactions. Renvoie ``{param: S1}``.
    """
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import sobol as sobol_sample

    p = params or ROIParameters()
    specs = specs or default_tornado_specs(p, heating_penalty_eur_per_year)
    names = list(specs.keys())
    bounds = [list(specs[n]) for n in names]
    problem = {"num_vars": len(names), "names": names, "bounds": bounds}

    param_values = sobol_sample.sample(problem, n_samples, seed=seed)

    def evaluate(row: list[float]) -> float:
        update = {n: v for n, v in zip(names, row, strict=True) if n != HEATING_PENALTY_KEY}
        hp = heating_penalty_eur_per_year
        for n, v in zip(names, row, strict=True):
            if n == HEATING_PENALTY_KEY:
                hp = v
        updated = p.model_copy(update=update) if update else p
        return compute_roi(updated, heating_penalty_eur_per_year=hp).npv_delta_eur

    y = np.array([evaluate(list(row)) for row in param_values])
    si = sobol_analyze.analyze(problem, y, seed=seed)
    return {name: float(s1) for name, s1 in zip(names, si["S1"], strict=True)}
