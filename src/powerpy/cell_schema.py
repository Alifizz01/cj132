# -*- coding: utf-8 -*-
"""Schema-aware cell model -- bridge between CellParameters and legacy cell physics.

This module provides a modernized cell interface that:
  1. Accepts CellParameters (schema-aware) instead of raw cell_type strings
  2. Uses the same proven physics from the legacy cell.py
  3. Works seamlessly with the simulation layer

The cell_schema.CellModel is the primary interface for simulations.
It wraps the legacy cell.cell class internally, loading data via the JSON
file references already resolved in CellParameters.

NOTE: This is NOT the same as simulation/cell_level.py's CellModel.
      simulation/cell_level.py will use (wrap) this class.
"""
from __future__ import annotations

from powerpy.schemas import CellParameters
from powerpy.cell import cell as LegacyCell
from powerpy.datamgmt import getCellData, getDiodeData


class CellModel:
    """Schema-aware wrapper around the legacy cell class.
    
    Provides the same physics interface but accepts CellParameters
    (which already has file paths resolved) instead of cell type strings.
    """

    def __init__(self, params: CellParameters):
        """Initialize from schema.
        
        Args:
            params: CellParameters with resolved file paths and electrical data
        """
        self.params = params
        
        # Load config and regressors from the JSON files referenced in params
        cell_config, cell_regressors = getCellData(str(params.reference_file))
        diode_config = getDiodeData(str(params.diode_reference_file))
        
        # Create the legacy cell with the loaded configuration
        # We pass None as cell_type since we're loading directly
        self._legacy_cell = LegacyCell(
            cell_type=None,
            model="RSeriesModel",
            diode_type=None,
            localCellFile=False,
            localDiodeFile=False,
        )
        
        # Manually populate the loaded configs
        self._legacy_cell.config = {**cell_config, **diode_config}
        self._legacy_cell.regressors = cell_regressors
        self._legacy_cell.type = params.name
        self._legacy_cell.temperature = cell_config.get("t_ref", 28)

    # Delegate all physics operations to the legacy cell
    def set_dose(self, dose_i: float, dose_v: float) -> None:
        """Set radiation dose in units of 1e14 e/cm²."""
        self._legacy_cell.setDose(dose_i, dose_v)

    def set_temperature(self, temperature_c: float) -> None:
        """Set cell temperature in °C."""
        self._legacy_cell.setTemperature(temperature_c)

    def set_season(self, season_factor: float) -> None:
        """Set season factor or season string (SS/WS/VEX/AEX)."""
        self._legacy_cell.setSeason(season_factor)

    def add_loss_i(self, name: str, factor: float, verbose: bool = False) -> None:
        """Add a multiplicative loss factor on current."""
        self._legacy_cell.addLossI(name, factor, verbose=verbose)

    def add_loss_v(self, name: str, factor: float, verbose: bool = False) -> None:
        """Add a multiplicative loss factor on voltage."""
        self._legacy_cell.addLossV(name, factor, verbose=verbose)

    def set_angles(self, alpha: float, beta: float) -> None:
        """Set solar incidence angles."""
        self._legacy_cell.setAngles(alpha, beta)

    def set_season_angle(self, season_angle: float) -> None:
        """Set seasonal angle offset."""
        self._legacy_cell.setSeasonAngle(season_angle)

    def remove_losses(self) -> None:
        """Remove all loss factors."""
        self._legacy_cell.removeLosses()

    def prepare_model(self):
        """Prepare the electrical model with current environment."""
        return self._legacy_cell.prepareModel()

    def build_model(self, name=None, dark=False):
        """Build ngspice model string."""
        return self._legacy_cell.buildModel(name=name, dark=dark)

    def calc_voc(self):
        """Calculate open-circuit voltage."""
        return self._legacy_cell.calcVoc()

    def calc_isc(self):
        """Calculate short-circuit current."""
        return self._legacy_cell.calcIsc()

    def current_at_voltage(self, voltage: float) -> float:
        """Simulate current at specified voltage."""
        return self._legacy_cell.currentAtVoltage(voltage)

    def power_at_voltage(self, voltage: float) -> float:
        """Simulate power at specified voltage."""
        return self._legacy_cell.powerAtVoltage(voltage)

    # Properties for inspection
    @property
    def temperature(self) -> float:
        return self._legacy_cell.temperature

    @property
    def season(self) -> float:
        return self._legacy_cell.season

    @property
    def doses(self) -> dict:
        return self._legacy_cell.doses

    @property
    def losses_i(self) -> dict:
        return self._legacy_cell.lossesI

    @property
    def losses_v(self) -> dict:
        return self._legacy_cell.lossesV
