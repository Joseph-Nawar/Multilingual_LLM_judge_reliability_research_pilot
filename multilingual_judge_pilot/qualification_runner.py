"""QC-gated, resumable, one-model-at-a-time competence-screen execution.

The runner module has no reference-key or study-data import path. Scoring is
implemented separately in :mod:`qualification_scoring`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
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
    INPUT_MANIFEST_VERSION,
    QUALIFICATION_CONFIG_VERSION,
    QUALIFICATION_RETRY_POLICY,
    item_sha256,
    sha256_text,
    validate_qualification_config,
    verify_input_manifest,
)


RUN_MANIFEST_VERSION = "p3-qualification-run-manifest-v1"
ITEM_RESULT_VERSION = "p3-qualification-item-result-v1"
ITEM_STATE_VERSION = "p3-qualification-item-state-v1"


class QualificationGateError(ValueError):
    """The independent bilingual review/owner acceptance gate is not satisfied."""


class QualificationResumeError(RuntimeError):
    """An existing run cannot be resumed without risking duplicate inference."""


def verify_qc_acceptance(
    config: Mapping[str, object],
    input_manifest: Mapping[str, object],
    acceptance: Mapping[str, object],
) -> None:
    """Require completed independent review, owner acceptance, and hash bindings."""
    config = validate_qualification_config(config)
    required = {
        "acceptance_version",
        "reviewer_disposition",
        "research_owner_disposition",
        "independent_review_complete",
        "input_manifest_sha256",
        "configuration_hash",
        "review_export_sha256",
    }
    if not isinstance(acceptance, Mapping) or set(acceptance) != required:
        raise QualificationGateError("QC acceptance record has missing or unknown fields")
    if acceptance.get("acceptance_version") != "p3-screen-qc-acceptance-1":
        raise QualificationGateError("unsupported QC acceptance record version")
    if acceptance.get("reviewer_disposition") != "accepted":
        raise QualificationGateError("independent bilingual reviewer has not accepted the screen")
    if acceptance.get("research_owner_disposition") != "accepted":
        raise QualificationGateError("research-owner acceptance is required before qualification")
    if acceptance.get("independent_review_complete") is not True:
        raise QualificationGateError("independent bilingual screen review is incomplete")
    if acceptance.get("input_manifest_sha256") != input_manifest.get("manifest_sha256"):
        raise QualificationGateError("QC acceptance is bound to a different screen input manifest")
    if config["input"].get("manifest_sha256") != input_manifest.get("manifest_sha256"):
        raise QualificationGateError("qualification configuration is bound to a different screen input manifest")
    if acceptance.get("configuration_hash") != config.get("configuration_hash"):
        raise QualificationGateError("QC acceptance is bound to a different qualification configuration")
    export_hash = acceptance.get("review_export_sha256")
    if not isinstance(export_hash, str) or len(export_hash) != 64 or any(ch not in "0123456789abcdef" for ch in export_hash):
        raise QualificationGateError("QC acceptance must bind the retained reviewer export SHA-256")


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
        raise QualificationResumeError(f"cannot read existing run record: {path.name}") from exc
    if not isinstance(value, dict):
        raise QualificationResumeError(f"existing run record is not an object: {path.name}")
    return value


def _item_filename(item_id: str) -> str:
    return hashlib.sha256(item_id.encode("utf-8")).hexdigest()


def _run_config(config: Mapping[str, object], input_manifest: Mapping[str, object]) -> RunConfig:
    model = config["model"]
    identity = ProviderIdentity(
        str(model["provider_id"]),
        str(model["model_tag"]),
        str(model["digest"]),
    )
    retry = config["retry_policy"]
    return RunConfig(
        provider=identity,
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


def _validate_result_envelope(
    envelope: Mapping[str, object],
    *,
    item_id: str,
    item_hash: str,
    configuration_hash: str,
    runner_configuration_hash: str,
    run_execution_id: str,
    expected_execution_id: str,
) -> None:
    if (
        envelope.get("record_version") != ITEM_RESULT_VERSION
        or envelope.get("item_id") != item_id
        or envelope.get("item_input_sha256") != item_hash
        or envelope.get("configuration_hash") != configuration_hash
        or envelope.get("runner_configuration_hash") != runner_configuration_hash
        or envelope.get("run_execution_id") != run_execution_id
        or envelope.get("execution_id") != expected_execution_id
        or not isinstance(envelope.get("run_result"), dict)
    ):
        raise QualificationResumeError("existing result is not bound to this item and configuration")
    run_result = envelope["run_result"]
    if (
        run_result.get("execution_id") != expected_execution_id
        or run_result.get("configuration_hash") != runner_configuration_hash
        or run_result.get("run_id") != f"run-{runner_configuration_hash}"
        or run_result.get("item_id") != item_id
    ):
        raise QualificationResumeError("nested result record is not bound to this item and configuration")


def run_qualification(
    items: Sequence[Mapping[str, object]],
    input_manifest: Mapping[str, object],
    config: Mapping[str, object],
    acceptance: Mapping[str, object],
    provider,
    run_directory: str | Path,
    *,
    max_items: int | None = None,
) -> dict[str, object]:
    """Execute or resume a single frozen direct-judging configuration.

    A result file is written before its state is marked complete. A leftover
    ``in_progress`` marker with no result is treated as ambiguous and blocks
    replay; it is never silently sent again.
    """
    config = validate_qualification_config(config)
    verify_input_manifest(items, input_manifest)
    verify_qc_acceptance(config, input_manifest, acceptance)
    if max_items is not None and (type(max_items) is not int or max_items < 1):
        raise ContractError("max_items must be a positive integer when supplied")

    model = config["model"]
    expected_identity = ProviderIdentity(str(model["provider_id"]), str(model["model_tag"]), str(model["digest"]))
    if getattr(provider, "identity", None) != expected_identity:
        raise ContractError("local judge provider identity/digest does not match frozen qualification configuration")

    parsed_items = [JudgeFacingInput.from_mapping(row) for row in items]
    if len({item.item_id for item in parsed_items}) != len(parsed_items):
        raise ContractError("qualification input item IDs must be unique")
    expected_hashes = input_manifest["item_hashes"]
    if set(item.item_id for item in parsed_items) != set(expected_hashes):
        raise ContractError("qualification item IDs do not match the input manifest")

    base = Path(run_directory)
    items_dir = base / "items"
    manifest_path = base / "run-manifest.json"
    lock_path = base / ".run.lock"
    base.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise QualificationResumeError("another qualification process owns the run lock") from exc
    try:
        os.write(lock_fd, f"pid={os.getpid()}\n".encode())
        os.close(lock_fd)
        if manifest_path.exists():
            run_manifest = _read_json(manifest_path)
            if (
                run_manifest.get("manifest_version") != RUN_MANIFEST_VERSION
                or run_manifest.get("configuration_hash") != config["configuration_hash"]
                or run_manifest.get("input_manifest_sha256") != input_manifest["manifest_sha256"]
                or run_manifest.get("item_hashes") != expected_hashes
            ):
                raise QualificationResumeError("existing run manifest differs from the frozen qualification inputs")
            run_execution_id = run_manifest.get("run_execution_id")
            if not isinstance(run_execution_id, str) or not run_execution_id:
                raise QualificationResumeError("existing run manifest lacks its execution identifier")
        else:
            run_execution_id = uuid4().hex
            run_manifest = {
                "manifest_version": RUN_MANIFEST_VERSION,
                "run_id": f"run-{config['configuration_hash']}",
                "configuration_hash": config["configuration_hash"],
                "input_manifest_sha256": input_manifest["manifest_sha256"],
                "model": dict(model),
                "run_execution_id": run_execution_id,
                "item_hashes": dict(expected_hashes),
                "status": "prepared",
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
            _atomic_json(manifest_path, run_manifest)

        items_dir.mkdir(parents=True, exist_ok=True)
        run_config = _run_config(config, input_manifest)
        runner_configuration_hash = run_config.config_hash
        if run_manifest.get("runner_configuration_hash", runner_configuration_hash) != runner_configuration_hash:
            raise QualificationResumeError("existing run manifest has a different provider run configuration")
        run_manifest["runner_configuration_hash"] = runner_configuration_hash
        _atomic_json(manifest_path, run_manifest)
        baseline = DirectMultilingualBaseline(DIRECT_PROMPT_V2)
        completed = 0
        skipped = 0
        new_attempts = 0
        pending = []
        for item in parsed_items:
            item_id = item.item_id
            file_prefix = _item_filename(item_id)
            result_path = items_dir / f"{file_prefix}.result.json"
            state_path = items_dir / f"{file_prefix}.state.json"
            expected_item_hash = expected_hashes[item_id]
            item_execution_id = hashlib.sha256(
                f"{run_execution_id}\0{item_id}".encode("utf-8")
            ).hexdigest()
            if result_path.exists():
                envelope = _read_json(result_path)
                _validate_result_envelope(
                    envelope,
                    item_id=item_id,
                    item_hash=expected_item_hash,
                    configuration_hash=str(config["configuration_hash"]),
                    runner_configuration_hash=runner_configuration_hash,
                    run_execution_id=run_execution_id,
                    expected_execution_id=item_execution_id,
                )
                if state_path.exists():
                    state = _read_json(state_path)
                    if state.get("status") not in {"in_progress", "completed"}:
                        raise QualificationResumeError("existing result has an incompatible item state")
                _atomic_json(
                    state_path,
                    {
                        "state_version": ITEM_STATE_VERSION,
                        "item_id": item_id,
                        "item_input_sha256": expected_item_hash,
                        "execution_id": item_execution_id,
                        "status": "completed",
                        "completed_at": envelope.get("completed_at"),
                    },
                )
                completed += 1
                skipped += 1
                continue
            if state_path.exists():
                state = _read_json(state_path)
                if state.get("status") == "in_progress":
                    raise QualificationResumeError(
                        f"ambiguous started attempt for item {item_id}; reconcile manually before resuming"
                    )
                if state.get("status") == "completed":
                    raise QualificationResumeError("completed item state has no retained result record")
            pending.append((item, item_id, item_execution_id, expected_item_hash, state_path, result_path))

        run_manifest["status"] = "running" if pending else "complete"
        run_manifest["updated_at"] = _utc_now()
        _atomic_json(manifest_path, run_manifest)

        selected = pending if max_items is None else pending[:max_items]
        new_attempts = len(selected)
        for item, item_id, item_execution_id, expected_item_hash, state_path, result_path in selected:
            started_at = _utc_now()
            _atomic_json(
                state_path,
                {
                    "state_version": ITEM_STATE_VERSION,
                    "item_id": item_id,
                    "item_input_sha256": expected_item_hash,
                    "execution_id": item_execution_id,
                    "status": "in_progress",
                    "started_at": started_at,
                },
            )
            plan = baseline.prepare(item, run_config)
            plan = replace(plan, execution_id=item_execution_id)
            result = JudgeExecutor(run_config, provider).run(plan)
            completed_at = _utc_now()
            envelope = {
                "record_version": ITEM_RESULT_VERSION,
                "configuration_hash": config["configuration_hash"],
                "runner_configuration_hash": runner_configuration_hash,
                "run_execution_id": run_execution_id,
                "execution_id": item_execution_id,
                "item_id": item_id,
                "item_input_sha256": expected_item_hash,
                "started_at": started_at,
                "completed_at": completed_at,
                "run_result": result.to_record(),
            }
            _atomic_json(result_path, envelope)
            _atomic_json(
                state_path,
                {
                    "state_version": ITEM_STATE_VERSION,
                    "item_id": item_id,
                    "item_input_sha256": expected_item_hash,
                    "execution_id": item_execution_id,
                    "status": "completed",
                    "started_at": started_at,
                    "completed_at": completed_at,
                },
            )
            completed += 1

        remaining = len(pending) - len(selected)
        run_manifest["status"] = "complete" if remaining == 0 else "partial"
        run_manifest["updated_at"] = _utc_now()
        run_manifest["completed_item_count"] = completed
        run_manifest["pending_item_count"] = remaining
        run_manifest["attempted_item_count"] = completed - skipped
        _atomic_json(manifest_path, run_manifest)
        return {
            "run_id": run_manifest["run_id"],
            "run_execution_id": run_execution_id,
            "configuration_hash": config["configuration_hash"],
            "run_status": run_manifest["status"],
            "completed_items": completed,
            "skipped_completed_items": skipped,
            "new_item_executions": new_attempts,
            "pending_items": remaining,
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
