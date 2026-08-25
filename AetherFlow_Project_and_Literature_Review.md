# AetherFlow: Dynamic Multi-LLM Routing and Benchmark Suite
## Master Project & Literature Review Document

**Project type:** Final Year Project (2-semester, Fall 2025 - Spring 2026)
**Status:** Phase 1 complete (~60%) - Phase 2 (routing experiments) pending
**Last updated:** August 2026

---

## Table of Contents
1. [Project Identity](#1-project-identity)
2. [Completed Assets](#2-completed-assets)
3. [Dataset Architecture](#3-dataset-architecture)
4. [Literature Review: 5 Papers & Their Relation to AetherFlow](#4-literature-review)
5. [Novelty & Positioning](#5-novelty-and-positioning)
6. [Research Questions (RQ1-RQ5)](#6-research-questions)
7. [Phase 2 Roadmap](#7-phase-2-roadmap)
8. [Defense / Viva Strategy](#8-defense-strategy)
9. [Thesis Structure Mapping](#9-thesis-structure)
10. [Key Numbers to Memorize](#10-key-numbers)

---

## 1. Project Identity

AetherFlow is a standardized empirical benchmark suite and routing research framework that evaluates eight state-of-the-art LLMs across 26 benchmark sources (consolidated into five capability classes) under a strict query-aligned schema with measured per-query cost and latency. On top of this ground truth, the project establishes the three-objective (Accuracy-Cost-Latency) Pareto frontier, implements oracle and practical query-level routers, and quantifies the gap between practical and theoretically optimal routing - with particular attention to how that gap widens on difficult queries.

**One-line essence:** We route requests based on *predicted answer quality per query*, not price lists - the intelligence layer that commercial aggregators (AgentRouter, OpenRouter) lack.

### The distinction that defines us

| | Commercial routers (AgentRouter / OpenRouter) | AetherFlow |
|---|---|---|
| Routing decision | Price list / availability / user preference | Predicted per-query correctness |
| Uses accuracy-outcome data | No | Yes - 1,887 x 8 aligned outcomes |
| Latency-aware per query | No | Yes (3-objective) |
| Oracle-gap / research analysis | No | Core contribution |

---

## 2. Completed Assets

### Data assets
- **26 benchmark sources** cleaned, audited, mapped into **5 capability classes**: Coding, Mathematical Reasoning, Scientific Questionnaire (MCQ), General Knowledge, Competitive Math
- **8 modern LLMs evaluated:** Llama-3.1-8B-Instruct, Qwen3-8B, DeepSeek-v3-0324, Gemini-2.5-Flash, Gemini-2.5-Pro, GPT-4.1, Claude-Sonnet-4, GPT-5
- **Strict alignment:** 1,887 identical prompts x 8 models (`cleaned/aligned_8_models/`); extended set 3,352 x 7 (`aligned_7_models/`); full individual sets (`individual/`)
- **Stable `query_id`** (SHA1-based) backfilled into all 15 aligned CSVs - verified 1,887/1,887 match across all 8 model files; any new model joins on ID, not row position
- **Known quirk:** aligned_7 contains ~246 duplicate queries (3,106 unique IDs of 3,352 rows) - must dedup before train/test splits to avoid leakage

### Infrastructure assets
- `models_registry.json` - config-driven model registry (provider, endpoint, pricing per 1M tokens, snapshot date, `_template` entry for future models)
- `run_eval.py` - generic OpenAI-compatible evaluation harness (any provider incl. local vLLM/Ollama; auto-scoring for boxed math, MCQ letters A-D, numeric equivalence; measured `actual_latency`; dry-run cost estimation)
- `add_query_ids.py` - query-ID backfill tool (idempotent)
- Analysis and graph tooling: `analyze_8_models.py`, `run_full_analysis_local.py`, graph generators
- Documentation: master docs, model selection rationale, citations file, this document

### Measured spread (the routing-relevant variance)
- **Cost differential:** ~6,200x ($0.000013 Llama-8B to $0.0829 Gemini-Pro per query)
- **Latency differential:** ~55x (0.19s Gemini-Flash to 10.8s CoT competition math)
- **Accuracy differential:** ~51.4 points (37.31% Llama-8B to 88.77% GPT-5)

---

## 3. Dataset Architecture

```
26 Benchmark Sources
        |
Cleaning + Auditing (sanitize, dedup, one-row-per-record)
        |
5 Capability Classes (Coding | Math Reasoning | Sci-QA MCQ | Gen Knowledge | Competitive Math)
        |
1,887 Aligned Queries (query_id joined across models)
        |
8 Modern LLMs (open-weights anchors -> flagship closed models)
        |
Accuracy | Cost (USD) | Measured Latency (s)   [17-column schema]
        |
Pareto Frontier (Accuracy-Cost-Latency)
        |
   Oracle Router  ->  Learned/Baseline Routers
        |
Evaluation: accuracy / cost / latency / savings / gap-to-oracle
        |
Difficulty-stratified failure analysis (Easy / Medium / Hard)
```

**Schema (17 columns):** `index, query_id, dataset_name, model_name, origin_query, prompt, ground_truth, prediction, score, correct, prompt_tokens, completion_tokens, total_tokens, cost, estimated_latency, actual_latency, raw_output`

**Model taxonomy (classes, not specific models - this is why the work does not age):**

| Class | Members | Role |
|---|---|---|
| Small open-weights | Llama-3.1-8B, Qwen3-8B | Zero/minimal-cost anchor, edge deployment |
| Efficient open flagship | DeepSeek-v3 | Cost-efficiency Pareto point |
| Fast cheap closed | Gemini-2.5-Flash | Ultra-low-latency anchor |
| Enterprise closed | GPT-4.1, Claude-Sonnet-4 | Commercial baselines |
| Flagship | GPT-5, Gemini-2.5-Pro | Accuracy ceiling |

New model releases (Opus-class, etc.) slot into existing classes - the taxonomy persists, only occupants rotate.

---

## 4. Literature Review

Five papers, ordered chronologically. Every paper maps to a **citation**, a **baseline**, or a **testable hypothesis** in our project.

### 4.1 FrugalGPT (Stanford, 2023) - arXiv:2305.14930
- **Contribution:** Introduced LLM cascades - try a cheap model first, escalate to stronger models when the answer is likely wrong; demonstrated large cost reductions on GPT-3/4-era benchmarks.
- **Relation to AetherFlow:** *Ancestor citation, not competitor.* Established the cost-saving premise, but: small cascades only, no query-aligned public benchmark, no latency objective, pre-2024 models.
- **Use in project:** Foundational motivation; implement a FrugalGPT-style confidence cascade as a baseline router.

### 4.2 RouteLLM (LMSYS / UC Berkeley, 2024) - arXiv:2407.21783
- **Contribution:** Learned pairwise router (strong vs. weak model) trained on preference data; showed ~2-3x cost savings at ~90% of GPT-4 quality; formalized the LLM routing problem.
- **Relation:** Closest methodological ancestor. But: pairwise only, cost-quality only (no latency), 2024-era models, no difficulty analysis, no oracle-gap quantification on modern flagships.
- **Use in project:** Implement a RouteLLM-style learned router as a baseline; cite for problem formulation.

### 4.3 Self-REF (Apple / Rice University, ICML 2025) - arXiv:2410.13284
- **Contribution:** Trains special *confidence tokens* into an LLM so it reliably self-reports whether its answer is correct; extracted confidence scores improve downstream routing and rejection.
- **Relation:** A *confidence-signal technique*, not a benchmark or router evaluation. Answers "how should a model express confidence?" - we answer "given 8 models' actual outcomes, how well can any router exploit query-level differences?" **Orthogonal.**
- **Use in project:** Cite for the confidence-routing family; lightweight variant (verbalized confidence, no training) becomes a baseline router signal.

### 4.4 Confident or Seek Stronger (2025) - arXiv:2502.04428
- **Contribution:** Comprehensive benchmark of *uncertainty-driven* SLM-to-LLM offloading across 1,500+ settings; finds uncertainty-correctness alignment (not downstream data) drives routing success; releases calibration-data pipeline for generalization.
- **Relation:** Closest in *spirit* (routing benchmarking), but four concrete differences:
  1. **Pairwise, not N-way** - routes between one SLM and one strong LLM; we do 8-way selection over a full Pareto frontier
  2. **Uncertainty-driven only** - no learned query-feature routing (kNN/embeddings), no oracle policy
  3. **No latency objective** - efficiency = avoided LLM invocations, not measured 3-objective tradeoffs
  4. **No difficulty/oracle-gap analysis** - they benchmark strategies; we quantify the structural gap between practical and optimal routing
- **Bonus - testable hypothesis in our data:** Their claim that uncertainty-correctness alignment determines routing success is directly verifiable on our 1,887 x 8 aligned dataset: compute per-class correlation between confidence signals and correctness across 8 models. A unique analysis chapter on modern flagships.
- **Use in project:** Cite for uncertainty-routing state of the art; uncertainty-based router becomes a baseline; their finding becomes one of our research sub-questions.

### 4.5 LLMRouterBench (Shanghai AI Laboratory, 2026) - arXiv:2601.07206
- **Contribution:** Large-scale routing benchmark; notes prior benchmarks "lack coverage of flagship models with realistic inference costs."
- **Relation:** The closest contemporaneous work - must be addressed explicitly. Our differentiators:
  1. **Query-level strict alignment** (1,887 x 8) enabling per-instance oracle computation - rare even in 2026 benchmarks
  2. **Measured per-query latency**, not token-count estimates
  3. **Difficulty-tiered capability classes** supporting routing-collapse / routing-plateau analysis
  4. **Three-objective Pareto frontier** (accuracy-cost-latency), not cost-quality only
- **Use in project:** Cite as the benchmark we extend; read its limitations section and answer each point in one thesis paragraph.

### 4.6 Related non-paper context
- **RouterBench (2024):** cost-quality only, GPT-4/Claude-2 era, admits no latency coverage - positioning foil.
- **Commercial aggregators (AgentRouter, OpenRouter):** request-forwarding infrastructure, no correctness prediction. AetherFlow is the research layer that would sit on top of them.

### 4.7 Summary matrix

| Paper | Year | Type | Threat to novelty | Our use |
|---|---|---|---|---|
| FrugalGPT | 2023 | Cascade method | None - ancestor | Citation + cascade baseline |
| RouteLLM | 2024 | Learned pairwise router | None - pairwise, no latency | Citation + learned baseline |
| Self-REF | 2025 | Confidence-signal training | None - orthogonal technique | Citation + confidence baseline |
| Confident or Seek Stronger | 2025 | Uncertainty routing benchmark | Low - pairwise, UQ-only, no latency | Baseline + testable hypothesis |
| LLMRouterBench | 2026 | Routing benchmark | Moderate - closest work | Explicit differentiation paragraph |

---

## 5. Novelty and Positioning

### What we do NOT claim
- We did not invent LLM routing (FrugalGPT/RouteLLM did the pioneering)
- We do not claim three-way Pareto routing is unprecedented (say nothing unless literature review proves it)
- We are not a commercial router

### What we DO claim (the combination novelty)
1. **Modern model pool:** 2025-26 flagships + open-weights anchors vs. GPT-4-era prior work
2. **Measured latency** per query, not token-count estimates
3. **Strictly query-aligned benchmark** across 5 capability classes (per-instance oracle possible)
4. **Three-objective Pareto frontier:** accuracy-cost-real latency
5. **Per-query oracle** quantifying the practical-vs-optimal routing gap
6. **Difficulty-stratified failure analysis** connecting to published routing-collapse / routing-plateau findings

### Safe positioning statement (use in thesis abstract)
> "AetherFlow investigates modern multi-LLM routing under a jointly measured Accuracy-Cost-Latency objective. We construct an independently curated and query-aligned benchmark spanning five capability classes and eight contemporary LLMs, including flagship and low-cost models with substantial variation in inference cost and measured latency. Beyond establishing the resulting Pareto frontier, we evaluate practical query-level routers against an oracle routing policy and analyze their performance across capability and difficulty levels, with particular attention to the gap between practical and optimal routing."

### Why the project is safe despite 5 related papers
Every paper maps to a citation, a baseline, or a hypothesis - the literature *scaffolds* the project rather than blocking it. FYPs are judged on competence + rigor, not invention; our empirical contribution (modern, measured, aligned) is genuine and defensible.

---

## 6. Research Questions

- **RQ1 - Model landscape:** How do modern LLMs differ across accuracy, cost, and latency? *(answered by benchmark)*
- **RQ2 - Pareto efficiency:** Which models are Pareto-optimal under Accuracy-Cost-Latency? *(answered by frontier)*
- **RQ3 - Routing effectiveness:** Can query-level routing achieve comparable quality at substantially lower cost and latency than always using the strongest model? *(main experiment)*
- **RQ4 - Difficulty:** Does routing performance deteriorate disproportionately on difficult queries? *(capability x difficulty analysis)*
- **RQ5 - Gap to oracle:** How close can practical routers get to the theoretically optimal per-query routing policy? *(most interesting analysis)*

**Oracle formulation:** for quality threshold A_min (e.g., 90%), for every query q:
`m*(q) = argmin_m [ C_m(q) + alpha * L_m(q) ]` subject to `correct_m(q) = 1`
Oracle Gap = Performance(oracle) - Performance(router)

---

## 7. Phase 2 Roadmap

| # | Task | Est. effort | Output |
|---|---|---|---|
| 1 | Oracle router on aligned data | ~1 day | Headline result: oracle table + gap baseline |
| 2 | Baselines: always-cheapest, always-strongest, FrugalGPT cascade, confidence router, RouteLLM-style kNN | ~1 week | Baseline roster table |
| 3 | One learned router as "our method" | 1-2 weeks | AetherFlow router row |
| 4 | Splits: 70/15/15 stratified by capability x difficulty + near-duplicate leakage checks (dedup aligned_7) | ~2 days | Trustworthy evaluation |
| 5 | Evaluation suite: main table + Easy/Medium/Hard breakdown | ~3 days | Strongest thesis chapter |
| 6 | Answer RQ1-RQ5 explicitly | writing | Report chapters |
| 7 | Fresh-model integration demo (via run_eval.py + registry) before viva | ~half day | Kills "why not latest models" question |
| 8 | Thesis writing + viva prep (live routing demo) | ongoing | Defense-ready |

**Rule:** stop expanding the benchmark; all remaining value is in the routing experiments.

**Target results table format (numbers illustrative):**

| Router | Accuracy | Cost/query | Latency | Cost reduction | Oracle gap |
|---|---|---|---|---|---|
| GPT-5 only | high | $$$ | slow | 0% | - |
| Cheapest only | low | $ | fast | ~90% | large |
| kNN router | ~92% | $$ | med | ~72% | ... |
| Cascade | ~93% | $$ | med | ~68% | ... |
| AetherFlow (ours) | ~94% | $$ | med | ~75% | ... |
| Oracle | upper bound | $$ | fast | ~82% | 0 |

Plus difficulty breakdown (Easy/Medium/Hard x router) - expected finding: gaps concentrate on hard queries, matching published routing-plateau results.

---

## 8. Defense Strategy

### Q: "Why are your models old / why not Opus 5 / latest models?"
Four-layer answer:
1. **Classes, not models:** our 8 models represent stable classes (small-open, efficient-open, fast-cheap, enterprise, flagship). New releases fill existing slots; the taxonomy does not age.
2. **Declared snapshot:** thesis states the evaluation window (Aug 2025 - Jan 2026) and that the framework accepts updated entries via configuration. Precedent: RouteLLM shipped on GPT-4-era models and is heavily cited.
3. **Live proof:** demo - newest released model integrated via `models_registry.json` + `run_eval.py` in hours on a 300-query subset. Slide: "Model released [date] -> integrated in [X] hours."
4. **Reframe:** hundreds of new models strengthen the motivation - choice paralysis makes automated routing a necessity, not an optimization.

### Q: "RouterBench / LLMRouterBench already exist?"
Answer: they established cost-quality tradeoffs on older models with estimated latency and without strict per-query alignment; we provide the modern, measured, aligned, difficulty-analyzed environment - and quantify the oracle gap they do not.

### Q: "What is your novelty if routing exists?"
Answer: the combination - modern pool + measured latency + query alignment + 3-objective frontier + per-query oracle + difficulty-stratified gap analysis. Empirical novelty is real novelty (RouterBench earned 200+ citations on measurement alone).

### Q: "How is this different from AgentRouter/OpenRouter?"
Answer: they move requests (price/availability rules); we predict per-query answer quality. They are plumbing; AetherFlow is the brain deciding which pipe to use. The 51.4-point accuracy spread is why the choice matters.

---

## 9. Thesis Structure Mapping

| Thesis chapter | Content | Source |
|---|---|---|
| 1. Introduction | Cost problem, choice proliferation, AetherFlow | this doc sec. 1 |
| 2. Literature review | 5 papers + RouterBench + aggregators | sec. 4 |
| 3. Benchmark methodology | 26 sources, 5 classes, alignment, schema, registry/harness | sec. 2-3 |
| 4. Model landscape & Pareto frontier | RQ1, RQ2 | existing graphs |
| 5. Routing experiments | RQ3, RQ5: baselines, our router, oracle gap | Phase 2 |
| 6. Difficulty & failure analysis | RQ4: Easy/Med/Hard, collapse/plateau | Phase 2 |
| 7. Conclusion & future work | extensibility, agentic tasks, live data | - |

Optional: workshop paper (efficient-LLM workshop at NeurIPS/ICML) reusing chapters 3-6.

---

## 10. Key Numbers to Memorize

- **8** models, **26** benchmark sources, **5** capability classes
- **1,887** aligned queries x 8 models; **3,352** x 7 extended (3,106 unique - dedup before splits)
- **6,200x** cost spread | **55x** latency spread | **51.4-point** accuracy spread
- Accuracy range: **37.31%** (Llama-8B) to **88.77%** (GPT-5)
- Cheapest: **$0.000013/query** (Llama-8B); priciest: **$0.0829/query** (Gemini-Pro); fastest: **0.194s** (Gemini-Flash)
- Target routing savings: **70-80%** cost at **90%+** flagship quality
- Split: **70/15/15** stratified; quality threshold for oracle: **A_min = 90%**

