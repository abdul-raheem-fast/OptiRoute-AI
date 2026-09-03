"""Inference core for the OptiRoute AI web demo.

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
        # Complexity tier names; the live tiers are DERIVED from the router's
        # own per-model confidence (see _derive_tier), not a trained head.
        self.tiers = ([str(t) for t in z["tiers"]] if "tiers" in z
                      else ["easy", "medium", "hard"])
        # Configurable routing policies (economy/balanced/quality) with their
        # thresholds and validation-split metrics, measured at export time.
        self.mode_presets = []
        if "mode_keys" in z:
            for i, key in enumerate([str(k) for k in z["mode_keys"]]):
                self.mode_presets.append({
                    "key": key,
                    "t": float(z["mode_t"][i]),
                    "val_accuracy_pct": float(z["mode_acc"][i]),
                    "val_avg_cost_per_query": float(z["mode_cost"][i]),
                    "meets_floor": bool(z["mode_floor"][i]),
                })
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
    def _derive_tier(self, p):
        """Complexity estimate DERIVED from the router's per-model confidence.

        Splits the cheap->strong cascade into thirds and reads the mean
        P(correct) of each: cheap / mid / strong competence. Complexity mass is
        then assigned by WHERE confidence appears along the cascade:
          easy   - cheap models are already competent (m0)
          medium - confidence first shows up in the middle tier (m1 - m0)
          hard   - it takes the strongest tier (m2 - m1), plus half-weighted
                   residual uncertainty when even the strongest are unsure
                   (1 - m2).
        This is honest: it reuses the router's own signal rather than a
        separately benchmarked difficulty classifier. For free-text queries
        outside the benchmark format the confidence profile is flat, so the
        bars stay near-balanced - which correctly reflects genuine uncertainty.
        """
        p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
        groups = np.array_split(np.arange(len(p)), 3)
        m = [float(p[g].mean()) for g in groups]
        easy = m[0]
        medium = max(0.0, m[1] - m[0])
        hard = max(0.0, m[2] - m[1]) + 0.5 * max(0.0, 1.0 - m[2])
        probs = np.array([easy, medium, hard], dtype=float)
        total = probs.sum()
        return probs / total if total > 0 else np.array([1.0, 0.0, 0.0])

    def route(self, text, cls=None, threshold=None):
        cls = cls if cls in self.classes else self.guess_class(text)
        t = self.t_star if threshold is None else float(threshold)
        x = self.featurize(text, cls)
        p = sigmoid(x @ self.W + self.b)

        tier_probs = self._derive_tier(p)
        tier = self.tiers[int(tier_probs.argmax())]

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
        is_fallback = (chosen == strongest and not trace[-1]["passes"]
                       if len(trace) == len(self.models) else False)

        # Explainability: human-readable reasons + strongest-model tradeoff.
        reasons = []
        reasons.append(f"complexity estimate: {tier} "
                       f"({tier_probs.max():.0%} of the router's confidence mass)")
        reasons.append(f"{cls} capability class")
        if is_fallback:
            reasons.append("no model cleared the confidence bar")
            reasons.append("escalated to strongest - quality is the constraint")
        else:
            reasons.append(f"{self.models[chosen]} is the cheapest model "
                           f"clearing t={t:.2f} (p={p[chosen]:.0%})")
            reasons.append("cost is the objective, quality is the constraint")
        delta_acc = float(p[strongest] - p[chosen]) * 100
        delta_cost = strongest_cost - est_cost
        if chosen == strongest:
            verdict = "the strongest model is the route"
        else:
            verdict = (f"+{delta_acc:.1f} pts expected quality for "
                       f"+${delta_cost:.5f}/query does not pay")

        return {
            "query_class": cls,
            "threshold": t,
            "chosen_model": self.models[chosen],
            "chosen_index": chosen,
            "is_fallback": is_fallback,
            "tier": tier,
            "tier_probs": ({t_: round(float(v), 3)
                            for t_, v in zip(self.tiers, tier_probs)}
                           if tier is not None else None),
            "reasons": reasons,
            "why_not_strongest": {
                "delta_accuracy_pts": round(delta_acc, 1),
                "delta_cost_per_query": round(delta_cost, 6),
                "verdict": verdict,
            },
            "p_correct": {m: round(float(v), 4) for m, v in zip(self.models, p)},
            "cascade_trace": trace,
            "est_cost_per_query": est_cost,
            "est_latency_s": float(self.avg_latency[chosen]),
            "strongest_cost_per_query": strongest_cost,
            "est_saving_pct": round((1 - est_cost / strongest_cost) * 100, 1),
            "class_prior_acc": {m: round(float(a) * 100, 1)
                                for m, a in zip(self.models, self.prior[cls])},
        }
