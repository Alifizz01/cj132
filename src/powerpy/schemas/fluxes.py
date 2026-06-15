"""Radiation fluxes (1 MeV equivalent electron fluence) by launch config / phase / param.

Launch config and flux param are plain strings (project-defined); matching is
case-insensitive via :func:`norm`.
"""
from dataclasses import dataclass

from powerpy.schemas._common import norm


class LaunchConfig:
    """Convenience constants for launch configuration (plain str)."""
    SINGLE = "single"
    DUAL = "dual"


class FluxParam:
    """Convenience constants for which cell parameter the fluence applies to."""
    ISC = "isc"
    VOC = "voc"


@dataclass(frozen=True)
class RadiationFlux:
    name: str
    launch_config: str
    phase: str
    param: str
    value: float        # e/cm² (1 MeV equivalent electron fluence)
    unit: str = "e/cm2"
    source: str = ""


@dataclass(frozen=True)
class RadiationFluxCollection:
    items: tuple[RadiationFlux, ...]

    def by_phase(self, phase: str) -> "RadiationFluxCollection":
        return RadiationFluxCollection(
            tuple(f for f in self.items if norm(f.phase) == norm(phase))
        )

    def by_launch_config(self, lc: str) -> "RadiationFluxCollection":
        return RadiationFluxCollection(
            tuple(f for f in self.items if norm(f.launch_config) == norm(lc))
        )

    def by_param(self, p: str) -> "RadiationFluxCollection":
        return RadiationFluxCollection(
            tuple(f for f in self.items if norm(f.param) == norm(p))
        )

    def lookup(self, *, launch_config: str, phase: str, param: str) -> float:
        """Get the single flux value matching all three keys (case-insensitive)."""
        matches = [
            f for f in self.items
            if norm(f.launch_config) == norm(launch_config)
            and norm(f.phase) == norm(phase)
            and norm(f.param) == norm(param)
        ]
        if not matches:
            raise KeyError(
                f"No radiation flux found for "
                f"launch_config={launch_config}, phase={phase}, param={param}"
            )
        if len(matches) > 1:
            raise ValueError(
                f"Multiple radiation fluxes found for "
                f"launch_config={launch_config}, phase={phase}, param={param}"
            )
        return matches[0].value

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return bool(self.items)
