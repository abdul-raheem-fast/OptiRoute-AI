"""Inference core for the AetherFlow web demo.

Loads the exported A3 router weights (webapp/export_weights.py) and answers
single-query routing requests without touching any model API. Featurization
mirrors routing.learned_router exactly, with one inference-side fix: the
capability-class one-hot uses the FIXED class order saved at export time
(training relied on all 5 classes being present in the batch; a single query
would otherwise produce the wrong feature width).
"""
import json

import numpy as np

from routing.config import ROOT
from routing.learned_router import D_HASH, _gram, sigmoid

WEIGHTS_PATH = ROOT / "routing" / "models" / "router_weights.npz"
REGISTRY_PATH = ROOT / "models_registry.json"

# Same regex intent as learned_router.scalar_features, applied to one string.
_CODE_MARKERS = ("```", "def ", "import ", "function")


class RouterCore:
    def __init__(self):
        z = np.load(WEIGHTS_PATH, allow_pickle=False)
        self.W, self.b, self.idf = z["W"], z["b"], z["idf"]
        self.models = [str(m) for m in z["models"]]
        self.classes = [str(c) for c in z["classes"]]
        self.t_star = float(z["t_star"])
        self.avg_cost = z["avg_cost"]
        self.avg_latency = z["avg_latency"]
        self.prior = {c: z[f"prior_{c}"] for c in self.classes}
        self.class_acc = {c: z[f"class_acc_{c}"] for c in self.classes}
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            reg = json.load(f)
        self.registry = {k: v for k, v in reg.items() if not k.startswith("_")}

    # ------------------------------------------------------------ features
    def _tfidf_one(self, text):
        x = np.zeros(D_HASH)
        s = text.lower()
        for j in range(max(0, len(s) - 3)):
            idx, sign = _gram(s, j)
            x[idx] += sign
        x = np.abs(x) * self.idf
        n = np.linalg.norm(x)
        return x / n if n > 0 else x

    def _scalars_one(self, text, cls):
        s = text or ""
        f = [
            np.log1p(len(s)),
            np.log1p(len(s.split())),
            sum(c.isdigit() for c in s) / max(1, len(s)),
            1.0 if any(m in s for m in _CODE_MARKERS) else 0.0,
            float(s.count("?")),
        ]
        f += [1.0 if cls == c else 0.0 for c in self.classes]
        return np.array(f)

    def featurize(self, text, cls):
        return np.concatenate([
            self._scalars_one(text, cls),
            self._tfidf_one(text),
            self.prior[cls],
        ])

    def guess_class(self, text):
        """Transparent keyword heuristic; the UI lets the user override it."""
        s = (text or "").lower()
        if any(m in s for m in _CODE_MARKERS) or "code" in s or "write a" in s and "function" in s:
            return "Coding"
        digit_frac = sum(c.isdigit() for c in s) / max(1, len(s))
        mathish = any(w in s for w in ("solve", "equation", "integer", "compute",
                                       "how many", "sum of", "probability"))
        if digit_frac > 0.08 and mathish:
            return "Competitive Math"
        if mathish or digit_frac > 0.12:
            return "Mathematical Reasoning"
        if any(w in s for w in ("physics", "chemistry", "biology", "cell",
                                "atom", "molecule", "energy", "species")):
            return "Scientific Questionnaire"
        return "General Knowledge"

    # ------------------------------------------------------------- routing
    def route(self, text, cls=None, threshold=None):
        cls = cls if cls in self.classes else self.guess_class(text)
        t = self.t_star if threshold is None else float(threshold)
        p = sigmoid(self.featurize(text, cls) @ self.W + self.b)

        chosen = len(self.models) - 1
        trace = []
        for m in range(len(self.models)):  # cheapest -> strongest
            passed = bool(p[m] >= t)
            trace.append({"model": self.models[m],
                          "p_correct": round(float(p[m]), 4),
                          "passes": passed})
            if passed:
                chosen = m
                break

        strongest = len(self.models) - 1
        est_cost = float(self.avg_cost[chosen])
        strongest_cost = float(self.avg_cost[strongest])
        return {
            "query_class": cls,
            "threshold": t,
            "chosen_model": self.models[chosen],
            "chosen_index": chosen,
            "is_fallback": chosen == strongest and not trace[-1]["passes"]
                           if len(trace) == len(self.models) else False,
            "p_correct": {m: round(float(v), 4) for m, v in zip(self.models, p)},
            "cascade_trace": trace,
            "est_cost_per_query": est_cost,
            "est_latency_s": float(self.avg_latency[chosen]),
            "strongest_cost_per_query": strongest_cost,
            "est_saving_pct": round((1 - est_cost / strongest_cost) * 100, 1),
            "class_prior_acc": {m: round(float(a) * 100, 1)
                                for m, a in zip(self.models, self.prior[cls])},
        }
