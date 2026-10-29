"""Adversarial regression tests for the independent P1 research audit."""

from dataclasses import replace
from decimal import Decimal

import pytest

from multilingual_judge_pilot.integrity import validate_counterfactual_pair, validate_scenario
from multilingual_judge_pilot.iso4217_snapshot import (
    CURRENCY_REGISTRY_SOURCE_SHA256,
    CURRENCY_REGISTRY_VERSION,
    SUPPORTED_CURRENCY_CODES,
)
from multilingual_judge_pilot.oracle import evaluate_history
from multilingual_judge_pilot.serialization import build_judge_facing_item, judge_facing_to_dict
from multilingual_judge_pilot.schema import (
    ActionField,
    ConversationTurn,
    HistoryState,
    IntroduceRequirement,
    Language,
    Money,
    NumericBound,
    NumericConstraint,
    ReviseRequirement,
    RestateRequirement,
    SchemaValidationError,
    Scope,
    TextSegment,
    TextSegmentKind,
    ToolParameterSchema,
    TurnRole,
    TransitionFamily,
    ValidityLabel,
)
from p1_fixtures import action, budget, english_variant, history, numerical_revision_pair, scenario, with_language_variants


def _minimum_seats(value: str, *, version: int = 1, scope: Scope | None = None) -> NumericConstraint:
    return NumericConstraint(
        "minimum-seats",
        scope or Scope.global_scope(),
        "seats",
        minimum=NumericBound(Decimal(value), inclusive=True),
        version=version,
    )


def test_primary_pair_rejects_different_initial_budgets_with_same_irrelevant_revision():
    initial_valid = HistoryState(requirements=(budget("100"), _minimum_seats("1")))
    initial_invalid = HistoryState(requirements=(budget("50"), _minimum_seats("1")))
    first = history(
        "causal-initial-h1",
        initial_valid,
        scenario_id="causal-initial",
        events=(ReviseRequirement("causal-initial-e1", 2, 0, "minimum-seats", _minimum_seats("2", version=2)),),
    )
    second = history(
        "causal-initial-h2",
        initial_invalid,
        scenario_id="causal-initial",
        events=(ReviseRequirement("causal-initial-e2", 2, 0, "minimum-seats", _minimum_seats("2", version=2)),),
    )
    action_with_seats = action(fields=(
        ActionField("price", action().fields[0].value),
        ActionField("seats", Decimal("2")),
    ))
    candidate = scenario(
        (first, second),
        scenario_id="causal-initial",
        family=TransitionFamily.NUMERICAL_REVISION,
        scenario_action=action_with_seats,
    )

    with pytest.raises(SchemaValidationError, match="initial.*equivalent|equivalent.*initial"):
        validate_counterfactual_pair(candidate)


def test_primary_pair_rejects_declared_family_event_that_does_not_explain_reversal():
    other_scope = Scope.entity("booking-2")
    other_requirement = NumericConstraint(
        "other-price",
        other_scope,
        "other-price",
        maximum=NumericBound(Decimal("100"), inclusive=True),
        currency_code="USD",
    )
    initial_valid = HistoryState(requirements=(budget("100"), other_requirement))
    initial_invalid = HistoryState(requirements=(budget("50"), other_requirement))
    first = history(
        "causal-family-h1",
        initial_valid,
        scenario_id="causal-family",
        events=(ReviseRequirement("causal-family-e1", 2, 0, "other-price", replace(other_requirement, maximum=NumericBound(Decimal("40"), True), version=2)),),
    )
    second = history(
        "causal-family-h2",
        initial_invalid,
        scenario_id="causal-family",
        events=(ReviseRequirement("causal-family-e2", 2, 0, "other-price", replace(other_requirement, maximum=NumericBound(Decimal("45"), True), version=2)),),
    )
    # The revision payloads are structurally valid but apply only to another entity.
    candidate = scenario((first, second), scenario_id="causal-family", family=TransitionFamily.NUMERICAL_REVISION)

    with pytest.raises(SchemaValidationError, match="initial.*equivalent|equivalent.*initial|decision-relevant|causal"):
        validate_counterfactual_pair(candidate)


def test_primary_pair_rejects_revision_that_only_increments_version():
    initial = HistoryState(requirements=(budget("100"),))
    version_only = replace(budget("100"), version=2)
    first = history(
        "causal-version-h1",
        initial,
        scenario_id="causal-version",
        events=(ReviseRequirement("causal-version-e1", 2, 0, "budget", version_only),),
    )
    second = history(
        "causal-version-h2",
        initial,
        scenario_id="causal-version",
        events=(ReviseRequirement("causal-version-e2", 2, 0, "budget", budget("50", version=2)),),
    )
    candidate = scenario((first, second), scenario_id="causal-version")

    with pytest.raises(SchemaValidationError, match="meaningful|semantic|state change"):
        validate_counterfactual_pair(candidate)


def test_primary_pair_rejects_labels_that_already_differ_before_decisive_revision():
    first = history(
        "causal-prefix-h1",
        HistoryState(requirements=(budget("100"),)),
        scenario_id="causal-prefix",
        events=(ReviseRequirement("causal-prefix-e1", 2, 0, "budget", budget("50", version=2)),),
    )
    second = history(
        "causal-prefix-h2",
        HistoryState(requirements=(budget("50"),)),
        scenario_id="causal-prefix",
        events=(ReviseRequirement("causal-prefix-e2", 2, 0, "budget", budget("100", version=2)),),
    )
    candidate = scenario((first, second), scenario_id="causal-prefix")

    with pytest.raises(SchemaValidationError, match="initial.*equivalent|equivalent.*initial|before.*decisive|pre-decisive"):
        validate_counterfactual_pair(candidate)


def test_primary_pair_rejects_pre_decisive_label_reversal_explained_by_another_transition():
    outside_scope = Scope.entity("booking-2")
    unrelated_requirement = NumericConstraint(
        "outside-limit",
        outside_scope,
        "other-price",
        maximum=NumericBound(Decimal("100"), inclusive=True),
        currency_code="USD",
    )
    initial = HistoryState(requirements=(budget("100"),))
    first = history(
        "prelabel-h1",
        initial,
        scenario_id="prelabel",
        events=(
            ReviseRequirement("prelabel-earlier-revision", 1, 0, "budget", budget("50", version=2)),
            IntroduceRequirement("prelabel-unrelated-introduction-a", 2, 0, unrelated_requirement),
        ),
    )
    second = history(
        "prelabel-h2",
        initial,
        scenario_id="prelabel",
        events=(
            RestateRequirement("prelabel-earlier-restatement", 1, 0, "budget", budget("100")),
            IntroduceRequirement("prelabel-unrelated-introduction-b", 2, 0, replace(unrelated_requirement, constraint_id="outside-limit-b")),
        ),
    )
    candidate = scenario((first, second), scenario_id="prelabel", family=TransitionFamily.INTRODUCTION)

    with pytest.raises(SchemaValidationError, match="labels must agree before the decisive"):
        validate_counterfactual_pair(candidate)


def test_primary_pair_rejects_inconsistent_action_decision_points():
    candidate = numerical_revision_pair()
    histories = (candidate.histories[0], replace(candidate.histories[1], action_turn_index=5))
    candidate = replace(candidate, histories=histories)

    with pytest.raises(SchemaValidationError, match="action decision point|action turn.*match|chronolog"):
        validate_counterfactual_pair(candidate)


def test_primary_pair_accepts_controlled_numeric_revision_and_control_keeps_distinct_initial_states():
    candidate = numerical_revision_pair()

    assert validate_counterfactual_pair(candidate).labels == (ValidityLabel.INVALID, ValidityLabel.VALID)


def test_primary_pair_accepts_equivalent_initial_and_nondecisive_states_with_different_bookkeeping_ids():
    first_initial = replace(budget("100"), constraint_id="budget-left", version=1)
    second_initial = replace(budget("100"), constraint_id="budget-right", version=3)
    first_restatement = RestateRequirement("bookkeeping-left-restate", 1, 0, "budget-left", first_initial)
    second_restatement = RestateRequirement("bookkeeping-right-restate", 1, 0, "budget-right", second_initial)
    first = history(
        "bookkeeping-h1",
        HistoryState(requirements=(first_initial,)),
        scenario_id="bookkeeping",
        events=(
            first_restatement,
            ReviseRequirement("bookkeeping-left-revision", 2, 0, "budget-left", replace(budget("50", version=2), constraint_id="budget-left")),
        ),
    )
    second = history(
        "bookkeeping-h2",
        HistoryState(requirements=(second_initial,)),
        scenario_id="bookkeeping",
        events=(
            second_restatement,
            ReviseRequirement("bookkeeping-right-revision", 2, 0, "budget-right", replace(budget("80", version=4), constraint_id="budget-right")),
        ),
    )
    candidate = scenario((first, second), scenario_id="bookkeeping")

    assert validate_counterfactual_pair(candidate).labels == (ValidityLabel.INVALID, ValidityLabel.VALID)


def test_primary_pair_rejects_different_nondecisive_conversation_context():
    candidate = numerical_revision_pair()
    first_variant = english_variant(history_id=candidate.histories[0].history_id)
    second_variant = english_variant(history_id=candidate.histories[1].history_id)
    changed_initial = replace(
        second_variant.turns[0].segments[0],
        text="Synthetic but different initial context.",
    )
    second_variant = replace(
        second_variant,
        turns=(replace(second_variant.turns[0], segments=(changed_initial,)), second_variant.turns[1]),
    )
    candidate = with_language_variants(candidate, (first_variant, second_variant))

    with pytest.raises(SchemaValidationError, match="non-decisive conversation context"):
        validate_scenario(candidate)


def test_primary_pair_rejects_decisive_turn_after_action():
    candidate = numerical_revision_pair()
    histories = tuple(replace(row, decisive_turn_index=5) for row in candidate.histories)
    candidate = replace(candidate, histories=histories)

    with pytest.raises(SchemaValidationError, match="decisive.*precede|chronolog"):
        validate_scenario(candidate)


def test_formal_event_turn_requires_a_user_conversation_turn():
    candidate = numerical_revision_pair()
    histories = []
    for row in candidate.histories:
        restatement = RestateRequirement(
            f"{row.history_id}-pre-restatement",
            1,
            0,
            "budget",
            budget("100"),
        )
        histories.append(replace(row, events=(restatement, row.events[0]), decisive_event_ids=(row.events[0].event_id,)))
    variant = english_variant(history_id=candidate.histories[0].history_id)
    candidate = with_language_variants(replace(candidate, histories=tuple(histories)), (variant,))

    with pytest.raises(SchemaValidationError, match="formal event.*user|user.*formal event"):
        validate_scenario(candidate)


def test_formal_decisive_event_cannot_correspond_to_a_non_user_turn():
    candidate = numerical_revision_pair()
    history_row = candidate.histories[0]
    variant = english_variant(history_id=history_row.history_id)
    non_user_decisive_turn = replace(variant.turns[1], role=TurnRole.ASSISTANT)

    with pytest.raises(SchemaValidationError, match="decisive constraint turns must be user turns"):
        replace(variant, turns=(variant.turns[0], non_user_decisive_turn))


def test_language_variant_decisive_turn_must_match_formal_decisive_event():
    candidate = numerical_revision_pair()
    shifted_histories = []
    variants = []
    for row in candidate.histories:
        shifted_event = replace(row.events[0], turn_index=3)
        shifted = replace(row, events=(shifted_event,), decisive_turn_index=3)
        shifted_histories.append(shifted)
        variant = english_variant(history_id=row.history_id)
        decisive_turn = replace(
            variant.turns[1],
            turn_index=3,
            segments=tuple(replace(segment, segment_id=f"{segment.segment_id}-at-3") for segment in variant.turns[1].segments),
        )
        variants.append(replace(variant, turns=(*variant.turns, decisive_turn)))
    candidate = with_language_variants(replace(candidate, histories=tuple(shifted_histories)), tuple(variants))

    with pytest.raises(SchemaValidationError, match="decisive turn.*formal|formal.*decisive turn"):
        validate_scenario(candidate)


def test_intermediate_non_decisive_turn_is_allowed_when_chronology_is_consistent():
    candidate = numerical_revision_pair()
    variant = english_variant(history_id=candidate.histories[0].history_id)
    intermediate = ConversationTurn(
        1,
        TurnRole.ASSISTANT,
        Language.ENGLISH,
        (TextSegment("intermediate", TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE, "Synthetic acknowledgement."),),
    )
    variant = replace(variant, turns=(variant.turns[0], intermediate, variant.turns[1]))
    candidate = with_language_variants(candidate, (variant,))

    validate_scenario(candidate)


def test_judge_projection_rejects_post_action_conversation_information():
    candidate = numerical_revision_pair()
    variant = english_variant(history_id=candidate.histories[0].history_id)
    after_action = ConversationTurn(
        candidate.histories[0].action_turn_index,
        TurnRole.USER,
        Language.ENGLISH,
        (TextSegment("after-action", TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE, "Synthetic later authorization."),),
    )
    variant = replace(variant, turns=(*variant.turns, after_action))
    candidate = with_language_variants(candidate, (variant,))

    with pytest.raises(SchemaValidationError, match="after the action|post-action"):
        build_judge_facing_item(
            candidate,
            candidate.histories[0].history_id,
            variant.derivative_id,
            opaque_item_id="opaque-post-action-fixture",
        )


def test_missing_required_tool_parameter_is_rejected():
    candidate = numerical_revision_pair()
    tool = replace(candidate.public_tool_schema, parameters=(ToolParameterSchema("price", "money", required=True),))
    action_without_price = action(fields=())

    with pytest.raises(SchemaValidationError, match="missing required public tool parameter"):
        replace(candidate, action=action_without_price, public_tool_schema=tool)


def test_optional_tool_parameter_may_be_absent():
    candidate = numerical_revision_pair()
    tool = replace(
        candidate.public_tool_schema,
        parameters=(*candidate.public_tool_schema.parameters, ToolParameterSchema("note", "string", required=False)),
    )
    validate_scenario(replace(candidate, public_tool_schema=tool))


def test_judge_public_schema_reports_required_parameter_policy():
    candidate = numerical_revision_pair()
    variant = english_variant(history_id=candidate.histories[0].history_id)
    candidate = with_language_variants(candidate, (variant,))
    item = build_judge_facing_item(
        candidate,
        candidate.histories[0].history_id,
        variant.derivative_id,
        opaque_item_id="opaque-required-schema-fixture",
    )

    assert judge_facing_to_dict(item)["public_tool_schema"]["parameters"] == [
        {"name": "price", "type": "money", "required": True}
    ]


def test_action_cannot_supply_a_parameter_undeclared_by_the_public_tool_schema():
    candidate = numerical_revision_pair()
    extra_fields = (
        *candidate.action.fields,
        ActionField("unexpected", "not-declared"),
    )
    with pytest.raises(SchemaValidationError, match="absent from the public tool schema"):
        replace(candidate, action=replace(candidate.action, fields=extra_fields))


def test_valid_required_tool_call_passes_schema_validation_and_oracle():
    candidate = numerical_revision_pair()
    validate_scenario(candidate)
    labels = tuple(evaluate_history(candidate, row.history_id).label for row in candidate.histories)

    assert labels == (ValidityLabel.INVALID, ValidityLabel.VALID)


def test_currency_code_must_exist_in_the_pinned_iso_snapshot():
    with pytest.raises(SchemaValidationError, match="fixed .* ISO 4217 snapshot"):
        NumericConstraint(
            "invalid-currency",
            Scope.global_scope(),
            "price",
            maximum=NumericBound(Decimal("100"), True),
            currency_code="AAA",
        )

    assert Money(Decimal("1.00"), "AED").currency_code == "AED"
    assert len(SUPPORTED_CURRENCY_CODES) == 178
    assert CURRENCY_REGISTRY_VERSION == "SIX-ISO-4217-List-One-2026-09-17"
    assert CURRENCY_REGISTRY_SOURCE_SHA256 == "33139b438657d1cee116ba737807ea71d19d6de4b90f799a09c56f0cc6a1b0ff"


def test_tool_parameter_required_flag_is_strictly_boolean():
    with pytest.raises(SchemaValidationError, match="required status must be boolean"):
        ToolParameterSchema("price", "money", required=1)
