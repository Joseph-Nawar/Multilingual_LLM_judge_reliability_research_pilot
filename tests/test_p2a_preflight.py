"""Unit tests for P2A preflight utilities using P1 synthetic fixtures only."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from multilingual_judge_pilot.preflight import (
    PrototypePreflight,
    PreflightValidationError,
    append_jsonl_record,
    canonical_scenario_sha256,
    export_reviewer_packets,
    render_redacted_preflight_report,
    summarize_annotations,
    validate_adjudication_records,
    validate_semantic_coverage,
    verify_research_data_exclusion,
    variant_sha256,
)
from multilingual_judge_pilot.schema import (
    HistoryState,
    PermissionGrant,
    PermissionKey,
    Scope,
    TextSegment,
    TextSegmentKind,
)
from p1_fixtures import english_variant, numerical_revision_pair, with_language_variants


def _scenario_with_one_synthetic_variant():
    candidate = numerical_revision_pair()
    variant = english_variant(history_id=candidate.histories[0].history_id)
    return with_language_variants(candidate, (variant,))


def _scenario_with_initial_permission():
    candidate = _scenario_with_one_synthetic_variant()
    grant = PermissionGrant("synthetic-grant", PermissionKey("book_service", Scope.global_scope()))
    histories = tuple(
        replace(history, initial_state=HistoryState(history.initial_state.requirements, (grant,)))
        for history in candidate.histories
    )
    return replace(candidate, histories=histories)


def _coverage(candidate):
    variant = candidate.language_variants[0]
    targets = [
        {"target_type": "context_fact", "target_id": "fixture", "segment_ids": ["n1"]},
        {"target_type": "action_field", "target_id": "price", "segment_ids": ["n1"]},
    ]
    targets.extend(
        {
            "target_type": "initial_requirement",
            "target_id": requirement.constraint_id,
            "segment_ids": ["n1"],
        }
        for requirement in candidate.histories[0].initial_state.requirements
    )
    targets.extend(
        {"target_type": "initial_permission", "target_id": grant.grant_id, "segment_ids": ["n1"]}
        for grant in candidate.histories[0].initial_state.grants
    )
    targets.extend(
        {"target_type": "event", "target_id": event.event_id, "segment_ids": ["n2"]}
        for event in candidate.histories[0].events
    )
    return {
        "schema_version": "p2a-coverage-1",
        "scenario_id": candidate.scenario_id,
        "draft_status": "machine_assisted_unvalidated",
        "variants": {
            variant.derivative_id: {
                "human_validation_status": "not_started",
                "targets": targets,
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

    with pytest.raises(PreflightValidationError, match="requires non-whitespace localized natural-language text"):
        validate_semantic_coverage(candidate, coverage)


@pytest.mark.parametrize("target_type", ["initial_requirement", "initial_permission", "event"])
def test_semantic_coverage_rejects_required_target_linked_to_empty_natural_language(target_type):
    candidate = _scenario_with_initial_permission() if target_type == "initial_permission" else _scenario_with_one_synthetic_variant()
    variant = candidate.language_variants[0]
    target_id = {
        "initial_requirement": "budget",
        "initial_permission": "synthetic-grant",
        "event": candidate.histories[0].events[0].event_id,
    }[target_type]
    segment_id = "n2" if target_type == "event" else "n1"
    updated_turns = tuple(
        replace(
            turn,
            segments=tuple(
                replace(segment, text="") if segment.segment_id == segment_id else segment
                for segment in turn.segments
            ),
        )
        for turn in variant.turns
    )
    candidate = with_language_variants(candidate, (replace(variant, turns=updated_turns),))
    coverage = _coverage(candidate)
    row = next(
        target
        for target in coverage["variants"][variant.derivative_id]["targets"]
        if target["target_type"] == target_type and target["target_id"] == target_id
    )
    row["segment_ids"] = [segment_id]

    with pytest.raises(PreflightValidationError, match="non-whitespace localized natural-language text"):
        validate_semantic_coverage(candidate, coverage)


def test_semantic_coverage_rejects_whitespace_only_natural_language_for_requirement():
    candidate = _scenario_with_one_synthetic_variant()
    variant = candidate.language_variants[0]
    updated_turns = tuple(
        replace(
            turn,
            segments=tuple(
                replace(segment, text=" \t\n ") if segment.segment_id == "n1" else segment
                for segment in turn.segments
            ),
        )
        for turn in variant.turns
    )
    candidate = with_language_variants(candidate, (replace(variant, turns=updated_turns),))

    with pytest.raises(PreflightValidationError, match="non-whitespace localized natural-language text"):
        validate_semantic_coverage(candidate, _coverage(candidate))


def test_semantic_coverage_rejects_empty_natural_language_even_with_an_invariant_literal():
    candidate = _scenario_with_initial_literal()
    variant = candidate.language_variants[0]
    updated_turns = tuple(
        replace(
            turn,
            segments=tuple(
                replace(segment, text="") if segment.segment_id == "n1" else segment
                for segment in turn.segments
            ),
        )
        for turn in variant.turns
    )
    candidate = with_language_variants(candidate, (replace(variant, turns=updated_turns),))
    coverage = _coverage(candidate)
    requirement = next(
        target
        for target in coverage["variants"][variant.derivative_id]["targets"]
        if target["target_type"] == "initial_requirement"
    )
    requirement["segment_ids"] = ["initial-budget-literal", "n1"]

    with pytest.raises(PreflightValidationError, match="non-whitespace localized natural-language text"):
        validate_semantic_coverage(candidate, coverage)


def test_semantic_coverage_accepts_meaningful_natural_language_with_technical_literal():
    candidate = _scenario_with_initial_literal()
    coverage = _coverage(candidate)
    requirement = next(
        target
        for target in coverage["variants"][candidate.language_variants[0].derivative_id]["targets"]
        if target["target_type"] == "initial_requirement"
    )
    requirement["segment_ids"] = ["n1", "initial-budget-literal"]

    audit = validate_semantic_coverage(candidate, coverage)

    assert audit.mapped_target_count == 4


def test_reviewer_packets_include_formal_spec_but_exclude_labels_and_judge_predictions(tmp_path):
    candidate = _scenario_with_one_synthetic_variant()

    packet_paths = export_reviewer_packets((candidate,), tmp_path, reviewer_ids=("reviewer_a", "reviewer_b"))

    assert len(packet_paths) == 2
    for path in packet_paths:
        packet = json.loads(path.read_text(encoding="utf-8"))
        assert packet["canonical_spec"]["initial_states"]
        assert packet["language_variants"][0]["example_sha256"] == variant_sha256(candidate.language_variants[0])
        assert packet["canonical_scenario_sha256"] == canonical_scenario_sha256(candidate)
        serialized = json.dumps(packet, ensure_ascii=False)
        assert "declared_label" not in serialized
        assert "oracle_label" not in serialized
        assert "judge_prediction" not in serialized
        assert "oracle_result" not in serialized


def _annotation(example_id, example_hash, reviewer_id, relation="equivalent", scenario_hash="c" * 64):
    return {
        "example_id": example_id,
        "example_sha256": example_hash,
        "canonical_scenario_sha256": scenario_hash,
        "reviewer_id": reviewer_id,
        "semantic_relation": relation,
        "linguistic_quality": "natural",
        "decisive_turn_sufficiency": "no",
        "historical_dependence_rationale": "The earlier requirement is needed to interpret the relative revision.",
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
    expected_scenarios = {"item-1": "c" * 64, "item-2": "d" * 64}
    records = [
        _annotation(item_id, digest, reviewer, relation, expected_scenarios[item_id])
        for item_id, digest, relation in (("item-1", "a" * 64, "equivalent"), ("item-2", "b" * 64, "ambiguous"))
        for reviewer in ("reviewer_a", "reviewer_b")
    ]

    summary = summarize_annotations(records, expected, expected_scenarios)

    assert summary.complete is True
    assert summary.reviewer_count == 2
    assert summary.raw_semantic_agreement == 1.0
    assert summary.cohen_kappa == 1.0
    assert summary.historical_dependence_agreement == 1.0
    assert summary.linguistic_quality_agreement == 1.0
    assert summary.issue_code_exact_agreement == 1.0
    assert summary.checklist_item_agreement["matches_formal_spec"] == 1.0


def test_annotation_requires_a_historical_dependence_assessment_and_rationale():
    expected = {"item-1": "a" * 64}
    expected_scenarios = {"item-1": "c" * 64}
    record = _annotation("item-1", "a" * 64, "reviewer_a")

    del record["decisive_turn_sufficiency"]
    with pytest.raises(PreflightValidationError, match="missing required fields"):
        summarize_annotations([record], expected, expected_scenarios)

    record = _annotation("item-1", "a" * 64, "reviewer_a")
    record["decisive_turn_sufficiency"] = "maybe"
    with pytest.raises(PreflightValidationError, match="decisive_turn_sufficiency is invalid"):
        summarize_annotations([record], expected, expected_scenarios)

    record = _annotation("item-1", "a" * 64, "reviewer_a")
    record["historical_dependence_rationale"] = "   "
    with pytest.raises(PreflightValidationError, match="historical_dependence_rationale is required"):
        summarize_annotations([record], expected, expected_scenarios)


def test_annotation_rejects_a_stale_canonical_scenario_hash():
    record = _annotation("item-1", "a" * 64, "reviewer_a", scenario_hash="b" * 64)

    with pytest.raises(PreflightValidationError, match="canonical_scenario_sha256 does not match"):
        summarize_annotations([record], {"item-1": "a" * 64}, {"item-1": "c" * 64})


def test_annotation_summary_reports_decisive_turn_sufficiency_agreement():
    records = [
        _annotation("item-1", "a" * 64, "reviewer_a"),
        _annotation("item-1", "a" * 64, "reviewer_b"),
    ]
    records[0]["decisive_turn_sufficiency"] = "yes"
    records[0]["historical_dependence_rationale"] = "The decisive instruction supplies the only changed requirement."
    records[1]["decisive_turn_sufficiency"] = "no"
    records[1]["historical_dependence_rationale"] = "The earlier constraint is needed to resolve the instruction."

    summary = summarize_annotations(records, {"item-1": "a" * 64}, {"item-1": "c" * 64})

    assert summary.historical_dependence_agreement == 0.0


def test_annotation_summary_rejects_reference_labels_and_prediction_fields():
    record = _annotation("item-1", "a" * 64, "reviewer_a")
    record["judge_prediction"] = "valid"

    with pytest.raises(PreflightValidationError, match="prohibited annotation fields"):
        summarize_annotations([record], {"item-1": "a" * 64}, {"item-1": "c" * 64})


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
    assert "16 valid" not in report
    assert "16 invalid" not in report
    assert "oracle labels" not in report
    assert "not independently validated" in report
