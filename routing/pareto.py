"""Reusable Pareto-frontier analysis over measured model statistics.

A model is *dominated* when another model is at least as good on every
considered dimension and strictly better on at least one.  Dimensions carry an
explicit direction so the same code serves quality (higher is better) and
cost / latency (lower is better).

The frontier is always computed on MEASURED benchmark aggregates that the
caller supplies (train-split statistics in production, see routing.tune_mo),
never on invented values.  Three frontier flavours are supported because a
model that is globally dominated can still be the right choice under a
different deployment constraint:

  * global frontier            - all models, all three dimensions
  * quality-floor frontier     - only models clearing a quality floor
  * privacy-filtered frontier  - only models a deployment policy allows

Dominance is evaluated *within* the supplied candidate set, so filtering first
and re-running the frontier is exactly how the router reasons about eligibility.
"""
from __future__ import annotations

from typing import Mapping, Sequence

# dimension name -> +1 when higher is better, -1 when lower is better
DIRECTIONS: dict[str, int] = {"quality": 1, "cost": -1, "latency": -1}


def dominates(a: Mapping[str, float], b: Mapping[str, float],
              dims: Sequence[str] = ("quality", "cost", "latency")) -> bool:
    """True when point ``a`` dominates point ``b`` on ``dims``."""
    better = False
    for d in dims:
        da, db = a[d] * DIRECTIONS[d], b[d] * DIRECTIONS[d]
        if da < db:
            return False
        if da > db:
            better = True
    return better


def pareto_mask(points: Sequence[Mapping[str, float]],
                dims: Sequence[str] = ("quality", "cost", "latency")) -> list[bool]:
    """Per-point mask: True for members of the Pareto frontier."""
    return [not any(dominates(q, p, dims) for q in points if q is not p)
            for p in points]


def pareto_frontier(points: Sequence[Mapping[str, float]],
                    dims: Sequence[str] = ("quality", "cost", "latency")) -> list[int]:
    """Indices of the non-dominated points, in input order."""
    return [i for i, keep in enumerate(pareto_mask(points, dims)) if keep]


def dominated_by(points: Sequence[Mapping[str, float]],
                 dims: Sequence[str] = ("quality", "cost", "latency")) -> list[list[int]]:
    """For every point, the indices of the points that dominate it."""
    return [[j for j, q in enumerate(points) if dominates(q, p, dims)]
            for p in points]


def model_frontier(names: Sequence[str], stats: Mapping[str, Sequence[float]],
                   dims: Sequence[str] = ("quality", "cost", "latency"),
                   keep: Sequence[bool] | None = None) -> list[str]:
    """Frontier member names from per-model statistic columns.

    ``stats`` maps dimension -> one measured value per model (same order as
    ``names``).  ``keep`` optionally restricts the candidate set first (e.g. a
    privacy eligibility mask); dominance is then judged inside that set.
    """
    if keep is None:
        keep = [True] * len(names)
    idx = [i for i, k in enumerate(keep) if k]
    pts = [{d: float(stats[d][i]) for d in dims} for i in idx]
    front = pareto_frontier(pts, dims)
    return [names[idx[i]] for i in front]
