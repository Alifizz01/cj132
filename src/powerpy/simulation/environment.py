"""Operating environment applied to the simulation tree.

The Environment carries everything that is *not* a fixed property of the
hardware: temperature, radiation dose, season (irradiance), pointing
angles, albedo, and pre-resolved loss multipliers.  It is a separate,
immutable object so the same array tree can be evaluated under many
conditions without rebuilding it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Environment:
    """One operating point for the whole array.

    Attributes
    ----------
    temperature_c
        Cell operating temperature, degrees Celsius.
    dose_i, dose_v
        Accumulated 1 MeV-equivalent electron fluence affecting the
        current and voltage parameters respectively, in units of
        1e14 e-/cm^2 (matches the legacy ``setDose`` convention).
    season
        Irradiance multiplier relative to AM0 (1367 W/m^2). 1.0 = AM0.
    angle_alpha_deg, angle_beta_deg
        Off-pointing angles of the array normal from the Sun line.
    albedo_w_m2
        Planet-reflected irradiance reaching the array, W/m^2.
    current_loss, voltage_loss
        Pre-resolved multiplicative loss factors applied at cell level.
        These are the *products* of every relevant LossFactor from the
        workbook, split by axis.  ``1.0`` means 'no loss applied yet'.
    reference_temperature_c
        Temperature at which the catalogue (BOL) points were quoted.
    """

    temperature_c: float = 28.0
    dose_i: float = 0.0
    dose_v: float = 0.0
    season: float = 1.0
    angle_alpha_deg: float = 0.0
    angle_beta_deg: float = 0.0
    albedo_w_m2: float = 0.0
    current_loss: float = 1.0
    voltage_loss: float = 1.0
    reference_temperature_c: float = 28.0
