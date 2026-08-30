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
print("models :", len(m["models"]), "| t* =", m["t_star"], "| classes =", m["classes"])
r = get("/api/results")
print("results:", list(r.keys()), "|", len(r["baselines_report"]), "policies")

samples = [
    "Write a Python function that merges two sorted linked lists into one sorted list.",
    "A fair coin is flipped 10 times. What is the probability of getting exactly 7 heads?",
    "What is the capital of Australia?",
    "Explain why the mitochondrion is called the powerhouse of the cell.",
]
for q in samples:
    d = post("/api/route", {"query": q})
    print(f"  -> {d['chosen_model']:24s} class={d['query_class']:26s} "
          f"save={d['est_saving_pct']:5.1f}% fallback={d['is_fallback']}")

print("stats  :", get("/api/stats"))
