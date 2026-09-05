import { Card, Section } from "./ui";

const STEPS = [
  {
    n: "a",
    title: "Score, don’t ask",
    body: "From the query text alone, a per-model head estimates P(correct) for all eight models — milliseconds, zero tokens.",
  },
  {
    n: "b",
    title: "Walk cheapest-first",
    body: "Models are tried cheapest-first; the first whose P(correct) clears t = 0.95 gets the query.",
  },
  {
    n: "c",
    title: "Escalate when unsure",
    body: "If nothing clears the bar, it falls back to the strongest model — behind the 94.8% quality / 68.4% cost-cut headline.",
  },
];

export function HowItWorks() {
  return (
    <Section
      id="how"
      index="04"
      eyebrow="How it works"
      title="A decision made before any tokens are spent"
      lead="A small local scorer decides before dispatch — no extra LLM call is needed to route."
    >
      <div className="steps">
        {STEPS.map((s) => (
          <Card key={s.n} variant="hover" className="step">
            <span className="n">{s.n}</span>
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </Card>
        ))}
      </div>
      <p className="note" style={{ marginTop: "var(--s5)" }}>
        These steps are the legacy cascade (single threshold t = 0.95). The multi-objective router
        uses the same scorer but ranks eligible models by utility behind privacy and latency limits.
      </p>
    </Section>
  );
}
