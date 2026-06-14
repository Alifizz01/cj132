"""High-level analysis helpers -- compose loader output into one run.

These functions are what ``test.py`` / the CLI / a notebook actually
calls.  They turn a loaded :class:`ReportMetadata` plus a few
operating-point knobs into a full :class:`SimulationResults`.

There is exactly one knob the schema does not yet carry: the loss
*axis* (current vs voltage).  Today every :class:`LossFactor` is a
scalar multiplier; the convention used here is:

* loss names starting with ``loss_v_``  -> applied as VOLTAGE loss
* every other name                       -> applied as CURRENT loss

When the schema grows a ``axis`` field, replace
:func:`_split_losses_by_axis` with a direct reading of it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from powerpy.schemas import (
    ReportMetadata,
    Phase,
    Level,
    LaunchConfig,
    FluxParam,
)
from powerpy.simulation.array_level import ArrayModel, build_from_report
from powerpy.simulation.environment import Environment
from powerpy.simulation.results import (
    LevelResult,
    SimulationResults,
    summarize,
)


# ---------------------------------------------------------------- losses
_VOLTAGE_LOSS_PREFIX = "loss_v_"


def _split_losses_by_axis(
    losses,
    *,
    voltage_prefix: str = _VOLTAGE_LOSS_PREFIX,
) -> tuple[float, float]:
    """Return (current_loss_product, voltage_loss_product)."""
    cur, volt = 1.0, 1.0
    for f in losses:
        if f.name.lower().startswith(voltage_prefix):
            volt *= f.value
        else:
            cur *= f.value
    return cur, volt


# ---------------------------------------------------------------- environment
def environment_for_phase(
    report: ReportMetadata,
    *,
    phase: Phase,
    launch_config: LaunchConfig = LaunchConfig.SINGLE,
    temperature_c: float | None = None,
    season: float = 1.0,
    angle_alpha_deg: float = 0.0,
    angle_beta_deg: float = 0.0,
    albedo_w_m2: float = 0.0,
    loss_levels: Iterable[Level] = (Level.CELL,),
    voltage_loss_prefix: str = _VOLTAGE_LOSS_PREFIX,
) -> Environment:
    """Resolve dose, losses and irradiance for one phase into an Environment.

    ``temperature_c`` falls back to mission's pva_temperature if not given.
    If pva_temperature is also missing, uses 25°C as a default.
    """
    if temperature_c is None:
        # Try to get pva_temperature from mission operating points
        try:
            temperature_c = report.mission.lookup(
                name="pva_temperature",
                launch_config=launch_config,
                phase=phase,
            )
        except KeyError:
            # Default to 25°C if not available
            temperature_c = 25.0

    # collect cell-axis losses for this phase
    losses = report.losses.by_phase(phase)
    losses_cell_axis = tuple(
        f for f in losses if f.level in tuple(loss_levels)
    )
    cur_loss, volt_loss = _split_losses_by_axis(
        losses_cell_axis, voltage_prefix=voltage_loss_prefix)

    # dose lookups; tolerate missing entries gracefully
    def _dose(param: FluxParam) -> float:
        try:
            raw = report.radiation_fluxes.lookup(
                launch_config=launch_config, phase=phase, param=param)
        except KeyError:
            return 0.0
        return raw / 1.0e14                       # legacy convention

    return Environment(
        temperature_c=temperature_c,
        dose_i=_dose(FluxParam.ISC),
        dose_v=_dose(FluxParam.VOC),
        season=season,
        angle_alpha_deg=angle_alpha_deg,
        angle_beta_deg=angle_beta_deg,
        albedo_w_m2=albedo_w_m2,
        current_loss=cur_loss,
        voltage_loss=volt_loss,
    )


# ---------------------------------------------------------------- run
def run(array: ArrayModel, env: Environment) -> SimulationResults:
    """Evaluate the array at one environment and summarize every level."""
    array.apply(env)
    return SimulationResults(
        environment=env,
        array=summarize(array),
        panels=tuple(summarize(p) for p in array.panels),
        sections=tuple(summarize(s) for p in array.panels
                       for s in p.sections),
    )


# ---------------------------------------------------------------- one-shot
@dataclass(frozen=True)
class AnalysisCase:
    """A single named operating point you want results for."""
    label: str
    phase: Phase
    launch_config: LaunchConfig = LaunchConfig.SINGLE
    temperature_c: float | None = None
    season: float = 1.0
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CompliancePoint:
    """A single (bus voltage -> current) check at a chosen V."""
    bus_voltage_v: float
    current_a: float
    power_w: float


@dataclass(frozen=True)
class CaseResult:
    """Full result of one named AnalysisCase."""
    case: AnalysisCase
    environment: Environment
    results: SimulationResults
    bus: CompliancePoint | None = None


def evaluate(
    report: ReportMetadata,
    cases: Iterable[AnalysisCase],
    *,
    bus_voltage_v: float | None = None,
    launch_config: LaunchConfig = LaunchConfig.SINGLE,
    build_kwargs: dict | None = None,
) -> list[CaseResult]:
    """Evaluate the array under every case.

    ``bus_voltage_v`` -- if given, also report I(V_bus) and P(V_bus) at
    the array terminals, per case. Default tries to get it from
    ``report.mission.lookup("bus_voltage", launch_config, phase)``.
    If not available, no bus compliance check is performed.
    """
    array = build_from_report(report, **(build_kwargs or {}))
    out: list[CaseResult] = []
    for case in cases:
        env = environment_for_phase(
            report,
            phase=case.phase,
            launch_config=case.launch_config,
            temperature_c=case.temperature_c,
            season=case.season,
            **case.extra,
        )
        res = run(array, env)
        
        # Determine bus voltage for this case
        case_bus_voltage = bus_voltage_v
        if case_bus_voltage is None:
            try:
                case_bus_voltage = report.mission.lookup(
                    name="bus_voltage",
                    launch_config=case.launch_config,
                    phase=case.phase,
                )
            except KeyError:
                case_bus_voltage = None
        
        # Calculate bus compliance if voltage is available
        bus = None
        if case_bus_voltage is not None:
            i_bus = array.current_at_voltage(case_bus_voltage)
            bus = CompliancePoint(
                bus_voltage_v=case_bus_voltage,
                current_a=float(i_bus),
                power_w=float(case_bus_voltage * i_bus),
            )
        
        out.append(CaseResult(case=case, environment=env, results=res, bus=bus))
    return out
