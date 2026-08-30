"""AetherFlow demo server: routing API + dashboard.

    python -m webapp.server            (serves http://127.0.0.1:8317)

Endpoints
  GET  /                 dashboard (static)
  POST /api/route        live routing decision for one query (no model APIs)
  GET  /api/results      frozen test-split policy table + threshold curve
  GET  /api/models       registry + per-model benchmark aggregates
  GET  /api/stats        session routing counters
  GET  /health           liveness probe

The /api/route endpoint runs the exported A3 router offline. Displayed cost
and latency for arbitrary queries are benchmark averages of the chosen model
(clearly labeled estimates); the headline savings numbers always come from
the frozen test-split reports in routing/results/.
"""
from collections import Counter
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from routing.config import RESULTS_DIR
from webapp.router_core import RouterCore

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="AetherFlow", docs_url="/api/docs", redoc_url=None)
core = RouterCore()
session = Counter()


class RouteRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    query_class: str | None = None
    threshold: float | None = Field(default=None, ge=0.5, le=0.99)


@app.post("/api/route")
def route(req: RouteRequest):
    result = core.route(req.query, req.query_class, req.threshold)
    session[result["chosen_model"]] += 1
    session["_total"] += 1
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
    return out


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
    return {"session_queries": total,
            "distribution": {m: session.get(m, 0) for m in core.models}}


@app.get("/health")
def health():
    return {"status": "ok", "models": len(core.models)}


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8317)
