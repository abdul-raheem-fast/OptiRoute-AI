import { Card, CardTitle, Section } from "./ui";

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

const ARCH = String.raw`
                        USER QUERY
                            |
                            v
                +-----------------------+
                |   FEATURE LAYER       |  hashed n-gram TF-IDF,
                |                       |  text stats, capability class
                +-----------+-----------+
                            v
                +-----------------------+
                | CONFIDENCE ESTIMATION |  P(correct) for all 8 models
                |                       |  + complexity tier estimate
                +-----------+-----------+
                            v
                      ROUTING POLICY  (economy / balanced / quality)
                   +----------+----------+
                   v          v          v
              efficient     mid      strongest
               models      models     model
                   +----------+----------+
                            v
                +-----------------------+
                |  QUALITY GUARDRAIL    |  floor = 90% of always-strongest
                +-----------+-----------+
                            v
                  RESPONSE + DECISION RECORD
`;

export function HowItWorks() {
  return (
    <Section
      id="how"
      index="07"
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

      <Card variant="elevated" style={{ marginTop: "var(--grid-gap)" }}>
        <CardTitle hint="request flow">Architecture</CardTitle>
        <pre className="arch">{ARCH}</pre>
      </Card>
    </Section>
  );
}
