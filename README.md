# AetherFlow — Dynamic Multi-LLM Routing & Benchmark Suite

Final Year Project (Fall 2025 – Spring 2026).

AetherFlow is a standardized empirical benchmark suite and routing research
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
| `graphs_output/` | Phase 1 analysis figures (accuracy, cost, latency, tradeoffs) |
| `Research Papers (AetherFlow)/` | The five reviewed papers (FrugalGPT, RouteLLM, Self-REF, Confident-or-Seek-Stronger, LLMRouterBench) |
| `run_eval.py` + `models_registry.json` | Generic OpenAI-compatible evaluation harness + config-driven model registry |
| `clean_and_merge_all.py`, `sanitize_excel_csvs.py`, `audit_junk_data.py`, `validate_cleaned.py`, `add_query_ids.py` | Data cleaning / auditing / alignment pipeline |
| `analyze_8_models.py`, `run_full_analysis_local.py`, `generate_*.py` | Phase 1 analysis & graph generation |
| `routing/` | Phase 2 routing experiments (oracle, baselines, learned router) |

## Dataset (out of git)

- 8 models: Llama-3.1-8B-Instruct, Qwen3-8B, DeepSeek-v3-0324,
  Gemini-2.5-Flash, Gemini-2.5-Pro, GPT-4.1, Claude-Sonnet-4, GPT-5
- 5 capability classes: Coding, Mathematical Reasoning, Scientific
  Questionnaire, General Knowledge, Competitive Math
- Strict alignment via SHA1 `query_id`: 1,887 queries × 8 models
- Observed spread: ~6,200× cost, ~55× latency, 51.4-point accuracy

## Documentation

- `AetherFlow_Master_Project_Document.docx` — master project & literature review
- `AetherFlow_Project_and_Literature_Review.md` — markdown twin of the above
- `model_selection_rationale.md`, `model_citations_and_references.md`
- `master_project_and_dataset_documentation.md`
- `PHASE2_TASK_ASSIGNMENTS.md` — Phase 2 work breakdown per contributor

## Status

Phase 1 (benchmark construction & landscape analysis): complete.
Phase 2 (routing experiments): in progress — see task board.
