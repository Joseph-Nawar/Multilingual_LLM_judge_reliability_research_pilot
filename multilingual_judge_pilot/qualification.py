"""Fixed, hash-bound configuration helpers for the private P3 competence screen.

This module handles only judge-facing screen evidence and configuration hashes.
It does not import the reference key or any study dataset module.
"""

from __future__ import annotations

import hashlib
import re
from typing import Mapping, Sequence

from .judge_inference import (
    BINARY_RESPONSE_CONTRACT,
    PARSER_VERSION,
    ContractError,
    JudgeFacingInput,
    canonical_json,
    response_schema,
)
from .p3_methodology_proposals import DIRECT_PROMPT_V2


QUALIFICATION_CONFIG_VERSION = "p3-local-qualification-config-v1"
INPUT_MANIFEST_VERSION = "p3-qualification-input-manifest-v1"
QUALIFICATION_SCORING_VERSION = "p3-competence-screen-scoring-v1"
QUALIFICATION_RETRY_POLICY = {
    "version": "p3-qualification-transient-retry-v1",
    "max_attempts": 2,
    "retryable_error_codes": [
        "http_500",
        "http_502",
        "http_503",
        "http_504",
        "local_connection_error",
        "local_timeout",
    ],
    "malformed_or_refused_outputs_retried": False,
}

QUALIFICATION_MODEL_DIGESTS = {
    "qwen3.5:9b-q4_K_M": "sha256:ddea16afe16ac5cd402c56ed3e7dcc0d9b250ff355e8913b3957f8ae80e4ed8b",
    "gemma4:12b-it-qat": "sha256:38044be4f923e5a55264ed7df4eaac2676651a905f735197c504045140c02bd3",
}
QUALIFICATION_DECODING = {
    "num_ctx": 4096,
    "num_predict": 96,
    "seed": 17,
    "temperature": 0.0,
    "think": False,
}
QUALIFICATION_THRESHOLDS = {
    "per_language_items": 24,
    "valid_items_per_language": 12,
    "invalid_items_per_language": 12,
    "minimum_correct_per_language": 20,
    "minimum_valid_correct_per_language": 10,
    "minimum_invalid_correct_per_language": 10,
    "invalid_or_unparseable_outputs_count_incorrect": True,
    "technical_missingness_blocks_pass": True,
}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def item_sha256(item: Mapping[str, object]) -> str:
    return sha256_text(canonical_json(item))


def build_input_manifest(
    items: Sequence[Mapping[str, object]], *, source_file_sha256: str
) -> dict[str, object]:
    """Bind the 48 judge-facing inputs without loading reference labels."""
    if not _SHA256.fullmatch(source_file_sha256):
        raise ContractError("source_file_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(items, (tuple, list)) or len(items) != 48:
        raise ContractError("qualification input manifest requires exactly 48 screen items")
    hashes: dict[str, str] = {}
    conditions: dict[str, int] = {"EN-EN": 0, "AR-AR": 0}
    for row in items:
        parsed = JudgeFacingInput.from_mapping(row)
        if parsed.item_id in hashes:
            raise ContractError("qualification item identifiers must be unique")
        if parsed.language_condition not in conditions:
            raise ContractError("qualification screen must contain only EN-EN and AR-AR items")
        hashes[parsed.item_id] = item_sha256(row)
        conditions[parsed.language_condition] += 1
    if conditions != {"EN-EN": 24, "AR-AR": 24}:
        raise ContractError("qualification input manifest must contain 24 English and 24 MSA items")
    body: dict[str, object] = {
        "manifest_version": INPUT_MANIFEST_VERSION,
        "source_file_sha256": source_file_sha256,
        "item_count": len(items),
        "condition_counts": conditions,
        "item_hashes": {key: hashes[key] for key in sorted(hashes)},
    }
    body["manifest_sha256"] = sha256_text(canonical_json(body))
    return body


def verify_input_manifest(
    items: Sequence[Mapping[str, object]], manifest: Mapping[str, object]
) -> None:
    if not isinstance(manifest, Mapping):
        raise ContractError("qualification input manifest must be an object")
    claimed_hash = manifest.get("manifest_sha256")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if not isinstance(claimed_hash, str) or claimed_hash != sha256_text(canonical_json(body)):
        raise ContractError("qualification input manifest hash is invalid")
    expected = build_input_manifest(
        items,
        source_file_sha256=str(manifest.get("source_file_sha256", "")),
    )
    if canonical_json(expected) != canonical_json(manifest):
        raise ContractError("qualification items do not match their hash-bound input manifest")


def build_qualification_config(
    *,
    model_tag: str,
    model_digest: str,
    input_manifest: Mapping[str, object],
    code_revision: str,
) -> dict[str, object]:
    """Create the one approved direct-judging configuration for a candidate."""
    if model_tag not in QUALIFICATION_MODEL_DIGESTS:
        raise ContractError("qualification accepts only the two approved local judge tags")
    if model_digest != QUALIFICATION_MODEL_DIGESTS[model_tag]:
        raise ContractError("model digest does not match the previously verified approved artifact")
    if not isinstance(code_revision, str) or not code_revision.strip():
        raise ContractError("code_revision is required")
    input_body = dict(input_manifest)
    claimed_input_hash = input_body.pop("manifest_sha256", None)
    if claimed_input_hash != sha256_text(canonical_json(input_body)):
        raise ContractError("input manifest hash is invalid")
    _validate_input_manifest_record(input_manifest)

    prompt_record = {
        "version": DIRECT_PROMPT_V2.version,
        "instruction": DIRECT_PROMPT_V2.instruction,
        "sha256": sha256_text(DIRECT_PROMPT_V2.instruction),
    }
    body: dict[str, object] = {
        "configuration_version": QUALIFICATION_CONFIG_VERSION,
        "status": "frozen_for_one_time_qualification_after_qc_acceptance",
        "baseline": "direct_multilingual",
        "translation_enabled": False,
        "model": {
            "provider_id": "ollama-local",
            "model_tag": model_tag,
            "digest": model_digest,
        },
        "prompt": prompt_record,
        "response_contract": {
            "version": BINARY_RESPONSE_CONTRACT,
            "schema": response_schema(BINARY_RESPONSE_CONTRACT),
            "parser_version": PARSER_VERSION,
        },
        "decoding": dict(QUALIFICATION_DECODING),
        "retry_policy": dict(QUALIFICATION_RETRY_POLICY),
        "input": {
            "manifest_sha256": claimed_input_hash,
            "source_file_sha256": input_manifest["source_file_sha256"],
            "item_count": 48,
            "condition_counts": dict(input_manifest["condition_counts"]),
            "item_hashes": dict(input_manifest["item_hashes"]),
        },
        "scoring": {
            "version": QUALIFICATION_SCORING_VERSION,
            **QUALIFICATION_THRESHOLDS,
        },
        "execution": {
            "one_model_loaded_at_a_time": True,
            "resumable": True,
            "completed_item_attempts_are_not_repeated": True,
            "ambiguous_started_attempts_require_manual_reconciliation": True,
            "raw_response_retention": True,
            "reference_labels_in_inference": False,
        },
        "code_revision": code_revision,
        "paid_inference_authorized": False,
    }
    body["configuration_hash"] = sha256_text(canonical_json(body))
    return body


def validate_qualification_config(config: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise ContractError("qualification configuration must be an object")
    record = dict(config)
    claimed = record.pop("configuration_hash", None)
    if not isinstance(claimed, str) or claimed != sha256_text(canonical_json(record)):
        raise ContractError("qualification configuration hash is invalid")
    model = record.get("model")
    if not isinstance(model, Mapping):
        raise ContractError("qualification configuration model identity is missing")
    tag, digest = model.get("model_tag"), model.get("digest")
    if tag not in QUALIFICATION_MODEL_DIGESTS or digest != QUALIFICATION_MODEL_DIGESTS[tag]:
        raise ContractError("qualification configuration uses an unapproved model digest")
    if record.get("configuration_version") != QUALIFICATION_CONFIG_VERSION:
        raise ContractError("unsupported qualification configuration version")
    expected_top_level = {
        "configuration_version",
        "status",
        "baseline",
        "translation_enabled",
        "model",
        "prompt",
        "response_contract",
        "decoding",
        "retry_policy",
        "input",
        "scoring",
        "execution",
        "code_revision",
        "paid_inference_authorized",
    }
    if set(record) != expected_top_level:
        raise ContractError("qualification configuration has missing or unknown fields")
    if record.get("status") != "frozen_for_one_time_qualification_after_qc_acceptance":
        raise ContractError("qualification configuration status is not frozen for the approved screen")
    if model.get("provider_id") != "ollama-local":
        raise ContractError("qualification must use the local Ollama provider")
    if record.get("baseline") != "direct_multilingual" or record.get("translation_enabled") is not False:
        raise ContractError("qualification configuration must use direct judging without translation")
    if record.get("decoding") != QUALIFICATION_DECODING:
        raise ContractError("qualification decoding settings differ from the fixed approved settings")
    if record.get("retry_policy") != QUALIFICATION_RETRY_POLICY:
        raise ContractError("qualification retry policy differs from the fixed approved policy")
    prompt = record.get("prompt")
    if not isinstance(prompt, Mapping) or prompt.get("version") != DIRECT_PROMPT_V2.version:
        raise ContractError("qualification prompt is not the approved direct prompt V2")
    if prompt.get("instruction") != DIRECT_PROMPT_V2.instruction or prompt.get("sha256") != sha256_text(DIRECT_PROMPT_V2.instruction):
        raise ContractError("qualification prompt content or hash differs from approved direct prompt V2")
    contract = record.get("response_contract")
    if contract != {
        "version": BINARY_RESPONSE_CONTRACT,
        "schema": response_schema(BINARY_RESPONSE_CONTRACT),
        "parser_version": PARSER_VERSION,
    }:
        raise ContractError("qualification response contract or parser differs from the approved binary contract")
    if record.get("scoring") != {"version": QUALIFICATION_SCORING_VERSION, **QUALIFICATION_THRESHOLDS}:
        raise ContractError("qualification scoring thresholds differ from the fixed approved thresholds")
    inputs = record.get("input")
    _validate_input_manifest_record(inputs)
    if not isinstance(record.get("code_revision"), str) or not record["code_revision"].strip():
        raise ContractError("qualification code revision must be retained")
    if record.get("execution") != {
        "one_model_loaded_at_a_time": True,
        "resumable": True,
        "completed_item_attempts_are_not_repeated": True,
        "ambiguous_started_attempts_require_manual_reconciliation": True,
        "raw_response_retention": True,
        "reference_labels_in_inference": False,
    } or record.get("paid_inference_authorized") is not False:
        raise ContractError("qualification execution policy differs from the approved local-only scope")
    return {**record, "configuration_hash": claimed}


def _validate_input_manifest_record(inputs: Mapping[str, object]) -> None:
    if not isinstance(inputs, Mapping):
        raise ContractError("qualification input manifest must be an object")
    required = {"manifest_sha256", "source_file_sha256", "item_count", "condition_counts", "item_hashes"}
    if frozenset(inputs) not in {frozenset(required), frozenset(required | {"manifest_version"})}:
        raise ContractError("qualification input manifest has missing or unknown fields")
    if "manifest_version" in inputs and inputs.get("manifest_version") != INPUT_MANIFEST_VERSION:
        raise ContractError("unsupported qualification input manifest version")
    source_hash = inputs.get("source_file_sha256")
    manifest_hash = inputs.get("manifest_sha256")
    item_hashes = inputs.get("item_hashes")
    if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
        raise ContractError("qualification input source hash is invalid")
    if not isinstance(item_hashes, Mapping) or len(item_hashes) != 48:
        raise ContractError("qualification configuration must bind exactly 48 item hashes")
    if any(not isinstance(key, str) or not isinstance(value, str) or not _SHA256.fullmatch(value) for key, value in item_hashes.items()):
        raise ContractError("qualification item hashes are malformed")
    if inputs.get("item_count") != 48 or inputs.get("condition_counts") != {"EN-EN": 24, "AR-AR": 24}:
        raise ContractError("qualification input counts do not match the fixed 48-item screen")
    body = {
        "manifest_version": INPUT_MANIFEST_VERSION,
        "source_file_sha256": source_hash,
        "item_count": 48,
        "condition_counts": {"EN-EN": 24, "AR-AR": 24},
        "item_hashes": {key: item_hashes[key] for key in sorted(item_hashes)},
    }
    if manifest_hash != sha256_text(canonical_json(body)):
        raise ContractError("qualification input manifest hash is invalid")
