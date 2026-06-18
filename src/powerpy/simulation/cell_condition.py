"""Per-cell condition (approach B, Phase 1) and its pure env resolver.

A :class:`CellCondition` is a frozen, fully-defaulted description of one cell's
state.  :func:`resolve_cell_env` folds EVERY field onto a base
:class:`Environment` (no field is wired-but-inert):

  * shade x incidence x life x imp_factor x sqrt(pmax_factor) ride the CURRENT
    axis -- the only current knob the analytic ``operating_points`` reads is
    ``current_loss`` (which never reads ``season``).
  * sqrt(pmax_factor) also rides the VOLTAGE axis (``voltage_loss``) so a Pmax
    multiplier ``m`` scales the cell's peak power by ~m (sqrt(m)*sqrt(m)).
  * shade x incidence is ALSO written to ``season`` for the ngspice path.
  * ``failed_open`` is realised as a near-dead but WELL-FORMED cell.  The
    LOAD-BEARING analytic effect is ``current_loss *= failed_open_epsilon``
    (tiny Isc); ``season *= failed_open_epsilon`` is set only for the ngspice
    path; ``voltage_loss`` is untouched so full Voc keeps the parallel
    ``combine_parallel`` (caps at smallest child Voc) from collapsing.  This is
    why it isolates only the affected series string in ``combine_series`` (caps
    at smallest child Isc) instead of killing the section.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from powerpy.simulation.environment import Environment

_VALID_STATES = ("healthy", "failed_open")


@dataclass(frozen=True)
class CellCondition:
    state: str = "healthy"
    shade: float = 1.0           # transmittance [0,1]; 1.0 = unshaded
    life: float = 1.0            # chipping current derate [0,1]; 1.0 = full
    incidence: float = 1.0       # cosine factor [0,1]; 1.0 = normal
    cell_type: str | None = None
    imp_factor: float = 1.0      # per-cell manufacturing current multiplier
    pmax_factor: float = 1.0     # per-cell manufacturing Pmax multiplier
    failed_open_epsilon: float = 1e-6  # current/season floor for a failed cell

    def __post_init__(self):
        if self.state not in _VALID_STATES:
            raise ValueError("CellCondition.state must be one of %s, got %r"
                             % (_VALID_STATES, self.state))
        for name in ("shade", "life", "incidence"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError("CellCondition.%s must be in [0, 1], got %r"
                                 % (name, v))
        for name in ("imp_factor", "pmax_factor"):
            if getattr(self, name) <= 0:
                raise ValueError("CellCondition.%s must be > 0, got %r"
                                 % (name, getattr(self, name)))


def resolve_cell_env(cond: CellCondition, base_env: Environment) -> Environment:
    """Pure: fold ``cond`` onto ``base_env`` -> a new Environment (no mutation).

    Consumes EVERY CellCondition field so none is produced-but-unread.
    """
    if cond.state == "failed_open":
        # LOAD-BEARING for the analytic engine: tiny Isc comes from current_loss
        # (operating_points ignores season).  season mirrors it for ngspice.
        season = base_env.season * cond.failed_open_epsilon
        current_loss = base_env.current_loss * cond.failed_open_epsilon
        voltage_loss = base_env.voltage_loss     # keep full Voc -> isolates string
        return dataclasses.replace(
            base_env, season=season,
            current_loss=current_loss, voltage_loss=voltage_loss)

    pmax_axis = math.sqrt(cond.pmax_factor)
    current_loss = (base_env.current_loss
                    * cond.life * cond.shade * cond.incidence
                    * cond.imp_factor * pmax_axis)
    voltage_loss = base_env.voltage_loss * pmax_axis
    season = base_env.season * cond.shade * cond.incidence
    return dataclasses.replace(
        base_env, season=season,
        current_loss=current_loss, voltage_loss=voltage_loss)
