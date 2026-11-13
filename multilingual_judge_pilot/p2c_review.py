"""Strict ingestion and comparison of the existing private P2C reviewer exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

from .preflight import (
    PreflightValidationError,
    summarize_annotations,
    validate_adjudication_records,
)


REVIEWER_SLOTS = ("reviewer_slot_1", "reviewer_slot_2")
SUBMISSION_INDEX_VERSION = "p2c-submission-index-1"
_DISAGREEMENT_FIELDS = (
    "semantic_relation",
    "linguistic_quality",
    "decisive_update_dependence",
    "whole_action_dependence",
    "issue_codes",
    "checklist",
)


class ReviewValidationError(ValueError):
    """A reviewer export, import record, or adjudication set is invalid."""


@dataclass(frozen=True)
class ReviewInventory:
    item_ids: tuple[str, ...]
    expected_hashes: Mapping[str, str]
    expected_scenario_hashes: Mapping[str, str]


def _unique_json_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise ReviewValidationError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _reject_json_constant(value: str):
    raise ReviewValidationError(f"unsupported JSON constant: {value}")


def _parse_jsonl(raw: bytes) -> list[dict]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewValidationError("submission must be UTF-8 JSONL") from exc
    lines = text.splitlines()
    if not lines:
        raise ReviewValidationError("submission is empty")
    rows = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ReviewValidationError(f"blank JSONL line at {line_number}")
        try:
            row = json.loads(
                line,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
            )
        except ReviewValidationError:
            raise
        except (json.JSONDecodeError, TypeError) as exc:
            raise ReviewValidationError(f"invalid JSONL row at line {line_number}") from exc
        if not isinstance(row, dict):
            raise ReviewValidationError(f"JSONL row {line_number} must be an object")
        rows.append(row)
    return rows


def _check_problem_explanations(rows: Sequence[dict]) -> None:
    for row in rows:
        has_problem = (
            row.get("semantic_relation") != "equivalent"
            or row.get("linguistic_quality") == "unnatural_or_unclear"
            or bool(row.get("issue_codes"))
            or any(value is False for value in row.get("checklist", {}).values())
        )
        if has_problem and not row.get("notes", "").strip():
            raise ReviewValidationError("detected problems require an explanatory note")


def parse_submission_jsonl(
    raw: bytes,
    *,
    reviewer_slot: str,
    expected_hashes: Mapping[str, str],
    expected_scenario_hashes: Mapping[str, str],
) -> list[dict]:
    """Parse and validate one complete slot export against current package hashes."""
    if reviewer_slot not in REVIEWER_SLOTS:
        raise ReviewValidationError("unknown reviewer slot")
    if set(expected_hashes) != set(expected_scenario_hashes) or not expected_hashes:
        raise ReviewValidationError("expected variant and scenario hash maps must have identical non-empty IDs")
    rows = _parse_jsonl(raw)
    ids = [row.get("example_id") for row in rows]
    if any(not isinstance(item_id, str) or not item_id for item_id in ids):
        raise ReviewValidationError("annotation example IDs must be strings")
    if len(ids) != len(set(ids)):
        raise ReviewValidationError("duplicate annotation example ID")
    if set(ids) != set(expected_hashes):
        raise ReviewValidationError("submission must contain the complete expected item set exactly once")
    if any(row.get("reviewer_id") != reviewer_slot for row in rows):
        raise ReviewValidationError("annotation reviewer identity does not match the assigned reviewer slot")
    try:
        summarize_annotations(rows, dict(expected_hashes), dict(expected_scenario_hashes))
    except PreflightValidationError as exc:
        raise ReviewValidationError(str(exc)) from exc
    _check_problem_explanations(rows)
    return rows


def load_review_inventory(dataset_root: str | Path) -> ReviewInventory:
    """Read only the existing blank templates to establish IDs and source hashes."""
    root = Path(dataset_root)
    maps: list[tuple[dict[str, str], dict[str, str]]] = []
    for slot in REVIEWER_SLOTS:
        template_path = root / "review-package" / slot / "annotation-template.jsonl"
        try:
            rows = _parse_jsonl(template_path.read_bytes())
        except OSError as exc:
            raise ReviewValidationError(f"review template is unavailable for {slot}") from exc
        expected = {}
        scenarios = {}
        for row in rows:
            item_id = row.get("example_id")
            if not isinstance(item_id, str) or item_id in expected:
                raise ReviewValidationError("review template IDs must be unique non-empty strings")
            if row.get("reviewer_id") != "" or row.get("semantic_relation") != "":
                raise ReviewValidationError("source annotation template is not blank")
            expected[item_id] = row["example_sha256"]
            scenarios[item_id] = row["canonical_scenario_sha256"]
        maps.append((expected, scenarios))
    if maps[0] != maps[1]:
        raise ReviewValidationError("reviewer templates do not bind the same IDs and source hashes")
    expected, scenarios = maps[0]
    if len(expected) != 448:
        raise ReviewValidationError("existing P2C review inventory must contain exactly 448 variants")
    return ReviewInventory(tuple(expected), expected, scenarios)


def _read_index(state_root: Path) -> dict:
    path = state_root / "submission-index.json"
    if not path.exists():
        return {"schema_version": SUBMISSION_INDEX_VERSION, "reviewers": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    except (OSError, json.JSONDecodeError, ReviewValidationError) as exc:
        raise ReviewValidationError("submission index is malformed") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SUBMISSION_INDEX_VERSION or not isinstance(value.get("reviewers"), dict):
        raise ReviewValidationError("submission index schema is unsupported")
    return value


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ingest_submission(
    reviewer_slot: str,
    source: str | Path,
    state_root: str | Path,
    *,
    expected_hashes: Mapping[str, str],
    expected_scenario_hashes: Mapping[str, str],
    revision_reason: str | None = None,
) -> dict[str, object]:
    """Validate, archive immutable source bytes, and update one slot's current pointer."""
    if reviewer_slot not in REVIEWER_SLOTS:
        raise ReviewValidationError("unknown reviewer slot")
    source_path = Path(source)
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise ReviewValidationError("reviewer export cannot be read") from exc
    rows = parse_submission_jsonl(
        raw,
        reviewer_slot=reviewer_slot,
        expected_hashes=expected_hashes,
        expected_scenario_hashes=expected_scenario_hashes,
    )
    source_hash = hashlib.sha256(raw).hexdigest()
    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".submission.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ReviewValidationError("another submission import is in progress") from exc
    try:
        os.close(lock_fd)
        index = _read_index(root)
        previous = index["reviewers"].get(reviewer_slot)
        if previous and previous.get("source_sha256") == source_hash:
            return dict(previous)
        if previous and (not isinstance(revision_reason, str) or not revision_reason.strip()):
            raise ReviewValidationError("a changed submission requires a revision reason")
        archive_relative = Path("reviewer-submissions") / reviewer_slot / f"{source_hash}.jsonl"
        archive_path = root / archive_relative
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != source_hash:
                raise ReviewValidationError("immutable submission archive path contains different bytes")
        else:
            fd = os.open(archive_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        record = {
            "reviewer_slot": reviewer_slot,
            "reviewer_id": reviewer_slot,
            "source_filename": source_path.name,
            "source_sha256": source_hash,
            "source_bytes": len(raw),
            "annotation_count": len(rows),
            "archived_path": archive_relative.as_posix(),
            "imported_at": _utc_now(),
            "supersedes_submission_sha256": previous.get("source_sha256") if previous else None,
            "revision_reason": revision_reason.strip() if previous and revision_reason else None,
        }
        event_path = root / "submission-imports.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_fd = os.open(event_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            os.write(event_fd, (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
            os.fsync(event_fd)
        finally:
            os.close(event_fd)
        index["reviewers"][reviewer_slot] = record
        _atomic_json(root / "submission-index.json", index)
        return dict(record)
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def load_current_submissions(state_root: str | Path) -> dict[str, dict[str, object]]:
    """Read current immutable archives and verify their recorded content hashes."""
    root = Path(state_root)
    index = _read_index(root)
    result = {}
    for slot, record in index["reviewers"].items():
        if slot not in REVIEWER_SLOTS or not isinstance(record, dict) or record.get("reviewer_slot") != slot:
            raise ReviewValidationError("submission index contains an invalid reviewer entry")
        archive = (root / str(record.get("archived_path", ""))).resolve()
        if not archive.is_relative_to(root.resolve()):
            raise ReviewValidationError("submission archive path escapes the private state directory")
        try:
            raw = archive.read_bytes()
        except OSError as exc:
            raise ReviewValidationError("current immutable reviewer export is missing") from exc
        if hashlib.sha256(raw).hexdigest() != record.get("source_sha256"):
            raise ReviewValidationError("current immutable reviewer export hash has changed")
        result[slot] = {**record, "rows": _parse_jsonl(raw)}
    return result


def ingest_adjudications(
    source: str | Path,
    state_root: str | Path,
    *,
    annotations: Sequence[dict],
    revision_reason: str | None = None,
) -> dict[str, object]:
    """Validate and immutably archive the full hash-bound adjudication JSONL export."""
    source_path = Path(source)
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise ReviewValidationError("adjudication export cannot be read") from exc
    records = _parse_jsonl(raw)
    try:
        audit = validate_adjudication_records(records, annotations)
    except PreflightValidationError as exc:
        raise ReviewValidationError(str(exc)) from exc
    source_hash = hashlib.sha256(raw).hexdigest()
    root = Path(state_root) / "adjudications"
    root.mkdir(parents=True, exist_ok=True)
    index_path = root / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
        except (OSError, json.JSONDecodeError, ReviewValidationError) as exc:
            raise ReviewValidationError("adjudication import index is malformed") from exc
        if not isinstance(index, dict) or index.get("schema_version") != "p2c-adjudication-index-1":
            raise ReviewValidationError("adjudication import index has an unsupported schema")
    else:
        index = {"schema_version": "p2c-adjudication-index-1", "current": None, "history": []}
    previous = index.get("current")
    if isinstance(previous, dict) and previous.get("source_sha256") != source_hash and (not isinstance(revision_reason, str) or not revision_reason.strip()):
        raise ReviewValidationError("a changed adjudication export requires a revision reason")
    relative = Path("adjudications") / f"{source_hash}.jsonl"
    archive = Path(state_root) / relative
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        if hashlib.sha256(archive.read_bytes()).hexdigest() != source_hash:
            raise ReviewValidationError("immutable adjudication archive path contains different bytes")
    else:
        fd = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    record = {
        "source_filename": source_path.name,
        "source_sha256": source_hash,
        "source_bytes": len(raw),
        "adjudication_count": len(records),
        "archived_path": relative.as_posix(),
        "imported_at": _utc_now(),
        "supersedes_sha256": previous.get("source_sha256") if isinstance(previous, dict) else None,
        "revision_reason": revision_reason.strip() if isinstance(previous, dict) and revision_reason else None,
        "audit": {
            "required_count": audit.required_count,
            "adjudication_count": audit.adjudication_count,
            "unresolved_count": audit.unresolved_count,
            "incomplete_pair_count": audit.incomplete_pair_count,
            "complete": audit.complete,
        },
    }
    index["current"] = record
    index.setdefault("history", []).append(record)
    _atomic_json(root / "index.json", index)
    return dict(record)


def load_current_adjudications(state_root: str | Path) -> dict[str, object]:
    """Read and hash-verify the current immutable adjudication export, if any."""
    root = Path(state_root) / "adjudications"
    index_path = root / "index.json"
    if not index_path.exists():
        return {"source_sha256": hashlib.sha256(b"").hexdigest(), "records": []}
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    except (OSError, json.JSONDecodeError, ReviewValidationError) as exc:
        raise ReviewValidationError("adjudication import index is malformed") from exc
    record = index.get("current") if isinstance(index, dict) else None
    if not isinstance(record, dict):
        raise ReviewValidationError("adjudication index has no current record")
    archive = (Path(state_root) / str(record.get("archived_path", ""))).resolve()
    if not archive.is_relative_to(Path(state_root).resolve()):
        raise ReviewValidationError("adjudication archive path escapes the private state directory")
    try:
        raw = archive.read_bytes()
    except OSError as exc:
        raise ReviewValidationError("current immutable adjudication export is missing") from exc
    if hashlib.sha256(raw).hexdigest() != record.get("source_sha256"):
        raise ReviewValidationError("current immutable adjudication export hash has changed")
    return {**record, "records": _parse_jsonl(raw)}


def build_disagreement_report(
    submissions: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    expected_hashes: Mapping[str, str],
) -> dict[str, object]:
    """Return categorical differences only; never choose or infer an adjudication."""
    if set(submissions) != set(REVIEWER_SLOTS):
        raise ReviewValidationError("both independent reviewer submissions are required")
    grouped = {}
    for slot in REVIEWER_SLOTS:
        by_id = {}
        for row in submissions[slot]:
            item_id = row.get("example_id")
            if item_id not in expected_hashes or item_id in by_id:
                raise ReviewValidationError("disagreement report contains unknown or duplicate item IDs")
            by_id[item_id] = row
        if set(by_id) != set(expected_hashes):
            raise ReviewValidationError("disagreement report requires complete submissions from both slots")
        grouped[slot] = by_id
    disagreements = []
    by_field = {field: 0 for field in _DISAGREEMENT_FIELDS}
    for item_id in sorted(expected_hashes):
        fields = {
            field: {slot: grouped[slot][item_id][field] for slot in REVIEWER_SLOTS}
            for field in _DISAGREEMENT_FIELDS
            if grouped[REVIEWER_SLOTS[0]][item_id][field] != grouped[REVIEWER_SLOTS[1]][item_id][field]
        }
        if fields:
            disagreements.append({"example_id": item_id, "fields": fields})
            for field in fields:
                by_field[field] += 1
    return {
        "report_version": "p2c-disagreement-report-1",
        "expected_item_count": len(expected_hashes),
        "disagreement_count": len(disagreements),
        "disagreement_counts_by_field": by_field,
        "disagreements": disagreements,
        "automatically_resolved": False,
    }


def validate_current_adjudications(
    annotations: Sequence[dict],
    adjudications: Sequence[dict],
    *,
    expected_hashes: Mapping[str, str],
    expected_scenario_hashes: Mapping[str, str],
):
    """Validate a complete two-reviewer table and all required hash-bound adjudications."""
    try:
        annotation_audit = summarize_annotations(
            annotations,
            dict(expected_hashes),
            dict(expected_scenario_hashes),
        )
        if not annotation_audit.complete or set(annotation_audit.reviewer_ids) != set(REVIEWER_SLOTS):
            raise ReviewValidationError("both reviewers must submit one complete, independent annotation set")
        adjudication_audit = validate_adjudication_records(adjudications, annotations)
    except PreflightValidationError as exc:
        raise ReviewValidationError(str(exc)) from exc
    if not adjudication_audit.complete:
        raise ReviewValidationError("unresolved disagreements or incomplete review pairs remain")
    return annotation_audit, adjudication_audit
