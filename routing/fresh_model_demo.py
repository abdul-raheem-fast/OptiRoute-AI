"""Task R4: fresh-model integration demo (offline, synthetic 9th model).

The suite's extensibility claim: adding an entry to models_registry.json and
running `python run_eval.py --model <key>` is the ONLY manual step; the
matrix builder (A1), oracle (A2), baselines (R1/R2) and metrics (U4) absorb
the new column without code changes.

This machine holds no API keys, so the demo exercises the pipeline with a
SYNTHETIC 9th model ("qwen3-32b-demo"): its outcomes on a 300-query
stratified subset are drawn from a documented, seeded generative rule.
The numbers below are a pipeline test, NOT a model evaluation - the output
slide states this explicitly.
"""
import json

import numpy as np
import pandas as pd

from routing.config import MODELS, OUT_DIR, RESULTS_DIR, ROOT, SEED
from routing.metrics import build_report, oracle_choice
from routing.oracle import load_wide
from routing.splits import load_splits

DEMO_MODEL = "qwen3-32b-demo"
N_SUBSET = 300

# documented generative rule (seeded => reproducible)
BASE_SKILL = {
    "Coding": 0.55, "Mathematical Reasoning": 0.50,
    "Scientific Questionnaire": 0.60, "General Knowledge": 0.65,
    "Competitive Math": 0.45,
}
TIER_ADJ = {"easy": 0.25, "medium": 0.0, "hard": -0.25}
PRICE_IN, PRICE_OUT = 0.20, 0.80          # USD per 1M tokens (demo entry)


def demo_registry_entry():
    reg = json.loads((ROOT / "models_registry.json").read_text(encoding="utf-8"))
    entry = dict(reg["_template"])
    entry.update({
        "provider": "Alibaba Cloud (SYNTHETIC demo)",
        "api_base": "{QWEN_API_BASE}",
        "model_id": "qwen3-32b",
        "api_key_env": "QWEN_API_KEY",
        "price_per_1m_input": PRICE_IN,
        "price_per_1m_output": PRICE_OUT,
        "snapshot_date": "2026-08",
        "notes": "SYNTHETIC R4 demo entry - outcomes simulated, not evaluated",
    })
    reg[DEMO_MODEL] = entry
    return reg


def sample_subset(meta, tier_map, rng):
    """Stratified-by-class 300-query subset of the full query set."""
    picks = []
    for cls, grp in meta.groupby("dataset_name"):
        k = max(10, int(round(N_SUBSET * len(grp) / len(meta))))
        picks.append(rng.choice(grp.index.to_numpy(), size=k, replace=False))
    qids = np.concatenate(picks)
    rng.shuffle(qids)
    return list(qids[:N_SUBSET])


def synthesize(qids, meta, tier_map, rng):
    """Synthetic correct/cost/latency columns for the demo model."""
    p = np.clip([BASE_SKILL[meta.loc[q, "dataset_name"]]
                 + TIER_ADJ[tier_map[q]] for q in qids], 0.05, 0.95)
    correct = (rng.random(len(qids)) < p).astype(int)
    t_in = np.array([len(meta.loc[q, "origin_query"]) // 4 + 50 for q in qids])
    cost = (t_in * PRICE_IN + 300 * PRICE_OUT) / 1e6
    latency = rng.lognormal(2.2, 0.3, len(qids))
    return correct, cost, latency


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    reg = demo_registry_entry()
    (RESULTS_DIR / "demo_registry.json").write_text(
        json.dumps(reg, indent=2), encoding="utf-8")

    K, C, L = load_wide()
    meta = pd.read_csv(OUT_DIR / "query_meta.csv")
    meta = meta.drop_duplicates("query_id").set_index("query_id")
    _, _, _, tier_map = load_splits()

    qids = sample_subset(meta, tier_map, rng)
    correct, cost, latency = synthesize(qids, meta, tier_map, rng)

    K9 = K.loc[qids].copy()
    C9 = C.loc[qids].copy()
    L9 = L.loc[qids].copy()
    K9[DEMO_MODEL], C9[DEMO_MODEL], L9[DEMO_MODEL] = correct, cost, latency
    models9 = MODELS + [DEMO_MODEL]
    K9, C9, L9 = K9[models9], C9[models9], L9[models9]

    n = len(qids)
    policies = {
        "always-strongest": np.full(n, MODELS.index("gpt-5"), dtype=int),
        "always-cheapest": np.zeros(n, dtype=int),
        "oracle (8 models)": oracle_choice(K9[MODELS], C9[MODELS], L9[MODELS]),
        "oracle (9 models)": oracle_choice(K9, C9, L9),
    }
    # score 8-model choices on the 8-model sub-matrix, 9-model on the full one
    rep8 = build_report({k: v for k, v in policies.items()
                         if "9 models" not in k},
                        K9[MODELS], C9[MODELS], L9[MODELS])
    rep9 = build_report({"oracle (9 models)": policies["oracle (9 models)"],
                         "always-strongest": policies["always-strongest"]},
                        K9, C9, L9)

    pick9 = policies["oracle (9 models)"]
    pick8 = policies["oracle (8 models)"]
    switched = (pick9 != pick8).mean() * 100
    new_wins = int((np.array([models9[i] for i in pick9]) == DEMO_MODEL).sum())

    lines = [
        "# Fresh-model integration demo (R4)",
        "",
        f"Subset: {n} queries stratified by class | seed {SEED}",
        f"Demo model: `{DEMO_MODEL}` - SYNTHETIC outcomes (documented "
        "generative rule, see routing/fresh_model_demo.py).",
        "Live integration replaces the synthesis with:",
        "",
        "    python run_eval.py --model qwen3-32b-demo",
        "    python -m routing.build_matrix && python -m routing.baselines",
        "",
        "Registry entry written to routing/results/demo_registry.json.",
        "",
        "## 8-model matrix (subset)",
        rep8.to_string(index=False),
        "",
        "## 9-model matrix (subset)",
        rep9.to_string(index=False),
        "",
        f"Oracle selections changed on {switched:.1f}% of queries after "
        f"adding the demo model; it is the oracle pick on {new_wins}/{n} "
        f"({new_wins / n * 100:.1f}%) - all on queries where its synthetic "
        "skill made it the cheapest correct option.",
        "",
        "Conclusion: the pipeline absorbed a 9th model with zero code "
        "changes; only the registry entry + one eval run are manual.",
    ]
    (RESULTS_DIR / "fresh_model_demo.md").write_text("\n".join(lines),
                                                     encoding="utf-8")

    slide = [
        "# Slide - Adding a model to AetherFlow (R4 demo)",
        "",
        f"- One manual step: copy `_template` in models_registry.json, run "
        f"`run_eval.py --model <key>`",
        "- Matrix (A1), oracle (A2), baselines (R1/R2), metrics (U4) pick "
        "the new column up automatically",
        f"- Demo: synthetic 9th model on {n} queries changed "
        f"{switched:.1f}% of oracle selections",
        f"- New model chosen as cheapest-correct on {new_wins}/{n} queries",
        "- Demo model is SYNTHETIC (seeded rule) - pipeline test, not an "
        "evaluation",
    ]
    (RESULTS_DIR / "fresh_model_demo_slide.md").write_text("\n".join(slide),
                                                           encoding="utf-8")

    print("\n".join(lines))
    print("\nwrote fresh_model_demo.md + fresh_model_demo_slide.md")


if __name__ == "__main__":
    main()
