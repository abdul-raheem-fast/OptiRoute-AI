<div align="center">

<br/>

# ⚡ OptiRoute AI

### Intelligent LLM Router — route every query to the cheapest model that can still answer it well

<br/>

[![Tests](https://img.shields.io/badge/tests-130%20passing-2ea44f?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Python](https://img.shields.io/badge/Python-3.11+-3572A5?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](webapp/server.py)
[![React](https://img.shields.io/badge/Frontend-React%2018%20+%20Vite-61dafb?style=for-the-badge&logo=react&logoColor=white)](webapp/frontend/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<br/>

> **94.8% of flagship quality · 68.4% lower cost**
>
> Measured on a frozen held-out test split of 282 real benchmark queries.
> Hindsight oracle ceiling: **80.8%** cost reduction on the same split.
> Now with an **experimental multi-objective router** that trades quality, cost, latency *and* privacy per query.

<br/>

[📊 Results](#-headline-results) · [🧠 How It Works](#-how-routing-works) · [🚀 Quickstart](#-quickstart) · [🔌 API Reference](#-api-reference) · [🧪 Tests](#-verification-suite) · [🔬 Reproduce](#-reproducing-the-research)

<br/>

</div>

---

## 🎯 The One-Line Thesis

> *Cost is the objective. Quality is the constraint.*

Frontier LLMs are excellent — and expensive. Small models are nearly free, and *usually* fine. **OptiRoute AI decides, per query and before any model is called, which one to use.**

---

## ✨ What Makes This Different

| | What was built | Why it matters |
|:---:|---|---|
| 📦 | **Ground-truth benchmark** | 8 LLMs × 1,887 queries × 26 sources = 15,096 measurements — real outcomes, not simulated scores |
| 🔒 | **Sealed test split** | Threshold `t*` tuned on **val only**; headline numbers from **test only** — no leakage |
| 📐 | **Explicit quality floor** | A router only *counts* if it keeps ≥ 90% of always-strongest accuracy |
| ⚡ | **~11 ms routing latency** | Local matrix multiply — no API keys, no live model calls, no network dependency |
| 🧪 | **130 automated tests** | The deployed router must reproduce frozen research numbers *exactly* |
| 🔬 | **Multi-objective extension** | Trade quality, cost, latency *and* privacy per query across 5 objective presets |

---

## 📊 Headline Results

> 282 queries · seed 42 · stratified split · every number regenerated from artifacts via `python -m routing.run_all`

| Policy | Accuracy | Quality vs Best | Cost / Query | Cost Cut | Meets Floor |
|---|:---:|:---:|:---:|:---:|:---:|
| always-strongest (GPT-5) | 88.65% | 100.0% | $0.019061 | 0.0% | ✅ |
| always-cheapest | 42.20% | 47.6% | $0.000013 | 99.9% | ❌ |
| random | 74.11% | 83.6% | $0.015865 | 16.8% | ❌ |
| class-based | 81.91% | 92.4% | $0.009377 | 50.8% | ✅ |
| prior-cascade (t = 0.80) | 83.69% | 94.4% | $0.009979 | 47.6% | ✅ |
| kNN-cascade (t = 0.60) | 87.94% | 99.2% | $0.018711 | 1.8% | ✅ |
| **🏆 learned-cascade (t\* = 0.95) — ours** | **84.04%** | **94.8%** | **$0.006023** | **68.4%** | ✅ |
| oracle (hindsight upper bound) | 94.68% | 106.8% | $0.003659 | 80.8% | ✅ |

**How to read it:** The learned cascade is the *only* floor-meeting policy with >50% cost reduction. The kNN cascade buys +3.9 accuracy points — but at the cost of nearly all savings (1.8% vs 68.4%). The **10.64-point oracle gap** sizes the remaining headroom honestly.

Full-data oracle sweep (`alpha = 0.002`, all 1,887 queries): **94.12%** accuracy vs **88.77%** always-strongest, at **80.7%** cost reduction.

### Accuracy by Difficulty Tier

Tiers derived from cross-model agreement: *easy* = 6–8 models correct · *medium* = 3–5 · *hard* = 0–2

| Policy | Easy | Medium | Hard |
|---|:---:|:---:|:---:|
| always-strongest | 99.48% | 85.19% | 32.35% |
| always-cheapest | 54.64% | 18.52% | 8.82% |
| class-based | 96.91% | 72.22% | 11.76% |
| kNN-cascade | 99.48% | 81.48% | 32.35% |
| **learned-cascade (ours)** | **98.45%** | **77.78%** | **11.76%** |
| oracle | 100.00% | 100.00% | 55.88% |

> **Honest weakness:** 111 queries are unsolvable by *all eight* models — no router fixes that, only a better pool does.

---

## 🤖 The Model Landscape

8 models, 1,887 queries. The spread the router exploits: **~6,200× in cost**, **~55× in latency**, **51.4 points in accuracy**.

| # | Model | Provider | Price ($/1M in·out) | Accuracy | Cost / Query | Latency |
|:---:|---|---|:---:|:---:|:---:|:---:|
| 1 | Llama-3.1-8B-Instruct | Meta / self-hosted | free | 37.31% | $0.000013 | 0.31 s |
| 2 | Qwen3-8B | Alibaba / self-hosted | free | 76.68% | $0.000807 | 3.67 s |
| 3 | deepseek-v3-0324 | DeepSeek AI | 0.27 · 1.10 | 75.73% | $0.000841 | 2.92 s |
| 4 | gemini-2.5-flash | Google DeepMind | 0.30 · 2.50 | 76.10% | $0.003463 | 0.19 s |
| 5 | gpt-4.1 | OpenAI | 2.00 · 8.00 | 72.39% | $0.004097 | 1.04 s |
| 6 | claude-sonnet-4 | Anthropic | 3.00 · 15.00 | 75.09% | $0.009877 | 0.33 s |
| 7 | gemini-2.5-pro | Google DeepMind | 1.25 · 10.00 | 87.44% | $0.082901 | 1.90 s |
| 8 | **gpt-5** | OpenAI | 1.25 · 10.00 | **88.77%** | $0.021178 | 0.81 s |

> Cascade order follows the price ladder in `routing/config.py`. The *confidence gate*, not the order, decides where a query lands. Latency is not the objective — it is traded away by default and reported per policy.

![Cost vs accuracy frontier](figures/accuracy_vs_cost_tradeoff.png)

---

## 🚀 Quickstart

### Backend Only (no Node, no API keys)

```bash
git clone https://github.com/abdul-raheem-fast/OptiRoute-AI.git
cd OptiRoute-AI
pip install -r requirements.txt

# Train heads, tune t*, write routing/models/router_weights.npz
python -m webapp.export_weights

# Start server at http://127.0.0.1:8317
python -m webapp.server

# Verify endpoints (server must be running)
python -m webapp.smoke_test
```

> If `webapp/frontend/dist` exists (committed, ~611 KB), the server serves the React dashboard.
> Otherwise it falls back to the legacy vanilla dashboard in `webapp/static/`.

### Frontend Development

```bash
cd webapp/frontend
npm install
npm run dev      # Vite dev server; proxies /api and /health to :8317
npm run build    # tsc --noEmit && vite build -> webapp/frontend/dist
```

---

## 🧠 How Routing Works

Two layers, strictly separated — **offline** research produces weights; **online** serving consumes them.

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
   export_weights.py -> router_weights.npz  ------->   first p_m >= t wins,
        (W, b, idf, priors, registry,                 else FALLBACK to gpt-5
         t_star, mode table)                                 |
                                                       decision + reasons + savings
```

### The 5-Step Decision Rule

1. **Featurize** the query into a **2,066-dimensional vector**: 5 text scalars · 5-way capability-class one-hot · 2,048 hashed char-4-gram TF-IDF features · 8 per-class prior accuracies
2. **Score** all 8 heads: `p_m = P(model m answers correctly | query)`
3. **Walk the cascade** cheapest→strongest; stop at the **first** model with `p_m >= t`
4. **Fall back** to GPT-5 if nothing clears the bar — an uncertain query buys quality, never a coin flip
5. **Explain**: chosen model · full probability vector · cascade trace · complexity tier · human-readable reasons · per-query saving

> The same query always yields the same route, bit for bit. If no capability class is supplied, the router infers one deterministically from the text.

### Routing Modes

Each mode is a real, measured operating point — not a marketing label:

| Mode | Threshold `t` | Val Accuracy | Val Cost / Query | Meets Floor |
|---|:---:|:---:|:---:|:---:|
| Economy | 0.80 | 75.97% | $0.002922 | ❌ Maximum savings, quality risk |
| **Balanced** (default `t*`) | **0.95** | **83.75%** | **$0.008142** | ✅ The headline policy |
| Quality First | 0.99 | 85.51% | $0.009672 | ✅ Escalates aggressively |

> An explicit `threshold` in the request always overrides `mode`. Every response echoes the **effective** threshold actually used.

### What the Router Is *Not*

- ❌ Never calls a model API — routing is a local matrix multiply
- ❌ Never trains at request time — weights loaded once at process start
- ❌ The complexity bars are not a separate difficulty classifier — they derive from the router's own confidence, and are labelled as such
- ❌ Per-query cost/latency in the UI are benchmark averages, not live quotes

---

## 🔬 Multi-Objective Routing *(Experimental)*

The legacy cascade optimises one objective (cost) under one constraint (quality). Real deployments also care about **latency** and **privacy**. The experimental MO router generalises to all four dimensions — same eight logistic heads, same feature vector, new scoring and constraint layer on top. It is **opt-in** — the legacy cascade remains the production default.

### The Utility Formula

```
utility(m) = calibrated_quality(m)
           - lambda_cost    * minmax(cost_m)
           - lambda_latency * minmax(latency_m)
```

`calibrated_quality(m)` is a **Platt-calibrated** probability fit on **train** and verified on **val**. `minmax(.)` normalises using pool-wide measured train statistics. Lambda weights are declared in `routing/models/mo_objectives.json`.

### Hard Constraints — Applied *Before* Ranking

Constraints are masks over the pool, applied in order. An ineligible model can never be selected, regardless of its utility score:

| # | Constraint | Behavior on failure |
|:---:|---|---|
| 1 | 🔒 **Privacy filter** | Sensitive query → only `approved_for_sensitive` models are admissible |
| 2 | ⏱️ **Latency budget** | Models over budget are removed; degrades gracefully to fastest eligible |
| 3 | 📐 **Quality floor** | Per-mode and per-query floors make inadmissible models ineligible |
| 4 | 🛡️ **Fallback** | If nothing survives all masks, escalate to strongest eligible model |

### Five Objective Presets — Evaluated on the Same Sealed Test Split

| Policy | Accuracy | Quality vs GPT-5 | Cost / Query | Cost Cut | Avg Latency | Privacy-Filtered |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| always-cheapest (Llama) | 42.20% | 47.6% | $0.000013 | 99.9% | 0.311 s | 0.0% |
| always-GPT-5 | 88.65% | 100.0% | $0.019061 | 0.0% | 0.763 s | 0.0% |
| **legacy cascade (t\* = 0.95)** | **84.04%** | **94.8%** | **$0.006023** | **68.4%** | 3.490 s | 0.0% |
| MO · Economy | 80.85% | 91.2% | $0.003334 | 82.5% | 2.401 s | 0.0% |
| MO · Balanced | 86.17% | 97.2% | $0.016260 | 14.7% | 0.624 s | 0.0% |
| MO · Speed | 77.30% | 87.2% | $0.003038 | 84.1% | **0.164 s** | 0.0% |
| MO · Quality | 86.52% | 97.6% | $0.046992 | −146.5% | 1.615 s | 0.0% |
| MO · Private | 74.82% | 84.4% | $0.000759 | 96.0% | 3.832 s | **75.0%** |

**Honest assessment:** No single mode dominates. Each MO mode unlocks something the legacy router cannot:
- ⚡ **Speed** — p95 latency: 13.0 s → 0.5 s
- 🔒 **Private** — 75% of sensitive traffic stays on local-only models
- 💰 **Economy** — cost cut pushed to 82.5%
- 🏆 **Quality** — reaches 97.6% of GPT-5 (deliberately spends more)

### Model Mix Per Mode

The MO router genuinely diversifies beyond the legacy's Qwen/gpt-5 binary:

| Policy | Model mix (% of test queries) |
|---|---|
| legacy cascade | Qwen3-8B 49.6 · gpt-5 50.4 |
| MO · Economy | Qwen3-8B 41.1 · gpt-4.1 39.0 · gemini-2.5-flash 18.4 · deepseek 1.4 |
| MO · Balanced | gpt-5 51.8 · gpt-4.1 39.0 · gemini-2.5-flash 9.2 |
| MO · Speed | gemini-2.5-flash 99.6 · gemini-2.5-pro 0.4 |
| MO · Quality | gpt-5 38.7 · gemini-2.5-pro 31.2 · gpt-4.1 28.4 · Qwen3-8B 1.8 |
| MO · Private | Qwen3-8B 92.6 · Llama-3.1-8B 7.4 |

> The legacy router concentrates on two models not because of a bug, but because on this benchmark no mid-tier model is both cheaper *and* better than the Qwen/gpt-5 pair — a **sparse Pareto frontier**, not a tuning failure.

### Pareto Frontiers

`routing/pareto.py` computes dominance with `{quality: +1, cost: -1, latency: -1}` and returns three frontiers:

| Frontier | Models |
|---|---|
| `global` | Llama-3.1-8B, Qwen3-8B, deepseek-v3, gemini-2.5-flash, gpt-5 |
| `quality_floor` | gpt-5 (only frontier model clearing the balanced floor) |
| `privacy_approved` | Llama-3.1-8B, Qwen3-8B (recomputed inside the local-only subset) |

### Leakage Hygiene

| Step | Script | Split used | Output |
|---|---|:---:|---|
| Freeze heads + calibrate + measure stats | `routing/tune_mo.py` | **train** | `routing/models/mo_objectives.json` |
| Verify each mode's quality floor | `routing/tune_mo.py` | **val** | `val_meets_floor`, `legacy_val` |
| Old-vs-new sealed evaluation | `routing/eval_mo.py` | **test** (sealed) | `routing/results/mo_eval_report.csv` |

---

## 🖥️ Dashboard

A self-contained service with 9 panels — FastAPI backend + React 18 + TypeScript + Vite + Recharts frontend:

| # | Section | What It Shows |
|:---:|---|---|
| 1 | **Route Arena** | Live decision: chosen model, per-model P(correct) bars, animated cascade walk, complexity estimate, explainable routing reasons, exact per-query saving |
| 2 | **Multi-Objective Playground** | 5-mode objective selector · sensitivity control · latency-budget & quality-floor sliders · calibrated routing score and full per-model comparison |
| 3 | **Cost ↔ Quality ↔ Latency ↔ Privacy** | Measured Pareto frontier scatter · sealed-test trade-off table · live deterministic sensitivity classifier |
| 4 | **Results + Quality Guardrail** | Frozen policy table · cost/accuracy frontier · floor-vs-current guardrail that fails loudly if quality drops below `A_min` |
| 5 | **Evidence Lab** | Splits manifest · seed · per-stratum counts · duplicate-id leakage audit |
| 6 | **Business Impact** | Daily / monthly / yearly savings at any query volume |
| 7 | **Operations** | Live session telemetry: escalation rate · model mix · cumulative savings sparkline |
| 8 | **Model Pool** | 8-model landscape with pricing, accuracy per capability class, cost, latency |
| 9 | **How It Works** | Architecture · feature vector · cascade — drawn from the same code the server runs |

A narration-ready walkthrough lives in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

---

## 🔌 API Reference

Base URL: `http://127.0.0.1:8317` · Interactive docs: `/api/docs`

| Method | Path | Purpose |
|:---:|---|---|
| `POST` | `/api/route` | Route one query (legacy + MO opt-in) |
| `GET` | `/api/objectives` | MO config: lambda weights, quality floors, calibration metrics |
| `GET` | `/api/pareto` | Per-model Pareto points + 3 frontiers |
| `GET` | `/api/privacy` | Administrator privacy metadata per model |
| `POST` | `/api/sensitivity` | Deterministic local sensitivity classifier |
| `GET` | `/api/results` | Frozen policy tables + splits manifest |
| `GET` | `/api/models` | Model pool: pricing, accuracy, cost, latency |
| `GET` | `/api/modes` | Mode presets with val-measured accuracy & cost |
| `GET` | `/api/scenarios` | Six real test-split demo chips |
| `GET` | `/api/stats` | Live session telemetry |
| `GET` | `/health` | Liveness probe |

**Legacy route request:**

```bash
curl -s -X POST http://127.0.0.1:8317/api/route \
  -H "Content-Type: application/json" \
  -d '{"query": "You are given two positive integers A and B. Output the square of A + B.",
       "query_class": "Coding", "mode": "balanced"}'
```

<details>
<summary>📄 Real response — Qwen3-8B selected at 96.2% savings (click to expand)</summary>

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

</details>

**Privacy-filtered route (MO router):**

```bash
curl -s -X POST http://127.0.0.1:8317/api/route \
  -H "Content-Type: application/json" \
  -d '{"query": "My email is jane@corp.com and my card is 4111 1111 1111 1111 - summarise my medical record.",
       "mode": "private"}'
```

<details>
<summary>📄 Real response — privacy filter blocks external models (click to expand)</summary>

```json
{
  "router": "multi_objective",
  "mode": "private",
  "selected_model": "Qwen3-8B",
  "routing_score": 0.6485,
  "privacy_status": "approved",
  "sensitive": true,
  "sensitivity": { "sensitivity": "sensitive", "reason": "local pattern #0 matched (PII/credential shape)" },
  "eligible_models": ["Llama-3.1-8B-Instruct", "Qwen3-8B"],
  "constraints": {
    "privacy_restricted": true,
    "lambda_cost": 0.5,
    "lambda_latency": 0.1,
    "quality_floor": null,
    "latency_budget_ms": null
  },
  "latency": { "router_overhead_ms": 1.063, "model_inference_ms": 3679.0, "end_to_end_ms": 3680.1 },
  "reason": "Best quality/cost/latency utility among eligible models under the Private objective.",
  "reason_code": "utility_argmax",
  "model_scores": [
    { "model": "Llama-3.1-8B-Instruct", "routing_score": 0.1799, "eligible": true,  "admissible": true },
    { "model": "Qwen3-8B",              "routing_score": 0.6485, "eligible": true,  "admissible": true },
    { "model": "gemini-2.5-flash",      "routing_score": 0.6571, "eligible": false, "admissible": false },
    { "model": "gpt-4.1",               "routing_score": 0.7078, "eligible": false, "admissible": false }
  ]
}
```

> `gemini-2.5-flash` (0.6571) and `gpt-4.1` (0.7078) both score *higher* than `Qwen3-8B` (0.6485) — but they are external models. The privacy filter marks them `eligible: false` before they can ever compete.

</details>

**Input validation:** Malformed input is rejected with **422**, never a 500. Missing/empty `query`, over-length text, out-of-range `threshold`, and unknown `mode` all fail at the schema boundary.

---

## 🧪 Verification Suite

```bash
pip install -r requirements-dev.txt
pytest tests/            # 130 passed in ~30-40 s
```

The suite is *verification only* — it never relaxes a tolerance to go green. See [`tests/README.md`](tests/README.md).

| File | Tests | What It Pins |
|---|:---:|---|
| `test_parity.py` | 4 | Deployed router reproduces **84.04% accuracy, $0.006023/query, 94.8% quality** — digit-identical to the frozen report |
| `test_router_core.py` | 11 | Feature width always 2,066 · cascade stops at first model over `t` · fallback to gpt-5 · bit-identical determinism |
| `test_modes.py` | 9 | Effective threshold is 0.80/0.95/0.99, not just a label · explicit threshold overrides mode |
| `test_edge_cases.py` | 20 | Empty, 10k-char, unicode/emoji, SQL/prompt-injection inputs stay sane · invalid input → 4xx, never 500 |
| `test_freetext_safety.py` | 3 | Any casual prompt routed to a cheap model must carry >0.90 confidence |
| `test_batch_consistency.py` | 5 | Batch and single-query routing agree across all 5 capability classes |
| `test_performance.py` | 4 | 100 calls within p50/p95/p99 bounds · weights not reloaded per request · no memory growth |
| `test_scenario_chips.py` | 5 | Six demo chips route to exactly the model and saving they advertise |
| `test_mo_pareto.py` | 10 | Dominance is irreflexive, asymmetric, transitive · 3 frontiers match hand-computed sets |
| `test_mo_privacy.py` | 15 | Sensitivity classifier is deterministic and in-process · privacy mask runs **before** selection |
| `test_mo_router.py` | 20 | Hard constraints applied before ranking · graceful degradation · per-mode determinism |
| `test_mo_api.py` | 24 | Legacy backward compat · MO opt-in dispatch · 422 validation · 4 new endpoints |

### Measured Baselines (asserted, not merely printed)

| Property | Measured | Bound |
|---|:---:|:---:|
| Parity vs frozen report | 84.04% / $0.006023 / 94.8% | exact after rounding |
| Free-text escalation rate | **92.9%** (13 of 14 casual prompts → gpt-5) | ≥ 50% |
| `/api/route` p50 / p95 / p99 latency | **11.4 ms / 24.1 ms / 27.4 ms** | p99 < 200 ms |
| Memory growth over 100 requests | **+0.11 MB** | < 8 MB |
| Per-request weight reload | none (structural guard) | must be none |

> The 92.9% escalation rate is the honest cost of the safety rule. On casual free text the router mostly refuses to gamble and escalates. Its savings come from benchmark-shaped queries — exactly what the test split measures.

---

## 🔬 Reproducing the Research

One command regenerates every Phase-2 artifact in dependency order:

```bash
python -m routing.run_all              # full run
python -m routing.run_all --fast       # skip the two slow training stages (5, 6)
python -m routing.run_all --from 4     # resume at stage N
```

| Stage | Task | Output |
|:---:|---|---|
| 0 | `validate_cleaned.py` — dataset gate | schema/alignment assertions |
| 1 | `routing.build_matrix` | `routing/data/routing_matrix.csv` |
| 2 | `routing.splits` | stratified splits + difficulty tiers + manifest |
| 3 | `routing.validate_dedup` | duplicate-id leakage audit |
| 4 | `routing.oracle` | hindsight oracle + alpha sweep |
| 5 | `routing.learned_router` | **our method**: heads, `t*`, report |
| 6 | `routing.baselines` | unified policy comparison table |
| 7 | `routing.plots` | publication figures |
| 8 | `routing.fresh_model_demo` | extensibility demo: add a 9th model |

`routing/config.py` centralises model order, `ALPHA`, `QUALITY_FLOOR`, `SEED` and all paths, so stages stay decoupled and reproducible.

### Multi-Objective Artifacts *(separate, opt-in)*

```bash
python -m routing.tune_mo    # calibrate on train, verify on val -> routing/models/mo_objectives.json
python -m routing.eval_mo    # sealed test split evaluation       -> routing/results/mo_eval_report.csv
```

> `tune_mo` never touches the test split. `eval_mo` is the **only** script that reads it.

### Data Policy

`cleaned/`, `raw/` and all `*.csv` files (1.3 GB) are **excluded from git** and exchanged out-of-band. Only source, config, docs, figures, and the built dashboard bundle are version-controlled. **No API key is ever committed** — `run_eval.py` resolves all secrets from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`, `QWEN_API_KEY`, `LLAMA_API_KEY`, plus `*_API_BASE` for self-hosted models).

---

## 📁 Repository Layout

```
OptiRoute-AI/
├── routing/                  # Research pipeline + MO layer
│   ├── build_matrix.py       #   A1: query x model outcome matrix
│   ├── splits.py             #   U1/U3: stratified train/val/test + difficulty tiers
│   ├── oracle.py             #   A2: hindsight oracle + alpha sweep
│   ├── learned_router.py     #   A3: our method — one head per model, t* tuned on val
│   ├── baselines.py          #   R1/R2: unified policy comparison
│   ├── run_all.py            #   One-command pipeline runner
│   ├── pareto.py             #   MO: dominance + 3 frontiers
│   ├── objectives.py         #   MO: mode/lambda config
│   ├── sensitivity.py        #   MO: deterministic local classifier
│   ├── mo_core.py            #   MO: shared selection core
│   ├── tune_mo.py            #   MO: calibrate + verify -> mo_objectives.json
│   └── eval_mo.py            #   MO: sealed-test evaluation -> mo_eval_report.csv
├── webapp/                   # Delivery layer
│   ├── server.py             #   FastAPI server
│   ├── router_core.py        #   Offline inference engine (~11 ms)
│   ├── export_weights.py     #   Train + tune + persist weights
│   ├── mo_router.py          #   Multi-objective router
│   ├── privacy_policy.json   #   Administrator privacy config
│   ├── smoke_test.py         #   Endpoint self-check
│   ├── static/               #   Legacy vanilla dashboard fallback
│   └── frontend/             #   React 18 + TypeScript + Vite + Recharts
│       └── src/              #     29 source files, committed dist/ (~611 KB)
├── tests/                    # 130-test correctness suite
│   └── README.md
├── scripts/                  # Phase-1 provenance: cleaning, auditing, analysis
├── figures/                  # Phase-1 analysis figures
├── docs/                     # model_selection_rationale.md, model_citations.md
├── references/               # Five reviewed papers
├── run_eval.py               # Generic OpenAI-compatible evaluation harness
├── models_registry.json      # Config-driven model registry
├── validate_cleaned.py       # Active dataset gate (pipeline stage 0)
├── DEMO_SCRIPT.md            # Narration-ready 3-minute walkthrough
├── requirements.txt          # numpy, pandas, fastapi, uvicorn, pydantic, matplotlib, seaborn
└── requirements-dev.txt      # + pytest, httpx
```

**Requirements:** Python 3.11+ · Node 18+ *(only to rebuild the frontend)*

---

## 📋 Research Questions

| RQ | Question | Answer |
|:---:|---|---|
| RQ1 | Cost achievable at a quality floor? | **94.8%** of flagship quality at **68.4%** cost reduction |
| RQ2 | What is the ceiling? | Oracle **94.68%** vs strongest **88.65%**; 111 queries unsolvable by any model |
| RQ3 | How do baselines compare? | Ours is the only floor-meeting policy above 50% reduction |
| RQ4 | Where does difficulty bite? | Hard tier separates routers most; oracle-learned gap widens there |
| RQ5 | How much headroom is left? | **10.64 points** — the case for calibrated confidence and richer features |
| RQ6 | Can quality, cost, latency and privacy be traded explicitly? | Yes — 5 MO presets expose the full trade-off surface |

---

## ⚠️ Honesty Notes & Limitations

- **10.64-point oracle gap remains** — we quantify the headroom rather than claiming we closed it
- **Hard tier is weak (11.76%)** — 111 queries are unsolvable by all eight models; no router fixes that
- **Latency is traded away** by the default policy — reported per policy, per mode, per query
- **Free text escalates ~93% of the time** — the router is conservative outside the benchmark distribution by design
- **One documented asymmetry:** training-side `make_X` sizes its one-hot block from classes present in a batch; inference-side `featurize` always uses the fixed 5-class order. Offline evaluation batches all five classes so frozen numbers are unaffected — and a regression test pins the behaviour
- **Self-hosted models priced at $0** — their compute cost is real but out-of-pocket-zero in this accounting; measured latency is not zero and is reported
- **Sparse Pareto frontier** — only 5 of 8 models are globally non-dominated; the legacy cascade concentrates on Qwen/gpt-5 because no mid-tier model is simultaneously cheaper *and* better — a property of the pool, not a tuning failure
- **MO Quality mode has a negative cost saving (−146.5%)** — it deliberately spends more than always-GPT-5 to maximise quality; labelled as such
- **Local routing ≠ a private model** — the sensitivity classifier runs locally, but real privacy is enforced only by the `approved_for_sensitive` mask in `webapp/privacy_policy.json`
- **Calibration is verified, not assumed** — MO `routing_score` is Platt-scaled on train and checked on val; legacy `p_correct` is explicitly *not* renamed because it is uncalibrated

---

## 📄 License

MIT © OptiRoute AI contributors