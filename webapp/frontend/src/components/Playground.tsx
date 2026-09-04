import { CodeBlock, CopyButton } from "./CodeBlock";
import { Card, CardTitle, Section } from "./ui";
import type { RouteDecision } from "../lib/types";

const ENDPOINTS: [string, string, string][] = [
  ["POST", "/api/route", "live routing decision for one query"],
  ["GET", "/api/results", "frozen test-split policy table + threshold curve"],
  ["GET", "/api/models", "registry pricing + per-model benchmark aggregates"],
  ["GET", "/api/modes", "configurable routing-policy presets"],
  ["GET", "/api/scenarios", "curated real benchmark queries for the demo"],
  ["GET", "/api/stats", "demo-session routing telemetry"],
  ["GET", "/health", "liveness probe"],
  ["GET", "/api/docs", "OpenAPI / Swagger UI"],
];

interface Props {
  query: string;
  mode: string;
  decision: RouteDecision | null;
}

export function Playground({ query, mode, decision }: Props) {
  const q = (query.trim() || "Explain blockchain simply").slice(0, 120);
  const requestBody = JSON.stringify({ query: q, mode }, null, 2);
  const responseBody = decision
    ? JSON.stringify(decision, null, 2)
    : "// Route a query in the arena to see the live JSON response.";
  const curl = `curl -X POST http://127.0.0.1:8317/api/route \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify({ query: q.replace(/'/g, ""), mode })}'`;

  return (
    <Section
      id="api"
      index="08"
      eyebrow="API playground"
      title="Integration-ready routing engine"
      lead="Every decision on this page comes from one endpoint. The request mirrors the
            arena state; the response is the live payload the UI just rendered."
    >
      <div className="pg-grid">
        <Card variant="elevated">
          <CardTitle hint="mirrors the arena">Request</CardTitle>
          <CodeBlock
            title="POST /api/route"
            language="json"
            json
            body={requestBody}
            action={<CopyButton text={curl} label="copy curl" />}
          />
          <div className="endpoint-list">
            {ENDPOINTS.map(([verb, path, what]) => (
              <a
                key={path}
                className="endpoint"
                href={verb === "GET" ? path : "#api"}
                title={what}
              >
                <span className={`verb ${verb === "POST" ? "post" : ""}`}>{verb}</span>
                <span>{path}</span>
              </a>
            ))}
          </div>
        </Card>

        <Card variant="elevated">
          <CardTitle
            hint={decision ? `routed → ${decision.chosen_model}` : "no decision yet"}
          >
            Response
          </CardTitle>
          <CodeBlock title="200 OK" language="json" json={!!decision} body={responseBody} />
          <p className="chart-caption">
            The router never calls a model API: <code className="mono">p_correct</code> comes
            from trained per-model heads over hashed text features, and cost/latency are
            benchmark averages of the chosen model.
          </p>
        </Card>
      </div>
    </Section>
  );
}
