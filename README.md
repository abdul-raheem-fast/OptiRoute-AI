<div align="center">

# OptiRoute AI
### Intelligent LLM Router — send every query to the cheapest model that can still answer it well

![tests](https://img.shields.io/badge/tests-61%20passing-2ea44f)
![python](https://img.shields.io/badge/python-3.11-3572A5)
![frontend](https://img.shields.io/badge/frontend-React%2018%20%2B%20Vite-61dafb)
![api](https://img.shields.io/badge/api-FastAPI-009688)
![license](https://img.shields.io/badge/license-MIT-blue)

**94.8% of flagship quality at 68.4% lower cost** — measured on a frozen held-out
test split of 282 real benchmark queries, with the hindsight oracle ceiling at
80.8% cost reduction on the same split.

[Results](#headline-results-frozen-held-out-test-split) ·
[Live demo](#live-demo-dashboard--routing-api) ·
[How routing works](#how-routing-actually-works) ·
[API](#api-reference) ·
[Tests](#verification-61-automated-correctness-tests) ·
[Reproduce](#reproducing-the-research)

</div>

---

## TL;DR

Frontier LLMs are excellent and expensive. Small models are nearly free and
*usually* fine. OptiRoute AI decides, **per query and before any model is
called**, which one to use.

- **The evidence base.** 8 state-of-the-art LLMs were run over **1,887 queries**
  drawn from **26 benchmark sources** consolidated into **5 capability classes**,
  under a single query-aligned schema that records correctness, cost and latency
  for every (query, model) pair — 15,096 measurements in total.
- **The method.** One binary logistic-regression head per model predicts
  *P(this model answers this query correctly)* from the query text alone. A
  cheap-to-strong cascade then walks the pool and stops at the first model whose
  predicted probability clears a threshold `t*` tuned on a validation split under
  an explicit quality floor.
- **The result (test split, 282 queries, never used for training or tuning).**
  **84.04%** accuracy vs **88.65%** for always-strongest — that is **94.8%** of
  flagship quality — at **$0.006023 per query instead of $0.019061**, a **68.4%**
  cost cut.
- **The delivery.** A FastAPI routing service plus a React dashboard that
  explains every single decision. The deployed router scores queries from
  exported weights — **no API keys, no live model calls, no network dependency**.
- **The proof.** A 61-test correctness suite verifies that the deployed router
  reproduces the frozen research numbers *exactly*, and pins its behaviour on
  adversarial inputs, free text, batch paths, latency and memory.

> **The one-line thesis:** cost is the objective, quality is the constraint.

---

## The problem, and why a benchmark came first

Routing research is easy to fake and hard to trust: pick a threshold, tune on the
same data you report, quote a cost saving that assumes the cheap model was right.
So this project built the ground truth first and treated the router as a
hypothesis to be falsified against it.

Three properties make the evaluation honest:

1. **Real outcomes, not proxies.** Every number comes from measured
   correct/incorrect labels with measured per-query cost and latency — no
   simulated scores.
2. **A sealed test split.** 1,887 queries were stratified by
   `capability class x difficulty tier` into train 1,322 / val 283 / test 282
   (seed 42). The threshold `t*` was tuned on **val only**; the headline numbers
   come from **test only**; the leakage audit confirms the 246 duplicate query
   ids present in the extended 7-model set appear in **zero** val/test rows.
3. **An explicit quality floor.** A router only counts if it keeps at least 90%
   of always-strongest accuracy (`A_min = 79.8%` on test). Cheaper-but-worse
   policies are reported as failures, not wins.

111 queries are answered incorrectly by **all eight** models — they are kept in
the data, because pretending otherwise would inflate every policy including the
oracle.

---

## Headline results (frozen, held-out test split)

282 queries, seed 42, stratified. Every row below is regenerated from artifacts
by `python -m routing.run_all`; nothing is hand-edited.

| Policy | Accuracy | Quality vs strongest | Avg cost / query | Avg latency | Cost cut vs strongest | Meets floor | Oracle gap |
|---|---:|---:|---:|---:|---:|:---:|---:|
| always-strongest (GPT-5) | 88.65% | 100.0% | $0.019061 | 0.763 s | 0.0% | Yes | 6.03 pts |
| always-cheapest | 42.20% | 47.6% | $0.000013 | 0.311 s | 99.9% | **No** | 52.48 pts |
| random | 74.11% | 83.6% | $0.015865 | 1.369 s | 16.8% | **No** | 20.57 pts |
| class-based | 81.91% | 92.4% | $0.009377 | 3.654 s | 50.8% | Yes | 12.77 pts |
| prior-cascade (t = 0.80) | 83.69% | 94.4% | $0.009979 | 2.799 s | 47.6% | Yes | 10.99 pts |
| kNN-cascade (t = 0.60) | 87.94% | 99.2% | $0.018711 | 0.819 s | 1.8% | Yes | 6.74 pts |
| **learned-cascade (t\* = 0.95) — ours** | **84.04%** | **94.8%** | **$0.006023** | 3.490 s | **68.4%** | **Yes** | 10.64 pts |
| oracle (hindsight upper bound) | 94.68% | 106.8% | $0.003659 | 0.602 s | 80.8% | Yes | — |

**How to read it.** The learned cascade is the *only* floor-meeting policy that
beats 50% cost reduction. The kNN cascade buys +3.9 accuracy points over ours but
keeps just 1.8% of the savings — it pays for quality with almost the entire
budget. The oracle row is not achievable by any real system (it reads the answer
key); it exists to size the remaining headroom: **10.64 points**.

Full-data oracle sweep (`alpha = 0.002` over `cost + alpha x latency`, all 1,887
queries): **94.12%** accuracy vs **88.77%** always-strongest, at **80.7%** cost
reduction.

### Accuracy by difficulty tier

Tiers are derived from cross-model agreement: *easy* = 6-8 of 8 models correct,
*medium* = 3-5, *hard* = 0-2.

| Policy | Easy | Medium | Hard |
|---|---:|---:|---:|
| always-strongest | 99.48% | 85.19% | 32.35% |
| always-cheapest | 54.64% | 18.52% | 8.82% |
| class-based | 96.91% | 72.22% | 11.76% |
| kNN-cascade | 99.48% | 81.48% | 32.35% |
| **learned-cascade (ours)** | **98.45%** | **77.78%** | **11.76%** |
| oracle | 100.00% | 100.00% | 55.88% |

The hard tier is where routers separate: nothing but the oracle does well there,
because 111 queries are unsolvable by the whole pool. Our router gives up the
most exactly where the ceiling is lowest — an honest, quantified weakness rather
than a hidden one.

### The model landscape (all 1,887 queries, per model)

| # | Model | Provider | $ / 1M in · out | Accuracy | Avg cost / query | Avg latency |
|---:|---|---|---|---:|---:|---:|
| 1 | Llama-3.1-8B-Instruct | Meta / self-hosted | 0 · 0 | 37.31% | $0.000013 | 0.31 s |
| 2 | Qwen3-8B | Alibaba / self-hosted | 0 · 0 | 76.68% | $0.000807 | 3.67 s |
| 3 | deepseek-v3-0324 | DeepSeek AI | 0.27 · 1.10 | 75.73% | $0.000841 | 2.92 s |
| 4 | gemini-2.5-flash | Google DeepMind | 0.30 · 2.50 | 76.10% | $0.003463 | 0.19 s |
| 5 | gpt-4.1 | OpenAI | 2.00 · 8.00 | 72.39% | $0.004097 | 1.04 s |
| 6 | claude-sonnet-4 | Anthropic | 3.00 · 15.00 | 75.09% | $0.009877 | 0.33 s |
| 7 | gemini-2.5-pro | Google DeepMind | 1.25 · 10.00 | 87.44% | $0.082901 | 1.90 s |
| 8 | gpt-5 | OpenAI | 1.25 · 10.00 | 88.77% | $0.021178 | 0.81 s |

The spread the router has to exploit: **~6,200x** in cost, **~55x** in latency,
**51.4 points** in accuracy — and the cheapest model is *not* the worst on every
class, which is precisely why per-query routing beats any static choice.

Two things this table makes obvious, and that we do not hide:

- Cascade order follows the declared price ladder in `routing/config.py`;
  measured per-query cost can disagree with it (gemini-2.5-pro answers are much
  longer on this benchmark, so its measured cost exceeds GPT-5's). The
  *confidence gate*, not the order, decides where a query lands.
- **Latency is not the objective.** The learned cascade averages 3.49 s vs 0.76 s
  for always-strongest, because cheap self-hosted models are slower per query
  even though they cost ~nothing. If your product is latency-bound, run
  `mode=economy` or tune `alpha` in the oracle sweep — the dashboard reports
  latency alongside cost so this trade-off is always visible.

![Cost vs accuracy frontier](figures/accuracy_vs_cost_tradeoff.png)

---

## Live demo: dashboard + routing API

A self-contained service: FastAPI backend, React 18 + TypeScript + Vite +
Recharts frontend, and an **offline** router that scores queries from exported
weights.

### Quickstart (backend only — no Node, no API keys)

```bash
git clone https://github.com/abdul-raheem-fast/OptiRoute-AI.git
cd OptiRoute-AI
pip install numpy pandas fastapi uvicorn pydantic

python -m webapp.export_weights   # trains the heads + tunes t*, writes routing/models/router_weights.npz
python -m webapp.server           # http://127.0.0.1:8317
python -m webapp.smoke_test       # endpoint self-check (server must be running)
```

`webapp/export_weights.py` needs the benchmark data (see
[Data policy](#data-policy)). If `webapp/frontend/dist` exists — and it is
committed, ~611 KB — the server serves the React dashboard; otherwise it falls
back to the legacy vanilla dashboard in `webapp/static/` so the API keeps working
on any checkout.

### Frontend development

```bash
cd webapp/frontend
npm install
npm run dev      # Vite dev server; proxies /api and /health to :8317
npm run build    # tsc --noEmit && vite build  ->  webapp/frontend/dist
```

### What the dashboard shows

| # | Section | What it proves |
|---:|---|---|
| 1 | **Route arena** | A live decision for one query: chosen model, per-model *P(correct)* bars, an animated cheap-to-strong cascade walk, a derived complexity estimate, an explainable *why this route* list, and the always-GPT-5 alternative with the exact per-query saving. Three routing modes and a **Challenge the router** button. The scenario chips are **real test-split benchmark queries** with their measured outcome attached. |
| 2 | **Results + quality guardrail** | The frozen policy table above, the cost/accuracy frontier, and a floor-vs-current guardrail that fails loudly if quality ever drops below `A_min`. |
| 3 | **Evidence Lab** | The splits manifest (seed, per-stratum counts, duplicate-id leakage audit) and strongest / OptiRoute / oracle comparison cards. |
| 4 | **Business impact** | Daily, monthly and yearly savings at any query volume, with a "what the savings buy" breakdown. |
| 5 | **Operations** | Live session telemetry: escalation rate, model and tier mix, cumulative savings sparkline, labelled demo-vs-session data. |
| 6 | **Model pool** | The 8-model landscape with pricing, measured accuracy per capability class, cost and latency. |
| 7 | **How it works** | The architecture, the feature vector and the cascade, drawn from the same code the server runs. |
| 8 | **API playground** | Editable requests against the live endpoints, with raw JSON responses. |

A narration-ready walkthrough lives in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

---

## How routing actually works

Two layers, strictly separated. **Offline** research produces weights;
**online** serving consumes them.

```
        OFFLINE (research, reproducible)                ONLINE (serving, ~11 ms)
  cleaned/aligned_8_models/*.csv                 query text  (+ optional class)
            |                                            |
   A1 build_matrix.py  ->  query x model            featurize(): 2,066 dims
        outcomes, cost, latency                     [5 scalars | 5 class one-hot
            |                                        | 2,048 hashed char-4-gram
   U1/U3 splits.py -> stratified train/val/test       TF-IDF | 8 class priors]
        + difficulty tiers                                 |
            |                                        8 logistic heads
   A3 learned_router.py -> one binary head            p_m = sigmoid(x . w_m + b_m)
        per model, t* tuned on VAL                         |
            |                                        cascade, cheapest -> strongest
   export_weights.py -> router_weights.npz  ------>   first p_m >= t wins,
        (W, b, idf, priors, registry,                 else FALLBACK to gpt-5
         t_star, mode table)                                 |
                                                      decision + reasons + savings
```

### The decision rule

1. **Featurize** the query into a fixed **2,066**-dimensional vector: 5 text
   scalars, a 5-way capability-class one-hot, 2,048 hashed signed char-4-gram
   TF-IDF features (md5-hashed, train-learned IDF, L2-normalised), and 8
   per-class prior accuracies. Hashing means the vector never grows with
   vocabulary and unseen words degrade gracefully.
2. **Score** all 8 heads: `p_m = P(model m answers correctly | query)`.
3. **Walk the cascade** in the configured cheap-to-strong order and stop at the
   **first** model with `p_m >= t`.
4. **Fall back** to the strongest model (gpt-5) if nothing clears the bar.
   Escalation is the safe default: an uncertain query buys quality, never a
   coin flip on a cheap model.
5. **Explain**: chosen model, full probability vector, the cascade trace with
   per-step pass/fail, a derived complexity tier, human-readable reasons, and the
   saving versus always-strongest.

If the caller supplies no capability class, the router infers one from the text
deterministically — the same query always yields the same route, bit for bit.

### Routing modes are threshold policies, not labels

Each mode is a real operating point, measured on the **same validation split**
used to tune `t*` (so the cards quote honest numbers, not marketing):

| Mode | Threshold `t` | Val accuracy | Val cost / query | Meets quality floor |
|---|---:|---:|---:|:---:|
| Economy | 0.80 | 75.97% | $0.002922 | No — maximum savings, quality risk |
| **Balanced** (default, `t*`) | **0.95** | **83.75%** | **$0.008142** | **Yes — the measured headline policy** |
| Quality First | 0.99 | 85.51% | $0.009672 | Yes — escalates aggressively |

An explicit `threshold` in the request always overrides `mode`, and every
response echoes the **effective** threshold it actually used — the dashboard
reads that value back rather than trusting the label.

### What the router is *not*

- It never calls a model API. Routing is a local matrix multiply.
- It never trains at request time. Weights are loaded once at process start.
- The complexity bars are **derived from the router's own confidence**, not a
  separately trained difficulty classifier — they are an explanation, and they
  are labelled as such.
- Per-query cost and latency shown in the UI are **benchmark averages of the
  chosen model**, not live quotes. Headline savings always come from the
  measured test split.

---

## API reference

Base URL `http://127.0.0.1:8317`. Interactive docs at `/api/docs`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/route` | Route one query. Body: `query` (1-20,000 chars, required), `query_class` (optional), `mode` (`economy` \| `balanced` \| `quality`, optional), `threshold` (0.50-0.99, optional; overrides `mode`) |
| `GET` | `/api/results` | Frozen policy tables + splits manifest (503 until the pipeline has been run) |
| `GET` | `/api/models` | Model pool: provider, pricing, measured cost/latency, per-class accuracy |
| `GET` | `/api/modes` | Mode presets with their val-measured accuracy, cost and floor verdict, plus `t_star` |
| `GET` | `/api/scenarios` | The six real test-split demo chips with expected model, route and saving |
| `GET` | `/api/stats` | Live session telemetry: distribution, escalation rate, savings, tier mix, route log |
| `GET` | `/health` | Liveness probe |

```bash
curl -s -X POST http://127.0.0.1:8317/api/route \
  -H "Content-Type: application/json" \
  -d '{"query": "You are given two positive integers A and B. Output the square of A + B.",
       "query_class": "Coding", "mode": "balanced"}'
```

Real response (trimmed — `cascade_trace` and `class_prior_acc` omitted):

```json
{
  "query_class": "Coding",
  "threshold": 0.95,
  "chosen_model": "Qwen3-8B",
  "chosen_index": 1,
  "is_fallback": false,
  "tier": "easy",
  "tier_probs": { "easy": 0.58, "medium": 0.0, "hard": 0.42 },
  "reasons": [
    "complexity estimate: easy (58% of the router's confidence mass)",
    "Coding capability class",
    "Qwen3-8B is the cheapest model clearing t=0.95 (p=100%)",
    "cost is the objective, quality is the constraint"
  ],
  "why_not_strongest": {
    "delta_accuracy_pts": -22.2,
    "delta_cost_per_query": 0.020371,
    "verdict": "+-22.2 pts expected quality for +$0.02037/query does not pay"
  },
  "p_correct": {
    "Llama-3.1-8B-Instruct": 0.2028, "Qwen3-8B": 0.9977,
    "deepseek-v3-0324": 0.6981, "gemini-2.5-flash": 0.4287,
    "gpt-4.1": 0.5094, "claude-sonnet-4": 0.3727,
    "gemini-2.5-pro": 0.8048, "gpt-5": 0.7759
  },
  "est_cost_per_query": 0.0008068,
  "est_latency_s": 3.6689,
  "strongest_cost_per_query": 0.0211778,
  "est_saving_pct": 96.2
}
```

Malformed input is rejected with **422**, never a 500: missing/empty `query`,
over-length text, out-of-range `threshold` and unknown `mode` all fail at the
schema boundary. Unknown capability classes fall back to the deterministic
text-based classifier instead of silently misrouting.

---

## Reproducing the research

One command regenerates every Phase-2 artifact in dependency order. Each stage
runs as a subprocess, so a failure halts the chain with a clear banner.

```bash
python -m routing.run_all              # full run
python -m routing.run_all --fast       # skip the two slow training stages (5, 6)
python -m routing.run_all --from 4     # resume at stage N
```

| Stage | Task | Output |
|---:|---|---|
| 0 | `validate_cleaned.py` — dataset gate (A4) | schema/alignment assertions |
| 1 | `routing.build_matrix` (A1) | `routing/data/routing_matrix.csv` |
| 2 | `routing.splits` (U1, U3) | stratified splits + difficulty tiers + manifest |
| 3 | `routing.validate_dedup` (U2) | duplicate-id leakage audit |
| 4 | `routing.oracle` (A2) | hindsight oracle + alpha sweep |
| 5 | `routing.learned_router` (A3) | **our method**: heads, `t*`, report |
| 6 | `routing.baselines` (R1, R2) | unified policy comparison table |
| 7 | `routing.plots` (R3) | publication figures |
| 8 | `routing.fresh_model_demo` (R4) | extensibility demo: add a 9th model |

Afterwards `routing/results/results_bundle.md` is rebuilt **from artifacts only**
(no hardcoded numbers), which is the single table source for the report chapter.
`routing/config.py` centralises the model order, `ALPHA`, `QUALITY_FLOOR`, `SEED`
and all paths, so stages stay decoupled and reproducible.

### Data policy

`cleaned/`, `raw/` and all `*.csv` files (1.3 GB) are **excluded from git** and
exchanged out-of-band; generated artifacts under `routing/data/`,
`routing/results/` and `routing/models/` are regenerated by the pipeline. Only
source, configuration, docs, figures and the built dashboard bundle are version
controlled. `run_eval.py` reads endpoints and pricing from
[`models_registry.json`](models_registry.json) and resolves every secret from
environment variables — no key is ever committed.

---

## Verification: 61 automated correctness tests

```bash
pip install pytest httpx
pytest tests/            # 61 passed in ~20-30 s
```

The suite is *verification only* — it never relaxes a tolerance to go green. See
[`tests/README.md`](tests/README.md).

| File | Tests | What it pins |
|---|---:|---|
| `test_parity.py` | 4 | The **deployed** router reproduces the frozen test-split numbers over the exact 282-query seed-42 split: 84.04% accuracy, $0.006023/query, 94.8% quality — digit-identical after report rounding. Uses the same split loaders as production, so a failure can only mean the router disagrees with itself. |
| `test_router_core.py` | 11 | Feature width is always 2,066; probabilities finite and in [0, 1] under stress input; the cascade returns the **first** model over `t` (proved by injecting a probability vector where only the 3rd-cheapest clears); fallback to gpt-5 when nothing clears; bit-identical determinism. |
| `test_modes.py` | 9 | The **effective** threshold is 0.80 / 0.95 / 0.99 — not just a label; an explicit threshold overrides the mode; no drift versus `export_weights.MODE_SPECS`; the default mode meets the quality floor. |
| `test_edge_cases.py` | 20 | Empty, 10k-character, flat-vector, unicode/emoji/non-Latin, SQL-injection and prompt-injection inputs stay sane through **both** `RouterCore.route()` and `POST /api/route`; invalid input yields 4xx, never 500. |
| `test_freetext_safety.py` | 3 | Conservative free-text guarantee: any casual prompt routed to a cheap model must carry > 0.90 confidence. Measured escalation rate is reported, never hardcoded. |
| `test_batch_consistency.py` | 5 | Batch `route_cascade()` and single `RouterCore.route()` agree on ~50 queries spanning all 5 classes; includes a regression test pinning the documented `make_X` vs `featurize` width asymmetry. |
| `test_performance.py` | 4 | 100 sequential API calls within p50/p95/p99 bounds; a structural guard proving weights are **not** reloaded per request; bounded session state; no memory growth. |
| `test_scenario_chips.py` | 5 | The six demo chips route to exactly the model, behaviour and saving they advertise — the demo cannot drift from the science. |

Measured baselines recorded by the suite (asserted, not merely printed):

| Property | Measured | Bound |
|---|---|---|
| Parity vs frozen report | 84.04% / $0.006023 / 94.8% | exact after rounding |
| Free-text escalation rate | **92.9%** (13 of 14 casual prompts -> gpt-5) | >= 50% |
| `/api/route` latency | p50 **11.4 ms**, p95 **24.1 ms**, p99 **27.4 ms** (max 65.5 ms) | p99 < 200 ms |
| Memory growth over 100 requests | **+0.11 MB** | < 8 MB |
| Per-request weight reload | none (structural guard) | must be none |

The 92.9% escalation figure is the honest cost of the safety rule: on casual
free text the router mostly refuses to gamble and escalates. Its savings come
from *benchmark-shaped* queries, which is exactly what the test split measures.

---

## Honesty notes and limitations

- **10.64 points of oracle gap remain.** Better calibrated confidence or richer
  features are the obvious next step; we quantify the headroom instead of
  claiming we closed it.
- **The hard tier is weak** (11.76%), because 111 queries are unsolvable by all
  eight models. No router fixes that; only a better pool does.
- **Latency is traded away** by the default policy. Reported per policy, per
  mode, per query.
- **Free text escalates ~93% of the time.** The router is conservative outside
  the benchmark distribution by design.
- **One documented asymmetry:** the training-side `make_X` sizes its one-hot
  block from the classes present in a batch, while the inference-side
  `featurize` always uses the fixed 5-class order. Offline evaluation always
  batches all five classes, so the frozen numbers are unaffected — and a
  regression test pins the behaviour so nobody trips over it silently.
- **Self-hosted models are priced at $0** in the registry (Llama-3.1-8B,
  Qwen3-8B). Their compute cost is real but out-of-pocket-zero in this accounting;
  measured latency is not zero, and is reported.

---

## Repository layout

| Path | Contents |
|---|---|
| `routing/` | **Phase 2**: matrix build, splits/tiers, oracle, learned router, baselines, plots, fresh-model demo, `run_all.py` |
| `webapp/` | **Delivery**: `server.py` (FastAPI), `router_core.py` (offline inference engine), `export_weights.py` (train + tune + persist), `smoke_test.py`, `static/` (legacy vanilla dashboard) |
| `webapp/frontend/` | React 18 + TypeScript + Vite + Recharts dashboard (committed `dist/`, 25 source files) |
| `tests/` | 61-test correctness suite + `tests/README.md` |
| `scripts/` | Phase-1 provenance: cleaning, auditing, analysis, graphing + the analysis notebook |
| `figures/` | Phase-1 analysis figures (accuracy, cost, latency, trade-offs) |
| `docs/` | `model_selection_rationale.md`, `model_citations_and_references.md` |
| `references/` | The five reviewed papers (see below) |
| `run_eval.py` + `models_registry.json` | Generic OpenAI-compatible evaluation harness + config-driven model registry |
| `validate_cleaned.py` | Active dataset gate (pipeline stage 0) |
| `DEMO_SCRIPT.md` | Narration-ready 3-minute walkthrough |
| `cleaned/`, `raw/`, `*.csv` *(not in git)* | 1.3 GB benchmark data — `aligned_8_models/` (1,887 x 8), `aligned_7_models/` (3,352 x 7), `individual/` |

Requires **Python 3.11+** (`numpy`, `pandas`, `fastapi`, `uvicorn`, `pydantic`;
`pytest` + `httpx` for the test suite) and **Node 18+** only if you want to
rebuild the frontend.

---

## Research questions

| # | Question | Answer |
|---|---|---|
| RQ1 | Cost achievable at a quality floor? | The learned cascade keeps **94.8%** of flagship quality at **68.4%** cost reduction. |
| RQ2 | What is the ceiling? | Oracle **94.68%** vs strongest **88.65%** on test; **111** queries are unsolvable by any model in the pool. |
| RQ3 | How do baselines compare? | Ours is the only floor-meeting policy above 50% reduction; kNN trades nearly all savings for +3.9 points of quality. |
| RQ4 | Where does difficulty bite? | Hard-tier accuracy separates routers most; the oracle-learned gap widens there. |
| RQ5 | How much headroom is left? | **10.64 points** — the case for calibrated confidence and richer features. |

Grounded in five reviewed papers, included under `references/`:
**FrugalGPT** (Stanford, 2023), **RouteLLM** (LMSYS / UC Berkeley, 2024),
**Self-REF** (Apple / Rice, ICML 2025), **Confident or Seek Stronger** (2025),
**LLMRouterBench** (Shanghai AI Laboratory, 2026). Selection rationale and full
citations: [`docs/`](docs).

---

## Team

Hackathon submission — focus area: **Open Innovation**.

| Contributor | Focus |
|---|---|
| Abdul Raheem | Benchmark construction, routing research, backend + inference engine, verification suite |
| Ahmad Rasheed | React dashboard, visualisation, demo experience |
| Umar Shoaib | Documentation, demo narrative, evaluation write-up |

Workflow: repo-local git identity per contributor, `feature/<task-id>-<name>`
branches, PRs into `main`, review required, no force-pushes to `main`. Commits
reflect actual authorship.

---

## License

MIT — see [`LICENSE`](LICENSE). Benchmark data is shared out-of-band under the
terms of its 26 source datasets; model names and pricing belong to their
respective providers.
