"""OptiRoute AI demo server: routing API + dashboard.

    python -m webapp.server            (serves http://127.0.0.1:8317)

Endpoints
  GET  /                 dashboard (static)
  POST /api/route        live routing decision for one query (no model APIs)
  GET  /api/results      frozen test-split policy table + threshold curve
                         + splits manifest
  GET  /api/models       registry + per-model benchmark aggregates
  GET  /api/modes        configurable routing-mode presets (val-tuned)
  GET  /api/stats        session routing telemetry (demo-session data)
  GET  /health           liveness probe

The /api/route endpoint runs the exported A3 router offline. Displayed cost
and latency for arbitrary queries are benchmark averages of the chosen model
(clearly labeled estimates); the headline savings numbers always come from
the frozen test-split reports in routing/results/.
"""
from collections import Counter, deque
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from routing.config import OUT_DIR, RESULTS_DIR
from routing.splits import load_splits
from webapp.router_core import RouterCore

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="OptiRoute AI", docs_url="/api/docs", redoc_url=None)
core = RouterCore()
session = Counter()
session_log = deque(maxlen=500)


def _load_modes():
    """Configurable routing-mode presets, measured on the validation split.

    These are routing POLICIES (different cascade thresholds), not separately
    benchmarked models. Each card quotes the validation-split accuracy/cost
    measured at export time and whether it clears the 90% quality floor, so no
    unmeasured numbers are implied. The headline test-split figures elsewhere
    correspond to the Balanced policy (t*).
    """
    labels = {"economy": "Economy", "balanced": "Balanced",
              "quality": "Quality First"}
    hints = {
        "economy": "Maximum savings - routes to cheaper models more eagerly",
        "balanced": "Best quality/cost tradeoff - the measured headline policy",
        "quality": "Escalates aggressively toward the strongest models",
    }
    out = []
    for p in core.mode_presets:
        key = p["key"]
        out.append({
            "key": key,
            "label": labels.get(key, key.title()),
            "description": hints.get(key, ""),
            "t": round(float(p["t"]), 2),
            "val_accuracy_pct": round(float(p["val_accuracy_pct"]), 2),
            "val_avg_cost_per_query": float(p["val_avg_cost_per_query"]),
            "meets_floor": bool(p["meets_floor"]),
            "measured_on": "validation split",
        })
    if not out:  # graceful fallback for older weight files
        out.append({"key": "balanced", "label": "Balanced",
                    "description": hints["balanced"], "t": round(core.t_star, 2),
                    "val_accuracy_pct": None, "val_avg_cost_per_query": None,
                    "meets_floor": True, "measured_on": "validation split"})
    return out


MODES = _load_modes()
MODE_T = {m["key"]: m["t"] for m in MODES}


# Curated demo scenarios: REAL test-split benchmark queries (never synthetic),
# chosen so the arena shows both cheap-routes-with-savings and escalations.
# (label, capability class, want a cheap route?, difficulty dot)
_SCENARIO_PLAN = [
    ("Easy coding task", "Coding", True, "easy"),
    ("Astrophysics estimate", "Scientific Questionnaire", True, "medium"),
    ("Combinatorics puzzle", "Competitive Math", True, "medium"),
    ("Hard algebra", "Mathematical Reasoning", False, "hard"),
    ("Organic synthesis", "Scientific Questionnaire", False, "hard"),
    ("Obscure trivia", "General Knowledge", False, "hard"),
]
_scenarios_cache = None


def _build_scenarios():
    """Pick representative real test-split queries for the demo buttons."""
    global _scenarios_cache
    if _scenarios_cache is not None:
        return _scenarios_cache
    meta = pd.read_csv(OUT_DIR / "query_meta.csv").drop_duplicates("query_id")
    meta = meta.set_index("query_id")
    _tr, _va, te, _tier = load_splits()
    te_meta = meta.loc[[q for q in te if q in meta.index]]
    routed = []
    for _qid, row in te_meta.iterrows():
        q = row["origin_query"]
        if not isinstance(q, str) or len(q) < 12:
            continue
        d = core.route(q, row["dataset_name"], core.t_star)
        routed.append({"query": q, "query_class": row["dataset_name"],
                       "cheap": not d["is_fallback"], "model": d["chosen_model"],
                       "saving_pct": d["est_saving_pct"], "len": len(q)})
    scen, used = [], set()
    for label, cls, want_cheap, dot in _SCENARIO_PLAN:
        cand = [r for r in routed if r["query_class"] == cls
                and r["cheap"] == want_cheap and r["query"] not in used
                and (r["len"] >= 40 or want_cheap)]
        cand.sort(key=lambda r: r["len"])
        if not cand:
            continue
        pick = cand[0]
        used.add(pick["query"])
        scen.append({"label": label, "dot": dot, "query": pick["query"],
                     "query_class": cls, "expected_model": pick["model"],
                     "expected_saving_pct": pick["saving_pct"],
                     "expected_route": "cheap" if want_cheap else "escalate"})
    pool = [r for r in routed if r["query"] not in used and r["len"] <= 320]
    pool.sort(key=lambda r: r["len"])
    challenges = []
    for r in pool:
        kind = "cheap" if r["cheap"] else "escalate"
        if sum(c["expected_route"] == kind for c in challenges) >= 4:
            continue
        challenges.append({"query": r["query"], "query_class": r["query_class"],
                           "expected_route": kind})
        if len(challenges) >= 8:
            break
    _scenarios_cache = {
        "scenarios": scen, "challenges": challenges,
        "source": "frozen test split (real benchmark queries)"}
    return _scenarios_cache


class RouteRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    query_class: str | None = None
    threshold: float | None = Field(default=None, ge=0.5, le=0.99)
    mode: str | None = Field(default=None, pattern="^(economy|balanced|quality)$")


@app.post("/api/route")
def route(req: RouteRequest):
    t = req.threshold if req.threshold is not None else \
        MODE_T.get(req.mode or "balanced", core.t_star)
    result = core.route(req.query, req.query_class, t)
    session[result["chosen_model"]] += 1
    session["_total"] += 1
    saved = result["strongest_cost_per_query"] - result["est_cost_per_query"]
    session["_saved"] += saved
    if result["is_fallback"]:
        session["_esc"] += 1
    if result["tier"]:
        session[f"_tier_{result['tier']}"] += 1
    session_log.append({"model": result["chosen_model"],
                        "tier": result["tier"],
                        "saved": round(saved, 6),
                        "fallback": result["is_fallback"]})
    return result


@app.get("/api/results")
def results():
    out = {}
    for name in ("baselines_report", "learned_router_report",
                 "oracle_report", "threshold_curves"):
        path = RESULTS_DIR / f"{name}.csv"
        if path.exists():
            out[name] = pd.read_csv(path).to_dict(orient="records")
    if not out:
        raise HTTPException(503, "results not built - run python -m routing.run_all")
    manifest = OUT_DIR / "splits_manifest.json"
    if manifest.exists():
        import json as _json
        out["splits_manifest"] = _json.loads(manifest.read_text(encoding="utf-8"))
    return out


@app.get("/api/modes")
def modes():
    return {"modes": MODES, "t_star": core.t_star}


@app.get("/api/scenarios")
def scenarios():
    return _build_scenarios()


@app.get("/api/models")
def models():
    rows = []
    for i, m in enumerate(core.models):
        reg = core.registry.get(m, {})
        rows.append({
            "model": m,
            "provider": reg.get("provider", ""),
            "price_in": reg.get("price_per_1m_input"),
            "price_out": reg.get("price_per_1m_output"),
            "avg_cost_per_query": float(core.avg_cost[i]),
            "avg_latency_s": float(core.avg_latency[i]),
            "class_accuracy": {c: round(float(core.class_acc[c][i]) * 100, 1)
                               for c in core.classes},
        })
    return {"models": rows, "classes": core.classes, "t_star": core.t_star}


@app.get("/api/stats")
def stats():
    total = session.get("_total", 0)
    esc = session.get("_esc", 0)
    return {"session_queries": total,
            "distribution": {m: session.get(m, 0) for m in core.models},
            "escalations": esc,
            "efficient_routes": total - esc,
            "escalation_rate_pct": round(esc / total * 100, 1) if total else 0.0,
            "est_savings_total": round(session.get("_saved", 0.0), 4),
            "tier_distribution": {t: session.get(f"_tier_{t}", 0)
                                  for t in ("easy", "medium", "hard")},
            "route_log": list(session_log)}


@app.get("/health")
def health():
    return {"status": "ok", "models": len(core.models)}


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8317)
