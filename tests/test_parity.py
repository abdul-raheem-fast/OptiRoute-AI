"""Parity: the exported weights must reproduce the frozen test-split numbers.

This is the load-bearing test of the whole demo. Every headline figure on the
dashboard (68.4% cost cut, 94.8% of flagship quality, $0.006023/query) comes
from routing/results/learned_router_report.csv, computed offline over the
official 282-query held-out test split. If the live RouterCore (the thing the
API actually runs) disagrees with those numbers, the dashboard is quoting
results the deployed router does not achieve.

The test re-runs the ONLINE path (RouterCore.route, per-query) over the exact
same test split that routing/learned_router.py evaluated, using the identical
loader (routing.splits.load_splits) and the identical routing_matrix pivots,
then compares against the frozen report.
"""
import json

import numpy as np
import pytest

from routing.config import MODELS, OUT_DIR, RESULTS_DIR, SEED

# Frozen ground truth: routing/results/learned_router_report.csv, row
# "learned cascade (t=0.95)" (mirrored in results_bundle.md).
FROZEN_ACCURACY_PCT = 84.04
FROZEN_AVG_COST_PER_QUERY = 0.006023
FROZEN_QUALITY_VS_STRONGEST_PCT = 94.8
FROZEN_STRONGEST_ACCURACY_PCT = 88.65

# Tolerances per the verification brief: genuine float/measurement noise only.
ACC_TOL_PTS = 0.5
COST_REL_TOL = 0.02
QUALITY_TOL_PTS = 0.5

TEST_SPLIT_SIZE = 282


def test_official_split_is_seed42_and_282(splits):
    """Guard: we are evaluating the SAME split the frozen numbers used."""
    manifest = json.loads((OUT_DIR / "splits_manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == SEED == 42
    assert manifest["split_counts"]["test"] == TEST_SPLIT_SIZE
    assert len(splits["test"]) == TEST_SPLIT_SIZE


def test_frozen_report_matches_documented_constants():
    """Guard: the csv the dashboard quotes still says 84.04 / 94.8 / 0.006023."""
    import pandas as pd

    rep = pd.read_csv(RESULTS_DIR / "learned_router_report.csv")
    row = rep[rep["policy"].str.startswith("learned cascade")].iloc[0]
    assert float(row["accuracy_pct"]) == pytest.approx(FROZEN_ACCURACY_PCT, abs=1e-9)
    assert float(row["quality_vs_strongest_pct"]) == pytest.approx(
        FROZEN_QUALITY_VS_STRONGEST_PCT, abs=1e-9
    )
    assert float(row["avg_cost_per_query"]) == pytest.approx(
        FROZEN_AVG_COST_PER_QUERY, abs=1e-9
    )
    strong = rep[rep["policy"] == "always-strongest"].iloc[0]
    assert float(strong["accuracy_pct"]) == pytest.approx(
        FROZEN_STRONGEST_ACCURACY_PCT, abs=1e-9
    )


def test_live_router_parity_on_frozen_test_split(core, splits, matrix, test_queries):
    """Run the ONLINE router over all 282 test queries and compare to frozen."""
    assert len(test_queries) == TEST_SPLIT_SIZE

    K, C = matrix["K"], matrix["C"]
    qids = [q[0] for q in test_queries]

    chosen_idx = []
    for _qid, text, cls in test_queries:
        d = core.route(text, cls, core.t_star)  # the exact path /api/route uses
        assert d["chosen_model"] in MODELS
        chosen_idx.append(MODELS.index(d["chosen_model"]))

    rows = np.arange(len(qids))
    acc = K.loc[qids].values[rows, chosen_idx].mean() * 100.0
    cost = C.loc[qids].values[rows, chosen_idx].mean()
    acc_strongest = K.loc[qids][MODELS[-1]].mean() * 100.0
    quality = acc / acc_strongest * 100.0

    assert acc_strongest == pytest.approx(FROZEN_STRONGEST_ACCURACY_PCT, abs=ACC_TOL_PTS)
    assert acc == pytest.approx(FROZEN_ACCURACY_PCT, abs=ACC_TOL_PTS), (
        f"live accuracy {acc:.2f}% != frozen {FROZEN_ACCURACY_PCT}% "
        f"(tolerance +/-{ACC_TOL_PTS} pts)"
    )
    assert cost == pytest.approx(FROZEN_AVG_COST_PER_QUERY, rel=COST_REL_TOL), (
        f"live avg cost ${cost:.6f} != frozen ${FROZEN_AVG_COST_PER_QUERY} "
        f"(tolerance {COST_REL_TOL:.0%})"
    )
    assert quality == pytest.approx(FROZEN_QUALITY_VS_STRONGEST_PCT, abs=QUALITY_TOL_PTS), (
        f"live quality-vs-GPT-5 {quality:.2f}% != frozen "
        f"{FROZEN_QUALITY_VS_STRONGEST_PCT}% (tolerance +/-{QUALITY_TOL_PTS} pts)"
    )


def test_live_router_rounds_to_the_frozen_figures(core, test_queries, matrix):
    """The frozen csv stores values ROUNDED (2dp accuracy, 6dp cost, 1dp
    quality). The honest exact-parity invariant is therefore: the live router,
    rounded the same way the report rounds, reproduces the frozen figures
    digit-for-digit. (Comparing unrounded live values to the rounded constants
    at 1e-6 would be a false expectation - the first run measured
    84.042553...% vs the stored 84.04.)"""
    K, C = matrix["K"], matrix["C"]
    qids = [q[0] for q in test_queries]
    idx = [MODELS.index(core.route(q[1], q[2], core.t_star)["chosen_model"])
           for q in test_queries]
    rows = np.arange(len(qids))
    acc = K.loc[qids].values[rows, idx].mean() * 100.0
    cost = C.loc[qids].values[rows, idx].mean()
    acc_strongest = K.loc[qids][MODELS[-1]].mean() * 100.0
    quality = acc / acc_strongest * 100.0

    assert round(acc, 2) == FROZEN_ACCURACY_PCT
    assert round(cost, 6) == FROZEN_AVG_COST_PER_QUERY
    assert round(quality, 1) == FROZEN_QUALITY_VS_STRONGEST_PCT
    # And the unrounded live values sit inside the rounding interval, i.e. the
    # residual is pure display rounding, far tighter than the stated tolerance.
    assert abs(acc - FROZEN_ACCURACY_PCT) < 0.005
    assert abs(cost - FROZEN_AVG_COST_PER_QUERY) < 5e-7
    assert abs(quality - FROZEN_QUALITY_VS_STRONGEST_PCT) < 0.05
