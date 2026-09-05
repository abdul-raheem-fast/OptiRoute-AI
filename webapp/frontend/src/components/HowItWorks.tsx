import { Card, Section } from "./ui";

const STEPS = [
  {
    n: "a",
    title: "Score, don’t ask",
    body: "From the query text alone, a per-model logistic head estimates P(correct) for all eight models. Milliseconds, zero tokens spent.",
  },
  {
    n: "b",
    title: "Walk cheapest-first",
    body: "Models are tried cheapest-first. The first whose P(correct) clears the threshold (t = 0.95) gets the query.",
  },
  {
    n: "c",
    title: "Escalate when unsure",
    body: "If nothing clears the bar, the query falls back to the strongest model — the safety valve behind the 94.8% quality / 68.4% cost-cut headline.",
  },
];

export function HowItWorks() {
  return (
    <Section
      id="how"
      index="04"
      eyebrow="How it works"
      title="A decision made before any tokens are spent"
      lead="Routing needs no live model calls — a small trained scorer runs before dispatch, so the
            decision is essentially free."
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
    </Section>
  );
}
