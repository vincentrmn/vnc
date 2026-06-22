# `data/validation/` — bancs de validation thermique (IDA ICE)

Ce dossier contient les cas de **validation** du screen thermique : le couple
**entrées + sorties** d'études STD réalisées sous IDA ICE. Ils servent à vérifier
que le modèle 5R1C (`zephyr.thermal`) reproduit les répartitions de température
observées dans une **tolérance définie** (CLAUDE.md §6, §7).

> STD = **validation, pas entraînement**. Trop peu de cas pour généraliser ; mais
> c'est le banc qui de-risque l'approche déterministe au moindre coût.

## ⚠️ Confidentialité

Les exports STD/CPE **réels** sont des données clients sensibles : **jamais
committés** (cf. `.gitignore` et CLAUDE.md §11). Seuls sont versionnés :
- des cas **anonymisés** explicitement validés (`*.example.json`) ;
- ce README.

Les `*.idm` bruts et tout autre export client sont gitignorés.

## Format d'un cas (`*.example.json`)

```jsonc
{
  "name": "identifiant court",
  "description": "contexte anonymisé",
  "tolerance": {
    "mean_temp_c": 1.5,            // tolérance absolue sur la température moyenne (°C)
    "overheating_hours_rel": 0.20  // tolérance relative sur les heures de surchauffe
  },
  "inputs": {
    "building": { ... },           // géométrie réduite : pièces, surfaces, HSP, orientations
    "envelope": { ... },           // U, g, perméabilité (cf. EnvelopeData)
    "internal_gains_w_m2": 4.0,    // apports internes moyens
    "ventilation_ach": 0.5,
    "climate_epw": "data/climate/<fichier>.epw"
  },
  "expected": {                    // sorties IDA ICE (référence)
    "rooms": [
      { "id": "sejour", "season": "ete",   "mean_temp_c": 25.8, "overheating_hours": 320 },
      { "id": "sejour", "season": "hiver", "mean_temp_c": 20.4, "overheating_hours": 0 }
    ],
    "heating_demand_kwh_m2_year": 42.0
  }
}
```

Le harnais `tests/validation/test_thermal_calibration.py` rejoue le 5R1C sur ces
cas et compare aux `expected` dans la tolérance. Tant que `zephyr.thermal` n'est
pas implémenté (Phase 2), le test est **skippé** — mais le harnais est en place.
