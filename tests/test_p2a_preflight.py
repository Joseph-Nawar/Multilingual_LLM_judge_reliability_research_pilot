"""Unit tests for P2A preflight utilities using P1 synthetic fixtures only."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from multilingual_judge_pilot.preflight import (
    PrototypePreflight,
    PreflightValidationError,
    append_jsonl_record,
    export_reviewer_packets,
    render_redacted_preflight_report,
    summarize_annotations,
    validate_adjudication_records,
    validate_semantic_coverage,
    verify_research_data_exclusion,
    variant_sha256,
)
from multilingual_judge_pilot.schema import TextSegment, TextSegmentKind
from p1_fixtures import english_variant, numerical_revision_pair, with_language_variants


def _scenario_with_one_synthetic_variant():
    candidate = numerical_revision_pair()
    variant = english_variant(history_id=candidate.histories[0].history_id)
    return with_language_variants(candidate, (variant,))


def _coverage(candidate):
    variant = candidate.language_variants[0]
    return {
        "schema_version": "p2a-coverage-1",
        "scenario_id": candidate.scenario_id,
        "draft_status": "machine_assisted_unvalidated",
        "variants": {
            variant.derivative_id: {
                "human_validation_status": "not_started",
                "targets": [
                    {"target_type": "context_fact", "target_id": "fixture", "segment_ids": ["n1"]},
                    {"target_type": "action_field", "target_id": "price", "segment_ids": ["n1"]},
                    {"target_type": "initial_requirement", "target_id": "budget", "segment_ids": ["n1"]},
                    {
                        "target_type": "event",
                        "target_id": candidate.histories[0].events[0].event_id,
                        "segment_ids": ["n2"],
                    },
                ],
            }
        },
    }


def test_semantic_coverage_maps_formal_requirements_and_events_to_user_spans():
    candidate = _scenario_with_one_synthetic_variant()

    audit = validate_semantic_coverage(candidate, _coverage(candidate))

    assert audit.variant_count == 1
    assert audit.mapped_target_count == 4
    assert audit.human_validation_status == "not_performed"


def test_semantic_coverage_rejects_a_hidden_initial_requirement():
    candidate = _scenario_with_one_synthetic_variant()
    coverage = _coverage(candidate)
    coverage["variants"][candidate.language_variants[0].derivative_id]["targets"] = [
        row
        for row in coverage["variants"][candidate.language_variants[0].derivative_id]["targets"]
        if row["target_type"] != "initial_requirement"
    ]

    with pytest.raises(PreflightValidationError, match="missing semantic coverage"):
        validate_semantic_coverage(candidate, coverage)


def test_semantic_coverage_rejects_an_event_mapped_before_its_conversation_turn():
    candidate = _scenario_with_one_synthetic_variant()
    coverage = _coverage(candidate)
    event_row = next(
        row
        for row in coverage["variants"][candidate.language_variants[0].derivative_id]["targets"]
        if row["target_type"] == "event"
    )
    event_row["segment_ids"] = ["n1"]

    with pytest.raises(PreflightValidationError, match="must map to user turn 2"):
        validate_semantic_coverage(candidate, coverage)


def _scenario_with_initial_literal():
    candidate = _scenario_with_one_synthetic_variant()
    variant = candidate.language_variants[0]
    initial_turn = variant.turns[0]
    literal = TextSegment("initial-budget-literal", TextSegmentKind.INVARIANT_LITERAL, "USD 75", literal_name="budget")
    updated_turn = replace(initial_turn, segments=(*initial_turn.segments, literal))
    updated_variant = replace(variant, turns=(updated_turn, *variant.turns[1:]))
    return with_language_variants(candidate, (updated_variant,))


def test_semantic_coverage_allows_action_values_mapped_to_invariant_literals():
    candidate = _scenario_with_initial_literal()
    coverage = _coverage(candidate)
    price = next(
        row
        for row in coverage["variants"][candidate.language_variants[0].derivative_id]["targets"]
        if row["target_type"] == "action_field"
    )
    price["segment_ids"] = ["initial-budget-literal"]

    audit = validate_semantic_coverage(candidate, coverage)

    assert audit.mapped_target_count == 4


def test_semantic_coverage_rejects_initial_requirement_mapped_only_to_literal():
    candidate = _scenario_with_initial_literal()
    coverage = _coverage(candidate)
    requirement = next(
        row
        for row in coverage["variants"][candidate.language_variants[0].derivative_id]["targets"]
        if row["target_type"] == "initial_requirement"
    )
    requirement["segment_ids"] = ["initial-budget-literal"]

    with pytest.raises(PreflightValidationError, match="mapped only to invariant literals"):
        validate_semantic_coverage(candidate, coverage)


def test_reviewer_packets_include_formal_spec_but_exclude_labels_and_judge_predictions(tmp_path):
    candidate = _scenario_with_one_synthetic_variant()

    packet_paths = export_reviewer_packets((candidate,), tmp_path, reviewer_ids=("reviewer_a", "reviewer_b"))

    assert len(packet_paths) == 2
    for path in packet_paths:
        packet = json.loads(path.read_text(encoding="utf-8"))
        assert packet["canonical_spec"]["initial_states"]
        assert packet["language_variants"][0]["example_sha256"] == variant_sha256(candidate.language_variants[0])
        serialized = json.dumps(packet, ensure_ascii=False)
        assert "declared_label" not in serialized
        assert "oracle_label" not in serialized
        assert "judge_prediction" not in serialized
        assert "oracle_result" not in serialized


def _annotation(example_id, example_hash, reviewer_id, relation="equivalent"):
    return {
        "example_id": example_id,
        "example_sha256": example_hash,
        "reviewer_id": reviewer_id,
        "semantic_relation": relation,
        "linguistic_quality": "natural",
        "issue_codes": [],
        "checklist": {
            "matches_formal_spec": True,
            "preserves_cross_language_meaning": True,
            "initial_requirements_communicated": True,
            "decisive_turn_expresses_event": True,
            "counterfactual_differences_controlled": True,
            "action_interpretation_preserved": True,
            "no_post_action_information": True,
            "msa_natural_and_unambiguous": True,
        },
        "notes": "Synthetic annotation fixture.",
    }


def test_annotation_summary_requires_two_independent_reviewers_and_reports_agreement():
    expected = {"item-1": "a" * 64, "item-2": "b" * 64}
    records = [
        _annotation(item_id, digest, reviewer, relation)
        for item_id, digest, relation in (("item-1", "a" * 64, "equivalent"), ("item-2", "b" * 64, "ambiguous"))
        for reviewer in ("reviewer_a", "reviewer_b")
    ]

    summary = summarize_annotations(records, expected)

    assert summary.complete is True
    assert summary.reviewer_count == 2
    assert summary.raw_semantic_agreement == 1.0
    assert summary.cohen_kappa == 1.0
    assert summary.linguistic_quality_agreement == 1.0
    assert summary.issue_code_exact_agreement == 1.0
    assert summary.checklist_item_agreement["matches_formal_spec"] == 1.0


def test_annotation_summary_rejects_reference_labels_and_prediction_fields():
    record = _annotation("item-1", "a" * 64, "reviewer_a")
    record["judge_prediction"] = "valid"

    with pytest.raises(PreflightValidationError, match="prohibited annotation fields"):
        summarize_annotations([record], {"item-1": "a" * 64})


def test_adjudication_is_required_for_disagreements_and_must_reference_exact_hash():
    digest = "a" * 64
    records = [
        _annotation("item-1", digest, "reviewer_a", "equivalent"),
        _annotation("item-1", digest, "reviewer_b", "ambiguous"),
    ]

    with pytest.raises(PreflightValidationError, match="missing adjudication"):
        validate_adjudication_records([], records)

    adjudication = {
        "example_id": "item-1",
        "example_sha256": digest,
        "reviewer_ids": ["reviewer_a", "reviewer_b"],
        "adjudicator_id": "adjudicator_1",
        "outcome": "retain",
        "rationale": "The ambiguity was resolved against the formal specification.",
    }
    assert validate_adjudication_records([adjudication], records) == 1


def test_jsonl_record_writer_appends_records_inside_the_private_data_root(tmp_path):
    output = append_jsonl_record(tmp_path, "annotations/review.jsonl", {"reviewer_id": "reviewer_a"})
    append_jsonl_record(tmp_path, "annotations/review.jsonl", {"reviewer_id": "reviewer_b"})

    assert output.read_text(encoding="utf-8").splitlines() == [
        '{"reviewer_id":"reviewer_a"}',
        '{"reviewer_id":"reviewer_b"}',
    ]
    with pytest.raises(PreflightValidationError, match="inside the research-data root"):
        append_jsonl_record(tmp_path, "../outside.jsonl", {"unsafe": True})


def test_research_data_paths_are_git_ignored_and_not_already_tracked():
    repo_root = Path(__file__).resolve().parents[1]

    isolation = verify_research_data_exclusion(repo_root)

    assert isolation.all_private_paths_ignored is True
    assert isolation.tracked_private_paths == ()


def test_redacted_preflight_report_omits_item_ids_hashes_and_reference_details():
    report = render_redacted_preflight_report(
        PrototypePreflight(
            scenario_count=4,
            language_variant_count=32,
            item_count=32,
            label_counts={"invalid": 16, "valid": 16},
            domain_family_cells=("booking/introduction",),
            template_counts={"private-template-id": 1},
            recipe_counts={"private-recipe-id": 1},
            exact_duplicate_group_count=0,
            normalized_duplicate_group_count=0,
            semantic_coverage_target_count=320,
            variant_hashes={"private-item-id": "f" * 64},
        )
    )

    assert "private-template-id" not in report
    assert "private-recipe-id" not in report
    assert "private-item-id" not in report
    assert "f" * 64 not in report
    assert "16 valid and 16 invalid" in report
    assert "not independently validated" in report
