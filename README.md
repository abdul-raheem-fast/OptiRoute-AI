# OptiRoute AI — Intelligent LLM Router

OptiRoute AI is a standardized empirical benchmark suite and routing research
framework. It evaluates eight state-of-the-art LLMs across 26 benchmark
sources (consolidated into five capability classes) under a strict
query-aligned schema with per-query cost and latency. On top of this ground
truth it establishes the three-objective (Accuracy–Cost–Latency) Pareto
frontier, implements oracle and practical query-level routers, and quantifies
the gap between practical and theoretically optimal routing.

## Repository layout

| Path | Contents |
|---|---|
| `cleaned/` *(not in git — 1.3 GB, shared out-of-band)* | `aligned_8_models/` (1,887 × 8), `aligned_7_models/` (3,352 × 7), `individual/` |
| `raw/` *(not in git)* | Uncleaned per-model source CSVs — the inputs to the Phase-1 cleaning pipeline |
| `scripts/` | Historical Phase-1 scripts (cleaning, auditing, analysis, graphing) + the analysis notebook, kept for provenance |
| `figures/` | Phase 1 analysis figures (accuracy, cost, latency, tradeoffs) |
| `screenshots/` *(not in git)* | Dashboard captures for slides and docs |
| `references/` | The five reviewed papers (FrugalGPT, RouteLLM, Self-REF, Confident-or-Seek-Stronger, LLMRouterBench) |
| `run_eval.py` + `models_registry.json` | Generic OpenAI-compatible evaluation harness + config-driven model registry |
| `validate_cleaned.py` | Active dataset gate (run_all stage 0) |
| `routing/` | Phase 2 routing experiments (oracle, baselines, learned router) |
| `webapp/` | Live dashboard + routing API (`python -m webapp.server`) |

## Dataset (out of git)

- 8 models: Llama-3.1-8B-Instruct, Qwen3-8B, DeepSeek-v3-0324,
  Gemini-2.5-Flash, Gemini-2.5-Pro, GPT-4.1, Claude-Sonnet-4, GPT-5
- 5 capability classes: Coding, Mathematical Reasoning, Scientific
  Questionnaire, General Knowledge, Competitive Math
- Strict alignment via SHA1 `query_id`: 1,887 queries × 8 models
- Observed spread: ~6,200× cost, ~55× latency, 51.4-point accuracy

## Documentation

- `docs/model_selection_rationale.md`, `docs/model_citations_and_references.md`

## Live demo (web dashboard + routing API)

A self-contained dashboard with an offline routing simulator (the trained A3
router scores queries locally — no model API keys needed). Sections:

1. **Route arena** — live decision for one query: chosen model, per-model
   P(correct), a derived complexity estimate (easy/medium/hard), an
   explainable *why this route* list, an always-GPT-5 alternative with the
   per-query saving, and an animated cascade walk. Three configurable routing
   modes (Economy / Balanced / Quality First) and a "Challenge the router"
   button. The scenario chips are **real test-split benchmark queries**.
2. **Results + quality guardrail** — frozen test-split policy table, the
   cost/accuracy frontier, and a floor-vs-current guardrail ("cost is the
   objective, quality is the constraint").
3. **Evidence Lab** — splits manifest (seed, strata, leakage audit) and the
   strongest / OptiRoute / oracle comparison cards.
4. **Business impact** — daily/monthly/yearly savings at any volume, with a
   "what the savings buy" breakdown.
5. **Operations** — live session telemetry (escalation rate, model/tier mix,
   cumulative-savings sparkline), labeled demo/session data.
6. **Models**, **7. How it works + architecture**, **8. API playground**.

    python -m webapp.export_weights   # once per matrix rebuild: trains + saves router heads
    python -m webapp.server           # http://127.0.0.1:8317
    python webapp/smoke_test.py       # endpoint self-check (server must be running)

Endpoints: `POST /api/route` (accepts `mode` or `threshold`), `GET /api/results`
(+ splits manifest), `/api/models`, `/api/modes`, `/api/scenarios`, `/api/stats`,
`/health`; interactive docs at `/api/docs`. The simulator's displayed per-query
cost and latency are benchmark averages of the chosen model, and the complexity
bars are derived from the router's own confidence — headline savings always
come from the measured test split.

## Status

Phase 1 (benchmark construction & landscape analysis): complete.
Phase 2 (routing experiments): complete — see task board and `routing/results/`.
