"""Radiation fluxes (1 MeV equivalent electron fluence) by launch config / phase / param."""
from dataclasses import dataclass
from enum import Enum

from powerpy.schemas._common import Phase


class LaunchConfig(str, Enum):
    SINGLE = "single"
    DUAL = "dual"


class FluxParam(str, Enum):
    """Which cell parameter the fluence applies to."""
    ISC = "isc"
    VOC = "voc"


@dataclass(frozen=True)
class RadiationFlux:
    name: str
    launch_config: LaunchConfig
    phase: Phase
    param: FluxParam
    value: float        # e/cm² (1 MeV equivalent electron fluence)
    unit: str = "e/cm2"
    source: str = ""


@dataclass(frozen=True)
class RadiationFluxCollection:
    items: tuple[RadiationFlux, ...]

    def by_phase(self, phase: Phase) -> "RadiationFluxCollection":
        return RadiationFluxCollection(
            tuple(f for f in self.items if f.phase == phase)
        )

    def by_launch_config(self, lc: LaunchConfig) -> "RadiationFluxCollection":
        return RadiationFluxCollection(
            tuple(f for f in self.items if f.launch_config == lc)
        )

    def by_param(self, p: FluxParam) -> "RadiationFluxCollection":
        return RadiationFluxCollection(
            tuple(f for f in self.items if f.param == p)
        )

    def lookup(
        self,
        *,
        launch_config: LaunchConfig,
        phase: Phase,
        param: FluxParam,
    ) -> float:
        """Get the single flux value matching all three keys."""
        matches = [
            f for f in self.items
            if f.launch_config == launch_config
            and f.phase == phase
            and f.param == param
        ]
        if not matches:
            raise KeyError(
                f"No radiation flux found for "
                f"launch_config={launch_config.value}, phase={phase.value}, param={param.value}"
            )
        if len(matches) > 1:
            raise ValueError(
                f"Multiple radiation fluxes found for "
                f"launch_config={launch_config.value}, phase={phase.value}, param={param.value}"
            )
        return matches[0].value

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return bool(self.items)
