from dataclasses import replace
from decimal import Decimal

import pytest

from multilingual_judge_pilot.integrity import (
    DuplicateIdentifierError,
    PartitionIntegrityError,
    ProvenanceError,
    assign_partitions,
    audit_duplicates,
    partition_manifest_json,
    validate_match_records,
    validate_partition_manifest,
    validate_language_variant_coverage,
    validate_scenario,
    validate_scenario_collection,
)
from multilingual_judge_pilot.schema import (
    DatasetKind,
    Domain,
    Language,
    LanguageCondition,
    MatchQuality,
    MatchRecord,
    Money,
    Partition,
    PartitionSubject,
    TransitionFamily,
    TurnLanguageAssignment,
    SchemaValidationError,
)
from p1_fixtures import (
    action,
    english_variant,
    numerical_revision_pair,
    no_change_control,
    structural_language_variant,
    with_language_variants,
)


def full_partition_subjects():
    subjects = []
    for domain in Domain:
        for family in (
            TransitionFamily.INTRODUCTION,
            TransitionFamily.NUMERICAL_REVISION,
            TransitionFamily.PERMISSION_REVOCATION,
            TransitionFamily.TEMPORAL_REVISION,
        ):
            for index in range(4):
                subjects.append(
                    PartitionSubject(
                        scenario_id=f"{domain.value}-{family.value}-{index}",
                        kind=DatasetKind.PRIMARY,
                        domain=domain,
                        transition_family=family,
                    )
                )
    subjects.extend(
        PartitionSubject(
            scenario_id=f"control-{index}",
            kind=DatasetKind.AUXILIARY_CONTROL,
            domain=Domain.BOOKING,
            transition_family=TransitionFamily.NO_CHANGE_RESTATEMENT,
        )
        for index in range(12)
    )
    return tuple(subjects)


def test_partition_allocator_is_deterministic_and_stratified():
    subjects = full_partition_subjects()
    first = assign_partitions(subjects, seed="p1-review-seed")
    reversed_input = assign_partitions(tuple(reversed(subjects)), seed="p1-review-seed")

    assert first == reversed_input
    validate_partition_manifest(subjects, first)
    primary_dev = [entry for entry in first if entry.kind is DatasetKind.PRIMARY and entry.partition is Partition.DEVELOPMENT]
    primary_locked = [entry for entry in first if entry.kind is DatasetKind.PRIMARY and entry.partition is Partition.LOCKED_PRIMARY]
    controls = [entry for entry in first if entry.kind is DatasetKind.AUXILIARY_CONTROL]
    assert len(primary_dev) == 12
    assert len(primary_locked) == 36
    assert len(controls) == 12
    assert all(entry.partition is Partition.LOCKED_AUXILIARY_CONTROL for entry in controls)
    assert partition_manifest_json(first, seed="p1-review-seed") == partition_manifest_json(reversed_input, seed="p1-review-seed")


def test_partition_manifest_rejects_incorrect_primary_cell_allocation():
    subjects = full_partition_subjects()
    assignments = assign_partitions(subjects, seed="p1-review-seed")
    changed = list(assignments)
    first_dev = next(i for i, row in enumerate(changed) if row.partition is Partition.DEVELOPMENT)
    dev_row = changed[first_dev]
    other_cell_locked = next(
        i
        for i, row in enumerate(changed)
        if row.kind is DatasetKind.PRIMARY
        and row.partition is Partition.LOCKED_PRIMARY
        and (row.domain, row.transition_family) != (dev_row.domain, dev_row.transition_family)
    )
    changed[first_dev] = replace(dev_row, partition=Partition.LOCKED_PRIMARY)
    changed[other_cell_locked] = replace(changed[other_cell_locked], partition=Partition.DEVELOPMENT)

    with pytest.raises(PartitionIntegrityError, match="one development scenario per cell"):
        validate_partition_manifest(subjects, tuple(changed))


def test_derivative_cannot_cross_canonical_scenario_partition():
    s = numerical_revision_pair()
    variant = english_variant(history_id=s.histories[0].history_id)
    bad_variant = replace(variant, partition=Partition.DEVELOPMENT)
    bad = replace(s, language_variants=(bad_variant,))

    with pytest.raises(PartitionIntegrityError, match="derivative partition"):
        validate_scenario(bad)


def test_shared_template_across_partitions_is_reported_not_counted_as_independent():
    development = numerical_revision_pair(scenario_id="dev-template", partition=Partition.DEVELOPMENT)
    locked = numerical_revision_pair(scenario_id="locked-template", partition=Partition.LOCKED_PRIMARY)
    locked = replace(locked, action=action("76"))

    audit = audit_duplicates((development, locked))
    assert audit.cross_partition_templates == ("fixture-template@1",)
    assert audit.template_counts["fixture-template@1"] == 2
    assert not audit.exact_duplicate_groups


def test_exact_scenario_duplicates_ignore_identifiers_but_compare_content():
    first = numerical_revision_pair(scenario_id="source-a")
    second = numerical_revision_pair(scenario_id="source-b")
    different = numerical_revision_pair(scenario_id="source-c")
    different_action = replace(different, action=replace(different.action, fields=()))

    audit = audit_duplicates((first, second, different_action))
    assert len(audit.exact_duplicate_groups) == 1
    assert set(audit.exact_duplicate_groups[0].scenario_ids) == {"source-a", "source-b"}


def test_normalized_text_duplicates_are_reported_without_semantic_claims():
    first = numerical_revision_pair(scenario_id="text-a")
    second = numerical_revision_pair(scenario_id="text-b")
    first_variant = english_variant(scenario_id="text-a", history_id=first.histories[0].history_id)
    second_variant = english_variant(scenario_id="text-b", history_id=second.histories[0].history_id)
    changed_turn = replace(
        second_variant.turns[0],
        segments=(replace(second_variant.turns[0].segments[0], text="  SYNTHETIC   INITIAL REQUEST. "),),
    )
    second_variant = replace(second_variant, turns=(changed_turn, second_variant.turns[1]))
    first = replace(first, language_variants=(first_variant,))
    second = replace(second, language_variants=(second_variant,))

    audit = audit_duplicates((first, second))
    assert audit.normalized_text_duplicate_groups
    assert any("text-a" in group.scenario_ids and "text-b" in group.scenario_ids for group in audit.normalized_text_duplicate_groups)
    assert audit.semantic_equivalence_was_assessed is False


def test_normalized_text_duplicate_audit_does_not_flag_repeated_text_within_one_scenario():
    first = numerical_revision_pair(scenario_id="same-scenario")
    first_variant = english_variant(scenario_id="same-scenario", history_id=first.histories[0].history_id)
    second_variant = replace(
        first_variant,
        derivative_id=f"{first.histories[1].history_id}-en-en",
        parent_history_id=first.histories[1].history_id,
    )
    first = replace(first, language_variants=(first_variant, second_variant))

    audit = audit_duplicates((first,))

    assert not audit.normalized_text_duplicate_groups


def test_language_variant_invariant_literals_must_match_exactly():
    s = numerical_revision_pair()
    english = english_variant(history_id=s.histories[0].history_id)
    mixed_assignment = replace(english.assignment, condition=LanguageCondition.EN_AR)
    # Empty synthetic natural-language span: this exercises language hooks
    # without creating an Arabic translation or study-language example.
    empty_natural_span = replace(english.turns[1].segments[0], text="")
    mixed_later_turn = replace(
        english.turns[1],
        language=Language.MSA,
        segments=(empty_natural_span, english.turns[1].segments[1]),
    )
    mixed = replace(
        english,
        derivative_id=f"{english.derivative_id}-mixed",
        assignment=mixed_assignment,
        turns=(english.turns[0], mixed_later_turn),
    )
    changed_literal = replace(mixed.turns[1].segments[1], text="booking_record")
    bad_mixed = replace(mixed, turns=(mixed.turns[0], replace(mixed.turns[1], segments=(mixed.turns[1].segments[0], changed_literal))))
    with_bad_literal = with_language_variants(s, (english, bad_mixed))

    with pytest.raises(SchemaValidationError, match="invariant literal"):
        validate_scenario(with_bad_literal)


def test_language_coverage_hook_requires_all_four_conditions_per_history():
    s = numerical_revision_pair()
    variants = tuple(
        structural_language_variant(
            scenario_id=s.scenario_id,
            history_id=history.history_id,
            partition=s.partition,
            condition=condition,
        )
        for history in s.histories
        for condition in LanguageCondition
    )
    complete = with_language_variants(s, variants)

    validate_language_variant_coverage(complete)

    incomplete = with_language_variants(complete, variants[:-1])
    with pytest.raises(SchemaValidationError, match="complete four-condition coverage"):
        validate_language_variant_coverage(incomplete)


def test_unmatched_controls_and_partial_matches_are_explicit_and_do_not_reassign_partitions():
    primary = numerical_revision_pair(scenario_id="primary-locked", partition=Partition.LOCKED_PRIMARY)
    control = no_change_control(scenario_id="control-locked")
    unmatched_control = no_change_control(scenario_id="control-unmatched")
    primary = replace(primary, match_set_id="match-1")
    control = replace(control, match_set_id="match-1")
    partial = MatchRecord(
        match_set_id="match-1",
        primary_scenario_id=primary.scenario_id,
        control_scenario_id=control.scenario_id,
        quality=MatchQuality.PARTIAL,
        matched_dimensions=("domain", "action_complexity"),
        note="Synthetic test record; not a study match.",
    )
    unmatched = MatchRecord(
        match_set_id="match-2",
        primary_scenario_id=None,
        control_scenario_id=unmatched_control.scenario_id,
        quality=MatchQuality.UNMATCHED,
        matched_dimensions=(),
        note="No eligible primary fixture.",
    )

    validate_match_records((primary, control, unmatched_control), (partial, unmatched))
    assert primary.partition is Partition.LOCKED_PRIMARY
    assert control.partition is Partition.LOCKED_AUXILIARY_CONTROL


def test_locked_control_cannot_be_matched_to_development_primary():
    primary = numerical_revision_pair(scenario_id="primary-dev", partition=Partition.DEVELOPMENT)
    control = no_change_control(scenario_id="control-locked")
    primary = replace(primary, match_set_id="match-dev-lock")
    control = replace(control, match_set_id="match-dev-lock")
    match = MatchRecord(
        match_set_id="match-dev-lock",
        primary_scenario_id=primary.scenario_id,
        control_scenario_id=control.scenario_id,
        quality=MatchQuality.PARTIAL,
        matched_dimensions=("domain",),
        note="Synthetic test record.",
    )

    with pytest.raises(PartitionIntegrityError, match="locked primary"):
        validate_match_records((primary, control), (match,))


def test_scenario_collection_rejects_duplicate_ids_and_unresolved_derivative_provenance():
    first = numerical_revision_pair(scenario_id="duplicate-id")
    second = numerical_revision_pair(scenario_id="duplicate-id")
    with pytest.raises(DuplicateIdentifierError, match="scenario ID"):
        validate_scenario_collection((first, second))

    broken_provenance = replace(first.provenance, derivative_ids=("missing-history",))
    broken = replace(first, provenance=broken_provenance)
    with pytest.raises(ProvenanceError, match="derivative provenance"):
        validate_scenario(broken)


def test_provenance_must_list_language_derivative_ids():
    s = numerical_revision_pair()
    variant = english_variant(history_id=s.histories[0].history_id)
    with_variant = replace(s, language_variants=(variant,))

    with pytest.raises(ProvenanceError, match="derivative provenance"):
        validate_scenario(with_variant)


def test_parent_scenario_derivation_cannot_cross_partition():
    development = numerical_revision_pair(scenario_id="source-dev", partition=Partition.DEVELOPMENT)
    locked = numerical_revision_pair(scenario_id="derived-locked", partition=Partition.LOCKED_PRIMARY)
    locked = replace(locked, provenance=replace(locked.provenance, parent_scenario_id=development.scenario_id))

    with pytest.raises(PartitionIntegrityError, match="relationship crosses partitions"):
        validate_scenario_collection((development, locked))


def test_duplicate_event_identifiers_and_unresolved_revision_targets_are_rejected():
    s = numerical_revision_pair()
    duplicate_event = replace(s.histories[1].events[0], event_id=s.histories[0].events[0].event_id)
    histories = (s.histories[0], replace(s.histories[1], events=(duplicate_event,)))
    with pytest.raises(DuplicateIdentifierError, match="event ID"):
        validate_scenario(replace(s, histories=histories))

    missing_target = replace(s.histories[0].events[0], constraint_id="missing")
    malformed = replace(s, histories=(replace(s.histories[0], events=(missing_target,)), s.histories[1]))
    with pytest.raises(SchemaValidationError, match="active requirement"):
        validate_scenario(malformed)


def test_language_assignment_enforces_condition_and_fixed_english_instruction():
    bad = TurnLanguageAssignment(
        condition=LanguageCondition.EN_AR,
        initial_turn_index=0,
        decisive_turn_index=2,
        judge_instruction_language=Language.MSA,
    )
    with pytest.raises(SchemaValidationError, match="judge instruction language"):
        bad.validate_turn_languages({0: Language.ENGLISH, 2: Language.MSA})


def test_public_currency_code_shape_rejects_non_iso_format():
    with pytest.raises(SchemaValidationError, match="three-letter uppercase"):
        Money(Decimal("2.00"), "usd")
