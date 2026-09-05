"""Vercel serverless entrypoint for the OptiRoute AI demo.

Vercel's ``@vercel/python`` runtime imports this module and serves the ASGI
``app`` object. We put the repository root on ``sys.path`` first so that
``import webapp`` / ``import routing`` resolve exactly as they do locally under
``python -m webapp.server``.

Routing is pure local NumPy arithmetic over the frozen weights in
``routing/models/router_weights.npz`` - no LLM API call and no API key. The
static React bundle in ``webapp/frontend/dist`` is served by the same FastAPI
app (``/`` and ``/assets``), so a single rewrite in vercel.json sends all
traffic here.
"""
import os
import sys

# /var/task/api/index.py -> /var/task (the deployed repo root). This is also
# where vercel.json's includeFiles places webapp/, routing/ and
# models_registry.json, so routing.config.ROOT resolves to /var/task.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from webapp.server import app  # noqa: E402  (sys.path must be set first)
