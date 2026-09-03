"""Smoke-test the demo server endpoints (server must be running)."""
import json
import urllib.request

BASE = "http://127.0.0.1:8317"


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.load(r)


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


print("health :", get("/health"))
m = get("/api/models")
print("models :", len(m["models"]), "| t* =", m["t_star"], "| classes =", len(m["classes"]))
modes = get("/api/modes")
for mo in modes["modes"]:
    print(f"  mode {mo['key']:9s} t={mo['t']:.2f} val_acc={mo['val_accuracy_pct']}% "
          f"val_cost={mo['val_avg_cost_per_query']:.4f} ({mo['measured_on']})")
r = get("/api/results")
print("results:", list(r.keys()), "|", len(r["baselines_report"]), "policies")
mf = r.get("splits_manifest", {})
print("manifest: seed", mf.get("seed"), "| test", mf.get("split_counts", {}).get("test"),
      "| dup-in-val/test", len(mf.get("duplicate_ids_in_val_or_test", [])))

samples = [
    ("Summarize photosynthesis in 3 sentences.", None),
    ("Design a fault-tolerant distributed payment system with idempotency, "
     "event sourcing and cross-region recovery.", None),
    ("Explain quantum computing to a 12-year-old", None),
]
for q, cls in samples:
    d = post("/api/route", {"query": q, "query_class": cls})
    print(f"  -> {d['chosen_model']:22s} tier={d['tier']:6s} "
          f"save={d['est_saving_pct']}% "
          f"fallback={d['is_fallback']}")
    print(f"     tier_probs={d['tier_probs']}")
    print(f"     reasons: {d['reasons'][0]} | {d['reasons'][-1]}")
    print(f"     why_not_strongest: {d['why_not_strongest']['verdict']}")

# mode override via API (no explicit threshold)
d = post("/api/route", {"query": "Compare REST and GraphQL for a startup.", "mode": "economy"})
print("economy mode ->", d["chosen_model"], "t =", d["threshold"])
d = post("/api/route", {"query": "Compare REST and GraphQL for a startup.", "mode": "quality"})
print("quality mode ->", d["chosen_model"], "t =", d["threshold"])

# real benchmark scenarios drive the demo buttons
sc = get("/api/scenarios")
cheap = sum(1 for s in sc["scenarios"] if s["expected_route"] == "cheap")
print("scenarios:", len(sc["scenarios"]), f"({cheap} cheap /",
      len(sc["scenarios"]) - cheap, "escalate) | challenges:", len(sc["challenges"]),
      "|", sc["source"])
for s in sc["scenarios"]:
    d = post("/api/route", {"query": s["query"], "query_class": s["query_class"]})
    assert d["chosen_model"] == s["expected_model"], (s["label"], d["chosen_model"])
print("  all scenario routes match their expected model")

s = get("/api/stats")
print("stats  :", s["session_queries"], "queries |", s["escalations"], "escalations |",
      s["escalation_rate_pct"], "% | saved", s["est_savings_total"],
      "| tiers", s["tier_distribution"], "| log", len(s["route_log"]))
print("ALL GREEN")
