# -*- coding: utf-8 -*-
"""Grid Monte-Carlo failure study, WITH lateral conduction.

Ties the layout convention, the lateral-conduction solver and the Monte-Carlo
pattern generators together: for each candidate set of failed cells, build a
per-tile electrical-power map (failed cells driven into reverse bias), solve the
panel thermally, and record the peak temperature and how many tiles exceed the
melt limit. Ranking the runs tells you which failure positions/counts are most
damaging -- now accounting for heat spreading to neighbours.

Status: standalone (numpy); reuses montecarlo's pattern generators; tested.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Sequence

import numpy as np

try:
    from ..solve.thermal import solve_panel
    from . import montecarlo as mc
except ImportError:                    # loaded by file path for isolated testing
    from thermal import solve_panel
    import montecarlo as mc


def cell_indices(layout) -> List[int]:
    """Flat (row-major) indices of tiles that are real cells (can fail)."""
    powers = layout.prop_arrays()["generates_power"]
    return [int(i) for i in np.nonzero(powers)[0]]


def make_pe(layout, failed: Sequence[int], healthy_w: float = 1.1,
            reverse_w: float = -9.6) -> np.ndarray:
    """Per-tile electrical power: healthy cells extract ``healthy_w``; cells in
    ``failed`` dissipate ``reverse_w`` (negative); non-cells are 0."""
    powers = layout.prop_arrays()["generates_power"]
    pe = np.where(powers, healthy_w, 0.0)
    failed = set(int(i) for i in failed)
    for i in failed:
        if powers[i]:
            pe[i] = reverse_w
    return pe


def failure_sweep(layout, patterns: Sequence[Sequence[int]], *, t_limit_c: float,
                  healthy_w: float = 1.1, reverse_w: float = -9.6,
                  solve_kwargs: Optional[Dict] = None, workers: int = 1) -> List[Dict]:
    """Run every failure ``pattern`` (a set of failed flat tile-indices) through
    the lateral-conduction solver; record peak T and tiles-over-limit per run.

    The patterns are independent. With ``workers > 1`` they run concurrently on a
    thread pool: numpy/scipy release the GIL during the (BLAS/sparse) solve, so
    this gives a real speed-up without pickling, and works with file-path-loaded
    modules. Results keep their original ``run_id`` order.
    """
    solve_kwargs = dict(solve_kwargs or {})

    def _one(item):
        k, failed = item
        pe = make_pe(layout, failed, healthy_w, reverse_w)
        res = solve_panel(layout, p_elec=pe, **solve_kwargs)
        front = np.asarray(res.t_front_c, float)
        return {
            "run_id": k,
            "failed": [int(i) for i in failed],
            "n_failed": len(failed),
            "peak_t_c": round(float(front.max()), 3),
            "mean_t_c": round(float(front.mean()), 3),
            "n_over_limit": int((front >= t_limit_c).sum()),
            "converged": bool(res.converged),
        }

    items = list(enumerate(patterns))
    if workers and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(_one, items))     # map preserves order
    return [_one(it) for it in items]


def rank(records: Sequence[Dict], key: str = "peak_t_c") -> List[Dict]:
    """Most-damaging first (highest peak temperature)."""
    return sorted(records, key=lambda r: r.get(key, float("-inf")), reverse=True)


def position_sweep_patterns(layout) -> List[List[int]]:
    """One pattern per single failed cell (which single failure is worst?)."""
    return [[i] for i in cell_indices(layout)]


def count_sweep_patterns(layout, ks: Sequence[int], samples_per_k: int, seed: int = 0):
    """Random patterns of fixed failure counts k (reuses montecarlo)."""
    ids = [str(i) for i in cell_indices(layout)]
    out = mc.count_patterns(ids, ks=ks, samples_per_k=samples_per_k, seed=seed)
    return [[int(x) for x in pat] for pat in out]


def worst_case_search(layout, *, max_failures: int, t_limit_c: float,
                      solve_kwargs: Optional[Dict] = None,
                      healthy_w: float = 1.1, reverse_w: float = -9.6,
                      workers: int = 1) -> Dict:
    """GREEDY hunt for the most damaging set of failures (not random sampling).

    Start with no failures; at each step try failing each remaining cell *in
    addition* to those already chosen, and keep the one that pushes the peak
    temperature highest. Repeat up to ``max_failures``. Because lateral
    conduction lets adjacent hot cells reinforce one another, this finds the
    worst-case *cluster* that random sampling usually misses.

    Cost: O(max_failures x n_cells) panel solves (candidate evaluation per step is
    parallelised via ``workers``). Returns ``{failed, peak_t_c, trajectory}``;
    ``trajectory`` records the peak after each added failure. Deterministic.
    """
    solve_kwargs = dict(solve_kwargs or {})
    remaining = cell_indices(layout)
    chosen: List[int] = []
    trajectory: List[Dict] = []
    best_peak = float("-inf")
    for step in range(max_failures):
        if not remaining:
            break
        patterns = [chosen + [c] for c in remaining]
        recs = failure_sweep(layout, patterns, t_limit_c=t_limit_c,
                             healthy_w=healthy_w, reverse_w=reverse_w,
                             solve_kwargs=solve_kwargs, workers=workers)
        bi = max(range(len(recs)), key=lambda i: recs[i]["peak_t_c"])
        add = remaining[bi]
        chosen.append(int(add))
        remaining = [c for c in remaining if c != add]
        best_peak = recs[bi]["peak_t_c"]
        trajectory.append({"step": step + 1, "added": int(add),
                           "failed": list(chosen), "peak_t_c": best_peak,
                           "n_over_limit": recs[bi]["n_over_limit"]})
    return {"failed": chosen, "peak_t_c": best_peak, "trajectory": trajectory}


def auto_monte_carlo(layout, *, t_limit_c: float, solve_kwargs: Optional[Dict] = None,
                     p_fail: float = 0.05, target_se: float = 2.0, batch: int = 50,
                     max_runs: int = 2000, seed: int = 0,
                     healthy_w: float = 1.1, reverse_w: float = -9.6,
                     workers: int = 1) -> Dict:
    """Random failure sampling that STOPS itself when the estimate is tight enough.

    Draw random failure patterns (each cell fails with probability ``p_fail``) in
    batches; after each batch compute the standard error of the mean peak
    temperature and stop once it is <= ``target_se`` (or ``max_runs`` is reached) --
    so you don't run a fixed N forever (standard error shrinks like 1/sqrt(N)).
    Reproducible for a fixed ``seed``. Returns a summary + the records.
    """
    solve_kwargs = dict(solve_kwargs or {})
    ids = [str(c) for c in cell_indices(layout)]
    peaks: List[float] = []
    records: List[Dict] = []
    se = float("inf")
    stopped = "max_runs"
    run = 0
    while run < max_runs:
        n = min(batch, max_runs - run)
        pats = [[int(x) for x in p] for p in
                mc.random_patterns(ids, p_fail=p_fail, n_samples=n, seed=seed + run)]
        recs = failure_sweep(layout, pats, t_limit_c=t_limit_c,
                            healthy_w=healthy_w, reverse_w=reverse_w,
                            solve_kwargs=solve_kwargs, workers=workers)
        records.extend(recs)
        peaks.extend(r["peak_t_c"] for r in recs)
        run += n
        if len(peaks) >= 2:
            se = float(mc.standard_error(peaks))
            if se <= target_se:
                stopped = "converged"
                break
    mean_peak = float(sum(peaks) / len(peaks)) if peaks else float("nan")
    return {"n_runs": run, "mean_peak_c": round(mean_peak, 3),
            "standard_error": round(se, 4), "max_peak_c": round(max(peaks), 3) if peaks else None,
            "stopped": stopped, "records": records}
