"""Synthetic-only contract tests for the locked Paper 2 state-access diagnostic."""

from __future__ import annotations

import hashlib
import json

import pytest

from multilingual_judge_pilot.paper2_state_access import (
    build_locked_state_access_artifacts,
    project_effective_state,
)
from scripts.paper2_scientific_checkpoint import INSTRUCTION, OPTIONS, SCHEMA, VERSION


def _canonical_state() -> dict[str, object]:
    return {
        "$type": "EffectiveState",
        "active_requirements": [
            {
                "$type": "NumericConstraint",
                "constraint_id": "synthetic-number",
                "scope": {"$type": "Scope", "entity_id": "synthetic-entity"},
                "field": "amount",
                "minimum": {"$type": "NumericBound", "value": {"$decimal": "10"}, "inclusive": True},
                "maximum": None,
                "version": 2,
                "currency_code": "USD",
            },
            {
                "$type": "TemporalConstraint",
                "constraint_id": "synthetic-time",
                "scope": {"$type": "Scope", "entity_id": None},
                "field": "scheduled_at",
                "earliest": {"$type": "TemporalBound", "value": {"$datetime": "2026-10-01T10:00:00.000000+00:00"}, "inclusive": True},
                "latest": None,
                "version": 1,
            },
        ],
        "active_grants": [
            {
                "$type": "PermissionGrant",
                "grant_id": "synthetic-grant",
                "key": {
                    "$type": "PermissionKey",
                    "permission": "confirm_booking",
                    "scope": {"$type": "Scope", "entity_id": "synthetic-entity"},
                },
            }
        ],
        "revoked_grants": [
            {
                "$type": "PermissionGrant",
                "grant_id": "revoked-grant",
                "key": {
                    "$type": "PermissionKey",
                    "permission": "send_receipt",
                    "scope": {"$type": "Scope", "entity_id": "synthetic-entity"},
                },
            }
        ],
        "superseded_requirements": [],
    }


def _locked_fixture():
    conditions = ("EN-EN", "AR-AR", "EN-AR", "AR-EN")
    families = ("introduction", "numerical_revision", "permission_revocation", "temporal_revision")
    items = []
    references = {}
    metadata = {}
    for scenario_number in range(48):
        scenario_id = f"synthetic-scenario-{scenario_number:02d}"
        dataset_kind = "primary" if scenario_number < 36 else "auxiliary_control"
        family = families[scenario_number % len(families)] if dataset_kind == "primary" else "no_change_restatement"
        for derivative_number in range(8):
            item_id = f"opaque-{scenario_number:02d}-{derivative_number}"
            items.append(
                {
                    "item_id": item_id,
                    "language_condition": conditions[derivative_number // 2],
                    "conversation": [
                        {"turn_index": 1, "speaker": "user", "language": "en", "content": "Synthetic request."}
                    ],
                    "action": {"tool": "synthetic", "amount": 10},
                    "public_tool_schema": {"tool": "synthetic"},
                }
            )
            references[item_id] = {
                "effective_state": _canonical_state(),
                "reference_verdict": "valid",
                "judge_prediction": "invalid",
            }
            metadata[item_id] = {
                "scenario_id": scenario_id,
                "dataset_kind": dataset_kind,
                "transition_family": family,
                "language_condition": conditions[derivative_number // 2],
            }
    return items, references, metadata


def test_projection_supplies_only_active_constraints_and_permissions():
    projected = project_effective_state(_canonical_state())

    assert projected == {
        "active_constraints": [
            {
                "constraint_type": "numerical",
                "field": "amount",
                "scope_entity": "synthetic-entity",
                "lower_bound": {"value": "10", "inclusive": True},
                "upper_bound": None,
                "currency_code": "USD",
            },
            {
                "constraint_type": "temporal",
                "field": "scheduled_at",
                "scope_entity": None,
                "lower_bound": {"value": "2026-10-01T10:00:00.000000+00:00", "inclusive": True},
                "upper_bound": None,
                "currency_code": None,
            },
        ],
        "active_permissions": [{"permission": "confirm_booking", "scope_entity": "synthetic-entity"}],
    }


def test_projection_rejects_label_or_prediction_fields_inside_canonical_state():
    unsafe = _canonical_state()
    unsafe["reference_verdict"] = "valid"

    with pytest.raises(ValueError, match="unsupported canonical state shape"):
        project_effective_state(unsafe)


def test_locked_bundle_freezes_768_label_free_paired_requests():
    items, references, metadata = _locked_fixture()
    artifacts = build_locked_state_access_artifacts(
        items, references, metadata, input_manifest_sha256="c" * 64, order_seed_hex="ab" * 32
    )
    plan = json.loads(artifacts["diagnostics/state-access/plan.json"])

    assert plan["prompt_version"] == VERSION
    assert plan["instruction_sha256"] == hashlib.sha256(INSTRUCTION.encode()).hexdigest()
    assert plan["response_schema"] == SCHEMA
    assert plan["options"] == OPTIONS
    assert plan["planned_item_count"] == 384
    assert plan["planned_request_count"] == 768
    assert len(plan["randomization"]["order"]) == 768
    assert len(set((row["item_id"], row["arm"]) for row in plan["randomization"]["order"])) == 768

    artifact_text = b"\n".join(artifacts.values())
    assert b"reference_verdict" not in artifact_text
    assert b"judge_prediction" not in artifact_text
    assert b"synthetic-scenario" not in artifact_text

    item_id = items[0]["item_id"]
    item_key = hashlib.sha256(item_id.encode()).hexdigest()
    withheld = json.loads(artifacts[f"diagnostics/state-access/requests/withheld/{item_key}.json"])
    supplied = json.loads(artifacts[f"diagnostics/state-access/requests/supplied/{item_key}.json"])
    assert set(withheld) == set(supplied)
    assert {key: value for key, value in withheld.items() if key != "effective_state"} == {
        key: value for key, value in supplied.items() if key != "effective_state"
    }
    assert withheld["effective_state"] is None
    assert supplied["effective_state"] == project_effective_state(_canonical_state())
    assert "language" not in withheld["conversation"][0]


def test_locked_bundle_randomization_and_hashes_are_deterministic():
    items, references, metadata = _locked_fixture()

    first = build_locked_state_access_artifacts(
        items, references, metadata, input_manifest_sha256="c" * 64, order_seed_hex="ab" * 32
    )
    second = build_locked_state_access_artifacts(
        items, references, metadata, input_manifest_sha256="c" * 64, order_seed_hex="ab" * 32
    )

    assert first == second
