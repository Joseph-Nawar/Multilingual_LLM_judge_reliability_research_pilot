"""Frozen shared-prompt state-access diagnostic contract and input builder."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import random
import re
from pathlib import Path
import tempfile
from typing import Mapping, Protocol, Sequence
from uuid import uuid4

from .judge_inference import BINARY_RESPONSE_CONTRACT, PARSER_VERSION, ProviderCallError, canonical_json, response_schema
from .qualification import QUALIFICATION_MODEL_DIGESTS


MODEL = "gemma4:12b-it-qat"
MODEL_DIGEST = QUALIFICATION_MODEL_DIGESTS[MODEL]
VERSION = "paper2-h2-shared-state-information-v2-20261115"
ORDER_SEED = 20261115
INSTRUCTION = (
    "Judge whether the proposed action is valid using only the conversation, proposed action, "
    "public tool contract, and effective_state in this request. First check public tool-contract "
    "conformance, including tool name, fields, types, and allowed values. Check conversational "
    "authorization separately; user permission cannot change the tool contract. If effective_state "
    "is null, reconstruct the active user requirements and permissions from the conversation: "
    "later revisions replace only what they change, restatements preserve requirements, and "
    "revocations remove the permissions they revoke. If effective_state is an object, use its "
    "active constraints and permissions as the current state while checking the action and public "
    "tool contract. An effective_state object does not state action validity. A valid action must "
    "satisfy the tool contract and all applicable active requirements. Return only one JSON object "
    "matching the supplied binary response schema, with no explanation or extra keys."
)
SCHEMA = response_schema(BINARY_RESPONSE_CONTRACT)
OPTIONS = {"num_ctx": 4096, "num_predict": 96, "seed": 17, "temperature": 0.0}
ALLOWED_STATE_FIELDS = {"active_constraints", "active_permissions"}
ALLOWED_CONSTRAINT_FIELDS = {
    "constraint_type", "field", "scope_entity", "lower_bound", "upper_bound", "currency_code"
}
ALLOWED_PERMISSION_FIELDS = {"permission", "scope_entity"}

LOCKED_STATE_ACCESS_DIRECTORY = "diagnostics/state-access"
LOCKED_STATE_ACCESS_PLAN_VERSION = "paper2-locked-state-access-plan-1"
ANALYSIS_VERSION = "paper2-locked-state-access-analysis-1"
ANALYSIS_DEFINITION: dict[str, object] = {
    "version": ANALYSIS_VERSION,
    "primary_estimand": "macro-average over primary scenarios of mean item correctness difference supplied minus withheld across eight items",
    "auxiliary_estimand": "macro-average over auxiliary scenarios of mean item correctness difference supplied minus withheld across eight items",
    "item_correctness": "valid parsed verdict equals the separate reference verdict; all other outcomes are incorrect in planned denominators",
    "correction": "withheld incorrect and supplied correct",
    "damage": "withheld correct and supplied incorrect",
    "scenario_cluster_bootstrap": {
        "method": "percentile bootstrap resampling scenario IDs with replacement and retaining all items in each selected scenario",
        "replicates": 10000,
        "seed": 17,
        "quantile_rule": "floor((n - 1) * p)",
        "interval": "95%",
    },
    "primary_versus_auxiliary": "exploratory difference between independent macro-averaged scenario effects; resample primary and auxiliary scenarios independently",
    "report_groups": ["language_condition", "transition_family", "dataset_kind"],
    "failure_accounting": "preserve planned denominator and report unattempted, ambiguous, technical, refusal, invalid-output, and parsed outcomes separately",
    "claim_limit": "behavioral response to supplied state does not establish an internal reasoning mechanism",
}

_CANONICAL_STATE_FIELDS = {
    "$type", "active_requirements", "active_grants", "revoked_grants", "superseded_requirements"
}
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class StateAccessError(ValueError):
    """A diagnostic state, bundle, or result violates its frozen contract."""


class LocalClient(Protocol):
    def discover_model(self, model_tag: str): ...

    def chat(self, payload: Mapping[str, object]) -> Mapping[str, object]: ...


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def safe_state(state: object) -> bool:
    if not isinstance(state, dict) or set(state) != ALLOWED_STATE_FIELDS:
        return False
    constraints, permissions = state["active_constraints"], state["active_permissions"]
    if not isinstance(constraints, list) or not isinstance(permissions, list):
        return False
    if any(not isinstance(row, dict) or set(row) != ALLOWED_CONSTRAINT_FIELDS for row in constraints):
        return False
    if any(not isinstance(row, dict) or set(row) != ALLOWED_PERMISSION_FIELDS for row in permissions):
        return False
    return all(
        value is None or isinstance(value, dict) and set(value) == {"value", "inclusive"}
        for row in constraints for value in (row["lower_bound"], row["upper_bound"])
    )


def evidence(row: Mapping[str, object], state: dict[str, object] | None) -> dict[str, object]:
    """Build the same label-free evidence object used by the development diagnostic."""
    conversation = row.get("conversation")
    if not isinstance(conversation, list):
        raise StateAccessError("diagnostic item conversation must be a list")
    try:
        turns = [{key: turn[key] for key in ("turn_index", "speaker", "content")} for turn in conversation]
        request = {
            "item_id": row["item_id"],
            "conversation": turns,
            "action": row["action"],
            "public_tool_schema": row["public_tool_schema"],
            "effective_state": state,
        }
    except (KeyError, TypeError) as exc:
        raise StateAccessError("diagnostic item is missing a required judge-facing field") from exc
    if not isinstance(request["item_id"], str) or not request["item_id"]:
        raise StateAccessError("diagnostic item ID must be a non-empty string")
    return request


def _expect_object(value: object, fields: set[str], type_name: str, description: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields or value.get("$type") != type_name:
        raise StateAccessError(f"{description} has an unsupported canonical state shape")
    return value


def _project_scope(value: object) -> str | None:
    scope = _expect_object(value, {"$type", "entity_id"}, "Scope", "constraint scope")
    entity_id = scope["entity_id"]
    if entity_id is not None and (not isinstance(entity_id, str) or not entity_id.strip()):
        raise StateAccessError("constraint scope entity must be a non-empty string or null")
    return entity_id


def _project_bound(value: object, *, temporal: bool) -> dict[str, object] | None:
    if value is None:
        return None
    bound_type = "TemporalBound" if temporal else "NumericBound"
    bound = _expect_object(value, {"$type", "value", "inclusive"}, bound_type, "constraint bound")
    if type(bound["inclusive"]) is not bool:
        raise StateAccessError("constraint bound inclusivity must be boolean")
    canonical_value = bound["value"]
    value_key = "$datetime" if temporal else "$decimal"
    if not isinstance(canonical_value, Mapping) or set(canonical_value) != {value_key}:
        raise StateAccessError("constraint bound value has an unsupported canonical encoding")
    text = canonical_value[value_key]
    if not isinstance(text, str) or not text:
        raise StateAccessError("constraint bound value must be non-empty text")
    return {"value": text, "inclusive": bound["inclusive"]}


def _project_requirement(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise StateAccessError("active requirement must be an object")
    type_name = value.get("$type")
    if type_name == "NumericConstraint":
        fields = {"$type", "constraint_id", "scope", "field", "minimum", "maximum", "version", "currency_code"}
        temporal = False
        lower_key, upper_key = "minimum", "maximum"
        constraint_type = "numerical"
    elif type_name == "TemporalConstraint":
        fields = {"$type", "constraint_id", "scope", "field", "earliest", "latest", "version"}
        temporal = True
        lower_key, upper_key = "earliest", "latest"
        constraint_type = "temporal"
    else:
        raise StateAccessError("active requirement has an unsupported canonical type")
    row = _expect_object(value, fields, type_name, "active requirement")
    if not isinstance(row["constraint_id"], str) or not row["constraint_id"]:
        raise StateAccessError("active requirement ID must be non-empty")
    if not isinstance(row["field"], str) or not row["field"].strip():
        raise StateAccessError("active requirement field must be non-empty")
    if type(row["version"]) is not int or row["version"] < 1:
        raise StateAccessError("active requirement version must be positive")
    lower = _project_bound(row[lower_key], temporal=temporal)
    upper = _project_bound(row[upper_key], temporal=temporal)
    if lower is None and upper is None:
        raise StateAccessError("active requirement must contain a bound")
    currency = row.get("currency_code") if not temporal else None
    if currency is not None and (not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)):
        raise StateAccessError("numeric constraint currency must be an uppercase three-letter code or null")
    return {
        "constraint_type": constraint_type,
        "field": row["field"],
        "scope_entity": _project_scope(row["scope"]),
        "lower_bound": lower,
        "upper_bound": upper,
        "currency_code": currency,
    }


def _project_grant(value: object) -> dict[str, object]:
    grant = _expect_object(value, {"$type", "grant_id", "key"}, "PermissionGrant", "active permission grant")
    if not isinstance(grant["grant_id"], str) or not grant["grant_id"]:
        raise StateAccessError("active permission grant ID must be non-empty")
    key = _expect_object(grant["key"], {"$type", "permission", "scope"}, "PermissionKey", "permission key")
    permission = key["permission"]
    if not isinstance(permission, str) or not permission.strip():
        raise StateAccessError("active permission name must be non-empty")
    return {"permission": permission, "scope_entity": _project_scope(key["scope"])}


def project_effective_state(state: Mapping[str, object]) -> dict[str, object]:
    """Project the canonical active state into the development diagnostic's allowlisted shape."""
    canonical = _expect_object(state, _CANONICAL_STATE_FIELDS, "EffectiveState", "effective state")
    requirements = canonical["active_requirements"]
    grants = canonical["active_grants"]
    if not isinstance(requirements, list) or not isinstance(grants, list):
        raise StateAccessError("effective state active requirements and grants must be lists")
    if not isinstance(canonical["revoked_grants"], list) or not isinstance(canonical["superseded_requirements"], list):
        raise StateAccessError("effective state history fields must be lists")
    projected = {
        "active_constraints": [_project_requirement(row) for row in requirements],
        "active_permissions": [_project_grant(row) for row in grants],
    }
    if not safe_state(projected):
        raise StateAccessError("effective state projection does not match the shared diagnostic contract")
    return projected


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * probability)]


def cluster_interval(rows: list[dict], field: str, *, seed: int = 17) -> tuple[float, float]:
    clusters: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        clusters[row["scenario_id"]].append(row[field])
    ids = sorted(clusters)
    rng = random.Random(seed)
    values = []
    for _ in range(10000):
        sample = [value for _ in ids for value in clusters[rng.choice(ids)]]
        values.append(sum(sample) / len(sample))
    return round(quantile(values, 0.025), 3), round(quantile(values, 0.975), 3)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_locked_state_access_artifacts(
    items: Sequence[Mapping[str, object]],
    reference_records: Mapping[str, Mapping[str, object]],
    analysis_metadata: Mapping[str, Mapping[str, object]],
    *,
    input_manifest_sha256: str,
    order_seed_hex: str,
) -> dict[str, bytes]:
    """Build a separate, hashed, label-free state-access bundle for locked items."""
    item_by_id = {str(item.get("item_id")): item for item in items}
    item_ids = set(item_by_id)
    if len(item_by_id) != len(items) or not item_ids or "None" in item_ids:
        raise StateAccessError("locked diagnostic items must have unique non-empty IDs")
    if set(reference_records) != item_ids or set(analysis_metadata) != item_ids:
        raise StateAccessError("locked diagnostic item, reference, and analysis inventories must match")
    if not _HASH_RE.fullmatch(input_manifest_sha256):
        raise StateAccessError("locked diagnostic input manifest hash must be lowercase SHA-256")
    if not _HASH_RE.fullmatch(order_seed_hex):
        raise StateAccessError("locked diagnostic order seed must be a 256-bit lowercase hexadecimal string")

    scenarios: dict[str, list[str]] = defaultdict(list)
    scenario_kind: dict[str, str] = {}
    scenario_family: dict[str, str] = {}
    for item_id, item in item_by_id.items():
        metadata = analysis_metadata[item_id]
        scenario_id = metadata.get("scenario_id")
        kind = metadata.get("dataset_kind")
        family = metadata.get("transition_family")
        condition = metadata.get("language_condition")
        if not all(isinstance(value, str) and value for value in (scenario_id, kind, family)):
            raise StateAccessError("locked diagnostic analysis metadata is incomplete")
        if condition not in {"EN-EN", "AR-AR", "EN-AR", "AR-EN"} or item.get("language_condition") != condition:
            raise StateAccessError("locked diagnostic language metadata differs from the frozen item")
        partition = metadata.get("partition")
        if partition is not None and partition not in {"locked_primary", "locked_auxiliary_control"}:
            raise StateAccessError("state-access diagnostic accepts locked items only")
        if kind not in {"primary", "auxiliary_control"}:
            raise StateAccessError("locked diagnostic dataset kind is unsupported")
        if scenario_id in scenario_kind and (scenario_kind[scenario_id] != kind or scenario_family[scenario_id] != family):
            raise StateAccessError("locked diagnostic scenario metadata is inconsistent")
        scenario_kind[scenario_id] = kind
        scenario_family[scenario_id] = family
        scenarios[scenario_id].append(item_id)
        if not isinstance(reference_records[item_id].get("effective_state"), Mapping):
            raise StateAccessError("locked diagnostic reference record lacks canonical effective state")

    if any(len(ids) != 8 for ids in scenarios.values()):
        raise StateAccessError("each locked diagnostic scenario must contain all eight derivatives")
    if any(Counter(analysis_metadata[item_id]["language_condition"] for item_id in ids) != Counter({condition: 2 for condition in ("EN-EN", "AR-AR", "EN-AR", "AR-EN")}) for ids in scenarios.values()):
        raise StateAccessError("each locked diagnostic scenario must contain two items per language condition")
    if len(item_ids) == 384 and Counter(scenario_kind.values()) != Counter({"primary": 36, "auxiliary_control": 12}):
        raise StateAccessError("the full locked diagnostic must contain 36 primary and 12 auxiliary scenarios")

    projected_states = {
        item_id: project_effective_state(reference_records[item_id]["effective_state"])
        for item_id in sorted(item_ids)
    }
    projection_raw = b"".join(
        (canonical_json({"item_id": item_id, "effective_state": projected_states[item_id]}) + "\n").encode("utf-8")
        for item_id in sorted(item_ids)
    )
    artifacts: dict[str, bytes] = {
        f"{LOCKED_STATE_ACCESS_DIRECTORY}/locked-state-projection.jsonl": projection_raw,
    }
    request_hashes: dict[str, str] = {}
    requests: dict[tuple[str, str], dict[str, object]] = {}
    for item_id in sorted(item_ids):
        requests[(item_id, "withheld")] = evidence(item_by_id[item_id], None)
        requests[(item_id, "supplied")] = evidence(item_by_id[item_id], projected_states[item_id])
        withheld = requests[(item_id, "withheld")]
        supplied = requests[(item_id, "supplied")]
        if {key: value for key, value in withheld.items() if key != "effective_state"} != {
            key: value for key, value in supplied.items() if key != "effective_state"
        }:
            raise StateAccessError("paired state-access requests differ outside effective_state")
        item_key = sha256(item_id.encode("utf-8")).hexdigest()
        for arm in ("withheld", "supplied"):
            request = requests[(item_id, arm)]
            request_raw = _json_bytes(request)
            artifacts[f"{LOCKED_STATE_ACCESS_DIRECTORY}/requests/{arm}/{item_key}.json"] = request_raw
            request_hashes[f"{arm}:{item_id}"] = digest(request)

    order = [(item_id, arm) for item_id in sorted(item_ids) for arm in ("withheld", "supplied")]
    random.Random(int(order_seed_hex, 16)).shuffle(order)
    plan_body: dict[str, object] = {
        "plan_version": LOCKED_STATE_ACCESS_PLAN_VERSION,
        "diagnostic_version": VERSION,
        "input_manifest_sha256": input_manifest_sha256,
        "item_count": len(item_ids),
        "scenario_count": len(scenarios),
        "scenario_counts": dict(sorted(Counter(scenario_kind.values()).items())),
        "planned_item_count": len(item_ids),
        "planned_request_count": len(order),
        "prompt_version": VERSION,
        "instruction": INSTRUCTION,
        "instruction_sha256": sha256(INSTRUCTION.encode("utf-8")).hexdigest(),
        "response_contract_version": BINARY_RESPONSE_CONTRACT,
        "response_schema": SCHEMA,
        "response_schema_sha256": digest(SCHEMA),
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "options": OPTIONS,
        "think": False,
        "parser_version": PARSER_VERSION,
        "attempt_policy": "one call per arm/item; no retries",
        "state_projection_sha256": sha256(projection_raw).hexdigest(),
        "request_sha256": dict(sorted(request_hashes.items())),
        "randomization": {
            "version": "python-random-shuffle-with-frozen-seed-v1",
            "seed_hex": order_seed_hex,
            "order": [{"item_id": item_id, "arm": arm} for item_id, arm in order],
        },
        "analysis_definition": ANALYSIS_DEFINITION,
    }
    plan = dict(plan_body)
    plan["plan_sha256"] = digest(plan_body)
    artifacts[f"{LOCKED_STATE_ACCESS_DIRECTORY}/plan.json"] = _json_bytes(plan)
    return artifacts


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateAccessError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, description: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    except (OSError, json.JSONDecodeError, StateAccessError) as exc:
        raise StateAccessError(f"{description} is missing or malformed") from exc
    if not isinstance(value, dict):
        raise StateAccessError(f"{description} must be an object")
    return value


def _write_json(path: Path, value: object, *, replace: bool = True) -> str:
    raw = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if not replace and path.exists():
            raise StateAccessError("attempt record already exists; refusing a duplicate call")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return sha256(raw).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_key(item_id: str, arm: str) -> str:
    return f"{arm}:{item_id}"


def _result_path(run_root: Path, item_id: str, arm: str) -> Path:
    item_key = sha256(item_id.encode("utf-8")).hexdigest()
    return run_root / "results" / arm / f"{item_key}.json"


def _verify_frozen_file(root: Path, files: Mapping[str, object], relative: str) -> bytes:
    expected = files.get(relative)
    if not isinstance(expected, str) or not _HASH_RE.fullmatch(expected):
        raise StateAccessError(f"frozen state-access file is absent from the manifest: {relative}")
    try:
        raw = (root / relative).read_bytes()
    except OSError as exc:
        raise StateAccessError(f"frozen state-access file is missing: {relative}") from exc
    if sha256(raw).hexdigest() != expected:
        raise StateAccessError(f"frozen state-access file hash mismatch: {relative}")
    return raw


def _load_locked_state_access_bundle(freeze_root: str | Path):
    from .p2c_inference import load_frozen_inputs

    root = Path(freeze_root)
    try:
        items, input_manifest, freeze_manifest = load_frozen_inputs(root, partition="locked")
    except (OSError, ValueError) as exc:
        raise StateAccessError("locked study freeze is invalid") from exc
    if (
        freeze_manifest.get("manifest_version") != "p2c-full-study-freeze-2"
        or freeze_manifest.get("state_access_diagnostic_separately_frozen") is not True
    ):
        raise StateAccessError("freeze lacks the separately frozen state-access bundle")
    files = freeze_manifest.get("files")
    if not isinstance(files, Mapping):
        raise StateAccessError("freeze file hash inventory is malformed")
    relative_plan = f"{LOCKED_STATE_ACCESS_DIRECTORY}/plan.json"
    relative_projection = f"{LOCKED_STATE_ACCESS_DIRECTORY}/locked-state-projection.jsonl"
    plan_raw = _verify_frozen_file(root, files, relative_plan)
    projection_raw = _verify_frozen_file(root, files, relative_projection)
    try:
        plan = json.loads(plan_raw, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, StateAccessError) as exc:
        raise StateAccessError("frozen state-access plan is malformed") from exc
    if not isinstance(plan, dict):
        raise StateAccessError("frozen state-access plan must be an object")
    plan_body = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if digest(plan_body) != plan.get("plan_sha256"):
        raise StateAccessError("frozen state-access plan self-hash is invalid")
    if (
        plan.get("plan_version") != LOCKED_STATE_ACCESS_PLAN_VERSION
        or plan.get("diagnostic_version") != VERSION
        or plan.get("prompt_version") != VERSION
        or plan.get("instruction") != INSTRUCTION
        or plan.get("instruction_sha256") != sha256(INSTRUCTION.encode("utf-8")).hexdigest()
        or plan.get("response_contract_version") != BINARY_RESPONSE_CONTRACT
        or plan.get("response_schema") != SCHEMA
        or plan.get("response_schema_sha256") != digest(SCHEMA)
        or plan.get("model") != MODEL
        or plan.get("model_digest") != MODEL_DIGEST
        or plan.get("options") != OPTIONS
        or plan.get("think") is not False
        or plan.get("parser_version") != PARSER_VERSION
        or plan.get("attempt_policy") != "one call per arm/item; no retries"
        or plan.get("analysis_definition") != ANALYSIS_DEFINITION
        or plan.get("input_manifest_sha256") != input_manifest.get("manifest_sha256")
        or plan.get("state_projection_sha256") != sha256(projection_raw).hexdigest()
    ):
        raise StateAccessError("frozen state-access plan differs from the development-tested contract")

    projection_by_id = {}
    try:
        projection_lines = projection_raw.decode("utf-8").splitlines()
        for line in projection_lines:
            if not line.strip():
                raise StateAccessError("frozen state projection contains a blank line")
            row = json.loads(line, object_pairs_hook=_unique_json_object)
            if not isinstance(row, dict) or set(row) != {"item_id", "effective_state"}:
                raise StateAccessError("frozen state projection row has unexpected fields")
            item_id = row["item_id"]
            if not isinstance(item_id, str) or item_id in projection_by_id or not safe_state(row["effective_state"]):
                raise StateAccessError("frozen state projection has duplicate IDs or an invalid state")
            projection_by_id[item_id] = row["effective_state"]
    except (UnicodeDecodeError, json.JSONDecodeError, StateAccessError) as exc:
        raise StateAccessError("frozen state projection is invalid") from exc

    item_by_id = {str(row["item_id"]): row for row in items}
    if set(projection_by_id) != set(item_by_id) or plan.get("item_count") != len(item_by_id):
        raise StateAccessError("frozen state projection does not match the locked item inventory")
    if plan.get("planned_item_count") != len(item_by_id) or plan.get("planned_request_count") != 2 * len(item_by_id):
        raise StateAccessError("frozen state-access request counts do not match the locked item inventory")

    request_hashes = plan.get("request_sha256")
    randomization = plan.get("randomization")
    if not isinstance(request_hashes, Mapping) or not isinstance(randomization, Mapping):
        raise StateAccessError("frozen state-access request or randomization inventory is malformed")
    order = randomization.get("order")
    seed_hex = randomization.get("seed_hex")
    if (
        randomization.get("version") != "python-random-shuffle-with-frozen-seed-v1"
        or not isinstance(seed_hex, str)
        or not _HASH_RE.fullmatch(seed_hex)
        or not isinstance(order, list)
    ):
        raise StateAccessError("frozen state-access order seed or order is malformed")
    expected_order = [(item_id, arm) for item_id in sorted(item_by_id) for arm in ("withheld", "supplied")]
    random.Random(int(seed_hex, 16)).shuffle(expected_order)
    expected_order_rows = [{"item_id": item_id, "arm": arm} for item_id, arm in expected_order]
    if order != expected_order_rows:
        raise StateAccessError("frozen state-access call order differs from its seed")
    expected_request_keys = {
        _request_key(item_id, arm) for item_id in item_by_id for arm in ("withheld", "supplied")
    }
    if set(request_hashes) != expected_request_keys or len(order) != len(expected_request_keys):
        raise StateAccessError("frozen state-access request inventory is incomplete or duplicated")

    requests = {}
    for item_id, item in item_by_id.items():
        for arm in ("withheld", "supplied"):
            item_key = sha256(item_id.encode("utf-8")).hexdigest()
            relative = f"{LOCKED_STATE_ACCESS_DIRECTORY}/requests/{arm}/{item_key}.json"
            request_raw = _verify_frozen_file(root, files, relative)
            try:
                request = json.loads(request_raw, object_pairs_hook=_unique_json_object)
            except (json.JSONDecodeError, StateAccessError) as exc:
                raise StateAccessError("frozen state-access request is malformed") from exc
            expected_state = None if arm == "withheld" else projection_by_id[item_id]
            if (
                not isinstance(request, dict)
                or request != evidence(item, expected_state)
                or digest(request) != request_hashes[_request_key(item_id, arm)]
            ):
                raise StateAccessError("frozen state-access request is not bound to its item and arm")
            requests[(item_id, arm)] = request
        withheld = requests[(item_id, "withheld")]
        supplied = requests[(item_id, "supplied")]
        if {key: value for key, value in withheld.items() if key != "effective_state"} != {
            key: value for key, value in supplied.items() if key != "effective_state"
        }:
            raise StateAccessError("paired state-access requests differ outside effective_state")
    freeze_sha = sha256((root / "freeze-manifest.json").read_bytes()).hexdigest()
    return root, items, input_manifest, freeze_manifest, freeze_sha, plan, requests


def _read_attempt_records(
    run_root: Path,
    plan: Mapping[str, object],
    requests: Mapping[tuple[str, str], object],
    *,
    run_id: str,
):
    expected = set(requests)
    records = {}
    result_root = run_root / "results"
    allowed = {
        (arm, f"{sha256(item_id.encode('utf-8')).hexdigest()}.json")
        for item_id, arm in expected
    }
    if result_root.exists():
        for path in result_root.rglob("*.json"):
            if (path.parent.name, path.name) not in allowed:
                raise StateAccessError("state-access run directory contains an unknown result record")
    for item_id, arm in expected:
        path = _result_path(run_root, item_id, arm)
        if not path.exists():
            continue
        record = _read_json(path, "state-access attempt record")
        expected_request_hash = plan["request_sha256"][_request_key(item_id, arm)]
        if (
            record.get("record_version") != "paper2-state-access-attempt-1"
            or record.get("run_id") != run_id
            or record.get("item_id") != item_id
            or record.get("arm") != arm
            or record.get("attempt_number") != 1
            or record.get("plan_sha256") != plan.get("plan_sha256")
            or record.get("request_sha256") != expected_request_hash
            or record.get("status") not in {"started", "completed", "technical_failure"}
        ):
            raise StateAccessError("state-access attempt record is not bound to its frozen request")
        if record["status"] == "completed" and not isinstance(record.get("raw_response"), Mapping):
            raise StateAccessError("completed state-access attempt lacks its raw response")
        records[(item_id, arm)] = record
    return records


def _attempt_summary(records: Mapping[tuple[str, str], Mapping[str, object]], planned: int) -> dict[str, int]:
    statuses = Counter(record["status"] for record in records.values())
    return {
        "planned_requests": planned,
        "attempts": len(records),
        "completed": statuses["completed"],
        "technical_failures": statuses["technical_failure"],
        "ambiguous_incomplete": statuses["started"],
        "not_attempted": planned - len(records),
    }


def _progress_record(
    *,
    run_root: Path,
    run_id: str,
    plan: Mapping[str, object],
    freeze_sha: str,
    records: Mapping[tuple[str, str], Mapping[str, object]],
    status: str,
) -> dict[str, object]:
    results = {
        _request_key(item_id, arm): sha256(_result_path(run_root, item_id, arm).read_bytes()).hexdigest()
        for item_id, arm in records
    }
    body: dict[str, object] = {
        "manifest_version": "paper2-state-access-run-manifest-1",
        "run_id": run_id,
        "plan_sha256": plan["plan_sha256"],
        "freeze_manifest_sha256": freeze_sha,
        "input_manifest_sha256": plan["input_manifest_sha256"],
        "planned_request_count": plan["planned_request_count"],
        "result_sha256": results,
        "status": status,
        "updated_at_utc": _utc_now(),
    }
    body["manifest_sha256"] = digest(body)
    return body


def _run_payload(request: Mapping[str, object]) -> dict[str, object]:
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": INSTRUCTION},
            {"role": "user", "content": canonical_json(request)},
        ],
        "format": SCHEMA,
        "options": OPTIONS,
        "think": False,
        "stream": False,
        "keep_alive": "10m",
    }


def run_locked_state_access(freeze_root: str | Path, client: LocalClient) -> dict[str, object]:
    """Run or safely resume the frozen diagnostic through the local client only."""
    root, _items, _input_manifest, _freeze_manifest, freeze_sha, plan, requests = _load_locked_state_access_bundle(freeze_root)
    try:
        descriptor = client.discover_model(MODEL)
    except ProviderCallError as exc:
        raise StateAccessError("pinned local diagnostic model is unavailable") from exc
    if getattr(descriptor, "model_tag", None) != MODEL or getattr(descriptor, "digest", None) != MODEL_DIGEST:
        raise StateAccessError("local diagnostic model identity/digest differs from the frozen contract")

    run_root = root / "runs" / "state-access"
    result_root = run_root / "results"
    run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(run_root, 0o700)
    lock_path = run_root / ".run.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StateAccessError("another process owns this state-access run") from exc
    os.close(lock_fd)
    progress_path = run_root / "run-manifest.json"
    run_id = uuid4().hex
    records: dict[tuple[str, str], dict] = {}
    reused = 0
    try:
        existing_progress = None
        if progress_path.exists():
            existing_progress = _read_json(progress_path, "state-access run manifest")
            progress_body = {key: value for key, value in existing_progress.items() if key != "manifest_sha256"}
            if (
                digest(progress_body) != existing_progress.get("manifest_sha256")
                or existing_progress.get("manifest_version") != "paper2-state-access-run-manifest-1"
                or existing_progress.get("plan_sha256") != plan.get("plan_sha256")
                or existing_progress.get("freeze_manifest_sha256") != freeze_sha
                or existing_progress.get("input_manifest_sha256") != plan.get("input_manifest_sha256")
                or existing_progress.get("status") not in {"running", "complete", "incomplete", "interrupted"}
            ):
                raise StateAccessError("existing state-access run manifest is not bound to this frozen plan")
            run_id = existing_progress.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise StateAccessError("existing state-access run ID is malformed")

        records = _read_attempt_records(run_root, plan, requests, run_id=run_id)
        reused = len(records)
        if existing_progress is not None:
            frozen_result_hashes = existing_progress.get("result_sha256")
            if not isinstance(frozen_result_hashes, Mapping):
                raise StateAccessError("existing state-access result hash inventory is malformed")
            if set(frozen_result_hashes) - {_request_key(item_id, arm) for item_id, arm in records}:
                raise StateAccessError("state-access manifest refers to an absent attempt")
            for (item_id, arm), record in records.items():
                key = _request_key(item_id, arm)
                if key in frozen_result_hashes:
                    actual = sha256(_result_path(run_root, item_id, arm).read_bytes()).hexdigest()
                    if actual != frozen_result_hashes[key]:
                        raise StateAccessError("state-access attempt changed after it was recorded")

        def persist_progress(status: str) -> None:
            progress = _progress_record(
                run_root=run_root,
                run_id=run_id,
                plan=plan,
                freeze_sha=freeze_sha,
                records=records,
                status=status,
            )
            _write_json(progress_path, progress)

        persist_progress("running")
        randomization = plan["randomization"]
        for entry in randomization["order"]:
            item_id, arm = entry["item_id"], entry["arm"]
            request_key = (item_id, arm)
            if request_key in records:
                continue
            request = requests[request_key]
            result_path = _result_path(run_root, item_id, arm)
            started_at = _utc_now()
            started = {
                "record_version": "paper2-state-access-attempt-1",
                "run_id": run_id,
                "item_id": item_id,
                "arm": arm,
                "attempt_number": 1,
                "plan_sha256": plan["plan_sha256"],
                "request_sha256": plan["request_sha256"][_request_key(item_id, arm)],
                "started_at_utc": started_at,
                "completed_at_utc": None,
                "status": "started",
                "error": None,
                "raw_error_response": None,
                "raw_response": None,
            }
            _write_json(result_path, started, replace=False)
            records[request_key] = started
            persist_progress("running")
            try:
                raw_response = client.chat(_run_payload(request))
                if not isinstance(raw_response, Mapping):
                    terminal = {**started, "status": "technical_failure", "error": "invalid_local_response_shape"}
                else:
                    terminal = {**started, "status": "completed", "raw_response": dict(raw_response)}
            except ProviderCallError as exc:
                terminal = {
                    **started,
                    "status": "technical_failure",
                    "error": exc.code,
                    "raw_error_response": exc.raw_response,
                }
            terminal["completed_at_utc"] = _utc_now()
            _write_json(result_path, terminal)
            records[request_key] = terminal
            persist_progress("running")

        summary = _attempt_summary(records, int(plan["planned_request_count"]))
        complete = summary["not_attempted"] == 0 and summary["ambiguous_incomplete"] == 0
        persist_progress("complete" if complete else "incomplete")
        return {"run_id": run_id, "status": "complete" if complete else "incomplete", "reused": reused, **summary}
    except BaseException:
        try:
            if records:
                persist_progress("interrupted")
        except Exception:
            pass
        raise
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
