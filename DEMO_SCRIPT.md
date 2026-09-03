# OptiRoute AI — 3-Minute Demo Script

Server: `python -m webapp.server` → http://127.0.0.1:8317
(Weights already exported; no API keys needed. Open the page in a clean
browser window, light theme, zoom 100%. The arena auto-routes a real
benchmark query on load, so you land on a live decision.)

Headline numbers are from the frozen held-out **test split** (282 queries):
**84.04% accuracy**, **68.4% lower cost**, **94.8% of GPT-5 quality**, with
the oracle ceiling at 80.8% cost cut. Everything on the page traces to these.

## 0:00 — The pitch (hero, ~25 s)

> "Eight production LLMs, 1,887 benchmark queries. A trained router decides —
> before spending a single token — which model each query actually needs.
> Result: **68.4% lower cost** while keeping **94.8% of GPT-5 quality**,
> measured on a held-out test split, not a projection. Cost is the objective;
> quality is the constraint."

## 0:25 — Route arena (section 01, ~70 s)

The six chips are **real benchmark queries** from the test split, chosen to
show the full routing spectrum. Click in this order:

1. **"Easy coding task"** → routes to **Qwen3-8B**, **96.2% cheaper** than
   GPT-5. Point at the *Alternative* box and the cascade walk: the cheapest
   confident model wins, one call, done.
2. **"Combinatorics puzzle"** → also a cheap route with big savings, but note
   the *Query complexity* bars lean harder — the router still found a cheap
   model that clears the bar.
3. **"Hard algebra"** → escalates to **gpt-5**. Point at the red "below t"
   chips and the fallback line: *no model was confident, so we escalate to the
   strongest*. This safety valve is why quality stays at 94.8%.

While the cascade animates:

> "This decision is made offline by a trained scorer — hashed n-gram features
> plus text statistics — in milliseconds. No model is called to decide."

Then the **three routing modes** (top of the arena):

- **Economy** (t = 0.80): routes cheaper, more aggressively — validation-split
  76.0% accuracy at $0.0029/query, *below* the quality floor.
- **Balanced** (t = 0.95): the measured headline policy — 83.8% at $0.0081.
- **Quality First** (t = 0.99): escalates readily — 85.5% at $0.0097.

> "These are configurable policies, each measured on the validation split —
> not marketing numbers. The headline test figures are the Balanced policy."

If time allows, hit **"Challenge the router"** once — it pulls another real
test query and routes it live.

## 1:35 — Results + guardrail (section 02, ~25 s)

- Policy table: the highlighted **learned cascade** row — 84.04% accuracy,
  68.4% cost cut, passes the floor. Compare always-cheapest (fails the floor)
  and oracle (the ceiling). Hover points on the frontier chart.
- **Quality guardrail**: floor 79.8%, current policy 84.04%, margin **+4.25
  pts**, **✓ SAFE**. Say the line: *"Cost is the objective; quality is the
  constraint — we optimize spend subject to a measured floor."*

## 2:00 — Evidence Lab (section 03, ~15 s)

> "This is reproducible, not a slide number: 282 held-out test queries, seed
> 42, 15 class×tier strata, leakage audit passed, 246 aligned-7 duplicates
> excluded." Hover *"what does oracle mean?"* — oracle has hindsight; we must
> decide before inference, so it's an upper bound, not a deployable baseline.

## 2:15 — Business impact (section 04, ~25 s)

Drag the volume slider from 10k → 1M queries/day:

> "At a million queries a day, always-GPT-5 costs about **$19,061/day**
> ($6.96M/year). OptiRoute runs the same workload for **$6,023/day**
> ($2.20M/year) — **$4.76M saved**, same quality floor. The 'what the savings
> buy' panel turns that into extra routed queries or extra GPT-5 calls for
> genuinely hard work."

## 2:40 — Operations + API (sections 05 & 08, ~15 s)

- **Operations**: live session telemetry — total queries, escalation rate,
  cumulative-savings sparkline. Note it's labeled demo/session data.
- **API playground**: the same decision is one `POST /api/route` away; click
  *copy curl*. "Drop-in on top of any existing LLM stack."

## 2:55 — Close (~5 s)

> "Model pool, per-class accuracy, pricing, and splits are all in the repo —
> every number reproducible from one command."

Tip: the **Dark/Light** toggle (top-right) is a clean way to end on-screen.

## Backup answers

- **"How close to the oracle?"** — Oracle picks with hindsight (knows the gold
  answer). The gap is concentrated in the hard tier, where no cheap model is
  confident — our fallback already sends those to the strongest model, the
  correct conservative move.
- **"Does the router call an LLM to decide?"** — No. Logistic heads over hashed
  text features; inference is microseconds and free.
- **"Why do typed free-text prompts often go to GPT-5?"** — The heads are
  trained on benchmark-format queries; arbitrary out-of-distribution text lands
  conservatively (nothing clears t = 0.95), so it escalates. That is the safe
  behavior, and the scenario chips use real benchmark queries to show the
  cheap-route wins.
- **"Is the complexity bar a separate model?"** — No. It's derived from the
  router's own per-model confidence (cheap/mid/strong thirds of the cascade),
  shown as an estimate — not a separately benchmarked classifier.
- **"What about latency?"** — Cheapest-first ordering also tends to pick faster
  models; latency numbers are in the model table (section 06).
