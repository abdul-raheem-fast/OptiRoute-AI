"""OptiRoute AI demo server: routing API + React dashboard.

    python -m webapp.server            (serves http://127.0.0.1:8317)

Endpoints
  GET  /                 dashboard (built React bundle)
  POST /api/route        live routing decision for one query (no model APIs)
  GET  /api/results      frozen test-split policy table + threshold curve
                         + splits manifest
  GET  /api/models       registry + per-model benchmark aggregates
  GET  /api/modes        configurable routing-mode presets (val-tuned)
  GET  /api/scenarios    curated real benchmark queries for the demo
  GET  /api/stats        session routing telemetry (demo-session data)
  GET  /health           liveness probe

Frontend: the dashboard is a Vite + React app in webapp/frontend. Build it with
`npm run build` (outputs webapp/frontend/dist) and this server serves that
bundle. During development run `npm run dev` in webapp/frontend - Vite proxies
/api and /health to this server on :8317.

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
from routing.sensitivity import classify_sensitivity, load_policy, model_privacy
from routing.pareto import dominated_by
from routing.splits import load_splits
from webapp.router_core import RouterCore

WEBAPP_DIR = Path(__file__).resolve().parent
# Built React bundle (webapp/frontend/dist). Falls back to the legacy vanilla
# dashboard in webapp/static if the frontend has not been built yet, so the API
# keeps working on a fresh checkout.
DIST_DIR = WEBAPP_DIR / "frontend" / "dist"
LEGACY_DIR = WEBAPP_DIR / "static"
FRONTEND_DIR = DIST_DIR if (DIST_DIR / "index.html").exists() else LEGACY_DIR
ASSETS_DIR = FRONTEND_DIR / "assets"

app = FastAPI(title="OptiRoute AI", docs_url="/api/docs", redoc_url=None)
core = RouterCore()

# Multi-objective router (experimental/advanced). Its artifact lives in the
# gitignored routing/models/, so degrade gracefully: the legacy path - and every
# existing test - keeps working even if `python -m routing.tune_mo` has not run.
try:
    from webapp.mo_router import get_router
    mo = get_router(core)
    MO_ART = mo.art
    MO_AVAILABLE = True
except Exception:                                   # pragma: no cover
    mo = None
    MO_ART = None
    MO_AVAILABLE = False

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
    # mode accepts the legacy three AND the two multi-objective-only modes.
    mode: str | None = Field(
        default=None, pattern="^(economy|balanced|quality|speed|private)$")
    # ---- multi-objective extensions (all optional; omitting them keeps the
    # ---- legacy behaviour byte-for-byte) ----
    router: str | None = Field(default=None, pattern="^(legacy|multi_objective)$")
    quality_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_budget_ms: float | None = Field(default=None, gt=0.0)
    sensitive: bool | None = None


MO_ONLY_MODES = {"speed", "private"}


def _wants_mo(req: RouteRequest) -> bool:
    """Backward-compatible dispatch. The multi-objective router answers ONLY on
    an explicit opt-in (``router``), an MO-only mode, or an MO-only parameter;
    every legacy-shaped request still hits the published cascade untouched."""
    if req.router == "multi_objective":
        return True
    if req.router == "legacy":
        return False
    if req.mode in MO_ONLY_MODES:
        return True
    return (req.quality_floor is not None or req.latency_budget_ms is not None
            or req.sensitive is not None)


def _tally(result: dict):
    """Session telemetry - tolerant of both the legacy and the MO schema."""
    chosen = result.get("chosen_model")
    if chosen:
        session[chosen] += 1
    session["_total"] += 1
    est = result.get("est_cost_per_query",
                     result.get("estimated_cost_per_query", 0.0))
    strong = result.get("strongest_cost_per_query")
    saved = (strong - est) if strong is not None else 0.0
    session["_saved"] += saved
    if result.get("is_fallback"):
        session["_esc"] += 1
    tier = result.get("tier")
    if tier:
        session[f"_tier_{tier}"] += 1
    session_log.append({"model": chosen, "tier": tier,
                        "saved": round(saved, 6),
                        "fallback": bool(result.get("is_fallback"))})


@app.post("/api/route")
def route(req: RouteRequest):
    if _wants_mo(req):
        if not MO_AVAILABLE:
            raise HTTPException(
                503,
                "multi-objective router not built - run: python -m routing.tune_mo")
        result = mo.route(req.query, req.query_class, req.mode,
                          req.quality_floor, req.latency_budget_ms, req.sensitive)
    else:
        t = req.threshold if req.threshold is not None else \
            MODE_T.get(req.mode or "balanced", core.t_star)
        result = core.route(req.query, req.query_class, t)
    _tally(result)
    return result


@app.get("/api/results")
def results():
    out = {}
    for name in ("baselines_report", "learned_router_report",
                 "oracle_report", "threshold_curves", "mo_eval_report"):
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


class SensitivityRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)


def _require_mo():
    if not MO_AVAILABLE:
        raise HTTPException(
            503, "multi-objective router not built - run: python -m routing.tune_mo")


@app.get("/api/objectives")
def objectives():
    """Multi-objective configuration + the measured evidence behind it.

    Every number (weights aside) is a MEASURED train-split statistic or a
    validation-split verification - nothing is invented. Exposes the mode
    definitions, resolved hard constraints, per-head calibration diagnostics
    and the legacy-vs-MO validation comparison.
    """
    _require_mo()
    return {
        "available": True,
        "default_router": MO_ART["default_router"],
        "mode_order": MO_ART["mode_order"],
        "modes": MO_ART["modes"],
        "normalization": MO_ART["normalization"],
        "measured_train_stats": MO_ART["measured_train_stats"],
        "calibration": MO_ART["calibration"],
        "legacy_val": MO_ART["legacy_val"],
        "meta": MO_ART["_meta"],
    }


@app.get("/api/pareto")
def pareto():
    """Pareto-frontier analysis over MEASURED train-split quality/cost/latency."""
    _require_mo()
    st = MO_ART["measured_train_stats"]
    points = [{"model": m, "quality": st[m]["accuracy"], "cost": st[m]["cost"],
               "latency_s": st[m]["latency_s"]} for m in core.models]
    pts3 = [{"quality": p["quality"], "cost": p["cost"], "latency": p["latency_s"]}
            for p in points]
    dom = dominated_by(pts3)
    for i, p in enumerate(points):
        p["dominated_by"] = [points[j]["model"] for j in dom[i]]
        p["on_global_frontier"] = p["model"] in MO_ART["frontiers"]["global"]
    return {
        "dimensions": {"quality": "higher is better", "cost": "lower is better",
                       "latency": "lower is better"},
        "points": points,
        "frontiers": MO_ART["frontiers"],
        "note": ("Frontier computed on measured train-split aggregates. A globally "
                 "dominated model is never discarded outright: a privacy policy "
                 "can still make it the eligible choice in another deployment."),
    }


@app.get("/api/privacy")
def privacy():
    """Deployment privacy policy + per-model privacy metadata.

    No provider guarantees are fabricated: every field is administrator-configured
    in webapp/privacy_policy.json and its provenance is reported.
    """
    pol = load_policy()
    sens = pol.get("sensitivity", {})
    return {
        "deployment": pol.get("deployment", {}),
        "models": {m: model_privacy(m) for m in core.models},
        "sensitivity_rules": {"n_patterns": len(sens.get("patterns", [])),
                              "keywords": sens.get("keywords", [])},
        "provenance": pol.get("_meta", {}).get("provenance", ""),
        "note": ("Local routing means the DECISION needs no extra LLM call; it "
                 "does NOT mean the selected model is private. Privacy comes only "
                 "from this policy filter."),
    }


@app.post("/api/sensitivity")
def sensitivity(req: SensitivityRequest):
    """Local, deterministic sensitivity check (no external LLM, no storage)."""
    return classify_sensitivity(req.query)


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


if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/")
def index():
    entry = FRONTEND_DIR / "index.html"
    if not entry.exists():
        raise HTTPException(
            503,
            "dashboard not built - run: cd webapp/frontend && npm install && npm run build",
        )
    return FileResponse(entry)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8317)
