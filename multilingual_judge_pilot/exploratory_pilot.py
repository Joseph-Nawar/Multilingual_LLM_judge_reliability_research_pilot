"""Narrow local runner for the authorized unvalidated screen pilot.

This path is deliberately separate from the formal qualification runner. It
accepts a complete pre-reveal reviewer assessment while recording that formal
review is incomplete. It never imports the screen reference key.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Mapping, Sequence
from uuid import uuid4

from .judge_baselines import DirectMultilingualBaseline
from .judge_inference import (
    BaselineKind,
    ContractError,
    JudgeExecutor,
    JudgeFacingInput,
    ProviderIdentity,
    RetryPolicy,
    RunConfig,
)
from .p3_methodology_proposals import DIRECT_PROMPT_V2
from .qualification import (
    QUALIFICATION_RETRY_POLICY,
    item_sha256,
    sha256_text,
    validate_qualification_config,
    verify_input_manifest,
)
from .screen_review import REVIEW_EXPORT_VERSION, validate_review_export


EXPLORATORY_STAGE = "PILOT_EXPLORATORY_UNVALIDATED"
EXPLORATORY_RUN_MANIFEST_VERSION = "p3-exploratory-screen-run-v1"
EXPLORATORY_ITEM_RESULT_VERSION = "p3-exploratory-screen-item-result-v1"
EXPLORATORY_ITEM_STATE_VERSION = "p3-exploratory-screen-item-state-v1"
_PRE_REVEAL_FIELDS = (
    "naturalness",
    "interpretation",
    "action_tool",
    "independent_verdict",
    "constraint_consistency",
    "ambiguity",
    "context_distinct",
)


class ExploratoryPilotResumeError(RuntimeError):
    """An existing exploratory run cannot be resumed without duplication risk."""


def validate_exploratory_review_export(
    review_export: Mapping[str, object],
    items: Sequence[Mapping[str, object]],
    input_manifest: Mapping[str, object],
) -> int:
    """Require all pre-reveal judgments but preserve the formally incomplete export."""
    validate_review_export(review_export, items, input_manifest)
    if review_export.get("schema_version") != REVIEW_EXPORT_VERSION:
        raise ContractError("unsupported reviewer export version")
    if (
        review_export.get("locked_before_label_reveal") is not False
        or review_export.get("reference_labels_revealed") is not False
        or review_export.get("review_complete") is not False
    ):
        raise ContractError("exploratory input must remain an incomplete pre-reveal reviewer export")
    declaration = review_export.get("reviewer_declaration")
    if not isinstance(declaration, Mapping) or declaration.get("independent") is not True:
        raise ContractError("exploratory run requires the submitted reviewer independence declaration")
    for field in (
        "english_proficiency",
        "msa_proficiency",
        "relevant_review_experience",
        "conflicts_of_interest",
        "prior_dataset_exposure",
    ):
        if not isinstance(declaration.get(field), str) or not declaration[field].strip():
            raise ContractError("exploratory reviewer declaration is incomplete")
    rows = review_export.get("items")
    if not isinstance(rows, list) or len(rows) != 48:
        raise ContractError("exploratory review must contain all 48 screen items")
    for row in rows:
        answers = row.get("answers") if isinstance(row, Mapping) else None
        if not isinstance(answers, Mapping) or any(
            not isinstance(answers.get(field), str) or not answers[field]
            for field in _PRE_REVEAL_FIELDS
        ):
            raise ContractError("exploratory review requires complete independent assessments for all 48 items")
        if "reference_label_review" in answers:
            raise ContractError("exploratory input must not contain post-reveal reference-label assessments")
    return len(rows)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExploratoryPilotResumeError(f"cannot read retained run record: {path.name}") from exc
    if not isinstance(value, dict):
        raise ExploratoryPilotResumeError(f"retained run record is not an object: {path.name}")
    return value


def _run_config(config: Mapping[str, object], input_manifest: Mapping[str, object]) -> RunConfig:
    model = config["model"]
    retry = config["retry_policy"]
    if retry != QUALIFICATION_RETRY_POLICY:
        raise ContractError("exploratory run must preserve the fixed qualification retry policy")
    return RunConfig(
        provider=ProviderIdentity(str(model["provider_id"]), str(model["model_tag"]), str(model["digest"])),
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=DIRECT_PROMPT_V2.version,
        input_manifest_sha256=str(input_manifest["manifest_sha256"]),
        code_revision=str(config["code_revision"]),
        decoding_parameters=tuple(sorted(config["decoding"].items())),
        retry_policy=RetryPolicy(
            max_attempts=int(retry["max_attempts"]),
            retryable_error_codes=tuple(retry["retryable_error_codes"]),
            version=str(retry["version"]),
        ),
        random_seed=17,
        response_contract_version=str(config["response_contract"]["version"]),
    )


def _check_result(
    record: Mapping[str, object], *, item_id: str, item_hash: str,
    config_hash: str, runner_config_hash: str, run_execution_id: str,
) -> None:
    execution_id = hashlib.sha256(f"{run_execution_id}\0{item_id}".encode()).hexdigest()
    if (
        record.get("record_version") != EXPLORATORY_ITEM_RESULT_VERSION
        or record.get("stage") != EXPLORATORY_STAGE
        or record.get("item_id") != item_id
        or record.get("item_input_sha256") != item_hash
        or record.get("configuration_hash") != config_hash
        or record.get("runner_configuration_hash") != runner_config_hash
        or record.get("run_execution_id") != run_execution_id
        or record.get("execution_id") != execution_id
        or not isinstance(record.get("run_result"), dict)
    ):
        raise ExploratoryPilotResumeError("retained item result is not bound to the exact input and run")
    nested = record["run_result"]
    if (
        nested.get("execution_id") != execution_id
        or nested.get("configuration_hash") != runner_config_hash
        or nested.get("run_id") != f"run-{runner_config_hash}"
        or nested.get("item_id") != item_id
    ):
        raise ExploratoryPilotResumeError("nested inference result has incompatible run bindings")


def run_exploratory_pilot(
    items: Sequence[Mapping[str, object]],
    input_manifest: Mapping[str, object],
    review_export: Mapping[str, object],
    review_export_sha256: str,
    config: Mapping[str, object],
    provider,
    run_directory: str | Path,
    *,
    runner_code_revision: str,
    max_items: int | None = None,
) -> dict[str, object]:
    """Execute one hash-bound direct-judging pilot without formal QC acceptance."""
    config = validate_qualification_config(config)
    verify_input_manifest(items, input_manifest)
    validate_exploratory_review_export(review_export, items, input_manifest)
    if (
        not isinstance(review_export_sha256, str)
        or len(review_export_sha256) != 64
        or any(char not in "0123456789abcdef" for char in review_export_sha256)
    ):
        raise ContractError("a lowercase SHA-256 of the submitted reviewer export is required")
    if max_items is not None and (type(max_items) is not int or max_items < 1):
        raise ContractError("max_items must be a positive integer when supplied")
    if not isinstance(runner_code_revision, str) or not runner_code_revision.strip():
        raise ContractError("exploratory runner code revision must be recorded")

    model = config["model"]
    expected_identity = ProviderIdentity(str(model["provider_id"]), str(model["model_tag"]), str(model["digest"]))
    if getattr(provider, "identity", None) != expected_identity:
        raise ContractError("local provider identity/digest does not match the fixed candidate configuration")

    parsed_items = [JudgeFacingInput.from_mapping(row) for row in items]
    expected_hashes = input_manifest["item_hashes"]
    if len(parsed_items) != 48 or {item.item_id for item in parsed_items} != set(expected_hashes):
        raise ContractError("exploratory pilot must use the exact hash-bound 48-item screen")
    item_map = {row["item_id"]: row for row in items}

    base = Path(run_directory)
    items_dir = base / "items"
    manifest_path = base / "run-manifest.json"
    lock_path = base / ".run.lock"
    base.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ExploratoryPilotResumeError("another process owns this exploratory run") from exc
    try:
        os.write(lock_fd, f"pid={os.getpid()}\n".encode())
        os.close(lock_fd)
        if manifest_path.exists():
            manifest = _read_json(manifest_path)
            if (
                manifest.get("manifest_version") != EXPLORATORY_RUN_MANIFEST_VERSION
                or manifest.get("stage") != EXPLORATORY_STAGE
                or manifest.get("configuration_hash") != config["configuration_hash"]
                or manifest.get("input_manifest_sha256") != input_manifest["manifest_sha256"]
                or manifest.get("review_export_sha256") != review_export_sha256
                or manifest.get("runner_code_revision") != runner_code_revision
                or manifest.get("item_hashes") != expected_hashes
                or manifest.get("formal_qc_accepted") is not False
            ):
                raise ExploratoryPilotResumeError("existing exploratory run has different input or provenance")
            run_execution_id = manifest.get("run_execution_id")
            if not isinstance(run_execution_id, str) or not run_execution_id:
                raise ExploratoryPilotResumeError("existing exploratory run lacks an execution identifier")
        else:
            run_execution_id = uuid4().hex
            manifest = {
                "manifest_version": EXPLORATORY_RUN_MANIFEST_VERSION,
                "stage": EXPLORATORY_STAGE,
                "formal_qc_accepted": False,
                "formal_qualification_claim": False,
                "configuration_hash": config["configuration_hash"],
                "runner_configuration_hash": None,
                "qualification_configuration_code_revision": config["code_revision"],
                "runner_code_revision": runner_code_revision,
                "model": dict(model),
                "input_manifest_sha256": input_manifest["manifest_sha256"],
                "source_file_sha256": input_manifest["source_file_sha256"],
                "review_export_sha256": review_export_sha256,
                "review_complete": False,
                "review_labels_revealed": False,
                "reference_labels_in_inference": False,
                "translation_enabled": False,
                "item_hashes": dict(expected_hashes),
                "run_execution_id": run_execution_id,
                "sessions": [],
                "status": "prepared",
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
            _atomic_json(manifest_path, manifest)

        run_config = _run_config(config, input_manifest)
        runner_config_hash = run_config.config_hash
        if manifest.get("runner_configuration_hash") not in {None, runner_config_hash}:
            raise ExploratoryPilotResumeError("existing run has a different effective provider configuration")
        manifest["runner_configuration_hash"] = runner_config_hash
        _atomic_json(manifest_path, manifest)
        baseline = DirectMultilingualBaseline(DIRECT_PROMPT_V2)
        pending = []
        skipped = 0
        for item in parsed_items:
            item_id = item.item_id
            prefix = hashlib.sha256(item_id.encode()).hexdigest()
            result_path = items_dir / f"{prefix}.result.json"
            state_path = items_dir / f"{prefix}.state.json"
            item_hash = expected_hashes[item_id]
            if result_path.exists():
                record = _read_json(result_path)
                _check_result(
                    record,
                    item_id=item_id,
                    item_hash=item_hash,
                    config_hash=str(config["configuration_hash"]),
                    runner_config_hash=runner_config_hash,
                    run_execution_id=run_execution_id,
                )
                if state_path.exists():
                    state = _read_json(state_path)
                    if state.get("status") not in {"in_progress", "completed"}:
                        raise ExploratoryPilotResumeError("item result has an incompatible state record")
                _atomic_json(state_path, {
                    "state_version": EXPLORATORY_ITEM_STATE_VERSION,
                    "item_id": item_id,
                    "item_input_sha256": item_hash,
                    "status": "completed",
                    "execution_id": record["execution_id"],
                    "completed_at": record.get("completed_at"),
                })
                skipped += 1
                continue
            if state_path.exists():
                state = _read_json(state_path)
                if state.get("status") == "in_progress":
                    raise ExploratoryPilotResumeError(f"ambiguous interrupted item {item_id}; reconcile before resume")
                if state.get("status") == "completed":
                    raise ExploratoryPilotResumeError("completed item state lacks its retained raw result")
            pending.append((item, item_id, item_hash, state_path, result_path))

        if manifest.get("status") == "complete" and not pending:
            return {
                "stage": EXPLORATORY_STAGE,
                "run_execution_id": run_execution_id,
                "configuration_hash": config["configuration_hash"],
                "review_export_sha256": review_export_sha256,
                "run_status": "complete",
                "completed_items": 48,
                "skipped_completed_items": skipped,
                "new_item_executions": 0,
            }

        selected = pending if max_items is None else pending[:max_items]
        session = {"session_id": uuid4().hex, "started_at": _utc_now(), "status": "running"}
        manifest["sessions"].append(session)
        manifest["status"] = "running"
        manifest["updated_at"] = _utc_now()
        _atomic_json(manifest_path, manifest)
        started = time.monotonic()
        completed = skipped
        try:
            for raw_item, item_id, item_hash, state_path, result_path in selected:
                execution_id = hashlib.sha256(f"{run_execution_id}\0{item_id}".encode()).hexdigest()
                started_at = _utc_now()
                _atomic_json(state_path, {
                    "state_version": EXPLORATORY_ITEM_STATE_VERSION,
                    "item_id": item_id,
                    "item_input_sha256": item_hash,
                    "execution_id": execution_id,
                    "status": "in_progress",
                    "started_at": started_at,
                })
                plan = baseline.prepare(JudgeFacingInput.from_mapping(item_map[item_id]), run_config)
                plan = replace(plan, execution_id=execution_id)
                result = JudgeExecutor(run_config, provider).run(plan)
                completed_at = _utc_now()
                record = {
                    "record_version": EXPLORATORY_ITEM_RESULT_VERSION,
                    "stage": EXPLORATORY_STAGE,
                    "configuration_hash": config["configuration_hash"],
                    "runner_configuration_hash": runner_config_hash,
                    "run_execution_id": run_execution_id,
                    "execution_id": execution_id,
                    "item_id": item_id,
                    "item_input_sha256": item_hash,
                    "review_export_sha256": review_export_sha256,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "run_result": result.to_record(),
                }
                _atomic_json(result_path, record)
                _atomic_json(state_path, {
                    "state_version": EXPLORATORY_ITEM_STATE_VERSION,
                    "item_id": item_id,
                    "item_input_sha256": item_hash,
                    "execution_id": execution_id,
                    "status": "completed",
                    "started_at": started_at,
                    "completed_at": completed_at,
                })
                completed += 1
        except BaseException:
            session["status"] = "interrupted"
            session["completed_at"] = _utc_now()
            session["elapsed_seconds"] = round(time.monotonic() - started, 6)
            manifest["status"] = "partial"
            manifest["updated_at"] = _utc_now()
            _atomic_json(manifest_path, manifest)
            raise
        elapsed = round(time.monotonic() - started, 6)
        remaining = len(pending) - len(selected)
        session["status"] = "complete" if remaining == 0 else "partial"
        session["completed_at"] = _utc_now()
        session["elapsed_seconds"] = elapsed
        manifest["status"] = "complete" if remaining == 0 else "partial"
        manifest["completed_at"] = _utc_now() if remaining == 0 else None
        manifest["elapsed_seconds"] = round(
            sum(float(row.get("elapsed_seconds", 0.0)) for row in manifest["sessions"]), 6
        )
        manifest["completed_item_count"] = completed
        manifest["new_item_execution_count"] = len(selected)
        manifest["pending_item_count"] = remaining
        manifest["updated_at"] = _utc_now()
        _atomic_json(manifest_path, manifest)
        return {
            "stage": EXPLORATORY_STAGE,
            "run_execution_id": run_execution_id,
            "configuration_hash": config["configuration_hash"],
            "review_export_sha256": review_export_sha256,
            "run_status": manifest["status"],
            "completed_items": completed,
            "skipped_completed_items": skipped,
            "new_item_executions": len(selected),
            "pending_items": remaining,
            "elapsed_seconds": elapsed,
        }
    finally:
        try:
            os.close(lock_fd)
        except OSError:
            pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
