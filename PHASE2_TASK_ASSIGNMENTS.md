# Phase 2 Task Assignments — AetherFlow Routing Experiments

**Target deadline:** September 3, 2026
**Working agreement:** each contributor works on their own branch
(`feature/<task-id>`), pushes under their own GitHub identity, and opens a
pull request into `main`. Commits are attributed to whoever actually did the
work.

## Contributor identities

| Contributor | GitHub username | Git email | Area of responsibility |
|---|---|---|---|
| Abdul Raheem | `abdul-raheem-fast` | abdulraheemghauri@gmail.com | Core infrastructure, oracle policy, integration |
| Umar Shoaib | `Umar-kh05` | umarshoaib66@gmail.com | Dataset integrity, splits, evaluation protocol |
| Ahmad Rasheed | `ahmadrasheed10` | ahmad5116492@gmail.com | Router baselines, visualization of results |

## Task board (all statuses: unclaimed until work starts)

### Abdul Raheem — core infrastructure & oracle
| ID | Task | Output | Status |
|---|---|---|---|
| A1 | Routing data matrix builder (pivot aligned_8 → query × model outcomes) | `routing/build_matrix.py`, `routing/data/` | done 2026-08-25 |
| A2 | Oracle router (argmin cost + α·latency s.t. correct) | `routing/oracle.py`, headline table | done 2026-08-25 |
| A3 | Learned router ("our method": query features → predicted correctness) | `routing/learned_router.py` | done 2026-08-25 (provisional split; re-run after U1) |
| A4 | Repo hygiene: fix stale `validate_cleaned.py` paths/schema | passing validator | done 2026-08-25 |
| A5 | Integration: end-to-end `routing/run_all.py` + final results | results bundle | done 2026-08-25 |

### Umar Shoaib — dataset integrity & evaluation protocol
| ID | Task | Output | Status |
|---|---|---|---|
| U1 | Stratified 70/15/15 split (capability × difficulty) + leakage audit | `routing/splits.py`, split manifest | done 2026-08-25 |
| U2 | aligned_7 dedup verification (246 known duplicates) + report | `routing/validate_dedup.py` | done 2026-08-25 |
| U3 | Difficulty tiers from cross-model agreement; validate distributions | tier column + report | done 2026-08-25 |
| U4 | Evaluation metrics implementation (cost reduction, oracle gap, A_min=90% check) | `routing/metrics.py` + tests | done 2026-08-25 |

### Ahmad Rasheed — baselines & visualization
| ID | Task | Output | Status |
|---|---|---|---|
| R1 | Static baselines (always-strongest, always-cheapest, random, class-based) | `routing/baselines.py` | done 2026-08-25 |
| R2 | FrugalGPT-style cascade baseline + kNN/learned-signal baseline | same module | done 2026-08-25 |
| R3 | Results visualization (main table plot, class × difficulty breakdown, oracle-gap curves) | `routing/plots.py`, figures | done 2026-08-25 |
| R4 | Fresh-model integration demo on 300-query subset (run_eval.py + registry) | demo log + slide | done 2026-08-25 |

## Sequence (logical development order)

1. A1 → (U1, U2, U3 in parallel) → A2 → R1 → R2 → A3 → U4 → A5 → R3 → R4

## Ground rules

- Never force-push to `main`; resolve conflicts via rebase on your branch.
- Data (`cleaned/`, `*.csv`) stays out of git — it is shared out-of-band.
- Every PR must include the console output / figures it produces, pasted in
  the PR description, so reviewers can verify without the dataset.
