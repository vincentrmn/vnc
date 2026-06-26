"""Paramètres du modèle ROI — *tout* est exposé, rien n'est en dur.

Porté du comparatif Excel ``comparatif_VNC_VMC`` (cas Pommerloch, mixte
logements + bureaux, LU). Cf. CLAUDE.md §6.

Les valeurs par défaut sont le **preset LU/Pommerloch**. Elles ont vocation à
être surchargées par des presets régionaux (``data/presets/``). Aucune de ces
valeurs ne doit migrer en constante en dur dans le moteur de calcul.

⚠️ Garde-fou (CLAUDE.md §5, §13.3) : ``heating_penalty_eur_per_year`` n'est PAS
dans ce modèle de paramètres « marché ». C'est une *sortie de `thermal`*,
injectée séparément dans le calcul. Tant que `thermal` n'existe pas, on passe une
valeur conservatrice explicite à `compute_roi` — jamais 0, jamais un % de récup
posé en dur.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field


class ROIParameters(BaseModel):
    """Hypothèses bâtiment, financières et de coûts du comparatif VNC vs VMC DF."""

    # ------------------------------------------------------------------ #
    # Bâtiment
    # ------------------------------------------------------------------ #
    num_logements: int = Field(default=40, ge=0, description="Nombre de logements.")
    surface_per_logement_m2: float = Field(
        default=75.0, ge=0, description="Surface moyenne par logement (m²)."
    )
    surface_tertiaire_m2: float = Field(
        default=1200.0, ge=0, description="Surface tertiaire / bureaux (m²)."
    )
    hsp_m: float = Field(default=2.6, gt=0, description="Hauteur sous plafond moyenne (m).")

    # ------------------------------------------------------------------ #
    # Financier
    # ------------------------------------------------------------------ #
    horizon_years: int = Field(default=20, ge=1, description="Horizon d'analyse (ans).")
    wacc: float = Field(default=0.03, ge=0, description="Taux d'actualisation (WACC).")
    inflation: float = Field(
        default=0.025, ge=0, description="Inflation annuelle OPEX (hors énergie)."
    )
    energy_inflation: float | None = Field(
        default=None, description="Inflation annuelle de l'énergie (défaut = inflation générale)."
    )
    price_elec_eur_kwh: float = Field(
        default=0.28, gt=0, description="Prix de l'électricité (€/kWh, Eurostat LU)."
    )
    contingency_rate: float = Field(
        default=0.10, ge=0, description="Provision aléas sur CAPEX (fraction)."
    )
    tva_rate: float = Field(
        default=0.0, ge=0, description="TVA appliquée au CAPEX (affichage TTC)."
    )

    # ------------------------------------------------------------------ #
    # Postes optionnels (neutres par défaut = 0 → n'altèrent pas le calcul)
    # ------------------------------------------------------------------ #
    subsidy_vnc_eur: float = Field(default=0.0, ge=0, description="Subvention/aide CAPEX VNC (€).")
    subsidy_vmc_eur: float = Field(default=0.0, ge=0, description="Subvention/aide CAPEX VMC (€).")
    carbon_price_eur_t: float = Field(default=0.0, ge=0, description="Prix du carbone (€/tCO₂).")
    grid_carbon_kg_kwh: float = Field(
        default=0.0, ge=0, description="Facteur carbone du réseau élec (kgCO₂/kWh)."
    )
    freecooling_kwh_year: float = Field(
        default=0.0, ge=0, description="kWh de froid évités/an par free-cooling VNC (bénéfice)."
    )
    num_ouvrants_override: int | None = Field(
        default=None, ge=0, description="Nb d'ouvrants imposé (depuis la géométrie tracée)."
    )
    vmc_fixed_eur: float = Field(
        default=0.0, ge=0, description="Part fixe CAPEX VMC (centrale de base), symétrie des coûts."
    )

    # ------------------------------------------------------------------ #
    # CAPEX VMC DF — ratios €/m²
    # ------------------------------------------------------------------ #
    vmc_centrales_eur_m2: float = Field(default=45.0, ge=0)
    vmc_reseau_gaines_eur_m2: float = Field(default=35.0, ge=0)
    vmc_pose_cvc_eur_m2: float = Field(default=25.0, ge=0)
    vmc_regulation_eur_m2: float = Field(default=12.0, ge=0)
    vmc_etancheite_eur_m2: float = Field(default=8.0, ge=0)
    vmc_etudes_eur_m2: float = Field(default=6.0, ge=0)
    vmc_commissioning_eur_m2: float = Field(default=4.0, ge=0)

    # ------------------------------------------------------------------ #
    # CAPEX VNC — quantités
    # ------------------------------------------------------------------ #
    vnc_m2_per_ouvrant: float = Field(
        default=25.0, gt=0, description="Surface couverte par ouvrant motorisé (~1/25 m²)."
    )
    vnc_price_per_ouvrant_eur: float = Field(
        default=1400.0, ge=0, description="Prix posé d'un ouvrant motorisé (€)."
    )
    vnc_m2_per_capteur: float = Field(
        default=50.0, gt=0, description="Surface couverte par capteur 4-en-1."
    )
    vnc_price_per_capteur_eur: float = Field(default=350.0, ge=0)
    vnc_num_stations_meteo: int = Field(default=1, ge=0)
    vnc_price_station_meteo_eur: float = Field(default=3500.0, ge=0)
    vnc_bos_platform_eur: float = Field(
        default=25000.0, ge=0, description="Forfait plateforme BOS (gateways, edge, intégration)."
    )
    vnc_cablage_eur_m2: float = Field(default=12.0, ge=0)
    vnc_extraction_humide_eur: float = Field(
        default=18000.0,
        ge=0,
        description="CAPEX extraction dédiée pièces humides (hors VNC, cf. §6).",
    )
    vnc_std_engineering_eur: float = Field(
        default=22000.0, ge=0, description="Forfait STD + ingénierie VNC."
    )
    vnc_commissioning_hypercare_eur: float = Field(default=15000.0, ge=0)

    # ------------------------------------------------------------------ #
    # OPEX an 1 (avant inflation)
    # ------------------------------------------------------------------ #
    # VMC : énergie ventilateurs
    vmc_ach: float = Field(
        default=0.5, ge=0, description="Renouvellement d'air opérationnel VMC (vol/h)."
    )
    vmc_sfp_wh_m3: float = Field(
        default=0.40, ge=0, description="Puissance spécifique des ventilateurs (Wh/m³ d'air)."
    )
    vmc_operating_hours_year: float = Field(
        default=8760.0, ge=0, description="Heures de fonctionnement annuelles des ventilateurs."
    )
    vmc_maintenance_eur_m2_year: float = Field(
        default=2.5, ge=0, description="Maintenance VMC (filtres, etc.) €/m²/an."
    )

    # VNC
    vnc_actuator_energy_kwh_year: float = Field(
        default=200.0, ge=0, description="Énergie des actionneurs (kWh/an, total bâtiment)."
    )
    vnc_maintenance_eur_m2_year: float = Field(
        default=1.5, ge=0, description="Maintenance ouvrants/capteurs €/m²/an."
    )
    bos_subscription_eur_per_point_year: float = Field(
        default=20.0, ge=0, description="Abonnement BOS cloud €/point/an."
    )

    # Extraction pièces humides — OPEX commun aux deux scénarios
    wet_extraction_opex_eur_year: float = Field(default=1500.0, ge=0)

    # ------------------------------------------------------------------ #
    # Renouvellement à mi-vie
    # ------------------------------------------------------------------ #
    renewal_year: int = Field(default=12, ge=1, description="Année du renouvellement à mi-vie.")
    vmc_renewal_rate: float = Field(
        default=0.25, ge=0, description="Renouvellement VMC (~25 % du CAPEX)."
    )
    vnc_renewal_rate: float = Field(
        default=0.15, ge=0, description="Renouvellement VNC (~15 % du CAPEX)."
    )

    # ------------------------------------------------------------------ #
    # Grandeurs dérivées
    # ------------------------------------------------------------------ #
    @property
    def total_floor_area_m2(self) -> float:
        """Surface totale ventilée (m²)."""
        return self.num_logements * self.surface_per_logement_m2 + self.surface_tertiaire_m2

    @property
    def total_volume_m3(self) -> float:
        """Volume total ventilé (m³)."""
        return self.total_floor_area_m2 * self.hsp_m

    @property
    def num_ouvrants(self) -> int:
        """Nombre d'ouvrants motorisés : depuis la géométrie si fournie, sinon ratio."""
        if self.num_ouvrants_override is not None:
            return max(self.num_ouvrants_override, 1)
        return math.ceil(self.total_floor_area_m2 / self.vnc_m2_per_ouvrant)

    @property
    def energy_inflation_rate(self) -> float:
        """Inflation énergie effective (défaut = inflation générale)."""
        return self.energy_inflation if self.energy_inflation is not None else self.inflation

    @property
    def num_capteurs(self) -> int:
        """Nombre de capteurs 4-en-1 (arrondi au supérieur)."""
        return math.ceil(self.total_floor_area_m2 / self.vnc_m2_per_capteur)

    @property
    def num_bos_points(self) -> int:
        """Nombre de points BOS facturés (ouvrants + capteurs + stations)."""
        return self.num_ouvrants + self.num_capteurs + self.vnc_num_stations_meteo
