import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

csv.field_size_limit(100000000)

ROOT = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(ROOT, "models_registry.json")

SCHEMA = [
    "index", "query_id", "dataset_name", "model_name", "origin_query",
    "prompt", "ground_truth", "prediction", "score", "correct",
    "prompt_tokens", "completion_tokens", "total_tokens", "cost",
    "estimated_latency", "actual_latency", "raw_output"
]


def load_registry():
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_env(value):
    return re.sub(r"\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)


def query_id(dataset_name, origin_query):
    import hashlib
    basis = f"{dataset_name.strip().lower()}||{origin_query.strip()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def call_model(cfg, prompt, temperature, max_tokens, retries=3):
    api_base = resolve_env(cfg["api_base"]).rstrip("/")
    url = f"{api_base}/chat/completions"
    key = os.environ.get(cfg["api_key_env"], "")
    payload = {
        "model": cfg["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    last_err = None
    for attempt in range(retries):
        start = time.perf_counter()
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            latency = time.perf_counter() - start
            return body, latency
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"    attempt {attempt + 1}/{retries} failed ({e}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"All {retries} attempts failed: {last_err}")


def normalize(text):
    text = str(text).strip().lower()
    text = text.replace(",", "").replace("$", "").replace(" ", "")
    text = text.rstrip(".")
    return text


def extract_boxed(text):
    matches = re.findall(r"\\boxed\{([^{}]+)\}", text)
    return matches[-1].strip() if matches else None


def extract_choice(text):
    m = re.search(r"\b([A-D])\b(?![a-zA-Z])", text)
    return m.group(1) if m else None


def extract_number(text):
    m = re.findall(r"-?\d+(?:\.\d+)?(?:/\d+)?", text.replace("{", "").replace("}", ""))
    return m[-1] if m else None


def score_answer(raw_output, prediction, ground_truth):
    gt = str(ground_truth).strip()

    if normalize(gt) == normalize(prediction or ""):
        return 1.0
    boxed = extract_boxed(raw_output or "")
    if boxed and normalize(boxed) == normalize(gt):
        return 1.0
    if re.fullmatch(r"[A-D]", gt, flags=re.IGNORECASE):
        choice = extract_choice(prediction or "") or extract_choice(raw_output or "")
        if choice and choice.upper() == gt.upper():
            return 1.0
        return 0.0
    gt_num = extract_number(gt)
    pred_nums = []
    for src in [boxed or "", prediction or "", raw_output or ""]:
        n = extract_number(src) if src else None
        if n:
            try:
                val = eval(n) if "/" in n else float(n)
                pred_nums.append(val)
            except Exception:
                pass
    if gt_num is not None and pred_nums:
        try:
            gt_val = eval(gt_num) if "/" in gt_num else float(gt_num)
            for pv in pred_nums:
                if abs(pv - gt_val) < 1e-6:
                    return 1.0
        except Exception:
            pass
    if prediction and normalize(gt) and normalize(gt) in normalize(prediction):
        return 1.0
    return 0.0


def main():
    ap = argparse.ArgumentParser(description="Generic model evaluation harness")
    ap.add_argument("--model", required=True, help="Model key in models_registry.json")
    ap.add_argument("--queries", required=True, help="CSV file supplying the aligned query set")
    ap.add_argument("--out", default=None, help="Output CSV path (default: cleaned/individual/<model>.new.csv)")
    ap.add_argument("--limit", type=int, default=None, help="Evaluate only the first N queries")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--dry-run", action="store_true", help="Validate config and queries without calling the API")
    args = ap.parse_args()

    registry = load_registry()
    if args.model not in registry or args.model.startswith("_"):
        print(f"ERROR: '{args.model}' not found in registry. Available: {[k for k in registry if not k.startswith('_')]}")
        sys.exit(1)
    cfg = registry[args.model]

    rows = []
    with open(args.queries, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    if args.limit:
        rows = rows[: args.limit]
    print(f"Loaded {len(rows)} queries from {args.queries}")

    missing_env = [cfg["api_key_env"]] if not resolve_env(cfg["api_base"]) else []
    key = os.environ.get(cfg["api_key_env"], "")
    if not key and not args.dry_run:
        print(f"WARNING: env var {cfg['api_key_env']} is not set; requests may fail with 401")

    out_path = args.out or os.path.join(ROOT, "cleaned", "individual", f"{args.model}.new.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if args.dry_run:
        print("DRY RUN OK:")
        print(f"  endpoint : {resolve_env(cfg['api_base'])}/chat/completions")
        print(f"  model_id : {cfg['model_id']}")
        print(f"  pricing  : ${cfg['price_per_1m_input']}/M in, ${cfg['price_per_1m_output']}/M out (snapshot {cfg['snapshot_date']})")
        est_in = sum(len((r.get('prompt') or '')) / 4.0 for r in rows)
        print(f"  queries  : {len(rows)} (~{est_in/1e6:.3f}M est input tokens)")
        print(f"  output   : {out_path}")
        return

    done, total_cost = 0, 0.0
    with open(out_path, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=SCHEMA, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for i, r in enumerate(rows, 1):
            ds = (r.get("dataset_name") or "").strip()
            origin = (r.get("origin_query") or "").strip()
            prompt = r.get("prompt") or r.get("origin_query") or ""
            gt = (r.get("ground_truth") or "").strip()
            qid = r.get("query_id") or query_id(ds, origin)
            try:
                body, latency = call_model(cfg, prompt, args.temperature, args.max_tokens)
                choice = body["choices"][0]["message"]["content"] or ""
                usage = body.get("usage", {})
                pt = usage.get("prompt_tokens", 0)
                ct = usage.get("completion_tokens", 0)
                cost = pt / 1e6 * cfg["price_per_1m_input"] + ct / 1e6 * cfg["price_per_1m_output"]
                s = score_answer(choice, choice.strip(), gt)
            except Exception as e:
                print(f"  [{i}/{len(rows)}] FAILED: {e}")
                choice, pt, ct, cost, s, latency = "", 0, 0, 0.0, 0.0, 0.0
            total_cost += cost
            writer.writerow({
                "index": i,
                "query_id": qid,
                "dataset_name": ds,
                "model_name": args.model,
                "origin_query": origin,
                "prompt": " ".join(str(prompt).split()),
                "ground_truth": gt,
                "prediction": " ".join(choice.split())[:2000],
                "score": s,
                "correct": int(s == 1.0),
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": pt + ct,
                "cost": round(cost, 8),
                "estimated_latency": "",
                "actual_latency": round(latency, 6),
                "raw_output": " ".join(str(choice).split()),
            })
            fout.flush()
            done += 1
            if i % 25 == 0 or i == len(rows):
                acc_so_far = 0.0
                print(f"  [{i}/{len(rows)}] running cost so far: ${total_cost:.4f}")

    print(f"\nDONE: {done} rows -> {out_path}")
    print(f"Total spend this run: ${total_cost:.4f}")


if __name__ == "__main__":
    main()
