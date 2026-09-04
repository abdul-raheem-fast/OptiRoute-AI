"""Pareto-frontier analysis (requirement 2).

Covers the reusable primitives on synthetic points (so the dominance logic is
pinned independent of the benchmark), then the MEASURED frontiers in the fitted
artifact - including the rule that a globally dominated model is never discarded
outright because a privacy policy can re-admit it.
"""
from routing.config import MODELS
from routing.pareto import (
    dominated_by, dominates, model_frontier, pareto_frontier, pareto_mask,
)

# Dimensions: quality (higher better), cost (lower better), latency (lower better)
A = {"quality": 0.90, "cost": 0.020, "latency": 0.8}   # strong, pricey, fast
B = {"quality": 0.80, "cost": 0.001, "latency": 3.5}   # weaker, cheap, slow
C = {"quality": 0.70, "cost": 0.005, "latency": 4.0}   # dominated by B (all 3)
PTS = [A, B, C]


def test_dominates_requires_ge_all_and_gt_one():
    assert dominates(B, C)              # strictly better on all three dims
    assert not dominates(C, B)
    assert not dominates(A, A)          # equal is NOT strict dominance
    assert not dominates(A, B)          # A better quality+latency but pricier


def test_dominates_is_direction_aware():
    # A beats C on quality (0.90>0.70) and latency (0.8<4.0) but is PRICIER
    # (0.020>0.005), so A does not dominate C across all three dims.
    assert not dominates(A, C, dims=("quality", "cost", "latency"))
    # Drop cost and A does dominate C.
    assert dominates(A, C, dims=("quality", "latency"))


def test_pareto_mask_and_frontier_indices():
    # C is dominated by B; A and B are mutually non-dominated.
    assert pareto_mask(PTS) == [True, True, False]
    assert pareto_frontier(PTS) == [0, 1]


def test_dominated_by_lists_the_dominators():
    dom = dominated_by(PTS)
    assert dom == [[], [], [1]]         # only B (index 1) dominates C (index 2)


def test_model_frontier_respects_eligibility_subset():
    names = ["A", "B", "C"]
    stats = {"quality": [0.90, 0.80, 0.70],
             "cost": [0.020, 0.001, 0.005],
             "latency": [0.8, 3.5, 4.0]}
    # Full set: C is dominated -> frontier {A, B}.
    assert model_frontier(names, stats) == ["A", "B"]
    # Restrict to {A, C}: dominance is judged INSIDE the subset, and neither
    # dominates the other (A is pricier), so both survive.
    assert set(model_frontier(names, stats, keep=[True, False, True])) == {"A", "C"}


# ------------------------------------------------------------- measured data
def test_artifact_global_frontier_is_nonempty_and_subset_of_pool(mo_art):
    front = mo_art["frontiers"]["global"]
    assert front and set(front).issubset(set(MODELS))
    # gpt-5 (highest measured quality) must be on the global frontier.
    assert "gpt-5" in front


def test_artifact_frontiers_recompute_from_measured_stats(mo_art):
    """The stored global frontier must equal a fresh recompute from the same
    measured train stats - no hand-editing."""
    st = mo_art["measured_train_stats"]
    stats = {"quality": [st[m]["accuracy"] for m in MODELS],
             "cost": [st[m]["cost"] for m in MODELS],
             "latency": [st[m]["latency_s"] for m in MODELS]}
    assert model_frontier(MODELS, stats) == mo_art["frontiers"]["global"]


def test_dominated_models_are_flagged_not_deleted(mo_art):
    """Every pool model is still described, even the dominated ones."""
    st = mo_art["measured_train_stats"]
    assert set(st.keys()) == set(MODELS)          # nothing discarded
    dominated = [m for m in MODELS if m not in mo_art["frontiers"]["global"]]
    # The published finding: several models are Pareto-dominated in this pool.
    assert dominated, "expected a sparse frontier with dominated models"


def test_quality_floor_frontier_is_a_subset_of_eligible_models(mo_art):
    """The floor-constrained frontier only contains models clearing the floor."""
    st = mo_art["measured_train_stats"]
    floor = mo_art["_meta"]["resolved_floor90"]
    for m in mo_art["frontiers"]["quality_floor"]:
        assert st[m]["accuracy"] >= floor - 1e-9


def test_privacy_frontier_is_a_subset_of_approved(mo_art):
    """The privacy frontier never admits a model outside the approved set."""
    from routing.sensitivity import load_policy
    approved = set(load_policy()["deployment"]["approved_for_sensitive"])
    assert set(mo_art["frontiers"]["privacy_approved"]).issubset(approved)
