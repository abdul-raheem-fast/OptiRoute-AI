import { Card, Section } from "./ui";

const STEPS = [
  {
    n: "a",
    title: "Score, don’t ask",
    body: "From the query text alone — hashed character n-gram TF-IDF, text statistics and the capability class — a per-model logistic head estimates P(correct) for all eight models. Milliseconds, zero tokens spent.",
  },
  {
    n: "b",
    title: "Walk cheapest-first",
    body: "Models are tried in ascending cost order. The first one whose P(correct) clears the threshold t = 0.95 gets the query. Confidence is the gate; cost is the ordering.",
  },
  {
    n: "c",
    title: "Escalate when unsure",
    body: "If no model clears the bar, the query falls back to the strongest model — the safety valve that keeps quality at 94.8% of always-GPT-5 while cutting cost 68.4%.",
  },
];

export function HowItWorks() {
  return (
    <Section
      id="how"
      index="09"
      eyebrow="How it works"
      title="A decision made before any tokens are spent"
      lead="No live model calls are needed to route — the router is a small trained scorer
            that runs before dispatch, so the decision is essentially free."
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
