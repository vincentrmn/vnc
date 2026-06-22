"""Module `climate` — lecture EPW/TMY, degrés-heures, géométrie solaire (Phase 2).

Calcule, à partir d'un fichier météo .epw (déterministe, CLAUDE.md §4) :
  - les séries horaires utiles au screen thermique (température, vent, solaire) ;
  - les degrés-heures (chauffe / surchauffe) ;
  - l'irradiance sur surfaces verticales par orientation (apports solaires).

Le module reste volontairement léger : parseur EPW maison + géométrie solaire
auto-portée (pas de dépendance lourde requise pour le cœur thermique).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from zephyr.schemas import Orientation

# Azimuts solaires conventionnels par orientation (0° = Sud, +Ouest, −Est),
# convention usuelle en physique du bâtiment (hémisphère Nord).
_ORIENTATION_AZIMUTH_DEG: dict[Orientation, float] = {
    Orientation.S: 0.0,
    Orientation.SW: 45.0,
    Orientation.W: 90.0,
    Orientation.NW: 135.0,
    Orientation.N: 180.0,
    Orientation.NE: -135.0,
    Orientation.E: -90.0,
    Orientation.SE: -45.0,
}

HOURS_PER_YEAR = 8760


@dataclass
class ClimateData:
    """Séries météo horaires (8760 valeurs) + métadonnées de site.

    Les champs solaires `dni`/`dhi` permettent une transposition correcte sur
    les façades verticales ; `ghi` reste disponible pour les degrés-heures et les
    contrôles simples.
    """

    dry_bulb_c: list[float]
    wind_speed_ms: list[float]
    ghi_w_m2: list[float]
    dni_w_m2: list[float] = field(default_factory=list)
    dhi_w_m2: list[float] = field(default_factory=list)
    latitude_deg: float = 49.6  # Luxembourg par défaut
    longitude_deg: float = 6.1
    timezone_h: float = 1.0
    source: str | None = None

    def __post_init__(self) -> None:
        n = len(self.dry_bulb_c)
        if not self.dni_w_m2:
            self.dni_w_m2 = [0.0] * n
        if not self.dhi_w_m2:
            self.dhi_w_m2 = [0.0] * n

    @property
    def n_hours(self) -> int:
        return len(self.dry_bulb_c)


# --------------------------------------------------------------------------- #
# Lecture EPW
# --------------------------------------------------------------------------- #
def read_epw(path: str | Path) -> ClimateData:
    """Lit un fichier météo EnergyPlus (.epw) et renvoie les séries horaires.

    Le format EPW : 8 lignes d'en-tête puis une ligne CSV par heure. Champs
    (0-based) utilisés : 6 = température sèche (°C), 13 = GHI (Wh/m²),
    14 = DNI (Wh/m²), 15 = DHI (Wh/m²), 21 = vitesse du vent (m/s).
    """
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 9:
        raise ValueError(f"EPW invalide (trop court) : {path}")

    # En-tête LOCATION : champs 6,7,8 = latitude, longitude, fuseau.
    loc = lines[0].split(",")
    try:
        lat = float(loc[6])
        lon = float(loc[7])
        tz = float(loc[8])
    except (IndexError, ValueError):
        lat, lon, tz = 49.6, 6.1, 1.0

    dry, wind, ghi, dni, dhi = [], [], [], [], []
    for raw in lines[8:]:
        if not raw.strip():
            continue
        f = raw.split(",")
        if len(f) < 22:
            continue
        dry.append(float(f[6]))
        ghi.append(float(f[13]))
        dni.append(float(f[14]))
        dhi.append(float(f[15]))
        wind.append(float(f[21]))

    return ClimateData(
        dry_bulb_c=dry,
        wind_speed_ms=wind,
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        latitude_deg=lat,
        longitude_deg=lon,
        timezone_h=tz,
        source=str(path.name),
    )


# --------------------------------------------------------------------------- #
# Degrés-heures
# --------------------------------------------------------------------------- #
def degree_hours(temperatures_c: list[float], base_c: float, *, mode: str = "above") -> float:
    """Cumul des degrés-heures par rapport à un seuil.

    Args:
        temperatures_c: série horaire de températures (°C).
        base_c: seuil de référence (°C).
        mode: ``"above"`` (surchauffe : Σ max(T−base, 0)) ou ``"below"``
            (chauffe : Σ max(base−T, 0)).
    """
    if mode == "above":
        return sum(max(t - base_c, 0.0) for t in temperatures_c)
    if mode == "below":
        return sum(max(base_c - t, 0.0) for t in temperatures_c)
    raise ValueError("mode doit être 'above' ou 'below'")


# --------------------------------------------------------------------------- #
# Géométrie solaire (auto-portée) — irradiance sur surfaces verticales
# --------------------------------------------------------------------------- #
def _solar_position(
    lat_deg: float, lon_deg: float, tz_h: float, doy: int, hour: float
) -> tuple[float, float]:
    """Position solaire approximée (NOAA simplifié) → (altitude, azimut) en degrés.

    azimut : 0° = Sud, positif vers l'Ouest. Suffisant pour un screen (pré-étude).
    """
    lat = math.radians(lat_deg)
    # Déclinaison (Cooper) et équation du temps (approx).
    decl = math.radians(23.45 * math.sin(math.radians(360 * (284 + doy) / 365)))
    b = math.radians(360 * (doy - 81) / 364)
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)  # minutes
    # Heure solaire vraie.
    standard_meridian = 15.0 * tz_h
    solar_time = hour + (4 * (lon_deg - standard_meridian) + eot) / 60.0
    hour_angle = math.radians(15.0 * (solar_time - 12.0))
    sin_alt = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(hour_angle)
    sin_alt = max(-1.0, min(1.0, sin_alt))
    altitude = math.asin(sin_alt)
    # Azimut (convention Sud=0, Ouest+).
    cos_az = (math.sin(altitude) * math.sin(lat) - math.sin(decl)) / (
        math.cos(altitude) * math.cos(lat) + 1e-9
    )
    cos_az = max(-1.0, min(1.0, cos_az))
    azimuth = math.acos(cos_az)
    if hour_angle < 0:
        azimuth = -azimuth
    return math.degrees(altitude), math.degrees(azimuth)


def vertical_irradiance(
    climate: ClimateData, orientation: Orientation, *, ground_albedo: float = 0.2
) -> list[float]:
    """Irradiance globale (W/m²) reçue par une façade verticale d'orientation donnée.

    Modèle de transposition isotrope : direct (projeté via l'angle d'incidence) +
    diffus ciel (vue 0,5) + réfléchi sol (vue 0,5). Niveau « pré-étude ».
    """
    n = climate.n_hours
    surf_az = math.radians(_ORIENTATION_AZIMUTH_DEG[orientation])
    out = [0.0] * n
    for i in range(n):
        doy = i // 24 + 1
        hour = i % 24 + 0.5  # milieu de l'heure
        alt_deg, sun_az_deg = _solar_position(
            climate.latitude_deg, climate.longitude_deg, climate.timezone_h, doy, hour
        )
        alt = math.radians(alt_deg)
        if alt <= 0:
            # Pas de direct ; un peu de diffus/réfléchi possible.
            diffuse = 0.5 * climate.dhi_w_m2[i]
            reflected = 0.5 * ground_albedo * climate.ghi_w_m2[i]
            out[i] = diffuse + reflected
            continue
        sun_az = math.radians(sun_az_deg)
        # cos de l'angle d'incidence sur surface verticale.
        cos_inc = math.cos(alt) * math.cos(sun_az - surf_az)
        cos_inc = max(0.0, cos_inc)
        direct = climate.dni_w_m2[i] * cos_inc
        diffuse = 0.5 * climate.dhi_w_m2[i]
        reflected = 0.5 * ground_albedo * climate.ghi_w_m2[i]
        out[i] = direct + diffuse + reflected
    return out


# --------------------------------------------------------------------------- #
# Climat synthétique (tests / démo, sans fichier EPW)
# --------------------------------------------------------------------------- #
def synthetic_climate(
    *,
    annual_mean_c: float = 9.5,
    seasonal_amplitude_c: float = 9.0,
    daily_amplitude_c: float = 5.0,
    peak_ghi_w_m2: float = 850.0,
    latitude_deg: float = 49.6,
) -> ClimateData:
    """Génère un climat horaire synthétique « type Luxembourg » (8760 h).

    Sinusoïde saisonnière + cycle diurne pour la température ; cloche solaire
    diurne modulée par la saison. **Non validé** — pour tests/démos uniquement.
    """
    dry, wind, ghi, dni, dhi = [], [], [], [], []
    for i in range(HOURS_PER_YEAR):
        doy = i // 24 + 1
        hour = i % 24
        seasonal = -math.cos(2 * math.pi * (doy - 15) / 365)  # min en janvier
        daily = -math.cos(2 * math.pi * (hour - 3) / 24)  # min ~3h
        t = annual_mean_c + seasonal_amplitude_c * seasonal + daily_amplitude_c * daily
        dry.append(round(t, 2))
        wind.append(3.0)
        # Solaire : non nul de jour, modulé par la saison.
        if 6 <= hour <= 18:
            day_factor = math.sin(math.pi * (hour - 6) / 12)
            season_factor = 0.4 + 0.6 * (0.5 + 0.5 * seasonal)
            g = peak_ghi_w_m2 * day_factor * season_factor
        else:
            g = 0.0
        ghi.append(round(g, 1))
        dni.append(round(g * 0.85, 1))
        dhi.append(round(g * 0.15, 1))
    return ClimateData(
        dry_bulb_c=dry,
        wind_speed_ms=wind,
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        latitude_deg=latitude_deg,
        source="synthetic",
    )
