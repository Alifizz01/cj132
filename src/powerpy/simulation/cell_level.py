"""Cell-level electrical model -- the leaf of the composition tree.

A :class:`CellModel` wraps a frozen :class:`~powerpy.schemas.CellParameters`
and derives the four operating points (Isc, Imp, Vmp, Voc) at any
:class:`Environment` directly from the schema's begin-of-life points, its
temperature coefficients and its radiation-degradation curves.

The I-V curve itself is produced **analytically** from a single-diode model
(:func:`single_diode_iv`) fitted to those four points (:func:`fit_rseries`).
This keeps the whole simulation self-contained: no native ngspice shared
library -- and no legacy-format cell file -- is required to generate the
curves the report figures consume.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from powerpy.schemas import CellParameters
from powerpy.simulation.base import SimNode
from powerpy.simulation.environment import Environment
from powerpy.simulation.cell_condition import CellCondition, resolve_cell_env


# --------------------------------------------------------------------------
# Single-diode model
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DiodeParams:
    """Five-parameter single-diode model of one cell, plus its sweep bound.

    The terminal relation is::

        I = Iph - I0 * (exp((V + I*Rs) / Vt) - 1) - (V + I*Rs) / Rsh
    """

    iph: float   # photo (short-circuit) current  [A]
    i0: float    # diode saturation current       [A]
    vt: float    # diode thermal voltage  n*kT/q  [V]
    rs: float    # lumped series resistance        [ohm]
    rsh: float   # shunt resistance                [ohm]
    voc: float   # open-circuit voltage (sweep upper bound) [V]


def fit_rseries(isc: float, imp: float, vmp: float, voc: float) -> DiodeParams:
    """Closed-form R-series single-diode fit from the four datasheet points.

    Mirrors the algebra of the legacy ``electric.RSeriesModel`` (shunt branch
    taken as effectively open).  Returns a degenerate-but-safe set when the
    cell delivers no current (``imp <= 0``), so dark / failed cells do not
    raise.
    """
    if imp <= 0 or isc <= 0 or voc <= 0:
        return DiodeParams(iph=max(isc, 0.0), i0=0.0, vt=1.0,
                           rs=0.0, rsh=1e9, voc=max(voc, 0.0))
    vt = (vmp * (isc - imp)) / imp
    i0 = isc / (np.exp(voc / vt) - 1.0)
    rs = (vt / imp) * np.log((isc - imp) / i0) - (vmp / imp)
    return DiodeParams(iph=isc, i0=i0, vt=vt,
                       rs=max(rs, 0.0), rsh=1e9, voc=voc)


def single_diode_iv(params: DiodeParams, *, step: float = 0.01,
                    n_min: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """Solve ``I(V)`` for the single-diode model over ``[0, Voc]``.

    The relation is implicit in ``I`` (because of the ``I*Rs`` drop); it is
    solved with a vectorised Newton iteration that converges in a handful of
    steps for physical parameters.  Returns ``(V, I)`` arrays with ``I``
    clipped to be non-negative.
    """
    p = params
    if p.voc <= 0 or p.iph <= 0:
        return np.array([0.0]), np.array([0.0])

    n = max(n_min, int(round(p.voc / step)) + 1)
    V = np.linspace(0.0, p.voc, n)
    I = np.full_like(V, p.iph)

    for _ in range(80):
        vd = V + I * p.rs
        e = np.exp(np.clip(vd / p.vt, -700.0, 700.0))
        f = p.iph - p.i0 * (e - 1.0) - vd / p.rsh - I
        df = -p.i0 * e * (p.rs / p.vt) - p.rs / p.rsh - 1.0
        delta = f / df
        I = I - delta
        if np.max(np.abs(delta)) < 1e-12:
            break

    I = np.clip(I, 0.0, None)
    return V, I


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _remaining_factor(curve, dose_1e14: float) -> float:
    """Interpolate a radiation remaining-factor curve at a given fluence.

    ``curve`` is a list of ``[fluence_e_per_cm2, factor]`` points (as stored in
    the cell JSON's ``degradation`` dict).  ``dose_1e14`` is the accumulated
    1 MeV-equivalent electron fluence in units of 1e14 e-/cm^2 (the Environment
    convention).  Interpolation is done in log-fluence and clamps at the ends;
    zero dose returns 1.0 (begin-of-life).
    """
    fluence = float(dose_1e14) * 1e14
    if not curve or fluence <= 0.0:
        return 1.0
    pts = sorted(curve, key=lambda p: p[0])
    xs = np.log10([max(float(p[0]), 1.0) for p in pts])
    ys = [float(p[1]) for p in pts]
    return float(np.interp(np.log10(fluence), xs, ys))


# --------------------------------------------------------------------------
# CellModel
# --------------------------------------------------------------------------
_NGSPICE_WARNED = False   # warn only once when ngspice is requested but absent


class CellModel(SimNode):
    """A single solar cell -- the leaf node.

    Construct it from a schema :class:`CellParameters`, then :meth:`apply` an
    :class:`Environment` to set the operating point.  The four operating points
    are derived from the schema; the I-V curve is then built analytically (no
    ngspice).
    """

    def __init__(self, params: CellParameters, name: str | None = None,
                 iv_engine: str = "analytic",
                 condition: "CellCondition | None" = None) -> None:
        self.params = params
        self.name = name or params.name
        self.condition = condition or CellCondition()
        self._env = resolve_cell_env(self.condition, Environment())
        # "analytic" = the self-contained single-diode model (no ngspice).
        # "ngspice"  = the vendored ngspice/PySpice path, used when the vendor
        #              is present; it falls back to analytic if it is not.
        self.iv_engine = iv_engine
        self._legacy = None   # lazily-built SchemaCellModel for the ngspice path

    def apply(self, env: Environment) -> None:
        """Resolve the per-cell condition onto the supplied base environment.

        Idempotent: ``resolve_cell_env`` always reads the *base* ``env`` handed
        down by the parent, never the already-resolved ``self._env``.  This
        relies on parents (String/Section/Panel/Array ``apply``) always passing
        the same base Environment down each solve, which they do.
        """
        self._env = resolve_cell_env(self.condition, env)

    def operating_points(self) -> tuple[float, float, float, float]:
        """(Isc, Imp, Vmp, Voc) at the current environment.

        Applies, to the begin-of-life schema points: the temperature
        coefficients (``%/C`` about the reference temperature), the
        radiation remaining-factors (current axis -> dose_i, voltage axis ->
        dose_v) and the pre-resolved current/voltage loss products.
        """
        e = self.params.electrical
        env = self._env
        dT = env.temperature_c - env.reference_temperature_c

        f_temp_i = 1.0 + (e.temp_coeff_isc / 100.0) * dT
        f_temp_v = 1.0 + (e.temp_coeff_voc / 100.0) * dT
        f_rad_i = _remaining_factor(e.degradation.get("isc"), env.dose_i)
        f_rad_v = _remaining_factor(e.degradation.get("voc"), env.dose_v)

        gain_i = f_temp_i * f_rad_i * env.current_loss
        gain_v = f_temp_v * f_rad_v * env.voltage_loss

        isc = e.isc_bol * gain_i
        imp = e.imp_bol * gain_i
        voc = e.voc_bol * gain_v
        vmp = e.vmp_bol * gain_v
        return isc, imp, vmp, voc

    def diode_params(self) -> DiodeParams:
        """Single-diode parameters at the current environment."""
        isc, imp, vmp, voc = self.operating_points()
        return fit_rseries(float(isc), float(imp), float(vmp), float(voc))

    def iv_curve(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (V, I) arrays for the I-V curve at the current environment.

        Uses the analytic single-diode model, unless ``iv_engine == "ngspice"``
        and the vendored ngspice runtime is available (then it runs real SPICE);
        if ngspice is absent or errors, it transparently falls back to analytic.
        """
        if self.iv_engine == "ngspice":
            iv = self._ngspice_iv_curve()
            if iv is not None:
                return iv
        return single_diode_iv(self.diode_params())

    def _ngspice_iv_curve(self):
        """Try the vendored ngspice/PySpice path; return None to fall back."""
        global _NGSPICE_WARNED
        try:
            with np.errstate(all="ignore"):   # mute legacy-math FP warnings
                if self._legacy is None:
                    from powerpy.cell_schema import CellModel as SchemaCellModel
                    self._legacy = SchemaCellModel(self.params)
                sc, e = self._legacy, self._env
                sc.set_temperature(e.temperature_c)
                sc.set_season(e.season)
                sc.set_dose(e.dose_i, e.dose_v)
                sc.remove_losses()
                sc.add_loss_i("current_loss", e.current_loss)
                sc.add_loss_v("voltage_loss", e.voltage_loss)
                df = sc._legacy_cell.calcIVCurve(step=0.01)   # runs ngspice
            v = np.asarray(df.index.values, dtype=float)
            i = np.asarray(df["current"].values, dtype=float)
            if v.size and i.size:
                return v, i
            return None
        except Exception as exc:   # ngspice vendor missing / DLL / runtime
            if not _NGSPICE_WARNED:
                import warnings
                warnings.warn(
                    f"iv_engine='ngspice' unavailable ({type(exc).__name__}: "
                    f"{exc}); falling back to the analytic single-diode model.",
                    RuntimeWarning, stacklevel=2)
                _NGSPICE_WARNED = True
            return None
