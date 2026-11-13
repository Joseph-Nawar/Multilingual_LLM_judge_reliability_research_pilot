#!/usr/bin/env python3
"""Integrated P2C validation, freeze, local inference, and analysis CLI."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multilingual_judge_pilot.local_ollama import OllamaLocalClient, OllamaLocalJudgeProvider, OllamaLocalTranslator
from multilingual_judge_pilot.p2c_analysis import analyze_frozen_runs
from multilingual_judge_pilot.p2c_freeze import FreezeBlockedError, create_freeze, verify_pre_freeze
from multilingual_judge_pilot.p2c_inference import prepare_translations, run_frozen_baseline
from multilingual_judge_pilot.p2c_review import (
    REVIEWER_SLOTS,
    ReviewValidationError,
    build_disagreement_report,
    ingest_adjudications,
    ingest_submission,
    load_current_adjudications,
    load_current_submissions,
    load_review_inventory,
    parse_submission_jsonl,
    validate_current_adjudications,
)


DEFAULT_DATASET = REPO_ROOT / ".research-data" / "p2c-full"
DEFAULT_STATE = DEFAULT_DATASET / "study-state"
DEFAULT_FREEZES = DEFAULT_DATASET / "freezes"
PRIVATE_ROOT = (REPO_ROOT / ".research-data").resolve()


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _private_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_relative_to(PRIVATE_ROOT):
        raise ValueError("private outputs and freeze inputs must remain under repository .research-data/")
    return path


def _current_annotations(dataset_root: Path, state_root: Path):
    inventory = load_review_inventory(dataset_root)
    stored = load_current_submissions(state_root)
    annotations = {}
    for slot in REVIEWER_SLOTS:
        if slot not in stored:
            continue
        annotations[slot] = parse_submission_jsonl(
            Path(state_root, stored[slot]["archived_path"]).read_bytes(),
            reviewer_slot=slot,
            expected_hashes=inventory.expected_hashes,
            expected_scenario_hashes=inventory.expected_scenario_hashes,
        )
    return inventory, stored, annotations


def _git_revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("could not identify the current code revision") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET, help="private P2C full-dataset package")
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE, help="private reviewer submission/adjudication archive")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show reviewer export arrival and inventory status")
    ingest = sub.add_parser("ingest", help="validate and archive one reviewer JSONL export")
    ingest.add_argument("reviewer_slot", choices=REVIEWER_SLOTS)
    ingest.add_argument("source", type=Path)
    ingest.add_argument("--revision-reason")
    sub.add_parser("disagreements", help="report reviewer disagreements without resolving them")
    adj_ingest = sub.add_parser("ingest-adjudications", help="validate and archive complete hash-bound adjudication JSONL")
    adj_ingest.add_argument("source", type=Path)
    adj_ingest.add_argument("--revision-reason")
    sub.add_parser("validate-adjudications", help="validate current reviewer/adjudication records")
    sub.add_parser("verify", help="check all pre-freeze requirements without writing a freeze")
    freeze = sub.add_parser("freeze", help="create the immutable freeze only when every gate passes")
    freeze.add_argument("--output-root", type=Path, default=DEFAULT_FREEZES)
    freeze.add_argument("--code-revision", default=None)

    translate = sub.add_parser("translate", help="run the local TranslateGemma pretranslation stage on a completed freeze")
    translate.add_argument("--freeze-root", type=Path, required=True)
    run = sub.add_parser("run", help="run or resume one locked local baseline")
    run.add_argument("baseline", choices=("direct", "translation_first", "structured"))
    run.add_argument("--freeze-root", type=Path, required=True)
    analyze = sub.add_parser("analyze", help="score immutable baseline outputs against the separate reference key")
    analyze.add_argument("--freeze-root", type=Path, required=True)
    analyze.add_argument("--partition", choices=("locked", "development"), default="locked")
    analyze.add_argument("--output", type=Path, default=None)
    return parser


def _status(dataset_root: Path, state_root: Path) -> dict[str, object]:
    inventory = load_review_inventory(dataset_root)
    try:
        stored = load_current_submissions(state_root)
    except ReviewValidationError as exc:
        return {"expected_annotations_per_reviewer": len(inventory.item_ids), "reviewers": {}, "error": str(exc)}
    reviewers = {}
    for slot in REVIEWER_SLOTS:
        record = stored.get(slot)
        reviewers[slot] = (
            {"status": "received", "annotation_count": record["annotation_count"], "source_sha256": record["source_sha256"], "imported_at": record["imported_at"]}
            if record else {"status": "missing", "annotation_count": 0}
        )
    adj = load_current_adjudications(state_root)
    return {
        "review_inventory_count": len(inventory.item_ids),
        "expected_annotations_per_reviewer": len(inventory.item_ids),
        "reviewers": reviewers,
        "adjudications": {"status": "received" if adj.get("records") else "missing", "record_count": len(adj.get("records", [])), "source_sha256": adj.get("source_sha256")},
        "both_submissions_received": all(reviewers[slot]["status"] == "received" for slot in REVIEWER_SLOTS),
    }


def dispatch(args: argparse.Namespace) -> int:
    dataset_root = _private_path(args.dataset_root)
    state_root = _private_path(args.state_root)
    if args.command == "status":
        _json(_status(dataset_root, state_root))
        return 0
    if args.command == "ingest":
        inventory = load_review_inventory(dataset_root)
        record = ingest_submission(
            args.reviewer_slot,
            args.source,
            state_root,
            expected_hashes=inventory.expected_hashes,
            expected_scenario_hashes=inventory.expected_scenario_hashes,
            revision_reason=args.revision_reason,
        )
        _json(record)
        return 0
    if args.command == "disagreements":
        inventory, _stored, submissions = _current_annotations(dataset_root, state_root)
        _json(build_disagreement_report(submissions, expected_hashes=inventory.expected_hashes))
        return 0
    if args.command == "ingest-adjudications":
        inventory, _stored, submissions = _current_annotations(dataset_root, state_root)
        if set(submissions) != set(REVIEWER_SLOTS):
            raise ReviewValidationError("both complete reviewer exports are required before adjudication ingestion")
        annotations = [row for slot in REVIEWER_SLOTS for row in submissions[slot]]
        record = ingest_adjudications(args.source, state_root, annotations=annotations, revision_reason=args.revision_reason)
        _json(record)
        return 0
    if args.command == "validate-adjudications":
        inventory, _stored, submissions = _current_annotations(dataset_root, state_root)
        current = load_current_adjudications(state_root)
        if set(submissions) != set(REVIEWER_SLOTS):
            raise ReviewValidationError("both complete reviewer exports are required")
        annotations = [row for slot in REVIEWER_SLOTS for row in submissions[slot]]
        annotation_audit, adjudication_audit = validate_current_adjudications(
            annotations,
            current["records"],
            expected_hashes=inventory.expected_hashes,
            expected_scenario_hashes=inventory.expected_scenario_hashes,
        )
        _json({"annotations": asdict(annotation_audit), "adjudications": asdict(adjudication_audit), "source_sha256": current["source_sha256"]})
        return 0
    if args.command == "verify":
        current = load_current_adjudications(state_root)
        adjudications_path = state_root / current["archived_path"] if current.get("archived_path") else None
        report = verify_pre_freeze(dataset_root, state_root, adjudications_path)
        _json(report)
        return 0 if report.get("ready") else 2
    if args.command == "freeze":
        output_root = _private_path(args.output_root)
        current = load_current_adjudications(state_root)
        adjudications_path = state_root / current["archived_path"] if current.get("archived_path") else None
        result = create_freeze(
            dataset_root,
            state_root,
            output_root,
            adjudications_path,
            code_revision=args.code_revision or _git_revision(),
        )
        _json({"freeze_id": result["freeze_id"], "freeze_root": result["freeze_root"], "manifest_sha256": result["manifest_sha256"], "status": result["status"]})
        return 0
    if args.command == "translate":
        freeze_root = _private_path(args.freeze_root)
        client = OllamaLocalClient()
        translator = OllamaLocalTranslator(client, "translategemma:4b-it-q4_K_M")
        _json(prepare_translations(freeze_root, translator))
        return 0
    if args.command == "run":
        freeze_root = _private_path(args.freeze_root)
        client = OllamaLocalClient()
        provider = OllamaLocalJudgeProvider(client, "gemma4:12b-it-qat")
        translator = OllamaLocalTranslator(client, "translategemma:4b-it-q4_K_M") if args.baseline == "translation_first" else None
        _json(run_frozen_baseline(freeze_root, args.baseline, provider, translator=translator, partition="locked"))
        return 0
    if args.command == "analyze":
        freeze_root = _private_path(args.freeze_root)
        output = _private_path(args.output) if args.output else freeze_root / "analysis" / f"{args.partition}-analysis.json"
        _json(analyze_frozen_runs(freeze_root, partition=args.partition, output_path=output))
        return 0
    raise ValueError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
