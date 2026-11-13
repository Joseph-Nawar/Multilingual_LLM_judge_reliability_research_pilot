"""Reference-side review gates and private pre-inference freeze construction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from typing import Callable, Mapping, Sequence
from uuid import uuid4

from .integrity import validate_language_variant_coverage, validate_scenario_collection
from .oracle import evaluate_history
from .p2c_review import (
    REVIEWER_SLOTS,
    ReviewInventory,
    ReviewValidationError,
    build_disagreement_report,
    load_current_submissions,
    load_review_inventory,
    parse_submission_jsonl,
    validate_current_adjudications,
)
from .preflight import canonical_scenario_sha256, variant_sha256
from .qualification import sha256_text
from .schema import (
    CanonicalScenario,
    DatasetKind,
    Partition,
    canonical_value,
)
from .serialization import (
    build_judge_facing_item,
    judge_facing_to_dict,
    scenario_from_json,
)
from .judge_inference import canonical_json
from .p2c_study_config import build_study_configs


FULL_STUDY_INVENTORY = {
    "scenarios": 60,
    "development_primary_scenarios": 12,
    "locked_primary_scenarios": 36,
    "locked_control_scenarios": 12,
    "review_scenarios": 56,
    "review_items": 448,
    "development_items": 96,
    "locked_primary_items": 288,
    "locked_control_items": 96,
    "locked_items": 384,
}
FREEZE_MANIFEST_VERSION = "p2c-full-study-freeze-1"
INPUT_MANIFEST_VERSION = "p2c-locked-input-manifest-1"
DEVELOPMENT_MANIFEST_VERSION = "p2c-development-input-manifest-1"


class FreezeBlockedError(ValueError):
    """The human-validation or data-integrity conditions for freeze are unmet."""


@dataclass(frozen=True)
class FreezeInventory:
    scenarios: int
    development_primary_scenarios: int
    locked_primary_scenarios: int
    locked_control_scenarios: int
    review_scenarios: int
    review_items: int
    development_items: int
    locked_primary_items: int
    locked_control_items: int
    locked_items: int


def _inventory(value: FreezeInventory | Mapping[str, int] | None) -> FreezeInventory:
    if value is None:
        value = FULL_STUDY_INVENTORY
    if isinstance(value, FreezeInventory):
        return value
    try:
        fields = {}
        for key in FULL_STUDY_INVENTORY:
            raw = value[key]
            if type(raw) is not int or raw < 0:
                raise ValueError(key)
            fields[key] = raw
        return FreezeInventory(**fields)
    except (KeyError, TypeError, ValueError) as exc:
        raise FreezeBlockedError("freeze inventory specification is malformed") from exc


def _clean_annotation_issues(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    problems = []
    for row in rows:
        codes = []
        if row["semantic_relation"] != "equivalent":
            codes.append("semantic_relation")
        if row["linguistic_quality"] == "unnatural_or_unclear":
            codes.append("linguistic_quality")
        if row["issue_codes"]:
            codes.append("issue_codes")
        false_checks = sorted(field for field, value in row["checklist"].items() if value is False)
        if false_checks:
            codes.extend(f"checklist:{field}" for field in false_checks)
        if codes:
            problems.append({"example_id": row["example_id"], "reviewer_id": row["reviewer_id"], "issues": codes})
    return problems


def validate_reviews_for_freeze(
    submissions: Mapping[str, Sequence[dict]],
    adjudications: Sequence[dict],
    *,
    expected_hashes: Mapping[str, str],
    expected_scenario_hashes: Mapping[str, str],
) -> dict[str, object]:
    """Require complete independent assessments and a positive pre-freeze review disposition."""
    blockers: list[str] = []
    if set(submissions) != set(REVIEWER_SLOTS):
        return {
            "ready": False,
            "blockers": ["both reviewer submissions are required"],
            "annotation_count_per_reviewer": {slot: len(submissions.get(slot, ())) for slot in REVIEWER_SLOTS},
            "disagreement_report": None,
            "content_issues": [],
        }
    checked: dict[str, list[dict]] = {}
    for slot in REVIEWER_SLOTS:
        try:
            raw = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in submissions[slot]) + "\n").encode("utf-8")
            checked[slot] = parse_submission_jsonl(
                raw,
                reviewer_slot=slot,
                expected_hashes=expected_hashes,
                expected_scenario_hashes=expected_scenario_hashes,
            )
        except (ReviewValidationError, TypeError, KeyError) as exc:
            blockers.append(f"{slot} submission is invalid: {exc}")
    if blockers:
        return {
            "ready": False,
            "blockers": blockers,
            "annotation_count_per_reviewer": {slot: len(submissions.get(slot, ())) for slot in REVIEWER_SLOTS},
            "disagreement_report": None,
            "content_issues": [],
        }

    disagreement_report = build_disagreement_report(checked, expected_hashes=expected_hashes)
    combined = [row for slot in REVIEWER_SLOTS for row in checked[slot]]
    try:
        annotation_audit, adjudication_audit = validate_current_adjudications(
            combined,
            list(adjudications),
            expected_hashes=expected_hashes,
            expected_scenario_hashes=expected_scenario_hashes,
        )
    except ReviewValidationError as exc:
        blockers.append(str(exc))
        annotation_audit = None
        adjudication_audit = None

    content_issues = _clean_annotation_issues(combined)
    if content_issues:
        blockers.append(f"{len(content_issues)} reviewer rows contain unresolved semantic/language content issues")
    if adjudication_audit is not None:
        for row in adjudications:
            if row.get("outcome") in {"unresolved", "exclude", "revise"}:
                blockers.append(f"adjudication {row.get('example_id')} has outcome {row.get('outcome')} and requires disposition/fresh review")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "annotation_count_per_reviewer": {slot: len(checked[slot]) for slot in REVIEWER_SLOTS},
        "annotation_audit": asdict(annotation_audit) if annotation_audit else None,
        "adjudication_audit": asdict(adjudication_audit) if adjudication_audit else None,
        "disagreement_report": disagreement_report,
        "content_issues": content_issues,
    }


def _private_package_validator(dataset_root: Path) -> Mapping[str, object]:
    """Run the existing read-only P2C validator shipped beside the local private package."""
    validator = dataset_root / "build_full_dataset.py"
    if not validator.is_file():
        raise FreezeBlockedError("the existing private P2C full-dataset validator is missing")
    completed = subprocess.run(
        [sys.executable, str(validator), "validate", "--root", str(dataset_root)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise FreezeBlockedError("the existing read-only P2C dataset validator failed")
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise FreezeBlockedError("the private P2C validator did not return a JSON summary") from exc
    if not isinstance(summary, dict):
        raise FreezeBlockedError("the private P2C validator returned an invalid summary")
    return summary


def _unique_json_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise FreezeBlockedError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    except (OSError, json.JSONDecodeError, FreezeBlockedError) as exc:
        raise FreezeBlockedError(f"required private record is unavailable or invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise FreezeBlockedError(f"required private record is not an object: {path.name}")
    return value


def _load_corpus(dataset_root: Path) -> list[CanonicalScenario]:
    scenario_dirs = (
        dataset_root / "development" / "primary" / "scenarios",
        dataset_root / "primary" / "scenarios",
        dataset_root / "controls" / "scenarios",
    )
    scenarios = []
    for directory in scenario_dirs:
        for path in sorted(directory.glob("*.json")):
            scenario = scenario_from_json(path.read_text(encoding="utf-8"))
            if path.stem != scenario.scenario_id:
                raise FreezeBlockedError("canonical scenario filename does not match its record ID")
            scenarios.append(scenario)
    return scenarios


def _current_hash_maps(scenarios: Sequence[CanonicalScenario], review_inventory: ReviewInventory) -> tuple[dict[str, str], dict[str, str]]:
    variants = {variant.derivative_id: (scenario, variant) for scenario in scenarios for variant in scenario.language_variants}
    if set(review_inventory.item_ids) != set(variants):
        # The P2C review scope intentionally omits the four previously reviewed
        # pilot scenarios. Use the existing templates as the review-scope selector.
        missing = set(review_inventory.item_ids) - set(variants)
        if missing:
            raise FreezeBlockedError("review template contains unknown variant IDs")
    expected_hashes = {}
    expected_scenario_hashes = {}
    for item_id in review_inventory.item_ids:
        scenario, variant = variants[item_id]
        expected_hashes[item_id] = variant_sha256(variant)
        expected_scenario_hashes[item_id] = canonical_scenario_sha256(scenario)
    if expected_hashes != dict(review_inventory.expected_hashes) or expected_scenario_hashes != dict(review_inventory.expected_scenario_hashes):
        raise FreezeBlockedError("current canonical/variant hashes differ from the commissioned reviewer package")
    return expected_hashes, expected_scenario_hashes


def _scenario_counts(scenarios: Sequence[CanonicalScenario]) -> dict[str, int]:
    return {
        "scenarios": len(scenarios),
        "development_primary_scenarios": sum(row.kind is DatasetKind.PRIMARY and row.partition is Partition.DEVELOPMENT for row in scenarios),
        "locked_primary_scenarios": sum(row.kind is DatasetKind.PRIMARY and row.partition is Partition.LOCKED_PRIMARY for row in scenarios),
        "locked_control_scenarios": sum(row.kind is DatasetKind.AUXILIARY_CONTROL and row.partition is Partition.LOCKED_AUXILIARY_CONTROL for row in scenarios),
        "development_items": sum(len(row.language_variants) for row in scenarios if row.partition is Partition.DEVELOPMENT),
        "locked_primary_items": sum(len(row.language_variants) for row in scenarios if row.partition is Partition.LOCKED_PRIMARY),
        "locked_control_items": sum(len(row.language_variants) for row in scenarios if row.partition is Partition.LOCKED_AUXILIARY_CONTROL),
    }


def _validate_corpus(
    dataset_root: Path,
    review_inventory: ReviewInventory,
    *,
    expected_inventory: FreezeInventory,
    package_validator: Callable[[Path], Mapping[str, object]],
) -> tuple[list[CanonicalScenario], dict[str, object], dict[str, str], dict[str, str]]:
    manifest = _read_json(dataset_root / "manifest.json")
    if manifest.get("dataset_frozen") is not False or manifest.get("model_inference_performed") is not False:
        raise FreezeBlockedError("source dataset package has an unauthorized frozen or inference status")
    summary = package_validator(dataset_root)
    if summary.get("scenario_count") != expected_inventory.scenarios:
        raise FreezeBlockedError("validated P2C scenario count does not match the required inventory")
    package_hash = summary.get("package_sha256")
    if not isinstance(package_hash, str) or len(package_hash) != 64 or any(char not in "0123456789abcdef" for char in package_hash):
        raise FreezeBlockedError("validated P2C package must provide a lowercase SHA-256 digest")
    scenarios = _load_corpus(dataset_root)
    if len(scenarios) != expected_inventory.scenarios:
        raise FreezeBlockedError("canonical scenario files do not match the required inventory")
    validate_scenario_collection(scenarios)
    for scenario in scenarios:
        validate_language_variant_coverage(scenario)
        if len(scenario.language_variants) != 8:
            raise FreezeBlockedError("each canonical scenario must have exactly eight history/language variants")
        for history in scenario.histories:
            evaluate_history(scenario, history.history_id)
    counts = _scenario_counts(scenarios)
    for key in (
        "scenarios",
        "development_primary_scenarios",
        "locked_primary_scenarios",
        "locked_control_scenarios",
        "development_items",
        "locked_primary_items",
        "locked_control_items",
    ):
        if counts[key] != getattr(expected_inventory, key):
            raise FreezeBlockedError(f"corpus allocation does not match the required {key} count")
    review_scenarios = {scenario.scenario_id for scenario in scenarios if any(variant.derivative_id in review_inventory.expected_hashes for variant in scenario.language_variants)}
    if len(review_scenarios) != expected_inventory.review_scenarios or len(review_inventory.item_ids) != expected_inventory.review_items:
        raise FreezeBlockedError("review scope does not match the commissioned P2C inventory")
    expected_hashes, expected_scenario_hashes = _current_hash_maps(scenarios, review_inventory)
    return scenarios, dict(summary), expected_hashes, expected_scenario_hashes


def _load_adjudications(path: str | Path | None) -> tuple[list[dict], str]:
    if path is None:
        return [], hashlib.sha256(b"").hexdigest()
    source = Path(path)
    if not source.exists():
        return [], hashlib.sha256(b"").hexdigest()
    raw = source.read_bytes()
    rows = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            raise FreezeBlockedError(f"blank adjudication JSONL line at {number}")
        try:
            row = json.loads(line, object_pairs_hook=_unique_json_object)
        except (json.JSONDecodeError, FreezeBlockedError) as exc:
            raise FreezeBlockedError(f"invalid adjudication JSONL line {number}") from exc
        if not isinstance(row, dict):
            raise FreezeBlockedError(f"adjudication line {number} must be an object")
        rows.append(row)
    return rows, hashlib.sha256(raw).hexdigest()


def verify_pre_freeze(
    dataset_root: str | Path,
    state_root: str | Path,
    adjudications_path: str | Path | None = None,
    *,
    review_inventory: ReviewInventory | None = None,
    expected_inventory: FreezeInventory | Mapping[str, int] | None = None,
    package_validator: Callable[[Path], Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Return an auditable readiness report without writing or freezing data."""
    root = Path(dataset_root)
    inventory = _inventory(expected_inventory)
    try:
        review_inventory = review_inventory or load_review_inventory(root)
        scenarios, package_summary, expected_hashes, expected_scenario_hashes = _validate_corpus(
            root,
            review_inventory,
            expected_inventory=inventory,
            package_validator=package_validator or _private_package_validator,
        )
    except Exception as exc:
        return {"ready": False, "blockers": [str(exc)], "scenario_count": 0, "review_inventory_count": 0}

    submissions = {}
    try:
        for slot, record in load_current_submissions(state_root).items():
            submissions[slot] = record["rows"]
    except ReviewValidationError as exc:
        return {"ready": False, "blockers": [str(exc)], "scenario_count": len(scenarios), "review_inventory_count": len(review_inventory.item_ids)}
    adjudications, adjudication_hash = _load_adjudications(adjudications_path)
    review_result = validate_reviews_for_freeze(
        submissions,
        adjudications,
        expected_hashes=expected_hashes,
        expected_scenario_hashes=expected_scenario_hashes,
    )
    return {
        **review_result,
        "scenario_count": len(scenarios),
        "package_sha256": package_summary.get("package_sha256"),
        "review_inventory_count": len(review_inventory.item_ids),
        "adjudications_sha256": adjudication_hash,
    }


def _atomic_bytes(path: Path, raw: bytes, mode: int = 0o444) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return raw


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_json(path: Path, value: object, mode: int = 0o444) -> str:
    raw = _json_bytes(value)
    _atomic_bytes(path, raw, mode)
    return hashlib.sha256(raw).hexdigest()


def _build_input_record(scenario: CanonicalScenario, history, variant, opaque_id: str) -> dict[str, object]:
    projected = build_judge_facing_item(
        scenario,
        history.history_id,
        variant.derivative_id,
        opaque_item_id=opaque_id,
    )
    public = judge_facing_to_dict(projected)
    turns = [
        {
            "turn_index": turn.turn_index,
            "speaker": turn.role.value,
            "language": "en" if turn.language.value == "en" else "ar",
            "content": turn.content,
        }
        for turn in variant.turns
    ]
    return {
        "item_id": opaque_id,
        "language_condition": variant.assignment.condition.value,
        "action_turn_index": history.action_turn_index,
        "conversation": turns,
        "action": public["action"],
        "public_tool_schema": public["public_tool_schema"],
    }


def _reference_record(scenario: CanonicalScenario, history_id: str) -> dict[str, object]:
    result = evaluate_history(scenario, history_id)
    return {
        "reference_verdict": result.label.value,
        "reason_codes": [code.value for code in result.reason_codes],
        "effective_state_sha256": result.state_digest,
        "effective_state": canonical_value(result.effective_state),
    }


def _build_frozen_records(scenarios: Sequence[CanonicalScenario]):
    records = []
    refs = {}
    metadata = {}
    opaque_map = {}
    for scenario in scenarios:
        for history_position, history in enumerate(scenario.histories, start=1):
            for variant in scenario.language_variants:
                if variant.parent_history_id != history.history_id:
                    continue
                opaque_id = str(uuid4())
                item = _build_input_record(scenario, history, variant, opaque_id)
                records.append((scenario, history, variant, item))
                refs[opaque_id] = _reference_record(scenario, history.history_id)
                metadata[opaque_id] = {
                    "scenario_id": scenario.scenario_id,
                    "pair_id": history.pair_id,
                    "history_id": history.history_id,
                    "history_position": history_position,
                    "derivative_id": variant.derivative_id,
                    "partition": scenario.partition.value,
                    "dataset_kind": scenario.kind.value,
                    "domain": scenario.domain.value,
                    "transition_family": scenario.transition_family.value,
                    "language_condition": variant.assignment.condition.value,
                    "template_family": scenario.provenance.authoring_template_id,
                    "semantic_recipe": scenario.provenance.semantic_recipe_id,
                }
                opaque_map[opaque_id] = {
                    "scenario_id": scenario.scenario_id,
                    "history_id": history.history_id,
                    "derivative_id": variant.derivative_id,
                }
    return records, refs, metadata, opaque_map


def _input_manifest(records: Sequence[Mapping[str, object]], package_sha256: str, *, ordered_ids: Sequence[str], manifest_version: str) -> dict[str, object]:
    item_hashes = {str(row["item_id"]): sha256_text(canonical_json(row)) for row in records}
    body = {
        "manifest_version": manifest_version,
        "source_dataset_package_sha256": package_sha256,
        "item_count": len(records),
        "item_hashes": {key: item_hashes[key] for key in sorted(item_hashes)},
        "ordered_item_ids": list(ordered_ids),
        "ordered_item_ids_sha256": sha256_text(canonical_json(list(ordered_ids))),
    }
    body["manifest_sha256"] = sha256_text(canonical_json(body))
    return body


def create_freeze(
    dataset_root: str | Path,
    state_root: str | Path,
    output_root: str | Path,
    adjudications_path: str | Path | None = None,
    *,
    review_inventory: ReviewInventory | None = None,
    expected_inventory: FreezeInventory | Mapping[str, int] | None = None,
    package_validator: Callable[[Path], Mapping[str, object]] | None = None,
    code_revision: str,
) -> dict[str, object]:
    """Build a one-time immutable split freeze only after the complete validation gate passes."""
    root = Path(dataset_root)
    inventory = _inventory(expected_inventory)
    review_inventory = review_inventory or load_review_inventory(root)
    ready = verify_pre_freeze(
        root,
        state_root,
        adjudications_path,
        review_inventory=review_inventory,
        expected_inventory=inventory,
        package_validator=package_validator,
    )
    if not ready.get("ready"):
        raise FreezeBlockedError("dataset freeze is blocked: " + "; ".join(ready.get("blockers", [])))
    scenarios = _load_corpus(root)
    package_sha256 = str(ready["package_sha256"])
    records, refs, metadata, opaque_map = _build_frozen_records(scenarios)
    locked = [(scenario, history, variant, item) for scenario, history, variant, item in records if scenario.partition is not Partition.DEVELOPMENT]
    development = [(scenario, history, variant, item) for scenario, history, variant, item in records if scenario.partition is Partition.DEVELOPMENT]
    locked_rows = [row[3] for row in locked]
    development_rows = [row[3] for row in development]
    if len(locked_rows) != inventory.locked_items or len(development_rows) != inventory.development_items:
        raise FreezeBlockedError("projected locked/development item counts differ from the approved inventory")

    seed = secrets.token_bytes(32)
    seed_hex = seed.hex()
    ordered_locked = sorted(
        (str(row["item_id"]) for row in locked_rows),
        key=lambda item_id: (hashlib.sha256(seed + b"\x00" + item_id.encode("utf-8")).hexdigest(), item_id),
    )
    ordered_development = sorted(str(row["item_id"]) for row in development_rows)
    locked_by_id = {row["item_id"]: row for row in locked_rows}
    development_by_id = {row["item_id"]: row for row in development_rows}
    locked_rows = [locked_by_id[item_id] for item_id in ordered_locked]
    development_rows = [development_by_id[item_id] for item_id in ordered_development]
    locked_manifest = _input_manifest(locked_rows, package_sha256, ordered_ids=ordered_locked, manifest_version=INPUT_MANIFEST_VERSION)
    development_manifest = _input_manifest(development_rows, package_sha256, ordered_ids=ordered_development, manifest_version=DEVELOPMENT_MANIFEST_VERSION)

    base = Path(output_root)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(base, 0o700)
    if any(base.glob("freeze-*")):
        raise FreezeBlockedError("a prior or partial freeze already exists; refusing to create a competing freeze")
    freeze_id = f"freeze-{uuid4().hex}"
    freeze_root = base / freeze_id
    try:
        freeze_root.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise FreezeBlockedError("freeze ID already exists; frozen inputs are immutable") from exc

    files = {}
    files["locked/inference-items.jsonl"] = hashlib.sha256(
        _atomic_jsonl(freeze_root / "locked" / "inference-items.jsonl", locked_rows)
    ).hexdigest()
    files["locked/input-manifest.json"] = _write_json(freeze_root / "locked" / "input-manifest.json", locked_manifest)
    files["development/inference-items.jsonl"] = hashlib.sha256(
        _atomic_jsonl(freeze_root / "development" / "inference-items.jsonl", development_rows)
    ).hexdigest()
    files["development/input-manifest.json"] = _write_json(freeze_root / "development" / "input-manifest.json", development_manifest)
    run_configs = build_study_configs(locked_manifest, code_revision)
    files["execution/run-configs.json"] = _write_json(
        freeze_root / "execution" / "run-configs.json",
        {
            "configurations": run_configs,
            "configurations_sha256": sha256_text(canonical_json(run_configs)),
            "development_configurations": build_study_configs(development_manifest, code_revision),
            "development_configurations_sha256": sha256_text(canonical_json(build_study_configs(development_manifest, code_revision))),
        },
        mode=0o600,
    )
    locked_ids = set(locked_manifest["item_hashes"])
    development_ids = set(development_manifest["item_hashes"])
    files["reference/locked-reference-key.json"] = _write_json(
        freeze_root / "reference" / "locked-reference-key.json",
        {item_id: refs[item_id] for item_id in sorted(locked_ids)},
        mode=0o600,
    )
    files["reference/development-reference-key.json"] = _write_json(
        freeze_root / "reference" / "development-reference-key.json",
        {item_id: refs[item_id] for item_id in sorted(development_ids)},
        mode=0o600,
    )
    files["reference/locked-analysis-metadata.json"] = _write_json(
        freeze_root / "reference" / "locked-analysis-metadata.json",
        {item_id: metadata[item_id] for item_id in sorted(locked_ids)},
        mode=0o600,
    )
    files["reference/development-analysis-metadata.json"] = _write_json(
        freeze_root / "reference" / "development-analysis-metadata.json",
        {item_id: metadata[item_id] for item_id in sorted(development_ids)},
        mode=0o600,
    )
    files["reference/opaque-item-map.json"] = _write_json(
        freeze_root / "reference" / "opaque-item-map.json",
        {**{key: opaque_map[key] for key in sorted(locked_ids | development_ids)}},
        mode=0o600,
    )
    files["reference/randomization.json"] = _write_json(
        freeze_root / "reference" / "randomization.json",
        {
            "randomization_version": "sha256-seed-item-id-order-1",
            "seed_hex": seed_hex,
            "locked_order_sha256": locked_manifest["ordered_item_ids_sha256"],
        },
        mode=0o600,
    )
    adjudication_source = Path(adjudications_path) if adjudications_path and Path(adjudications_path).exists() else None
    raw_adjudications = adjudication_source.read_bytes() if adjudication_source else b""
    files["reference/adjudications.jsonl"] = hashlib.sha256(
        _atomic_bytes(freeze_root / "reference" / "adjudications.jsonl", raw_adjudications, mode=0o600)
    ).hexdigest()
    manifest = {
        "manifest_version": FREEZE_MANIFEST_VERSION,
        "freeze_id": freeze_id,
        "status": "frozen",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "code_revision": code_revision,
        "dataset_package_sha256": package_sha256,
        "reviewer_submission_sha256": {
            slot: load_current_submissions(state_root)[slot]["source_sha256"] for slot in REVIEWER_SLOTS
        },
        "adjudications_sha256": ready["adjudications_sha256"],
        "inventory": asdict(inventory),
        "locked_item_count": len(locked_rows),
        "development_item_count": len(development_rows),
        "locked_input_manifest_sha256": locked_manifest["manifest_sha256"],
        "development_input_manifest_sha256": development_manifest["manifest_sha256"],
        "files": files,
        "reference_files_separated_from_inference": True,
    }
    manifest_sha256 = _write_json(freeze_root / "freeze-manifest.json", manifest)
    _atomic_bytes(freeze_root / "freeze-manifest.sha256", (manifest_sha256 + "  freeze-manifest.json\n").encode("ascii"))
    return {"freeze_id": freeze_id, "freeze_root": str(freeze_root), "manifest_sha256": manifest_sha256, **manifest}


def _atomic_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> bytes:
    raw = b"".join((canonical_json(row) + "\n").encode("utf-8") for row in rows)
    _atomic_bytes(path, raw)
    return raw
