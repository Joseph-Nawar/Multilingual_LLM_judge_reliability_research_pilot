#!/usr/bin/env python3
"""Import/reconcile the submitted screen review, run the local exploratory pilot, and score it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multilingual_judge_pilot.exploratory_pilot import run_exploratory_pilot, validate_exploratory_review_export
from multilingual_judge_pilot.exploratory_pilot_scoring import score_exploratory_pilot
from multilingual_judge_pilot.judge_inference import ContractError
from multilingual_judge_pilot.local_ollama import OllamaLocalClient, OllamaLocalJudgeProvider
from multilingual_judge_pilot.qualification import sha256_file, verify_input_manifest
from multilingual_judge_pilot.screen_review import REVIEW_EXPORT_VERSION


PRIVATE_ROOT = Path(".research-data/p3-local-method-stabilization")
SCREEN_DIR = PRIVATE_ROOT / "competence-screen"
REVIEW_DIR = PRIVATE_ROOT / "competence-screen-review"
DELIVERY_DIR = REVIEW_DIR / "reviewer-delivery"
SUBMISSION_PATH = REVIEW_DIR / "reviewer-submission" / "p3-competence-screen-review.json"
RECONCILIATION_PATH = REVIEW_DIR / "exploratory-review-reconciliation.json"
CONFIG_DIR = PRIVATE_ROOT / "qualification-configurations"
RUNS_DIR = PRIVATE_ROOT / "exploratory-pilots" / "pilot-01"
ANALYSIS_DIR = PRIVATE_ROOT / "exploratory-pilot-analysis" / "pilot-01"
MODEL_CONFIGS = {
    "qwen35": ("qwen35-9b.json", "qwen35-9b"),
    "gemma4": ("gemma4-12b.json", "gemma4-12b"),
}


def _private_path(path: Path) -> Path:
    resolved = path.resolve()
    private_root = (REPO_ROOT / PRIVATE_ROOT).resolve()
    try:
        resolved.relative_to(private_root)
    except ValueError as exc:
        raise ValueError("exploratory run, report, and imported review records must remain under .research-data/") from exc
    return resolved


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path.name}")
    return value


def _write_json(path: Path, value: dict) -> None:
    _private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_screen():
    screen_dir = _private_path(REPO_ROOT / SCREEN_DIR)
    items_path = screen_dir / "screen_inference_items.json"
    items_document = _read_json(items_path)
    items = items_document.get("items")
    if not isinstance(items, list):
        raise ValueError("screen inference file does not contain an item list")
    manifest = _read_json(DELIVERY_DIR / "qualification-input-manifest.json")
    verify_input_manifest(items, manifest)
    if manifest.get("source_file_sha256") != sha256_file(items_path):
        raise ValueError("screen inference source changed after the reviewer/configuration package was prepared")
    return items, manifest, items_path


def import_review(source_path: Path) -> dict:
    """Verify and preserve the submitted pre-reveal export byte-for-byte."""
    source_path = source_path.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    raw = source_path.read_bytes()
    export_hash = hashlib.sha256(raw).hexdigest()
    review_export = json.loads(raw.decode("utf-8"))
    items, manifest, _items_path = _load_screen()
    if not isinstance(review_export, dict) or review_export.get("schema_version") != REVIEW_EXPORT_VERSION:
        raise ContractError("submitted review does not use the existing hash-bound review-export contract")
    count = validate_exploratory_review_export(review_export, items, manifest)
    target = _private_path(REPO_ROOT / SUBMISSION_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != export_hash:
            raise FileExistsError("a different reviewer submission is already preserved at the private destination")
    else:
        shutil.copy2(source_path, target)
    per_item = []
    labels = _read_json(SCREEN_DIR / "screen_reference_key.json")["labels"]
    families = _read_json(SCREEN_DIR / "screen_design_metadata.json")["families"]
    response_by_id = {row["item_id"]: row for row in review_export["items"]}
    agreement = {"agreement": 0, "disagreement": 0, "unclear": 0}
    by_language = {
        "EN-EN": {"agreement": 0, "disagreement": 0, "unclear": 0},
        "AR-AR": {"agreement": 0, "disagreement": 0, "unclear": 0},
    }
    issue_cross_tab: dict[str, int] = {}
    item_by_id = {item["item_id"]: item for item in items}
    for item_id, item in item_by_id.items():
        answer = response_by_id[item_id]["answers"]
        expected = "valid" if labels[item_id]["expected_valid"] else "invalid"
        human = answer["independent_verdict"]
        key = "unclear" if human == "unclear" else "agreement" if human == expected else "disagreement"
        agreement[key] += 1
        by_language[item["language_condition"]][key] += 1
        per_item.append({
            "item_id": item_id,
            "source_sha256": response_by_id[item_id]["source_sha256"],
            "language_condition": item["language_condition"],
            "competency_family": families[item_id],
            "reference_label": expected,
            "reviewer_independent_verdict": human,
            "agreement_status": key,
            "constraint_consistency": answer["constraint_consistency"],
            "issue_note_present": bool(str(answer.get("issue_note", "")).strip()),
        })
        if answer["constraint_consistency"] == "issue":
            cross_key = f"{expected}|{human}"
            issue_cross_tab[cross_key] = issue_cross_tab.get(cross_key, 0) + 1
    determinate = agreement["agreement"] + agreement["disagreement"]
    report = {
        "report_version": "p3-exploratory-screen-review-reconciliation-v1",
        "stage": "PILOT_EXPLORATORY_UNVALIDATED",
        "review_export_sha256": export_hash,
        "review_export_schema": review_export["schema_version"],
        "input_manifest_sha256": manifest["manifest_sha256"],
        "review_export_formally_complete": False,
        "review_export_reference_labels_revealed": False,
        "post_reveal_responses_created": False,
        "screen_item_count": count,
        "agreement_counts": agreement,
        "agreement_fraction_among_determinate": agreement["agreement"] / determinate if determinate else None,
        "agreement_fraction_of_all_items": agreement["agreement"] / count,
        "by_language": by_language,
        "constraint_consistency_issue_count": sum(issue_cross_tab.values()),
        "constraint_consistency_issue_cross_tab": issue_cross_tab,
        "per_item_reconciliation": per_item,
        "reference_labels_modified": False,
        "study_data_used_in_inference": False,
    }
    _write_json(RECONCILIATION_PATH, report)
    return {
        "preserved_submission": str(SUBMISSION_PATH),
        "submission_sha256": export_hash,
        "report_path": str(RECONCILIATION_PATH),
        "screen_items_verified": count,
        "agreement_counts": agreement,
        "formally_complete": False,
    }


def run_one_model(model_key: str) -> dict:
    if model_key not in MODEL_CONFIGS:
        raise ValueError("choose one approved local judge: qwen35 or gemma4")
    if not SUBMISSION_PATH.exists() or not RECONCILIATION_PATH.exists():
        raise ValueError("import and reconcile the submitted pre-reveal reviewer export before the pilot")
    items, input_manifest, items_path = _load_screen()
    review_export = _read_json(SUBMISSION_PATH)
    review_hash = sha256_file(SUBMISSION_PATH)
    if _read_json(RECONCILIATION_PATH).get("review_export_sha256") != review_hash:
        raise ValueError("reconciliation report does not bind the preserved reviewer submission")
    config_filename, model_slug = MODEL_CONFIGS[model_key]
    config_path = _private_path(REPO_ROOT / CONFIG_DIR / config_filename)
    config = _read_json(config_path)
    if config.get("input", {}).get("source_file_sha256") != sha256_file(items_path):
        raise ValueError("fixed qualification configuration does not bind the current unchanged screen source")
    _private_path(REPO_ROOT / RUNS_DIR)

    client = OllamaLocalClient("http://127.0.0.1:11434")
    model_tag = config["model"]["model_tag"]
    active_models = client.list_running_models()
    if any(name != model_tag for name in active_models):
        raise RuntimeError("another Ollama model is loaded; unload it before this single-model pilot run")
    provider = OllamaLocalJudgeProvider(client, model_tag)
    if provider.identity.model_version != config["model"]["digest"]:
        raise RuntimeError("installed Ollama digest differs from the pinned pilot configuration")
    if "thinking" not in provider.descriptor.capabilities:
        raise RuntimeError("model metadata does not confirm the fixed thinking-disable control")
    runner_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    run_dir = RUNS_DIR / model_slug / str(config["configuration_hash"])
    result = run_exploratory_pilot(
        items,
        input_manifest,
        review_export,
        review_hash,
        config,
        provider,
        REPO_ROOT / run_dir,
        runner_code_revision=runner_revision,
    )
    return {**result, "model": config["model"], "run_directory": str(run_dir)}


def score_one_model(model_key: str) -> dict:
    if model_key not in MODEL_CONFIGS:
        raise ValueError("choose one approved local judge: qwen35 or gemma4")
    items, input_manifest, items_path = _load_screen()
    config_filename, model_slug = MODEL_CONFIGS[model_key]
    config = _read_json(CONFIG_DIR / config_filename)
    run_dir = RUNS_DIR / model_slug / str(config["configuration_hash"])
    run_manifest = _read_json(run_dir / "run-manifest.json")
    if run_manifest.get("stage") != "PILOT_EXPLORATORY_UNVALIDATED" or run_manifest.get("status") != "complete":
        raise ValueError("score only after all 48 items have one retained result record")
    if run_manifest.get("configuration_hash") != config["configuration_hash"] or run_manifest.get("input_manifest_sha256") != input_manifest["manifest_sha256"]:
        raise ValueError("run manifest does not match the fixed configuration and current screen")
    records = []
    for path in sorted((run_dir / "items").glob("*.result.json")):
        record = _read_json(path)
        item_id = record.get("item_id")
        expected_item_hash = input_manifest["item_hashes"].get(item_id) if isinstance(item_id, str) else None
        if (
            record.get("stage") != "PILOT_EXPLORATORY_UNVALIDATED"
            or record.get("review_export_sha256") != run_manifest.get("review_export_sha256")
            or record.get("configuration_hash") != run_manifest.get("configuration_hash")
            or record.get("run_execution_id") != run_manifest.get("run_execution_id")
            or record.get("item_input_sha256") != expected_item_hash
        ):
            raise ValueError("raw result is not bound to the current screen, run, config, and reviewer submission")
        records.append(record)
    if len(records) != 48:
        raise ValueError("exploratory scoring requires exactly 48 raw item result records")

    # Reference-key reads occur only here, after inference artifacts are complete.
    labels = _read_json(SCREEN_DIR / "screen_reference_key.json")["labels"]
    families = _read_json(SCREEN_DIR / "screen_design_metadata.json")["families"]
    review_export = _read_json(SUBMISSION_PATH)
    score = score_exploratory_pilot(items, records, labels, families, review_export)
    attempts = 0
    for record in records:
        run_result = record.get("run_result", {})
        for step in run_result.get("steps", []) if isinstance(run_result, dict) else []:
            attempts += len(step.get("attempts", [])) if isinstance(step, dict) and isinstance(step.get("attempts"), list) else 0
    output = {
        **score,
        "model": run_manifest["model"],
        "configuration_hash": run_manifest["configuration_hash"],
        "scorer_code_revision": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "runner_code_revision": run_manifest["runner_code_revision"],
        "qualification_configuration_code_revision": run_manifest["qualification_configuration_code_revision"],
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "review_export_sha256": run_manifest["review_export_sha256"],
        "run_execution_id": run_manifest["run_execution_id"],
        "elapsed_seconds": run_manifest.get("elapsed_seconds"),
        "judge_provider_attempts": attempts,
        "paid_api_cost_usd": 0,
        "translation_calls": 0,
    }
    output_path = ANALYSIS_DIR / model_slug / "exploratory-screen-score.json"
    _write_json(output_path, output)
    return {"analysis_path": str(output_path), "decision": score["provisional_threshold_comparison"]["pilot_decision"], "accuracy": score["overall"]["accuracy"], "elapsed_seconds": output["elapsed_seconds"], "judge_provider_attempts": attempts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reconcile = commands.add_parser("reconcile", help="hash-check, preserve, and reconcile a pre-reveal reviewer export")
    reconcile.add_argument("--source", type=Path, required=True)
    run = commands.add_parser("run", help="run one local model under PILOT_EXPLORATORY_UNVALIDATED status")
    run.add_argument("--model", choices=tuple(MODEL_CONFIGS), required=True)
    score = commands.add_parser("score", help="score a completed raw run against private labels")
    score.add_argument("--model", choices=tuple(MODEL_CONFIGS), required=True)
    args = parser.parse_args()
    if args.command == "reconcile":
        result = import_review(args.source)
    elif args.command == "run":
        result = run_one_model(args.model)
    else:
        result = score_one_model(args.model)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
