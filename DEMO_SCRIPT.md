# AetherFlow — 3-Minute Demo Script

Server: `python -m webapp.server` → http://127.0.0.1:8317
(Weights already exported; no API keys needed. Have the page open in a
clean browser window, light theme, zoom 100%.)

## 0:00 — The pitch (hero, ~30 s)

Land on the hero. Read the headline, then point at the four numbers:

> "Eight production LLMs, 1,887 benchmark queries. A trained router decides —
> before spending a single token — which model each query actually needs.
> Result: **68.4% lower cost** while keeping **94.8% of GPT-5 quality**,
> measured on a held-out test split, not a projection. 80.8% is the oracle
> ceiling — hindsight-perfect routing — so we capture most of what's
> theoretically possible."

## 0:30 — Live simulator (~75 s)

Click through the chips in this order — they are chosen to hit three
different routing behaviors:

1. **"capital city"** — trivial fact.
   Point out: the cheapest model clears the bar instantly. One cheap
   model, one call, done.
2. **"merge lists"** — coding task.
   Point out: a mid-tier model clears it. The cascade walked past the
   cheapest and stopped where confidence was earned.
3. **"probability"** — hard math.
   Point out the red "below t" chips and the fallback: *no model was
   confident, so we escalate to the strongest*. This is the safety valve —
   the reason quality stays at 94.8%.

If time allows, type one audience-suggested query and run it (Ctrl+Enter).

One line while the cascade animates:

> "This decision is made offline by a trained scorer — hashed n-gram features
> plus text statistics — in milliseconds. No model is called to decide."

## 1:45 — Measured results (~30 s)

Scroll to section 02.

- Policy table: highlight row is the learned cascade — 84% accuracy, 68.4%
  cost cut, passes the quality floor. Compare against always-cheapest
  (fails the floor) and oracle (the ceiling).
- Chart: hover the learned-cascade dot → "84.04% at $0.006 per query";
  hover always-strongest → "88.65% at $0.019". Up and to the left is
  better; we sit on the frontier.

## 2:15 — What it's worth (~30 s)

Section 03. Drag the slider from 10k to 1M queries/day while you say:

> "At 10,000 queries a day, routing saves about $47,000 a year. At a
> million a day it's $4.7 million. Same quality floor either way."

## 2:45 — Close (~15 s)

> "The model pool, per-class accuracy, and pricing are all in the repo —
> every number reproducible from one command. Routing is a free lunch on
> top of any existing LLM stack."

## Backup answers

- **"How close are you to the oracle?"** — Oracle picks with hindsight
  (it knows the gold answer). The gap is concentrated in the hard tier,
  where no cheap model is confident — our fallback already sends those to
  the strongest model, which is the correct conservative move.
- **"Does the router call an LLM to decide?"** — No. Logistic heads over
  hashed text features; inference is microseconds and free.
- **"What about latency?"** — Same story: cheapest-first ordering also
  tends to pick faster models; latency numbers are in the model table.
