"""Frozen shared-prompt state-access diagnostic contract and input builder."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
import random
import re
from typing import Mapping, Sequence

from .judge_inference import BINARY_RESPONSE_CONTRACT, PARSER_VERSION, canonical_json, response_schema
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
