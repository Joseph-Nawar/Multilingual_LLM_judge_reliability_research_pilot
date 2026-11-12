#!/usr/bin/env python3
"""Prepare frozen local screen configs, run after QC, or score retained outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multilingual_judge_pilot.local_ollama import OllamaLocalClient, OllamaLocalJudgeProvider
from multilingual_judge_pilot.qualification import (
    QUALIFICATION_MODEL_DIGESTS,
    build_input_manifest,
    build_qualification_config,
    sha256_file,
    verify_input_manifest,
)
from multilingual_judge_pilot.qualification_runner import run_qualification, verify_qc_acceptance
from multilingual_judge_pilot.qualification_scoring import score_qualification_results


DEFAULT_SCREEN = Path(".research-data/p3-local-method-stabilization/competence-screen")
DEFAULT_REVIEW = Path(".research-data/p3-local-method-stabilization/competence-screen-review/reviewer-delivery")
DEFAULT_CONFIGS = Path(".research-data/p3-local-method-stabilization/qualification-configurations")
DEFAULT_RUNS = Path(".research-data/p3-local-method-stabilization/qualification-runs")


def _require_private_path(path: Path) -> Path:
    resolved = path.resolve()
    private_root = (Path.cwd() / ".research-data").resolve()
    try:
        resolved.relative_to(private_root)
    except ValueError as exc:
        raise ValueError("qualification configs, acceptance records, inputs, outputs, and scores must stay under .research-data/") from exc
    return resolved


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path.name}")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def prepare_configs(screen_dir: Path, review_dir: Path, output_dir: Path, code_revision: str | None) -> dict:
    screen_dir = _require_private_path(screen_dir)
    review_dir = _require_private_path(review_dir)
    output_dir = _require_private_path(output_dir)
    items_path = screen_dir / "screen_inference_items.json"
    items = _load_json(items_path).get("items")
    if not isinstance(items, list):
        raise ValueError("screen inference source does not contain an item list")
    input_manifest = _load_json(review_dir / "qualification-input-manifest.json")
    verify_input_manifest(items, input_manifest)
    if input_manifest.get("source_file_sha256") != sha256_file(items_path):
        raise ValueError("screen source has changed since the reviewer package was prepared")
    if not code_revision:
        code_revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    output_dir.mkdir(parents=True, exist_ok=True)
    configurations = {}
    for tag, digest in QUALIFICATION_MODEL_DIGESTS.items():
        config = build_qualification_config(
            model_tag=tag,
            model_digest=digest,
            input_manifest=input_manifest,
            code_revision=code_revision,
        )
        filename = "qwen35-9b.json" if tag.startswith("qwen3.5:") else "gemma4-12b.json"
        path = output_dir / filename
        _write_json(path, config)
        configurations[filename] = {
            "sha256": sha256_file(path),
            "configuration_hash": config["configuration_hash"],
            "model_tag": tag,
            "model_digest": digest,
        }
        acceptance_template = {
            "acceptance_version": "p3-screen-qc-acceptance-1",
            "reviewer_disposition": "pending",
            "research_owner_disposition": "pending",
            "independent_review_complete": False,
            "input_manifest_sha256": input_manifest["manifest_sha256"],
            "configuration_hash": config["configuration_hash"],
            "review_export_sha256": None,
        }
        _write_json(output_dir / filename.replace(".json", ".qc-acceptance.template.json"), acceptance_template)
    manifest = {
        "manifest_version": "p3-qualification-config-set-manifest-1",
        "code_revision": code_revision,
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "configurations": configurations,
    }
    _write_json(output_dir / "configuration-set-manifest.json", manifest)
    return manifest


def run_one_model(
    screen_dir: Path,
    input_manifest_path: Path,
    config_path: Path,
    acceptance_path: Path,
    runs_root: Path,
    max_items: int | None,
) -> dict:
    screen_dir = _require_private_path(screen_dir)
    input_manifest_path = _require_private_path(input_manifest_path)
    config_path = _require_private_path(config_path)
    acceptance_path = _require_private_path(acceptance_path)
    runs_root = _require_private_path(runs_root)
    items_path = screen_dir / "screen_inference_items.json"
    items = _load_json(items_path).get("items")
    if not isinstance(items, list):
        raise ValueError("screen inference source does not contain an item list")
    input_manifest = _load_json(input_manifest_path)
    config = _load_json(config_path)
    acceptance = _load_json(acceptance_path)
    verify_input_manifest(items, input_manifest)
    if input_manifest.get("source_file_sha256") != sha256_file(items_path):
        raise ValueError("screen source has changed since the frozen qualification package was prepared")
    verify_qc_acceptance(config, input_manifest, acceptance)

    model_tag = config["model"]["model_tag"]
    model_slug = "qwen35-9b" if model_tag.startswith("qwen3.5:") else "gemma4-12b"
    run_dir = runs_root / model_slug / str(config["configuration_hash"])
    _require_private_path(run_dir)
    client = OllamaLocalClient("http://127.0.0.1:11434")
    active = client.list_running_models()
    if any(name != model_tag for name in active):
        raise RuntimeError("another model is loaded in local Ollama; stop it before running this candidate")
    provider = OllamaLocalJudgeProvider(client, model_tag)
    if provider.identity.model_version != config["model"]["digest"]:
        raise RuntimeError("local Ollama model digest differs from the frozen qualification configuration")
    if "thinking" not in provider.descriptor.capabilities:
        raise RuntimeError("local model metadata does not confirm the required thinking control")
    result = run_qualification(items, input_manifest, config, acceptance, provider, run_dir, max_items=max_items)
    return {**result, "run_directory": str(run_dir)}


def score_run(screen_dir: Path, run_dir: Path, output_path: Path) -> dict:
    screen_dir = _require_private_path(screen_dir)
    run_dir = _require_private_path(run_dir)
    output_path = _require_private_path(output_path)
    items_path = screen_dir / "screen_inference_items.json"
    items = _load_json(items_path).get("items")
    labels = _load_json(screen_dir / "screen_reference_key.json").get("labels")
    if not isinstance(items, list) or not isinstance(labels, dict):
        raise ValueError("screen source or reference key is malformed")
    run_manifest = _load_json(run_dir / "run-manifest.json")
    input_manifest = build_input_manifest(items, source_file_sha256=sha256_file(items_path))
    if run_manifest.get("input_manifest_sha256") != input_manifest["manifest_sha256"]:
        raise ValueError("run results do not match the current hash-bound screen inputs")
    records = []
    item_dir = run_dir / "items"
    for path in sorted(item_dir.glob("*.result.json")):
        record = _load_json(path)
        item_id = record.get("item_id")
        if (
            not isinstance(item_id, str)
            or item_id not in input_manifest["item_hashes"]
            or record.get("item_input_sha256") != input_manifest["item_hashes"][item_id]
            or record.get("configuration_hash") != run_manifest.get("configuration_hash")
            or record.get("run_execution_id") != run_manifest.get("run_execution_id")
        ):
            raise ValueError("retained result is not bound to the current run and screen item hashes")
        records.append(record)
    result = score_qualification_results(items, records, labels)
    _write_json(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-configs", help="write fixed, hash-bound configs under .research-data/")
    prepare.add_argument("--screen-dir", type=Path, default=DEFAULT_SCREEN)
    prepare.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW)
    prepare.add_argument("--output-dir", type=Path, default=DEFAULT_CONFIGS)
    prepare.add_argument("--code-revision")

    run = commands.add_parser("run", help="run one model after reviewer and owner acceptance")
    run.add_argument("--screen-dir", type=Path, default=DEFAULT_SCREEN)
    run.add_argument("--input-manifest", type=Path, default=DEFAULT_REVIEW / "qualification-input-manifest.json")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--acceptance", type=Path, required=True)
    run.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    run.add_argument("--max-items", type=int)

    score = commands.add_parser("score", help="score retained outputs separately from inference")
    score.add_argument("--screen-dir", type=Path, default=DEFAULT_SCREEN)
    score.add_argument("--run-dir", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare-configs":
        result = prepare_configs(args.screen_dir, args.review_dir, args.output_dir, args.code_revision)
    elif args.command == "run":
        result = run_one_model(args.screen_dir, args.input_manifest, args.config, args.acceptance, args.runs_root, args.max_items)
    else:
        result = score_run(args.screen_dir, args.run_dir, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
