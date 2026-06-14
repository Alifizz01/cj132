# -*- coding: utf-8 -*-
"""Monte-Carlo failure sweep over a Circuit.

Three sampling modes choose WHICH failures to simulate:

  * position -- fail each cell in turn (O(N) runs); find the worst location.
  * count    -- fail k random cells for k = 1..K; degradation vs #failures.
  * random   -- many random patterns; full distribution of outcomes.

The per-run evaluation (build circuit, plant failures, run the electro-thermal
solve, apply breakdown criteria, return a record) is injected as ``evaluate`` so
this driver stays independent of ngspice. Patterns are generated from a seeded
RNG for reproducibility.

Status: pattern generation, driver and ranking are standalone & tested with a
synthetic ``evaluate``; the production ``evaluate`` wires Circuit + electrothermal
+ breakdown (pending a clean ``cell.buildModel``).
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np

Pattern = Tuple[str, ...]
Record = Dict[str, object]


def position_patterns(cell_ids: Sequence[str]) -> List[Pattern]:
    """One single-cell failure per location."""
    return [(cid,) for cid in cell_ids]


def count_patterns(cell_ids: Sequence[str], ks: Iterable[int],
                   samples_per_k: int, seed: int = 0) -> List[Pattern]:
    """``samples_per_k`` random k-cell failure sets for each k in ``ks``."""
    rng = np.random.default_rng(seed)
    ids = np.asarray(cell_ids, dtype=object)
    out: List[Pattern] = []
    for k in ks:
        k = int(k)
        if k < 1 or k > len(ids):
            raise ValueError("k=%d out of range 1..%d" % (k, len(ids)))
        for _ in range(samples_per_k):
            pick = rng.choice(len(ids), size=k, replace=False)
            out.append(tuple(sorted(ids[pick].tolist())))
    return out


def random_patterns(cell_ids: Sequence[str], p_fail: float,
                    n_samples: int, seed: int = 0) -> List[Pattern]:
    """``n_samples`` patterns, each cell failing independently with prob p_fail."""
    if not (0.0 <= p_fail <= 1.0):
        raise ValueError("p_fail must be in [0,1]")
    rng = np.random.default_rng(seed)
    ids = np.asarray(cell_ids, dtype=object)
    out: List[Pattern] = []
    for _ in range(n_samples):
        mask = rng.random(len(ids)) < p_fail
        out.append(tuple(sorted(ids[mask].tolist())))
    return out


def run_sweep(patterns: Sequence[Pattern],
              evaluate: Callable[[Pattern], Record]) -> List[Record]:
    """Evaluate every failure pattern; return one record per run."""
    records: List[Record] = []
    for run_id, pat in enumerate(patterns):
        rec = dict(evaluate(pat))
        rec.setdefault("run_id", run_id)
        rec.setdefault("failed_ids", ",".join(pat))
        rec.setdefault("n_failed", len(pat))
        records.append(rec)
    return records


def rank(records: Sequence[Record], key: str = "max_temp_c",
         descending: bool = True) -> List[Record]:
    """Rank runs by a recorded metric (default: most-damaging first)."""
    return sorted(records, key=lambda r: r.get(key, float("nan")), reverse=descending)


def standard_error(values: Sequence[float]) -> float:
    """Standard error of the mean = s / sqrt(N)."""
    v = np.asarray(values, dtype=float)
    if v.size < 2:
        return float("nan")
    return float(np.std(v, ddof=1) / np.sqrt(v.size))


def runs_needed(se_now: float, n_now: int, se_target: float) -> int:
    """How many runs to reach a target standard error (SE ~ 1/sqrt(N))."""
    return int(np.ceil(n_now * (se_now / se_target) ** 2))
