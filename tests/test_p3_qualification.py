from __future__ import annotations

import json
import hashlib
import inspect
from pathlib import Path

import pytest

from multilingual_judge_pilot.judge_inference import (
    DeterministicMockProvider,
    ProviderCallError,
    ProviderIdentity,
    ProviderResponse,
    Verdict,
)
from multilingual_judge_pilot.qualification import (
    QUALIFICATION_MODEL_DIGESTS,
    build_input_manifest,
    build_qualification_config,
    validate_qualification_config,
)
from multilingual_judge_pilot.qualification_runner import (
    QualificationGateError,
    QualificationResumeError,
    run_qualification,
    verify_qc_acceptance,
)
from multilingual_judge_pilot.qualification_scoring import score_qualification_results
from multilingual_judge_pilot.screen_review import render_review_html, validate_review_export


def _synthetic_items() -> list[dict[str, object]]:
    rows = []
    for language, condition, message in (
        ("en", "EN-EN", "Synthetic fixture: prepare sample tray number 11."),
        ("ar", "AR-AR", "مثال اصطناعي مستقل: جهّز صينية العينة رقم ١١."),
    ):
        for index in range(24):
            rows.append(
                {
                    "item_id": f"SYNTH-QUAL-{language.upper()}-{index + 1:02d}",
                    "language_condition": condition,
                    "action_turn_index": 1,
                    "conversation": [
                        {"turn_index": 0, "speaker": "user", "language": language, "content": f"{message} Case {index + 1}."}
                    ],
                    "action": {"tool_name": "prepare_sample_tray", "count": index + 1},
                    "public_tool_schema": {
                        "tool_name": "prepare_sample_tray",
                        "parameters": [{"name": "count", "type": "integer", "required": True}],
                    },
                }
            )
    return rows


def _bundle():
    items = _synthetic_items()
    input_manifest = build_input_manifest(items, source_file_sha256="a" * 64)
    config = build_qualification_config(
        model_tag="qwen3.5:9b-q4_K_M",
        model_digest=QUALIFICATION_MODEL_DIGESTS["qwen3.5:9b-q4_K_M"],
        input_manifest=input_manifest,
        code_revision="synthetic-test-revision",
    )
    return items, input_manifest, config


def _accepted(config: dict[str, object], input_manifest: dict[str, object]) -> dict[str, object]:
    return {
        "acceptance_version": "p3-screen-qc-acceptance-1",
        "reviewer_disposition": "accepted",
        "research_owner_disposition": "accepted",
        "independent_review_complete": True,
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "configuration_hash": config["configuration_hash"],
        "review_export_sha256": "b" * 64,
    }


def test_qualification_configuration_is_fixed_complete_and_hash_bound():
    _items, manifest, config = _bundle()
    validated = validate_qualification_config(config)
    assert validated["configuration_hash"] == config["configuration_hash"]
    assert config["decoding"] == {
        "num_ctx": 4096,
        "num_predict": 96,
        "seed": 17,
        "temperature": 0.0,
        "think": False,
    }
    assert config["input"]["manifest_sha256"] == manifest["manifest_sha256"]
    assert config["response_contract"]["version"] == "binary-verdict-v1"
    tampered = dict(config)
    tampered["decoding"] = {**config["decoding"], "temperature": 0.2}
    with pytest.raises(ValueError, match="hash"):
        validate_qualification_config(tampered)
    gemma = build_qualification_config(
        model_tag="gemma4:12b-it-qat",
        model_digest=QUALIFICATION_MODEL_DIGESTS["gemma4:12b-it-qat"],
        input_manifest=manifest,
        code_revision="synthetic-test-revision",
    )
    assert gemma["prompt"] == config["prompt"]
    assert gemma["decoding"] == config["decoding"]
    assert gemma["configuration_hash"] != config["configuration_hash"]


def test_qc_acceptance_gate_requires_review_owner_and_exact_hashes():
    _items, manifest, config = _bundle()
    assert verify_qc_acceptance(config, manifest, _accepted(config, manifest)) is None
    rejected = _accepted(config, manifest)
    rejected["reviewer_disposition"] = "pending"
    with pytest.raises(QualificationGateError):
        verify_qc_acceptance(config, manifest, rejected)
    mismatched = _accepted(config, manifest)
    mismatched["input_manifest_sha256"] = "c" * 64
    with pytest.raises(QualificationGateError):
        verify_qc_acceptance(config, manifest, mismatched)


def test_mock_qualification_run_preserves_raw_outputs_and_resumes_without_duplicate_calls(tmp_path: Path):
    items, manifest, config = _bundle()
    acceptance = _accepted(config, manifest)
    identity = ProviderIdentity(
        "ollama-local",
        config["model"]["model_tag"],
        config["model"]["digest"],
    )
    provider = DeterministicMockProvider(
        identity,
        [ProviderResponse(raw_response='{"verdict":"valid"}', prompt_tokens=10, completion_tokens=4)] * 48,
    )
    first = run_qualification(items, manifest, config, acceptance, provider, tmp_path)
    assert first["completed_items"] == 48
    assert len(provider.calls) == 48
    result_files = list((tmp_path / "items").glob("*.result.json"))
    assert len(result_files) == 48
    saved = json.loads(result_files[0].read_text())
    assert saved["run_result"]["steps"][0]["attempts"][0]["raw_response"] == '{"verdict":"valid"}'
    request = json.loads(provider.calls[0][0])
    assert set(request) == {
        "response_contract_version",
        "response_schema",
        "item_id",
        "instruction",
        "conversation",
        "action",
        "public_tool_schema",
    }
    assert "expected_valid" not in provider.calls[0][0]
    assert "screen_reference_key" not in inspect.getsource(__import__("multilingual_judge_pilot.qualification_runner", fromlist=["run_qualification"]))

    resumed_provider = DeterministicMockProvider(identity, [])
    second = run_qualification(items, manifest, config, acceptance, resumed_provider, tmp_path)
    assert second["completed_items"] == 48
    assert second["skipped_completed_items"] == 48
    assert resumed_provider.calls == []


def test_transient_local_failure_uses_fixed_single_retry_and_retains_attempts(tmp_path: Path):
    items, manifest, config = _bundle()
    acceptance = _accepted(config, manifest)
    identity = ProviderIdentity("ollama-local", config["model"]["model_tag"], config["model"]["digest"])
    responses = [ProviderCallError("local_timeout"), ProviderResponse(raw_response='{"verdict":"valid"}')]
    responses.extend([ProviderResponse(raw_response='{"verdict":"valid"}')] * 47)
    provider = DeterministicMockProvider(identity, responses)
    run_qualification(items, manifest, config, acceptance, provider, tmp_path)
    assert len(provider.calls) == 49
    first_result = next((tmp_path / "items").glob("*.result.json"))
    # The hashed filenames sort independently of the source sequence; inspect all records.
    records = [json.loads(path.read_text()) for path in (tmp_path / "items").glob("*.result.json")]
    retry_records = [record for record in records if len(record["run_result"]["steps"][0]["attempts"]) == 2]
    assert len(retry_records) == 1
    attempts = retry_records[0]["run_result"]["steps"][0]["attempts"]
    assert [row["attempt_number"] for row in attempts] == [1, 2]
    assert attempts[0]["failure_code"] == "local_timeout"
    assert attempts[1]["raw_response"] == '{"verdict":"valid"}'


def test_resume_stops_on_ambiguous_started_attempt_instead_of_repeating(tmp_path: Path):
    items, manifest, config = _bundle()
    acceptance = _accepted(config, manifest)
    identity = ProviderIdentity("ollama-local", config["model"]["model_tag"], config["model"]["digest"])
    run_qualification(
        items,
        manifest,
        config,
        acceptance,
        DeterministicMockProvider(identity, [ProviderResponse(raw_response='{"verdict":"valid"}')]),
        tmp_path,
        max_items=1,
    )
    first_id = items[0]["item_id"]
    prefix = hashlib.sha256(first_id.encode()).hexdigest()
    result_path = tmp_path / "items" / f"{prefix}.result.json"
    state_path = tmp_path / "items" / f"{prefix}.state.json"
    state = json.loads(state_path.read_text())
    state["status"] = "in_progress"
    state_path.write_text(json.dumps(state))
    result_path.unlink()
    with pytest.raises(QualificationResumeError, match="ambiguous"):
        run_qualification(items, manifest, config, acceptance, DeterministicMockProvider(identity, []), tmp_path)


def test_scoring_uses_fixed_per_language_and_class_thresholds_and_separates_failures():
    items, _manifest, _config = _bundle()
    labels = {item["item_id"]: {"expected_valid": index % 2 == 0} for index, item in enumerate(items)}
    outcomes = [
        {
            "item_id": item["item_id"],
            "run_result": {"final_result": {"status": "parsed", "verdict": "valid" if labels[item["item_id"]]["expected_valid"] else "invalid"}},
        }
        for item in items
    ]
    passing = score_qualification_results(items, outcomes, labels)
    assert passing["decision"] == "pass"
    assert passing["languages"]["en"]["correct"] == 24
    assert passing["languages"]["ar"]["correct"] == 24
    assert passing["languages"]["en"]["confusion_matrix"]["valid"]["valid"] == 12

    outcomes[0]["run_result"]["final_result"] = {"status": "invalid_output", "verdict": None}
    scored = score_qualification_results(items, outcomes, labels)
    assert scored["invalid_or_unparseable_outputs"] == 1
    assert scored["languages"]["en"]["correct"] == 23
    assert scored["languages"]["en"]["confusion_matrix"]["valid"]["invalid_or_unparseable"] == 1

    outcomes[1]["run_result"]["final_result"] = {"status": "provider_failure", "verdict": None}
    missing = score_qualification_results(items, outcomes, labels)
    assert missing["technical_missingness"] == 1
    assert missing["decision"] == "incomplete_not_qualified"
    assert missing["languages"]["en"]["confusion_matrix"]["invalid"]["technical_missing"] == 1

    five_wrong = [
        {
            "item_id": item["item_id"],
            "run_result": {"final_result": {"status": "parsed", "verdict": "valid" if labels[item["item_id"]]["expected_valid"] else "invalid"}},
        }
        for item in items
    ]
    for index in (0, 2, 4, 6, 8):
        five_wrong[index] = {
            "item_id": items[index]["item_id"],
            "run_result": {"final_result": {"status": "parsed", "verdict": "invalid"}},
        }
    score_fail = score_qualification_results(items, five_wrong, labels)
    assert score_fail["decision"] == "fail"
    assert score_fail["languages"]["en"]["by_validity_class"]["valid"]["threshold_met"] is False


def test_offline_reviewer_page_binds_items_and_gates_reference_labels():
    items = _synthetic_items()
    labels = {item["item_id"]: {"expected_valid": i % 2 == 0} for i, item in enumerate(items)}
    manifest = build_input_manifest(items, source_file_sha256="a" * 64)
    html = render_review_html(items, labels, manifest)
    assert "Lock independent judgments and reveal reference labels" in html
    assert "localStorage" in html
    assert "Export JSON" in html and "Import JSON" in html
    assert "connect-src 'none'" in html
    assert "https://" not in html

    export = {
        "schema_version": "p3-screen-review-export-1",
        "input_manifest_sha256": manifest["manifest_sha256"],
        "reviewer_declaration": {},
        "locked_before_label_reveal": False,
        "items": [],
    }
    for item in items:
        export["items"].append(
            {
                "item_id": item["item_id"],
                "source_sha256": manifest["item_hashes"][item["item_id"]],
                "answers": {},
            }
        )
    assert validate_review_export(export, items, manifest)["valid"] is True
    export["items"][0]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        validate_review_export(export, items, manifest)


def test_complete_synthetic_review_export_round_trips_and_requires_notes_for_flags():
    items = _synthetic_items()
    manifest = build_input_manifest(items, source_file_sha256="a" * 64)
    export = {
        "schema_version": "p3-screen-review-export-1",
        "input_manifest_sha256": manifest["manifest_sha256"],
        "locked_before_label_reveal": True,
        "reference_labels_revealed": True,
        "review_complete": True,
        "reviewer_declaration": {
            "english_proficiency": "synthetic check",
            "msa_proficiency": "synthetic check",
            "relevant_review_experience": "synthetic check",
            "conflicts_of_interest": "none",
            "prior_dataset_exposure": "none",
            "independent": True,
        },
        "items": [],
    }
    for item in items:
        language = item["language_condition"]
        answers = {
            "naturalness": "natural",
            "interpretation": "correct",
            "action_tool": "correct",
            "independent_verdict": "valid",
            "constraint_consistency": "consistent",
            "ambiguity": "no",
            "context_distinct": "yes",
            "reference_label_review": "correct",
        }
        export["items"].append(
            {"item_id": item["item_id"], "source_sha256": manifest["item_hashes"][item["item_id"]], "answers": answers}
        )
    round_trip = json.loads(json.dumps(export))
    checked = validate_review_export(round_trip, items, manifest)
    assert checked["valid"] is True and checked["review_complete"] is True
    round_trip["items"][0]["answers"]["naturalness"] = "major_issue"
    with pytest.raises(ValueError, match="issue note"):
        validate_review_export(round_trip, items, manifest)


def test_local_ollama_running_model_inventory_is_loopback_only_and_validated():
    from multilingual_judge_pilot.local_ollama import OllamaLocalClient

    client = OllamaLocalClient()
    calls = []

    def response(method, path, _payload=None):
        calls.append((method, path))
        return {"models": [{"name": "qwen3.5:9b-q4_K_M"}]}

    client._json_request = response
    assert client.list_running_models() == ("qwen3.5:9b-q4_K_M",)
    assert calls == [("GET", "/api/ps")]
