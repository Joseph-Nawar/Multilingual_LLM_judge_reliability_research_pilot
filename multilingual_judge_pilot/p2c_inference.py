"""Reference-free, resumable execution over hash-verified frozen inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping
from uuid import uuid4

from .judge_baselines import (
    BaselinePlan,
    DirectMultilingualBaseline,
    SingleVerdictAggregator,
    StructuredSingleCallBaseline,
    TranslationFirstBaseline,
)
from .judge_inference import (
    BaselineKind,
    ContractError,
    JudgeExecutor,
    JudgeFacingInput,
    ParseResult,
    ParseStatus,
    ProviderIdentity,
    RunConfig,
    canonical_json,
)
from .p2c_study_config import build_run_configs, build_study_configs
from .qualification import sha256_text
from .translation_artifacts import TranslationArtifact


FROZEN_RUN_MANIFEST_VERSION = "p2c-frozen-run-manifest-1"
FROZEN_ITEM_RESULT_VERSION = "p2c-frozen-item-result-1"
FROZEN_ITEM_STATE_VERSION = "p2c-frozen-item-state-1"
FROZEN_OUTPUT_MANIFEST_VERSION = "p2c-frozen-run-output-manifest-1"
TRANSLATION_STAGE_VERSION = "p2c-translation-stage-1"
TRANSLATION_OUTPUT_MANIFEST_VERSION = "p2c-translation-output-manifest-1"


class FrozenExecutionError(RuntimeError):
    """A frozen-input, configuration, or safe-resume precondition failed."""


def _unique_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise FrozenExecutionError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError, FrozenExecutionError) as exc:
        raise FrozenExecutionError(f"frozen execution record is missing or malformed: {path.name}") from exc
    if not isinstance(value, dict):
        raise FrozenExecutionError(f"frozen execution record must be an object: {path.name}")
    return value


def _atomic_write(path: Path, raw: bytes, mode: int = 0o600) -> None:
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


def _write_json(path: Path, value: object, *, mode: int = 0o600) -> str:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    _atomic_write(path, raw, mode=mode)
    return hashlib.sha256(raw).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    try:
        raw = path.read_bytes()
        lines = raw.decode("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise FrozenExecutionError(f"frozen input JSONL is missing or not UTF-8: {path.name}") from exc
    result = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise FrozenExecutionError(f"frozen input JSONL has a blank line at {line_number}")
        try:
            value = json.loads(line, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, FrozenExecutionError) as exc:
            raise FrozenExecutionError(f"frozen input JSONL is invalid at line {line_number}") from exc
        if not isinstance(value, dict):
            raise FrozenExecutionError(f"frozen input JSONL row {line_number} must be an object")
        result.append(value)
    return result


def _check_hash(path: Path, expected: object, description: str) -> bytes:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if not isinstance(expected, str) or actual != expected:
        raise FrozenExecutionError(f"{description} hash does not match the freeze manifest")
    return raw


def load_frozen_inputs(freeze_root: str | Path, *, partition: str = "locked") -> tuple[list[dict[str, object]], dict[str, object], dict[str, object]]:
    """Load only a frozen judge-facing partition; this module never reads reference files."""
    if partition not in {"locked", "development"}:
        raise FrozenExecutionError("partition must be locked or development")
    root = Path(freeze_root)
    manifest_path = root / "freeze-manifest.json"
    manifest = _read_json(manifest_path)
    try:
        sidecar = (root / "freeze-manifest.sha256").read_text(encoding="ascii").strip().split()[0]
    except (OSError, IndexError, UnicodeDecodeError) as exc:
        raise FrozenExecutionError("freeze manifest checksum sidecar is unavailable") from exc
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if sidecar != manifest_sha or manifest.get("status") != "frozen" or manifest.get("manifest_version") != "p2c-full-study-freeze-1":
        raise FrozenExecutionError("input package is not a valid immutable freeze")
    prefix = f"{partition}/"
    file_hashes = manifest.get("files")
    if not isinstance(file_hashes, dict):
        raise FrozenExecutionError("freeze manifest file hash table is malformed")
    input_path = root / prefix / "inference-items.jsonl"
    input_manifest_path = root / prefix / "input-manifest.json"
    configs_path = root / "execution" / "run-configs.json"
    _check_hash(input_path, file_hashes.get(f"{partition}/inference-items.jsonl"), "inference items")
    _check_hash(input_manifest_path, file_hashes.get(f"{partition}/input-manifest.json"), "input manifest")
    config_bytes = _check_hash(configs_path, file_hashes.get("execution/run-configs.json"), "run configurations")
    try:
        input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        config_bundle = json.loads(config_bytes, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, FrozenExecutionError) as exc:
        raise FrozenExecutionError("frozen input manifest or run configuration is invalid") from exc
    if not isinstance(input_manifest, dict) or not isinstance(config_bundle, dict):
        raise FrozenExecutionError("frozen input manifest or run configuration must be an object")
    manifest_body = {key: value for key, value in input_manifest.items() if key != "manifest_sha256"}
    if sha256_text(canonical_json(manifest_body)) != input_manifest.get("manifest_sha256"):
        raise FrozenExecutionError("partition input manifest self-hash is invalid")
    config_key = "configurations" if partition == "locked" else "development_configurations"
    checksum_key = "configurations_sha256" if partition == "locked" else "development_configurations_sha256"
    configurations = config_bundle.get(config_key)
    if not isinstance(configurations, dict) or sha256_text(canonical_json(configurations)) != config_bundle.get(checksum_key):
        raise FrozenExecutionError("frozen run configuration checksum is invalid")
    expected_configs = build_study_configs(input_manifest, str(manifest.get("code_revision", "")))
    if configurations != expected_configs:
        raise FrozenExecutionError("frozen run configurations differ from the accepted methods and model digests")
    rows = _read_jsonl(input_path)
    hashes = input_manifest.get("item_hashes")
    ordered_ids = input_manifest.get("ordered_item_ids")
    if not isinstance(hashes, dict) or not isinstance(ordered_ids, list) or len(rows) != len(ordered_ids):
        raise FrozenExecutionError("frozen item inventory does not match its manifest")
    seen = set()
    for row in rows:
        item = JudgeFacingInput.from_mapping(row)
        item_id = item.item_id
        if item_id in seen or item_id not in hashes:
            raise FrozenExecutionError("frozen inputs contain duplicate or unmanifested item IDs")
        if sha256_text(canonical_json(row)) != hashes[item_id]:
            raise FrozenExecutionError("frozen item hash is invalid")
        seen.add(item_id)
    if seen != set(hashes) or [row["item_id"] for row in rows] != ordered_ids:
        raise FrozenExecutionError("frozen input order or item set differs from its manifest")
    return rows, input_manifest, manifest


def _runtime_config(freeze_root: Path, baseline_name: str, input_manifest: Mapping[str, object], freeze_manifest: Mapping[str, object]) -> tuple[RunConfig, object]:
    configs = build_run_configs(input_manifest, str(freeze_manifest["code_revision"]))
    if baseline_name not in configs:
        raise FrozenExecutionError("unknown frozen study baseline")
    config_bundle = _read_json(freeze_root / "execution" / "run-configs.json")
    key = "configurations" if input_manifest.get("manifest_version") == "p2c-locked-input-manifest-1" else "development_configurations"
    stored = config_bundle.get(key)
    expected = build_study_configs(input_manifest, str(freeze_manifest["code_revision"]))
    if stored != expected:
        raise FrozenExecutionError("runtime configuration does not match the immutable freeze record")
    return configs[baseline_name]


def _item_filename(item_id: str) -> str:
    return hashlib.sha256(item_id.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_one_local_model(provider) -> None:
    client = getattr(provider, "client", None)
    if client is None or not hasattr(client, "list_running_models") or not hasattr(client, "unload_model"):
        return
    desired = provider.identity.model_id
    for model_tag in client.list_running_models():
        if model_tag != desired:
            client.unload_model(model_tag)
    remaining = client.list_running_models()
    if any(model_tag != desired for model_tag in remaining):
        raise FrozenExecutionError("could not ensure only the configured local model is loaded")


def _translation_path(root: Path, item_id: str) -> Path:
    return root / "translation-artifacts" / f"{_item_filename(item_id)}.json"


def _seal_translation_record(record: Mapping[str, object]) -> dict[str, object]:
    sealed = dict(record)
    sealed["record_sha256"] = sha256_text(canonical_json(sealed))
    return sealed


def _verify_translation_record(record: Mapping[str, object]) -> None:
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    if sha256_text(canonical_json(body)) != record.get("record_sha256"):
        raise FrozenExecutionError("translation record self-hash is invalid")


def prepare_translations(
    freeze_root: str | Path,
    translator,
    *,
    output_root: str | Path | None = None,
    partition: str = "locked",
) -> dict[str, int]:
    """Translate each frozen item once, persist every attempt, and hash-bind reusable artifacts."""
    if partition != "locked":
        raise FrozenExecutionError("the full-study translation stage accepts only frozen locked inputs")
    root = Path(freeze_root)
    rows, input_manifest, freeze_manifest = load_frozen_inputs(root, partition=partition)
    config, _prompt = _runtime_config(root, "translation_first", input_manifest, freeze_manifest)
    if config.translation is None or translator.identity != config.translation.translator:
        raise FrozenExecutionError("translator identity/digest differs from the frozen configuration")
    _ensure_one_local_model(translator)
    baseline = TranslationFirstBaseline(_prompt, translator)
    outputs = Path(output_root) if output_root is not None else root / "runs" / "translation-first"
    outputs.mkdir(parents=True, exist_ok=True, mode=0o700)
    prior_manifest_path = outputs / "translation-manifest.json"
    prior_hashes: dict[str, str] = {}
    if prior_manifest_path.exists():
        prior = _read_json(prior_manifest_path)
        prior_body = {key: value for key, value in prior.items() if key != "manifest_sha256"}
        if (
            sha256_text(canonical_json(prior_body)) != prior.get("manifest_sha256")
            or prior.get("input_manifest_sha256") != input_manifest["manifest_sha256"]
            or prior.get("translation_config_hash") != config.translation.config_hash
        ):
            raise FrozenExecutionError("existing translation manifest differs from this frozen translation run")
        if not isinstance(prior.get("record_sha256"), dict):
            raise FrozenExecutionError("existing translation manifest has no record hash map")
        prior_hashes = prior["record_sha256"]
        for item_id, digest in prior_hashes.items():
            candidate = _translation_path(outputs, item_id)
            try:
                actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
            except OSError as exc:
                raise FrozenExecutionError("existing translation manifest references a missing artifact") from exc
            if actual != digest:
                raise FrozenExecutionError("existing translation artifact changed after manifest creation")
    completed = failures = skipped = 0
    for raw in rows:
        item = JudgeFacingInput.from_mapping(raw)
        path = _translation_path(outputs, item.item_id)
        item_hash = input_manifest["item_hashes"][item.item_id]
        if path.exists():
            existing = _read_json(path)
            _verify_translation_record(existing)
            if existing.get("item_id") != item.item_id or existing.get("item_sha256") != item_hash or existing.get("translation_config_hash") != config.translation.config_hash:
                raise FrozenExecutionError("existing translation record is bound to different input or configuration")
            if item.item_id in prior_hashes and hashlib.sha256(path.read_bytes()).hexdigest() != prior_hashes[item.item_id]:
                raise FrozenExecutionError("existing translation record hash differs from its previous manifest")
            if existing.get("status") == "success":
                artifact = TranslationArtifact.from_json(json.dumps(existing["artifact"], ensure_ascii=False, sort_keys=True))
                artifact.validate_for(item, config)
            elif existing.get("status") != "failure":
                raise FrozenExecutionError("existing translation record has an unknown status")
            skipped += 1
            continue
        plan = baseline.prepare(item, config)
        if plan.preprocessing_result is not None:
            record = _seal_translation_record({
                "record_version": TRANSLATION_STAGE_VERSION,
                "item_id": item.item_id,
                "item_sha256": item_hash,
                "translation_config_hash": config.translation.config_hash,
                "status": "failure",
                "failure_status": plan.preprocessing_result.status.value,
                "translation_attempts": [attempt.to_record() for attempt in plan.translation_attempts],
            })
            _write_json(path, record, mode=0o444)
            failures += 1
            continue
        artifact = TranslationArtifact.from_plan(item, config, plan)
        _write_json(path, _seal_translation_record({
            "record_version": TRANSLATION_STAGE_VERSION,
            "item_id": item.item_id,
            "item_sha256": item_hash,
            "translation_config_hash": config.translation.config_hash,
            "status": "success",
            "artifact": artifact.to_record(),
        }), mode=0o444)
        completed += 1
    record_hashes = {}
    item_hashes = {}
    for raw in rows:
        item_id = str(raw["item_id"])
        path = _translation_path(outputs, item_id)
        if path.is_file():
            record_hashes[item_id] = hashlib.sha256(path.read_bytes()).hexdigest()
            item_hashes[item_id] = input_manifest["item_hashes"][item_id]
    output_manifest = {
        "manifest_version": TRANSLATION_OUTPUT_MANIFEST_VERSION,
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "translation_config_hash": config.translation.config_hash,
        "item_hashes": item_hashes,
        "record_sha256": record_hashes,
        "status": "complete" if len(record_hashes) == len(rows) else "partial",
        "generated_at": _utc_now(),
    }
    output_manifest["manifest_sha256"] = sha256_text(canonical_json(output_manifest))
    _write_json(outputs / "translation-manifest.json", output_manifest)
    return {"translated": completed, "failed": failures, "reused": skipped, "total": len(rows)}


def _load_translation(root: Path, item: JudgeFacingInput, item_hash: str, config: RunConfig) -> tuple[TranslationArtifact | None, dict[str, object] | None]:
    path = _translation_path(root / "runs" / "translation-first", item.item_id)
    if not path.is_file():
        raise FrozenExecutionError("translation-first run requires a complete pretranslation stage")
    manifest = _read_json(root / "runs" / "translation-first" / "translation-manifest.json")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if (
        sha256_text(canonical_json(body)) != manifest.get("manifest_sha256")
        or manifest.get("input_manifest_sha256") != config.input_manifest_sha256
        or manifest.get("translation_config_hash") != config.translation.config_hash
        or manifest.get("status") != "complete"
        or manifest.get("item_hashes", {}).get(item.item_id) != item_hash
        or manifest.get("record_sha256", {}).get(item.item_id) != hashlib.sha256(path.read_bytes()).hexdigest()
    ):
        raise FrozenExecutionError("translation output manifest or item artifact hash is invalid")
    record = _read_json(path)
    _verify_translation_record(record)
    if record.get("item_id") != item.item_id or record.get("item_sha256") != item_hash or record.get("translation_config_hash") != config.translation.config_hash:
        raise FrozenExecutionError("translation artifact input/configuration hash mismatch")
    if record.get("status") == "failure":
        return None, record
    if record.get("status") != "success" or not isinstance(record.get("artifact"), dict):
        raise FrozenExecutionError("translation stage record has an invalid state")
    artifact = TranslationArtifact.from_json(json.dumps(record["artifact"], ensure_ascii=False, sort_keys=True))
    artifact.validate_for(item, config)
    return artifact, None


def _result_path(run_root: Path, item_id: str) -> Path:
    return run_root / "items" / f"{_item_filename(item_id)}.result.json"


def _write_output_manifest(run_root: Path, run_manifest: Mapping[str, object]) -> None:
    results = {}
    for item_id in sorted(run_manifest["item_hashes"]):
        path = _result_path(run_root, item_id)
        if path.is_file():
            results[item_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    body = {
        "manifest_version": FROZEN_OUTPUT_MANIFEST_VERSION,
        "run_id": run_manifest["run_id"],
        "run_execution_id": run_manifest["run_execution_id"],
        "baseline": run_manifest["baseline"],
        "configuration_hash": run_manifest["configuration_hash"],
        "input_manifest_sha256": run_manifest["input_manifest_sha256"],
        "item_hashes": dict(run_manifest["item_hashes"]),
        "result_sha256": results,
        "status": run_manifest["status"],
        "generated_at": run_manifest.get("updated_at", run_manifest.get("created_at")),
    }
    body["manifest_sha256"] = sha256_text(canonical_json(body))
    _write_json(run_root / "run-output-manifest.json", body)


def _verify_existing_output_manifest(run_root: Path, run_manifest: Mapping[str, object]) -> dict[str, str]:
    path = run_root / "run-output-manifest.json"
    if not path.exists():
        return {}
    manifest = _read_json(path)
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if (
        sha256_text(canonical_json(body)) != manifest.get("manifest_sha256")
        or manifest.get("manifest_version") != FROZEN_OUTPUT_MANIFEST_VERSION
        or manifest.get("run_execution_id") != run_manifest.get("run_execution_id")
        or manifest.get("configuration_hash") != run_manifest.get("configuration_hash")
        or manifest.get("input_manifest_sha256") != run_manifest.get("input_manifest_sha256")
        or manifest.get("item_hashes") != run_manifest.get("item_hashes")
        or manifest.get("status") != run_manifest.get("status")
        or manifest.get("baseline") != run_manifest.get("baseline")
        or manifest.get("run_id") != run_manifest.get("run_id")
    ):
        raise FrozenExecutionError("existing run output manifest is not hash-bound to the frozen run")
    digests = manifest.get("result_sha256")
    if not isinstance(digests, dict) or set(digests) - set(run_manifest["item_hashes"]):
        raise FrozenExecutionError("existing output manifest contains unknown item IDs")
    for item_id, expected in digests.items():
        try:
            actual = hashlib.sha256(_result_path(run_root, item_id).read_bytes()).hexdigest()
        except OSError as exc:
            raise FrozenExecutionError("existing output manifest references a missing result") from exc
        if actual != expected:
            raise FrozenExecutionError("existing result changed after its output manifest was written")
    return {str(item_id): str(digest) for item_id, digest in digests.items()}


def run_frozen_baseline(
    freeze_root: str | Path,
    baseline_name: str,
    provider,
    *,
    translator=None,
    partition: str = "locked",
    max_items: int | None = None,
) -> dict[str, object]:
    """Run/resume one fixed baseline; only this layer sees opaque inputs and raw model responses."""
    if partition != "locked":
        raise FrozenExecutionError("the full-study runner accepts only frozen locked inputs")
    if max_items is not None and (type(max_items) is not int or max_items < 1):
        raise FrozenExecutionError("max_items must be a positive integer")
    root = Path(freeze_root)
    rows, input_manifest, freeze_manifest = load_frozen_inputs(root, partition=partition)
    config, prompt = _runtime_config(root, baseline_name, input_manifest, freeze_manifest)
    if provider.identity != config.provider:
        raise FrozenExecutionError("local judge model identity/digest differs from frozen configuration")
    _ensure_one_local_model(provider)
    if baseline_name == "direct":
        baseline = DirectMultilingualBaseline(prompt)
    elif baseline_name == "structured":
        baseline = StructuredSingleCallBaseline(prompt)
    elif baseline_name == "translation_first":
        if translator is None or config.translation is None or translator.identity != config.translation.translator:
            raise FrozenExecutionError("translation-first baseline requires the configured local translator")
        baseline = TranslationFirstBaseline(prompt, translator)
    else:
        raise FrozenExecutionError("unknown baseline name")

    run_root = root / "runs" / baseline_name
    items_dir = run_root / "items"
    run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = run_root / ".run.lock"
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FrozenExecutionError("another process owns this baseline run") from exc
    try:
        os.close(lock_fd)
        run_manifest_path = run_root / "run-manifest.json"
        item_hashes = dict(input_manifest["item_hashes"])
        if run_manifest_path.exists():
            run_manifest = _read_json(run_manifest_path)
            if (
                run_manifest.get("manifest_version") != FROZEN_RUN_MANIFEST_VERSION
                or run_manifest.get("configuration_hash") != config.config_hash
                or run_manifest.get("input_manifest_sha256") != input_manifest["manifest_sha256"]
                or run_manifest.get("item_hashes") != item_hashes
                or run_manifest.get("baseline") != baseline_name
            ):
                raise FrozenExecutionError("existing run manifest is bound to different frozen inputs/configuration")
        else:
            run_manifest = {
                "manifest_version": FROZEN_RUN_MANIFEST_VERSION,
                "run_id": config.run_id,
                "run_execution_id": uuid4().hex,
                "baseline": baseline_name,
                "configuration_hash": config.config_hash,
                "input_manifest_sha256": input_manifest["manifest_sha256"],
                "model": config.provider.to_record(),
                "item_hashes": item_hashes,
                "status": "prepared",
                "created_at": _utc_now(),
            }
            _write_json(run_manifest_path, run_manifest)
        run_execution_id = run_manifest["run_execution_id"]
        items_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        manifest_result_hashes = _verify_existing_output_manifest(run_root, run_manifest)
        allowed_result_files = {f"{_item_filename(item_id)}.result.json" for item_id in item_hashes}
        if {path.name for path in items_dir.glob("*.result.json")} - allowed_result_files:
            raise FrozenExecutionError("run directory contains an unmanifested result for an unknown item")
        executor = JudgeExecutor(config, provider)
        completed = skipped = translation_failures = new_calls = 0
        selected_rows = rows[:max_items] if max_items is not None else rows
        for raw in selected_rows:
            item = JudgeFacingInput.from_mapping(raw)
            item_hash = item_hashes[item.item_id]
            result_path = _result_path(run_root, item.item_id)
            state_path = result_path.with_suffix(".state.json")
            expected_execution = hashlib.sha256(f"{run_execution_id}\0{item.item_id}".encode("utf-8")).hexdigest()
            if result_path.exists():
                existing = _read_json(result_path)
                if (
                    existing.get("record_version") != FROZEN_ITEM_RESULT_VERSION
                    or existing.get("item_id") != item.item_id
                    or existing.get("item_sha256") != item_hash
                    or existing.get("configuration_hash") != config.config_hash
                    or existing.get("run_execution_id") != run_execution_id
                    or existing.get("execution_id") != expected_execution
                ):
                    raise FrozenExecutionError("existing item result is not bound to this frozen input/run")
                if not isinstance(existing.get("run_result"), dict):
                    raise FrozenExecutionError("existing item result lacks its immutable response record")
                result_digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
                if manifest_result_hashes.get(item.item_id, result_digest) != result_digest:
                    raise FrozenExecutionError("existing result differs from its output manifest")
                if not state_path.exists():
                    raise FrozenExecutionError("existing result has no completed state record; refusing to infer its completion")
                existing_state = _read_json(state_path)
                if (
                    existing_state.get("item_id") != item.item_id
                    or existing_state.get("item_sha256") != item_hash
                    or existing_state.get("execution_id") != expected_execution
                    or existing_state.get("status") != "completed"
                    or existing_state.get("result_sha256") != result_digest
                ):
                    raise FrozenExecutionError("existing item state is inconsistent with its completed result")
                skipped += 1
                continue
            if state_path.exists():
                state = _read_json(state_path)
                if state.get("status") != "pending":
                    raise FrozenExecutionError("item has an ambiguous in-progress state without a result; refusing duplicate inference")
            _write_json(state_path, {"state_version": FROZEN_ITEM_STATE_VERSION, "item_id": item.item_id, "item_sha256": item_hash, "execution_id": expected_execution, "status": "in_progress", "started_at": _utc_now()})
            if baseline_name == "translation_first":
                artifact, failure = _load_translation(root, item, item_hash, config)
                if failure:
                    attempts = tuple(_translation_attempt_from_record(row) for row in failure["translation_attempts"])
                    plan = BaselinePlan(
                        BaselineKind.TRANSLATION_FIRST.value,
                        (),
                        SingleVerdictAggregator(),
                        item_id=item.item_id,
                        execution_id=attempts[-1].execution_id,
                        translation_attempts=attempts,
                        preprocessing_result=ParseResult(ParseStatus.PROVIDER_FAILURE),
                    )
                    translation_failures += 1
                else:
                    plan = baseline.prepare(item, config, translation_artifact=artifact)
            else:
                plan = baseline.prepare(item, config)
            result = executor.run(plan)
            new_calls += sum(len(step.attempts) for step in result.steps)
            envelope = {
                "record_version": FROZEN_ITEM_RESULT_VERSION,
                "item_id": item.item_id,
                "item_sha256": item_hash,
                "configuration_hash": config.config_hash,
                "run_execution_id": run_execution_id,
                "execution_id": expected_execution,
                "baseline": baseline_name,
                "completed_at": _utc_now(),
                "run_result": result.to_record(),
            }
            result_digest = _write_json(result_path, envelope, mode=0o444)
            _write_json(state_path, {"state_version": FROZEN_ITEM_STATE_VERSION, "item_id": item.item_id, "item_sha256": item_hash, "execution_id": expected_execution, "status": "completed", "completed_at": envelope["completed_at"], "result_sha256": result_digest})
            completed += 1
        run_manifest["status"] = "completed" if len(list(items_dir.glob("*.result.json"))) == len(rows) else "partial"
        run_manifest["updated_at"] = _utc_now()
        _write_json(run_manifest_path, run_manifest)
        _write_output_manifest(run_root, run_manifest)
        return {"baseline": baseline_name, "completed": completed, "reused": skipped, "translation_failures": translation_failures, "new_judge_attempts": new_calls, "total_items": len(rows), "run_root": str(run_root)}
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _translation_attempt_from_record(record: Mapping[str, object]):
    from .judge_baselines import TranslationAttemptRecord

    translator = record.get("translator")
    if not isinstance(translator, Mapping):
        raise FrozenExecutionError("translation attempt lacks translator identity")
    keys = {
        "execution_id": record.get("execution_id"),
        "attempt_id": record.get("attempt_id"),
        "configuration_hash": record.get("configuration_hash"),
        "translation_config_hash": record.get("translation_config_hash"),
        "translation_config_version": record.get("translation_config_version"),
        "translation_prompt_version": record.get("translation_prompt_version"),
        "input_id": record.get("input_id"),
        "input_sha256": record.get("input_sha256"),
        "translator_provider": translator.get("provider_id"),
        "translator_model": translator.get("model_id"),
        "translator_version": translator.get("model_version"),
        "attempt_number": record.get("attempt_number"),
        "max_attempts": record.get("max_attempts"),
        "retry_policy_version": record.get("retry_policy_version"),
        "failure_policy": record.get("failure_policy"),
        "started_at_utc": record.get("started_at_utc"),
        "completed_at_utc": record.get("completed_at_utc"),
        "status": record.get("status"),
        "error_category": record.get("error_category"),
        "retry_decision": record.get("retry_decision"),
        "raw_response": record.get("raw_response"),
        "translated_conversation_sha256": record.get("translated_conversation_sha256"),
        "prompt_tokens": record.get("prompt_tokens"),
        "completion_tokens": record.get("completion_tokens"),
        "cost_usd": record.get("cost_usd"),
        "latency_ms": record.get("latency_ms"),
        "provider_call_records": tuple(record.get("provider_call_records", [])),
    }
    try:
        return TranslationAttemptRecord(**keys)
    except (TypeError, ValueError) as exc:
        raise FrozenExecutionError("retained translation attempt is invalid") from exc
