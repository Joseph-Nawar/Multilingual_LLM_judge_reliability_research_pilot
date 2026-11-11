from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from multilingual_judge_pilot.judge_inference import (
    DeterministicMockProvider,
    ProviderIdentity,
    ProviderResponse,
)
from multilingual_judge_pilot.qualification import (
    QUALIFICATION_MODEL_DIGESTS,
    build_input_manifest,
    build_qualification_config,
    item_sha256,
)
from multilingual_judge_pilot.exploratory_pilot import (
    ExploratoryPilotResumeError,
    run_exploratory_pilot,
    validate_exploratory_review_export,
)
from multilingual_judge_pilot.exploratory_pilot_scoring import score_exploratory_pilot


def _synthetic_items() -> list[dict[str, object]]:
    items = []
    families = ("tool_contract", "numerical", "temporal", "permission", "revision_preservation", "combined_constraints")
    for language, condition, sentence in (
        ("en", "EN-EN", "Synthetic exercise: place sample tray 11 on table S-4."),
        ("ar", "AR-AR", "تمرين اصطناعي: ضع صينية العينة ١١ على الطاولة س-٤."),
    ):
        for index in range(24):
            items.append({
                "item_id": f"SYNTH-PILOT-{language.upper()}-{index + 1:02d}",
                "language_condition": condition,
                "action_turn_index": 1,
                "conversation": [{
                    "turn_index": 0,
                    "speaker": "user",
                    "language": language,
                    "content": f"{sentence} Fixture {index + 1}.",
                }],
                "action": {"tool_name": "place_sample_tray", "table": "S-4", "count": index + 1},
                "public_tool_schema": {
                    "tool_name": "place_sample_tray",
                    "parameters": [
                        {"name": "table", "type": "string", "required": True},
                        {"name": "count", "type": "integer", "required": True},
                    ],
                },
                "_synthetic_family": families[index // 4],
            })
    # Family metadata is for the test scorer only, not judge-facing input.
    return items


def _bundle():
    items = _synthetic_items()
    families = {row["item_id"]: row.pop("_synthetic_family") for row in items}
    manifest = build_input_manifest(items, source_file_sha256="a" * 64)
    config = build_qualification_config(
        model_tag="qwen3.5:9b-q4_K_M",
        model_digest=QUALIFICATION_MODEL_DIGESTS["qwen3.5:9b-q4_K_M"],
        input_manifest=manifest,
        code_revision="synthetic-pilot-test-revision",
    )
    labels = {row["item_id"]: {"expected_valid": (index % 2 == 0)} for index, row in enumerate(items)}
    reviewer_rows = []
    for index, row in enumerate(items):
        expected = "valid" if labels[row["item_id"]]["expected_valid"] else "invalid"
        independent = (
            "unclear" if index in {0, 25, 42}
            else ("invalid" if expected == "valid" else "valid") if index in {2, 3, 4, 5, 26, 27}
            else expected
        )
        reviewer_rows.append({
            "item_id": row["item_id"],
            "source_sha256": item_sha256(row),
            "answers": {
                "naturalness": "natural",
                "interpretation": "correct",
                "action_tool": "correct",
                "independent_verdict": independent,
                "constraint_consistency": "consistent",
                "ambiguity": "no",
                "context_distinct": "yes",
            },
        })
    review = {
        "schema_version": "p3-screen-review-export-1",
        "input_manifest_sha256": manifest["manifest_sha256"],
        "locked_before_label_reveal": False,
        "reference_labels_revealed": False,
        "review_complete": False,
        "reviewer_declaration": {
            "english_proficiency": "synthetic test",
            "msa_proficiency": "synthetic test",
            "relevant_review_experience": "synthetic test",
            "conflicts_of_interest": "none",
            "prior_dataset_exposure": "none",
            "independent": True,
        },
        "items": reviewer_rows,
    }
    return items, families, labels, manifest, config, review


def test_exploratory_runner_accepts_incomplete_pre_reveal_export_without_formal_acceptance(tmp_path: Path):
    items, _families, _labels, manifest, config, review = _bundle()
    review_bytes = json.dumps(review, ensure_ascii=False, sort_keys=True).encode()
    review_hash = hashlib.sha256(review_bytes).hexdigest()
    identity = ProviderIdentity("ollama-local", config["model"]["model_tag"], config["model"]["digest"])
    provider = DeterministicMockProvider(
        identity,
        [ProviderResponse(raw_response='{"verdict":"valid"}', prompt_tokens=12, completion_tokens=4) for _ in items],
    )
    result = run_exploratory_pilot(items, manifest, review, review_hash, config, provider, tmp_path, runner_code_revision="synthetic-runner")
    assert result["run_status"] == "complete"
    assert result["completed_items"] == 48
    records = list((tmp_path / "items").glob("*.result.json"))
    assert len(records) == 48
    saved = json.loads(records[0].read_text())
    assert saved["stage"] == "PILOT_EXPLORATORY_UNVALIDATED"
    assert saved["run_result"]["steps"][0]["attempts"][0]["raw_response"] == '{"verdict":"valid"}'
    request = json.loads(provider.calls[0][0])
    assert "expected_valid" not in provider.calls[0][0]
    assert "reviewer_declaration" not in provider.calls[0][0]
    assert "screen_reference_key" not in provider.calls[0][0]
    assert result["review_export_sha256"] == review_hash

    second = run_exploratory_pilot(
        items,
        manifest,
        review,
        review_hash,
        config,
        DeterministicMockProvider(identity, []),
        tmp_path,
        runner_code_revision="synthetic-runner",
    )
    assert second["skipped_completed_items"] == 48
    assert second["new_item_executions"] == 0


def test_exploratory_review_gate_rejects_post_reveal_or_incomplete_pre_reveal_exports():
    items, _families, _labels, manifest, _config, review = _bundle()
    assert validate_exploratory_review_export(review, items, manifest) == 48
    post_reveal = json.loads(json.dumps(review))
    post_reveal["locked_before_label_reveal"] = True
    post_reveal["reference_labels_revealed"] = True
    with pytest.raises(ValueError, match="pre-reveal"):
        validate_exploratory_review_export(post_reveal, items, manifest)
    incomplete = json.loads(json.dumps(review))
    incomplete["items"][4]["answers"].pop("independent_verdict")
    with pytest.raises(ValueError, match="complete independent assessments"):
        validate_exploratory_review_export(incomplete, items, manifest)


def test_exploratory_runner_stops_on_ambiguous_interrupted_item(tmp_path: Path):
    items, _families, _labels, manifest, config, review = _bundle()
    review_hash = hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest()
    identity = ProviderIdentity("ollama-local", config["model"]["model_tag"], config["model"]["digest"])
    run_exploratory_pilot(
        items, manifest, review, review_hash, config,
        DeterministicMockProvider(identity, [ProviderResponse(raw_response='{"verdict":"valid"}')]),
        tmp_path, runner_code_revision="synthetic-runner", max_items=1,
    )
    manifest_path = tmp_path / "run-manifest.json"
    state = json.loads(manifest_path.read_text())
    item_id = items[1]["item_id"]
    state_path = tmp_path / "items" / f"{hashlib.sha256(item_id.encode()).hexdigest()}.state.json"
    state_path.write_text(json.dumps({"status": "in_progress"}))
    with pytest.raises(ExploratoryPilotResumeError, match="ambiguous"):
        run_exploratory_pilot(
            items, manifest, review, review_hash, config,
            DeterministicMockProvider(identity, []), tmp_path,
            runner_code_revision="synthetic-runner",
        )


def test_exploratory_score_reports_language_family_and_sensitivity_without_formal_claims():
    items, families, labels, manifest, _config, review = _bundle()
    outcomes = []
    for index, row in enumerate(items):
        predicted = "valid" if labels[row["item_id"]]["expected_valid"] else "invalid"
        if index in {0, 1, 25}:
            predicted = "invalid" if predicted == "valid" else "valid"
        outcomes.append({"item_id": row["item_id"], "final_status": "parsed", "verdict": predicted})
    result = score_exploratory_pilot(items, outcomes, labels, families, review)
    assert result["stage"] == "PILOT_EXPLORATORY_UNVALIDATED"
    assert result["formal_qualification_claim"] is False
    assert result["languages"]["en"]["total"] == 24
    assert result["languages"]["ar"]["invalid_class_recall"] == 11 / 12
    assert len(result["competency_families"]) == 12
    assert result["sensitivity"]["exclude_reviewer_unclear"]["total"] == 45
    assert result["sensitivity"]["exclude_human_disagreements_and_unclear"]["total"] == 39
    assert result["provisional_threshold_comparison"]["formal_qualification"] is False
    assert result["provisional_threshold_comparison"]["pilot_decision"] == "provisional_pass_pattern"
    outcomes[0]["final_status"] = "provider_failure"
    incomplete = score_exploratory_pilot(items, outcomes, labels, families, review)
    assert incomplete["provisional_threshold_comparison"]["pilot_decision"] == "provisional_incomplete"
