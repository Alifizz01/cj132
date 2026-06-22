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


def _regressor_factor(reg: dict, dose_1e14: float) -> float:
    """Remaining factor from a measured ``r_*`` regressor curve.

    Unlike :func:`_remaining_factor` (which reads the coarse 3-point
    ``degradation`` placeholder in absolute fluence), the manufacturer's
    ``r_isc``/``r_imp``/``r_vmp``/``r_voc`` curves are stored as
    ``{"dose": [...], "value": [...]}`` with the dose axis already in the
    Environment's ``1e14 e-/cm^2`` units -- so the dose is read directly and
    linearly interpolated (clamped at the ends).  Missing/empty curve -> 1.0.
    """
    if not reg:
        return 1.0
    xs = reg.get("dose")
    ys = reg.get("value")
    if not xs or not ys:
        return 1.0
    return float(np.interp(float(dose_1e14), xs, ys))


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

        Mirrors the legacy ``cell.prepareModel`` formula: the begin-of-life
        points are degraded by the measured radiation remaining-factors per
        parameter (r_isc/r_imp on dose_i, r_vmp/r_voc on dose_v), then shifted by
        the **additive**, dose-dependent temperature coefficients
        (isc_dt/imp_dt/vmp_dt/voc_dt, in A/K or V/K, about the reference
        temperature). Finally the current/voltage loss products and the
        sun-intensity ``season`` (current axis) are applied multiplicatively.

        When the measured regressor curves are absent the model falls back to the
        coarse 3-point ``degradation`` placeholder with simple ``%/C`` temperature
        coefficients.
        """
        e = self.params.electrical
        env = self._env
        t_ref = env.reference_temperature_c
        temp = env.temperature_c
        dT = temp - t_ref

        reg = e.regressors or {}
        if "r_imp" in reg or "r_isc" in reg:
            # radiation remaining-factors (current axis -> dose_i, voltage -> dose_v)
            rf_isc = _regressor_factor(reg.get("r_isc"), env.dose_i)
            rf_imp = _regressor_factor(reg.get("r_imp"), env.dose_i)
            rf_voc = _regressor_factor(reg.get("r_voc"), env.dose_v)
            rf_vmp = _regressor_factor(reg.get("r_vmp"), env.dose_v)
            # additive, dose-dependent temperature coefficients [A/K, V/K]
            isc_dt = _regressor_factor(reg.get("isc_dt"), env.dose_i)
            imp_dt = _regressor_factor(reg.get("imp_dt"), env.dose_i)
            vmp_dt = _regressor_factor(reg.get("vmp_dt"), env.dose_v)
            voc_dt = _regressor_factor(reg.get("voc_dt"), env.dose_v)
            # below 0 C the legacy model blends imp_dt toward isc_dt
            if temp <= 0:
                imp_dt = (isc_dt * (-temp) + imp_dt * t_ref) / (t_ref - temp)
            isc = e.isc_bol * rf_isc + isc_dt * dT
            imp = e.imp_bol * rf_imp + imp_dt * dT
            vmp = e.vmp_bol * rf_vmp + vmp_dt * dT
            voc = e.voc_bol * rf_voc + voc_dt * dT
        else:
            # placeholder fallback: 3-point degradation + simple %/C temperature
            f_temp_i = 1.0 + (e.temp_coeff_isc / 100.0) * dT
            f_temp_v = 1.0 + (e.temp_coeff_voc / 100.0) * dT
            rf_i = _remaining_factor(e.degradation.get("isc"), env.dose_i)
            rf_v = _remaining_factor(e.degradation.get("voc"), env.dose_v)
            isc = e.isc_bol * f_temp_i * rf_i
            imp = e.imp_bol * f_temp_i * rf_i
            voc = e.voc_bol * f_temp_v * rf_v
            vmp = e.vmp_bol * f_temp_v * rf_v

        # current/voltage loss products; sun intensity (season) scales the
        # photocurrent so it rides on the current axis.
        isc = isc * env.current_loss * env.season
        imp = imp * env.current_loss * env.season
        voc = voc * env.voltage_loss
        vmp = vmp * env.voltage_loss
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
