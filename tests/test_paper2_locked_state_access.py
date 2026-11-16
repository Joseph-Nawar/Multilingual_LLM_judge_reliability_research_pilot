"""Synthetic-only contract tests for the locked Paper 2 state-access diagnostic."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from multilingual_judge_pilot.paper2_state_access import (
    MODEL,
    MODEL_DIGEST,
    StateAccessError,
    analyze_locked_state_access,
    build_locked_state_access_artifacts,
    digest,
    project_effective_state,
    run_locked_state_access,
    summarize_state_access_rows,
)
from multilingual_judge_pilot.judge_inference import ProviderCallError
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


class _SyntheticLocalClient:
    def __init__(
        self,
        *,
        interrupt_on_call: int | None = None,
        technical_failure_on_call: int | None = None,
        invalid_output_on_call: int | None = None,
        refusal_on_call: int | None = None,
        digest: str = MODEL_DIGEST,
    ):
        self.calls = []
        self.interrupt_on_call = interrupt_on_call
        self.technical_failure_on_call = technical_failure_on_call
        self.invalid_output_on_call = invalid_output_on_call
        self.refusal_on_call = refusal_on_call
        self.digest = digest

    def discover_model(self, model_tag: str):
        assert model_tag == MODEL
        return SimpleNamespace(model_tag=model_tag, digest=self.digest)

    def chat(self, payload):
        self.calls.append(payload)
        if self.interrupt_on_call == len(self.calls):
            raise KeyboardInterrupt("synthetic interruption")
        if self.technical_failure_on_call == len(self.calls):
            raise ProviderCallError("synthetic_transport_error", raw_response="synthetic local failure")
        if self.invalid_output_on_call == len(self.calls):
            content = "not-json"
            refusal = False
        elif self.refusal_on_call == len(self.calls):
            content = ""
            refusal = True
        else:
            content = '{"verdict":"valid"}'
            refusal = False
        return {
            "model": MODEL,
            "message": {"role": "assistant", "content": content, "refusal": refusal},
            "done": True,
        }


def _synthetic_freeze(tmp_path):
    from tests.test_p2c_full_study import _create_synthetic_freeze

    return _create_synthetic_freeze(tmp_path)


def test_runner_preserves_raw_outputs_and_skips_all_terminal_attempts(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    first_client = _SyntheticLocalClient()

    summary = run_locked_state_access(freeze_root, first_client)

    assert summary["planned_requests"] == 16
    assert summary["attempts"] == 16
    assert summary["completed"] == 16
    assert len(first_client.calls) == 16
    request = json.loads(first_client.calls[0]["messages"][1]["content"])
    assert set(request) == {"item_id", "conversation", "action", "public_tool_schema", "effective_state"}
    assert "reference_verdict" not in json.dumps(request)
    assert first_client.calls[0]["model"] == MODEL
    assert first_client.calls[0]["options"] == OPTIONS

    result_files = list((freeze_root / "runs" / "state-access" / "results").glob("*/*.json"))
    assert len(result_files) == 16
    record = json.loads(result_files[0].read_text())
    assert record["raw_response"]["model"] == MODEL
    assert record["raw_response"]["done"] is True

    resumed_client = _SyntheticLocalClient()
    resumed = run_locked_state_access(freeze_root, resumed_client)

    assert resumed["reused"] == 16
    assert resumed_client.calls == []


def test_runner_never_resends_an_interrupted_started_attempt(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    interrupted_client = _SyntheticLocalClient(interrupt_on_call=1)

    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        run_locked_state_access(freeze_root, interrupted_client)

    resume_client = _SyntheticLocalClient()
    summary = run_locked_state_access(freeze_root, resume_client)

    assert len(interrupted_client.calls) == 1
    assert len(resume_client.calls) == 15
    assert summary["planned_requests"] == 16
    assert summary["attempts"] == 16
    assert summary["completed"] == 15
    assert summary["ambiguous_incomplete"] == 1
    assert summary["not_attempted"] == 0


def test_runner_rejects_model_digest_mismatch_before_any_call(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    client = _SyntheticLocalClient(digest="sha256:wrong")

    with pytest.raises(StateAccessError, match="model identity/digest"):
        run_locked_state_access(freeze_root, client)

    assert client.calls == []


def test_runner_rejects_a_tampered_frozen_request_before_any_call(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    request_path = next((freeze_root / "diagnostics" / "state-access" / "requests" / "supplied").glob("*.json"))
    request_path.chmod(0o600)
    request_path.write_bytes(request_path.read_bytes() + b" ")
    client = _SyntheticLocalClient()

    with pytest.raises(StateAccessError, match="hash mismatch"):
        run_locked_state_access(freeze_root, client)

    assert client.calls == []


def test_runner_rejects_attempt_record_missing_from_resume_manifest(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    first = _SyntheticLocalClient()
    run_locked_state_access(freeze_root, first)
    manifest_path = freeze_root / "runs" / "state-access" / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["result_sha256"].pop(next(iter(manifest["result_sha256"])))
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    manifest["manifest_sha256"] = digest(body)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))

    resumed = _SyntheticLocalClient()
    with pytest.raises(StateAccessError, match="attempt records"):
        run_locked_state_access(freeze_root, resumed)

    assert resumed.calls == []


def _scored_rows():
    scenarios = (
        ("primary-improved", "primary", "numerical_revision", "improved"),
        ("primary-damaged", "primary", "temporal_revision", "damaged"),
        ("auxiliary-stable", "auxiliary_control", "no_change_restatement", "stable"),
        ("auxiliary-improved", "auxiliary_control", "no_change_restatement", "improved"),
    )
    rows = []
    for scenario_id, dataset_kind, family, pattern in scenarios:
        for item_number, condition in enumerate(("EN-EN", "EN-EN", "AR-AR", "AR-AR", "EN-AR", "EN-AR", "AR-EN", "AR-EN")):
            if pattern == "improved":
                withheld_correct, supplied_correct = False, item_number < 2
            elif pattern == "damaged":
                withheld_correct, supplied_correct = True, item_number != 0
            elif pattern == "stable":
                withheld_correct = supplied_correct = True
            else:
                withheld_correct, supplied_correct = False, item_number == 0
            row = {
                "scenario_id": scenario_id,
                "dataset_kind": dataset_kind,
                "transition_family": family,
                "language_condition": condition,
                "reference": "valid",
                "withheld_prediction": "valid" if withheld_correct else "invalid",
                "supplied_prediction": "valid" if supplied_correct else "invalid",
                "withheld_correct": withheld_correct,
                "supplied_correct": supplied_correct,
                "withheld_parse_status": "parsed",
                "supplied_parse_status": "parsed",
                "withheld_attempt_status": "completed",
                "supplied_attempt_status": "completed",
            }
            if pattern == "improved" and item_number == 2:
                row.update(withheld_prediction=None, withheld_correct=False, withheld_parse_status="provider_failure", withheld_attempt_status="technical_failure")
            if pattern == "improved" and item_number == 3:
                row.update(supplied_prediction=None, supplied_correct=False, supplied_parse_status="missing", supplied_attempt_status="not_attempted")
            rows.append(row)
    return rows


def test_analysis_reports_paired_scenario_effects_conditions_families_and_exploratory_control():
    rows = _scored_rows()

    summary = summarize_state_access_rows(rows)
    repeated = summarize_state_access_rows(rows)

    primary = summary["primary"]
    assert primary["overall"]["corrections"] == 2
    assert primary["overall"]["damages"] == 1
    assert primary["overall"]["parsed_pair_corrections"] == 2
    assert primary["overall"]["parsed_pair_damages"] == 1
    assert primary["overall"]["scenario_macro_difference"] == 0.0625
    assert primary["overall"]["scenario_clustered_95pct_ci"]["cluster_count"] == 2
    assert primary["overall"]["scenario_clustered_95pct_ci"]["replicates"] == 10000
    assert primary["overall"]["scenario_clustered_95pct_ci"] == repeated["primary"]["overall"]["scenario_clustered_95pct_ci"]
    assert set(primary["by_language_condition"]) == {"EN-EN", "AR-AR", "EN-AR", "AR-EN"}
    assert set(primary["by_transition_family"]) == {"numerical_revision", "temporal_revision"}
    assert primary["by_transition_family"]["numerical_revision"]["overall"]["withheld"]["attempt_status_counts"]["technical_failure"] == 1
    assert primary["by_transition_family"]["numerical_revision"]["overall"]["supplied"]["attempt_status_counts"]["not_attempted"] == 1
    comparison = summary["primary_vs_auxiliary_exploratory"]
    assert comparison["status"] == "exploratory"
    assert comparison["primary_minus_auxiliary"] == -0.0625
    assert summary["analysis_sha256"] == repeated["analysis_sha256"]


def test_analysis_scores_raw_outputs_without_changing_attempt_records(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    client = _SyntheticLocalClient(technical_failure_on_call=1, invalid_output_on_call=2, refusal_on_call=3)
    run_locked_state_access(freeze_root, client)
    result_files = sorted((freeze_root / "runs" / "state-access" / "results").rglob("*.json"))
    hashes_before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in result_files}

    report = analyze_locked_state_access(freeze_root)
    repeated = analyze_locked_state_access(freeze_root)

    assert report["planned_items"] == 8
    assert report["primary"]["overall"]["planned_denominator_per_arm"] == 8
    assert sum(report["primary"]["overall"]["withheld"]["parse_status_counts"].values()) == 8
    assert sum(report["primary"]["overall"]["supplied"]["parse_status_counts"].values()) == 8
    primary_arms = report["failure_accounting"]["primary"]
    assert sum(arm["technical_failure"] for arm in primary_arms.values()) == 1
    assert sum(arm["invalid_output"] for arm in primary_arms.values()) == 1
    assert sum(arm["refusal"] for arm in primary_arms.values()) == 1
    assert sum(arm["parsed"] for arm in primary_arms.values()) == 13
    detail = freeze_root / "runs" / "state-access" / "reference-analysis" / "scored-items.jsonl"
    assert hashlib.sha256(detail.read_bytes()).hexdigest() == report["scored_item_detail_sha256"]
    assert report["analysis_sha256"] == repeated["analysis_sha256"]
    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in result_files} == hashes_before


def test_analysis_counts_ambiguous_and_unattempted_items_after_interruption(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    interrupted = _SyntheticLocalClient(interrupt_on_call=1)
    with pytest.raises(KeyboardInterrupt):
        run_locked_state_access(freeze_root, interrupted)

    report = analyze_locked_state_access(freeze_root)
    failure_counts = report["failure_accounting"]["primary"]
    assert sum(arm["ambiguous_incomplete"] for arm in failure_counts.values()) == 1
    assert sum(arm["not_attempted"] for arm in failure_counts.values()) == 15


def test_analysis_rejects_output_path_outside_the_diagnostic_run_directory(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    outside_output = tmp_path / "public-analysis.json"

    with pytest.raises(StateAccessError, match="dedicated file directly inside the frozen diagnostic run directory"):
        analyze_locked_state_access(freeze_root, output_path=outside_output)

    assert not outside_output.exists()
    assert not (tmp_path / "reference-analysis" / "scored-items.jsonl").exists()


def test_analysis_rejects_output_path_that_could_replace_a_raw_result(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    output_inside_results = freeze_root / "runs" / "state-access" / "results" / "withheld" / "analysis.json"

    with pytest.raises(StateAccessError, match="dedicated file directly inside the frozen diagnostic run directory"):
        analyze_locked_state_access(freeze_root, output_path=output_inside_results)

    assert not output_inside_results.exists()


def test_analysis_requires_a_settled_run_before_reading_references(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)

    with pytest.raises(StateAccessError, match="settled state-access inference run"):
        analyze_locked_state_access(freeze_root)

    assert not (freeze_root / "runs" / "state-access" / "reference-analysis").exists()


def test_analysis_refuses_to_read_references_while_run_lock_exists(tmp_path):
    freeze_root = _synthetic_freeze(tmp_path)
    run_locked_state_access(freeze_root, _SyntheticLocalClient())
    lock_path = freeze_root / "runs" / "state-access" / ".run.lock"
    lock_path.touch()

    with pytest.raises(StateAccessError, match="active state-access run lock"):
        analyze_locked_state_access(freeze_root)

    assert not (freeze_root / "runs" / "state-access" / "reference-analysis").exists()
