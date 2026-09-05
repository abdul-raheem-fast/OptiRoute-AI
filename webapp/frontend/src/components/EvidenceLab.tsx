import type { ReactNode } from "react";
import { Card, Section } from "./ui";
import { fmtInt, fmtUSD } from "../lib/format";
import type { PolicyRow, ResultsPayload } from "../lib/types";

const ORACLE_TIP =
  "Oracle has hindsight: it knows which model would perform best after seeing outcomes. " +
  "OptiRoute must decide before inference, so Oracle is a theoretical upper bound, not a " +
  "deployable baseline.";

function EvCard({
  title,
  row,
  us = false,
  extra,
}: {
  title: string;
  row: PolicyRow;
  us?: boolean;
  extra?: ReactNode;
}) {
  return (
    <Card variant={us ? "hero" : "hover"} className="ev-card">
      <h4>{title}</h4>
      <div className="line">
        <span>accuracy</span>
        <b>{Number(row.accuracy_pct).toFixed(2)}%</b>
      </div>
      <div className="line">
        <span>cost / query</span>
        <b>{fmtUSD(Number(row.avg_cost_per_query), 6)}</b>
      </div>
      <div className="line">
        <span>latency / query</span>
        <b>{Number(row.avg_latency_s).toFixed(3)} s</b>
      </div>
      {extra ? <div className="flag">{extra}</div> : null}
    </Card>
  );
}

export function EvidenceLab({ results }: { results: ResultsPayload }) {
  const rows = results.baselines_report ?? [];
  const mf = results.splits_manifest;
  const strongest = rows.find((r) => r.policy === "always-strongest");
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  const oracle = rows.find((r) => r.policy === "oracle");
  const leakageOk = (mf?.duplicate_ids_in_val_or_test?.length ?? 0) === 0;

  return (
    <Section
      id="evidence"
      index="06"
      eyebrow="Evidence lab"
      title="The provenance behind every number"
      lead="Split protocol, seed, strata and leakage audit — plus the three reference policies side by side."
    >
      {mf ? (
        <div className="manifest">
          <span className="m">
            split <b>test</b>
          </span>
          <span className="m">
            queries <b>{fmtInt(mf.split_counts.test)}</b>
          </span>
          <span className="m">
            train / val <b>{fmtInt(mf.split_counts.train)} / {fmtInt(mf.split_counts.val)}</b>
          </span>
          <span className="m">
            seed <b>{mf.seed}</b>
          </span>
          <span className="m">
            strata <b>{Object.keys(mf.strata).length}</b> class&times;tier
          </span>
          <span className="m">
            leakage audit <b>{leakageOk ? "passed" : "FAILED"}</b>
          </span>
          <span className="m">
            aligned_7 dups excluded <b>{fmtInt(mf.aligned7_duplicate_ids)}</b>
          </span>
        </div>
      ) : null}

      <div className="grid grid-3">
        {strongest ? <EvCard title="Always strongest" row={strongest} /> : null}
        {learned ? (
          <EvCard
            title="OptiRoute AI"
            row={learned}
            us
            extra={
              <>
                <b>{Number(learned.cost_reduction_vs_strongest_pct).toFixed(1)}% cheaper</b> at{" "}
                {Number(learned.quality_vs_strongest_pct).toFixed(1)}% of flagship quality
              </>
            }
          />
        ) : null}
        {oracle ? (
          <EvCard
            title="Oracle ceiling"
            row={oracle}
            extra={
              <span className="tip" data-tip={ORACLE_TIP}>
                what does oracle mean?
              </span>
            }
          />
        ) : null}
      </div>
    </Section>
  );
}
