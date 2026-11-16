"""One frozen, development-only state-information diagnostic for Paper 2.

Private inputs and raw outputs stay under ignored .research-data/. This script
contains no study examples, reference verdicts, or inference credentials.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multilingual_judge_pilot.judge_inference import (
    canonical_json, parse_verdict_response,
)
from multilingual_judge_pilot.local_ollama import OllamaLocalClient, OllamaLocalError
from multilingual_judge_pilot.paper2_state_access import (
    ALLOWED_CONSTRAINT_FIELDS,
    ALLOWED_PERMISSION_FIELDS,
    ALLOWED_STATE_FIELDS,
    INSTRUCTION,
    MODEL,
    OPTIONS,
    ORDER_SEED,
    SCHEMA,
    VERSION,
    cluster_interval,
    digest,
    evidence,
    safe_state,
    quantile,
)
from multilingual_judge_pilot.qualification import QUALIFICATION_MODEL_DIGESTS


SOURCE = ROOT / ".research-data/p3-four-language-feasibility-20261111"
PRIOR_STATE = ROOT / ".research-data/p3-h2-development-diagnostic-20261112/reference/item-map-and-effective-states.json"
OUT = ROOT / ".research-data/paper2-state-information-v2-20261115"
def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def prepare() -> None:
    if OUT.exists():
        raise RuntimeError("versioned output exists; preparation cannot overwrite or optimize it")
    manifest = read(SOURCE / "inputs/input-manifest.json")
    if manifest.get("partition") != "development_primary_only" or manifest.get("item_count") != 96:
        raise RuntimeError("source is not the expected development partition")
    rows = read(SOURCE / "inputs/judge-facing-items.json")["items"]
    mapping = read(SOURCE / "inputs/scoring-map.json")["items"]
    states = read(PRIOR_STATE)["expected_effective_states"]
    selected = [row for row in rows if row["item_id"] in states]
    if set(states) != {row["item_id"] for row in selected}:
        raise RuntimeError("state map does not exactly match selected development items")
    scenarios = {mapping[row["item_id"]]["scenario_id"] for row in selected}
    if len(selected) != 64 or len(scenarios) != 8 or any(not s.startswith("P2C-DEV-") for s in scenarios):
        raise RuntimeError("expected eight P2C development scenarios and 64 derivatives")
    if Counter(mapping[row["item_id"]]["condition"] for row in selected) != Counter({x: 16 for x in ("EN-EN", "AR-AR", "EN-AR", "AR-EN")}):
        raise RuntimeError("language conditions are not balanced")
    if any(digest(row) != manifest["item_hashes"].get(row["item_id"]) for row in selected):
        raise RuntimeError("source item hash mismatch")
    if any(not safe_state(states[row["item_id"]]) for row in selected):
        raise RuntimeError("state projection contains disallowed fields")
    client = OllamaLocalClient(timeout_seconds=30)
    descriptor = client.discover_model(MODEL)
    if descriptor.digest != QUALIFICATION_MODEL_DIGESTS[MODEL]:
        raise RuntimeError("pinned model digest mismatch")
    order = [(row["item_id"], arm) for row in selected for arm in ("A", "B")]
    random.Random(ORDER_SEED).shuffle(order)
    plan = {
        "version": VERSION, "source_manifest_sha256": manifest["manifest_sha256"],
        "source_state_sha256": sha256(PRIOR_STATE.read_bytes()).hexdigest(),
        "model": MODEL, "model_digest": descriptor.digest, "instruction": INSTRUCTION,
        "response_schema": SCHEMA, "options": OPTIONS, "think": False,
        "order_seed": ORDER_SEED, "order": order,
        "design": "one call per arm and item; no prompt optimization or technical retries",
    }
    write_once(OUT / "plan.json", plan)
    for row in selected:
        item_id = row["item_id"]
        for arm, state in (("A", None), ("B", states[item_id])):
            write_once(OUT / "requests" / arm / f"{item_id}.json", evidence(row, state))
    print(canonical_json({"prepared": 128, "scenarios": 8, "plan_sha256": digest(plan)}))


def run() -> None:
    plan = read(OUT / "plan.json")
    if plan["version"] != VERSION or plan["model"] != MODEL or plan["instruction"] != INSTRUCTION or plan["options"] != OPTIONS:
        raise RuntimeError("frozen plan differs from code")
    client = OllamaLocalClient(timeout_seconds=600)
    if client.discover_model(MODEL).digest != plan["model_digest"]:
        raise RuntimeError("model digest changed")
    for index, (item_id, arm) in enumerate(plan["order"], 1):
        path = OUT / "results" / arm / f"{item_id}.json"
        if path.exists():
            continue
        request = read(OUT / "requests" / arm / f"{item_id}.json")
        if (request["effective_state"] is None) != (arm == "A"):
            raise RuntimeError("arm state mismatch")
        payload = {
            "model": MODEL,
            "messages": [{"role": "system", "content": INSTRUCTION}, {"role": "user", "content": canonical_json(request)}],
            "format": SCHEMA, "options": OPTIONS, "think": False, "stream": False, "keep_alive": "10m",
        }
        started = datetime.now(timezone.utc).isoformat()
        try:
            response = client.chat(payload)
            status, error, raw_error = "completed", None, None
        except OllamaLocalError as exc:
            response, status, error, raw_error = None, "technical_failure", exc.code, exc.raw_response
        write_once(path, {
            "version": VERSION, "item_id": item_id, "arm": arm,
            "plan_sha256": digest(plan), "request_sha256": digest(request),
            "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": status, "error": error, "raw_error_response": raw_error, "raw_response": response,
        })
        print(canonical_json({"completed": index, "total": 128, "arm": arm, "status": status}), flush=True)


def score() -> None:
    plan = read(OUT / "plan.json")
    mapping = read(SOURCE / "inputs/scoring-map.json")["items"]
    label_doc = read(SOURCE / "reference/reference-labels.json")
    if label_doc["input_manifest_sha256"] != plan["source_manifest_sha256"]:
        raise RuntimeError("reference map does not match frozen development source")
    labels = label_doc["labels"]
    if len(plan["order"]) != 128 or len(set(map(tuple, plan["order"]))) != 128:
        raise RuntimeError("incomplete frozen order")
    rows = []
    for item_id in sorted({item_id for item_id, _ in plan["order"]}):
        row = {"item_id": item_id, "scenario_id": mapping[item_id]["scenario_id"],
               "transition_family": mapping[item_id]["transition_family"],
               "condition": mapping[item_id]["condition"], "reference": labels[item_id]["expected"]}
        for arm in ("A", "B"):
            request = read(OUT / "requests" / arm / f"{item_id}.json")
            result = read(OUT / "results" / arm / f"{item_id}.json")
            if (result["item_id"] != item_id or result["arm"] != arm
                    or result["request_sha256"] != digest(request) or result["plan_sha256"] != digest(plan)):
                raise RuntimeError("result/request hash mismatch")
            response = result["raw_response"]
            message = response.get("message", {}) if isinstance(response, dict) else {}
            parsed = parse_verdict_response(message.get("content"), provider_refused=bool(message.get("refusal"))) if result["status"] == "completed" else None
            row[arm + "_status"] = parsed.status.value if parsed else result["status"]
            row[arm + "_verdict"] = parsed.verdict.value if parsed and parsed.verdict else None
            row[arm + "_correct"] = int(row[arm + "_verdict"] == row["reference"])
        row["difference"] = row["B_correct"] - row["A_correct"]
        rows.append(row)
    write_once(OUT / "analysis" / "scored-private.json", {"rows": rows})
    summary = {"items": len(rows), "scenarios": len({r["scenario_id"] for r in rows}),
               "A_correct": sum(r["A_correct"] for r in rows), "B_correct": sum(r["B_correct"] for r in rows),
               "corrected": sum(r["difference"] == 1 for r in rows),
               "damaged": sum(r["difference"] == -1 for r in rows),
               "difference_interval": cluster_interval(rows, "difference"),
               "A_accuracy_interval": cluster_interval(rows, "A_correct"),
               "B_accuracy_interval": cluster_interval(rows, "B_correct"),
               "by_scenario": {}, "by_family": {}, "by_condition": {}, "by_reference": {}, "statuses": {}}
    for key, field in (("by_scenario", "scenario_id"), ("by_family", "transition_family"),
                       ("by_condition", "condition"), ("by_reference", "reference")):
        for value in sorted({r[field] for r in rows}):
            subset = [r for r in rows if r[field] == value]
            summary[key][value] = {"n": len(subset), "A": sum(r["A_correct"] for r in subset),
                                   "B": sum(r["B_correct"] for r in subset),
                                   "corrected": sum(r["difference"] == 1 for r in subset),
                                   "damaged": sum(r["difference"] == -1 for r in subset)}
    for arm in ("A", "B"):
        summary["statuses"][arm] = dict(Counter(r[arm + "_status"] for r in rows))
    write_once(OUT / "analysis" / "aggregate.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "score": score}[sys.argv[1]]()
