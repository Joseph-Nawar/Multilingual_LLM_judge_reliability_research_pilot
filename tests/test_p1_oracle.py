from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from multilingual_judge_pilot.integrity import validate_counterfactual_pair, validate_scenario
from multilingual_judge_pilot.oracle import evaluate_history
from multilingual_judge_pilot.schema import (
    ActionContract,
    ActionField,
    ConstraintEventOrderError,
    DatasetKind,
    GrantPermission,
    HistoryState,
    Money,
    NumericBound,
    NumericConstraint,
    PermissionKey,
    PermissionGrant,
    Partition,
    RevokePermission,
    RestatePermission,
    RestateRequirement,
    ReviseRequirement,
    Scope,
    TemporalBound,
    TemporalConstraint,
    TransitionFamily,
    ValidityLabel,
    IntroduceRequirement,
    SchemaValidationError,
    stable_digest,
)
from p1_fixtures import (
    action,
    budget,
    history,
    numerical_revision_pair,
    no_change_control,
    scenario,
)


def test_equal_exact_budget_boundary_is_valid_and_just_over_is_invalid():
    constraint = budget("100.10")
    state = HistoryState(requirements=(constraint,))
    valid = history("exact-valid", state, scenario_id="budget-boundary", action_turn_index=2)
    invalid = history("exact-invalid", state, scenario_id="budget-boundary", action_turn_index=2)
    valid_scenario = scenario(
        (valid, invalid),
        scenario_id="budget-boundary",
        family=TransitionFamily.INTRODUCTION,
        scenario_action=action("100.10"),
    )
    over_scenario = replace(valid_scenario, action=action("100.1001"))

    assert evaluate_history(valid_scenario, valid.history_id).label is ValidityLabel.VALID
    over = evaluate_history(over_scenario, valid.history_id)
    assert over.label is ValidityLabel.INVALID
    assert "NUMERIC_ABOVE_MAXIMUM" in over.reason_codes


def test_exclusive_numeric_boundary_rejects_equality():
    constraint = budget("100", inclusive=False)
    state = HistoryState(requirements=(constraint,))
    h1 = history("exclusive-h1", state, scenario_id="exclusive", action_turn_index=2)
    h2 = history("exclusive-h2", state, scenario_id="exclusive", action_turn_index=2)
    s = scenario((h1, h2), scenario_id="exclusive", family=TransitionFamily.INTRODUCTION, scenario_action=action("100"))

    result = evaluate_history(s, h1.history_id)
    assert result.label is ValidityLabel.INVALID
    assert "NUMERIC_ABOVE_MAXIMUM" in result.reason_codes


def test_permission_granted_then_revoked_blocks_irreversible_action():
    permission = PermissionKey("cancel_booking", Scope.entity("booking-1"))
    events = (
        GrantPermission("grant-1", 1, 0, "grant-1", permission),
        RevokePermission("revoke-1", 2, 0, "grant-1"),
    )
    h1 = history("permission-h1", HistoryState(), events=events, scenario_id="permission")
    h2 = history("permission-h2", HistoryState(), events=events, scenario_id="permission")
    s = scenario(
        (h1, h2),
        scenario_id="permission",
        family=TransitionFamily.PERMISSION_REVOCATION,
        contract=ActionContract(irreversible=True, required_permissions=(permission,)),
    )

    result = evaluate_history(s, h1.history_id)
    assert result.label is ValidityLabel.INVALID
    assert "PERMISSION_REVOKED" in result.reason_codes


def test_permission_revocation_counterfactual_pair_has_opposite_oracle_labels():
    permission = PermissionKey("cancel_booking", Scope.entity("booking-1"))
    initial = HistoryState(grants=(PermissionGrant("pair-grant", permission),))
    revoked = history(
        "revoke-pair-invalid",
        initial,
        scenario_id="revoke-pair",
        events=(RevokePermission("pair-revocation", 2, 0, "pair-grant"),),
    )
    retained = history("revoke-pair-valid", initial, scenario_id="revoke-pair")
    s = scenario(
        (revoked, retained),
        scenario_id="revoke-pair",
        family=TransitionFamily.PERMISSION_REVOCATION,
        contract=ActionContract(irreversible=True, required_permissions=(permission,)),
    )

    assert validate_counterfactual_pair(s).labels == (ValidityLabel.INVALID, ValidityLabel.VALID)


def test_missing_permission_is_not_treated_as_granted():
    required = PermissionKey("approve_refund", Scope.entity("booking-1"))
    h1 = history("missing-permission-h1", HistoryState(), scenario_id="missing-permission")
    h2 = history("missing-permission-h2", HistoryState(), scenario_id="missing-permission")
    s = scenario(
        (h1, h2),
        scenario_id="missing-permission",
        family=TransitionFamily.PERMISSION_REVOCATION,
        contract=ActionContract(irreversible=True, required_permissions=(required,)),
    )

    result = evaluate_history(s, h1.history_id)
    assert result.label is ValidityLabel.INVALID
    assert "PERMISSION_NOT_GRANTED" in result.reason_codes


def test_irreversible_action_without_declared_permission_is_rejected():
    with pytest.raises(SchemaValidationError, match="irreversible action must declare"):
        ActionContract(irreversible=True, required_permissions=())


def test_numerical_revision_preserves_unrelated_active_requirement():
    initial = HistoryState(
        requirements=(
            budget("100"),
            NumericConstraint(
                "minimum-seats",
                Scope.global_scope(),
                "seats",
                minimum=NumericBound(Decimal("1"), inclusive=True),
            ),
        )
    )
    event = ReviseRequirement("revise-budget", 2, 0, "budget", budget("80", version=2))
    h1 = history("revision-h1", initial, events=(event,), scenario_id="preserve")
    h2 = history("revision-h2", initial, events=(event,), scenario_id="preserve")
    a = action(fields=(ActionField("price", Money(Decimal("80"), "USD")), ActionField("seats", Decimal("2"))))
    s = scenario((h1, h2), scenario_id="preserve", scenario_action=a)

    result = evaluate_history(s, h1.history_id)
    assert result.label is ValidityLabel.VALID
    assert {c.constraint_id for c in result.effective_state.active_requirements} == {"budget", "minimum-seats"}
    assert len(result.effective_state.superseded_requirements) == 1


def test_introduced_additional_restriction_is_enforced():
    introduced = budget("100")
    event = IntroduceRequirement("introduce-budget", 1, 0, introduced)
    h1 = history("intro-h1", HistoryState(), events=(event,), scenario_id="introduction")
    h2 = history("intro-h2", HistoryState(), events=(event,), scenario_id="introduction")
    s = scenario(
        (h1, h2),
        scenario_id="introduction",
        family=TransitionFamily.INTRODUCTION,
        scenario_action=action("101"),
    )

    result = evaluate_history(s, h1.history_id)
    assert result.label is ValidityLabel.INVALID
    assert "NUMERIC_ABOVE_MAXIMUM" in result.reason_codes


def test_introduction_counterfactual_pair_has_opposite_oracle_labels():
    restrictive = history(
        "intro-pair-invalid",
        HistoryState(),
        scenario_id="intro-pair",
        events=(IntroduceRequirement("intro-pair-event-a", 1, 0, budget("50")),),
    )
    permissive = history(
        "intro-pair-valid",
        HistoryState(),
        scenario_id="intro-pair",
        events=(IntroduceRequirement("intro-pair-event-b", 1, 0, budget("100")),),
    )
    s = scenario(
        (restrictive, permissive),
        scenario_id="intro-pair",
        family=TransitionFamily.INTRODUCTION,
    )

    assert validate_counterfactual_pair(s).labels == (ValidityLabel.INVALID, ValidityLabel.VALID)


def test_temporal_revision_compares_instants_across_offsets_and_inclusive_edge():
    initial = TemporalConstraint(
        "window",
        Scope.global_scope(),
        "starts_at",
        earliest=TemporalBound(datetime.fromisoformat("2026-11-01T09:00:00+03:00"), True),
        latest=TemporalBound(datetime.fromisoformat("2026-11-01T11:00:00+03:00"), True),
    )
    revised = TemporalConstraint(
        "window",
        Scope.global_scope(),
        "starts_at",
        earliest=TemporalBound(datetime.fromisoformat("2026-11-01T10:00:00+03:00"), True),
        latest=TemporalBound(datetime.fromisoformat("2026-11-01T12:00:00+03:00"), False),
        version=2,
    )
    initial_state = HistoryState(requirements=(initial,))
    event = ReviseRequirement("revise-window", 2, 0, "window", revised)
    h1 = history("time-h1", initial_state, events=(event,), scenario_id="time")
    h2 = history("time-h2", initial_state, events=(event,), scenario_id="time")
    action_at_boundary = action(
        fields=(ActionField("starts_at", datetime.fromisoformat("2026-11-01T09:00:00+02:00")),)
    )
    s = scenario((h1, h2), scenario_id="time", family=TransitionFamily.TEMPORAL_REVISION, scenario_action=action_at_boundary)

    assert evaluate_history(s, h1.history_id).label is ValidityLabel.VALID
    after_exclusive_end = replace(
        s,
        action=action(fields=(ActionField("starts_at", datetime.fromisoformat("2026-11-01T10:00:00+01:00")),)),
    )
    result = evaluate_history(after_exclusive_end, h1.history_id)
    assert result.label is ValidityLabel.INVALID
    assert "TEMPORAL_AFTER_LATEST" in result.reason_codes


def test_temporal_revision_counterfactual_pair_has_opposite_oracle_labels():
    initial = TemporalConstraint(
        "window",
        Scope.global_scope(),
        "starts_at",
        earliest=TemporalBound(datetime.fromisoformat("2026-10-29T11:00:00+00:00"), True),
        latest=TemporalBound(datetime.fromisoformat("2026-10-29T15:00:00+00:00"), True),
    )
    too_late = TemporalConstraint(
        "window",
        Scope.global_scope(),
        "starts_at",
        earliest=TemporalBound(datetime.fromisoformat("2026-10-29T13:00:00+00:00"), True),
        latest=TemporalBound(datetime.fromisoformat("2026-10-29T16:00:00+00:00"), True),
        version=2,
    )
    acceptable = TemporalConstraint(
        "window",
        Scope.global_scope(),
        "starts_at",
        earliest=TemporalBound(datetime.fromisoformat("2026-10-29T12:00:00+00:00"), True),
        latest=TemporalBound(datetime.fromisoformat("2026-10-29T14:00:00+00:00"), True),
        version=2,
    )
    invalid = history(
        "temporal-pair-invalid",
        HistoryState(requirements=(initial,)),
        scenario_id="temporal-pair",
        events=(ReviseRequirement("temporal-pair-event-a", 2, 0, "window", too_late),),
    )
    valid = history(
        "temporal-pair-valid",
        HistoryState(requirements=(initial,)),
        scenario_id="temporal-pair",
        events=(ReviseRequirement("temporal-pair-event-b", 2, 0, "window", acceptable),),
    )
    s = scenario(
        (invalid, valid),
        scenario_id="temporal-pair",
        family=TransitionFamily.TEMPORAL_REVISION,
        scenario_action=action(fields=(ActionField("starts_at", datetime.fromisoformat("2026-10-29T12:30:00+00:00")),)),
    )

    assert validate_counterfactual_pair(s).labels == (ValidityLabel.INVALID, ValidityLabel.VALID)


def test_naive_temporal_values_and_empty_intervals_are_rejected():
    with pytest.raises(SchemaValidationError, match="timezone-aware"):
        TemporalBound(datetime(2026, 11, 1, 9, 0), inclusive=True)
    with pytest.raises(SchemaValidationError, match="interval"):
        TemporalConstraint(
            "bad-window",
            Scope.global_scope(),
            "starts_at",
            earliest=TemporalBound(datetime.fromisoformat("2026-11-01T10:00:00+00:00"), False),
            latest=TemporalBound(datetime.fromisoformat("2026-11-01T10:00:00+00:00"), True),
        )


def test_multiple_ordered_events_apply_without_losing_prior_state():
    initial = HistoryState(requirements=(budget("100"),))
    events = (
        IntroduceRequirement(
            "introduce-minimum",
            1,
            0,
            NumericConstraint("minimum", Scope.global_scope(), "price", minimum=NumericBound(Decimal("10"), True), currency_code="USD"),
        ),
        ReviseRequirement("revise-budget", 2, 0, "budget", budget("80", version=2)),
    )
    h1 = history("ordered-h1", initial, events=events, scenario_id="ordered")
    h2 = history("ordered-h2", initial, events=events, scenario_id="ordered")
    s = scenario((h1, h2), scenario_id="ordered")

    result = evaluate_history(s, h1.history_id)
    assert result.label is ValidityLabel.VALID
    assert {c.constraint_id for c in result.effective_state.active_requirements} == {"budget", "minimum"}


def test_out_of_order_events_are_rejected_not_reordered():
    events = (
        IntroduceRequirement("later", 2, 0, budget("100")),
        RestateRequirement("earlier", 1, 0, "budget", budget("100")),
    )
    h = history("bad-order", HistoryState(), events=events, scenario_id="bad-order")
    s = scenario((h, replace(h, history_id="bad-order-2")), scenario_id="bad-order", family=TransitionFamily.INTRODUCTION)

    with pytest.raises(ConstraintEventOrderError, match="strictly ordered"):
        evaluate_history(s, h.history_id)


def test_repeated_requirement_introduction_is_rejected():
    events = (
        IntroduceRequirement("introduce-a", 1, 0, budget("100")),
        IntroduceRequirement("introduce-b", 2, 0, budget("90")),
    )
    h = history("repeat-intro", HistoryState(), events=events, scenario_id="repeat-intro")
    s = scenario((h, replace(h, history_id="repeat-intro-other")), scenario_id="repeat-intro", family=TransitionFamily.INTRODUCTION)

    with pytest.raises(SchemaValidationError, match="already used"):
        evaluate_history(s, h.history_id)


def test_no_change_restatement_records_identical_before_and_after_state():
    s = no_change_control()
    validate_scenario(s)
    result = evaluate_history(s, s.histories[0].history_id)
    restatement = next(step for step in result.event_audit if step.event_id == "control-1-restate-1")

    assert restatement.before_digest == restatement.after_digest
    assert result.effective_state.digest == result.state_digest


def test_permission_restatement_is_audited_as_an_exact_no_op():
    required = PermissionKey("cancel_booking", Scope.entity("booking-1"))
    other = PermissionKey("view_booking", Scope.entity("booking-1"))
    shared_requirement = budget("100")
    valid_state = HistoryState(
        requirements=(shared_requirement,),
        grants=(PermissionGrant("valid-grant", required),),
    )
    invalid_state = HistoryState(
        requirements=(shared_requirement,),
        grants=(PermissionGrant("invalid-grant", other),),
    )
    valid_history = history(
        "permission-control-valid",
        valid_state,
        scenario_id="permission-control",
        events=(RestatePermission("restate-valid-permission", 2, 0, "valid-grant", required),),
    )
    invalid_history = history(
        "permission-control-invalid",
        invalid_state,
        scenario_id="permission-control",
        events=(RestatePermission("restate-other-permission", 2, 0, "invalid-grant", other),),
    )
    control = scenario(
        (valid_history, invalid_history),
        scenario_id="permission-control",
        kind=DatasetKind.AUXILIARY_CONTROL,
        family=TransitionFamily.NO_CHANGE_RESTATEMENT,
        partition=Partition.LOCKED_AUXILIARY_CONTROL,
        contract=ActionContract(irreversible=True, required_permissions=(required,)),
    )

    validate_scenario(control)
    result = evaluate_history(control, valid_history.history_id)

    assert result.label is ValidityLabel.VALID
    assert result.event_audit[0].before_digest == result.event_audit[0].after_digest


def test_control_that_restates_a_different_value_is_rejected():
    s = no_change_control()
    bad_history = replace(
        s.histories[0],
        events=(RestateRequirement("secret-change", 2, 0, "budget", budget("80")),),
    )
    bad = replace(s, histories=(bad_history, s.histories[1]))

    with pytest.raises(SchemaValidationError, match="restatement"):
        validate_scenario(bad)


def test_no_change_control_rejects_a_hidden_permission_change():
    s = no_change_control()
    hidden_change = GrantPermission(
        "secret-grant-event",
        2,
        0,
        "secret-grant",
        PermissionKey("cancel_booking", Scope.entity("booking-1")),
    )
    bad_history = replace(s.histories[0], events=(hidden_change,))

    with pytest.raises(SchemaValidationError, match="cannot contain state-changing events"):
        validate_scenario(replace(s, histories=(bad_history, s.histories[1])))


def test_oracle_establishes_opposite_labels_for_identical_counterfactual_action():
    s = numerical_revision_pair()
    pair = validate_counterfactual_pair(s)

    assert pair.labels == (ValidityLabel.INVALID, ValidityLabel.VALID)
    assert pair.action_fingerprint == stable_digest(s.action)


def test_incorrect_supplied_counterfactual_label_is_rejected_by_oracle():
    s = numerical_revision_pair(declared_labels=(ValidityLabel.VALID, ValidityLabel.INVALID))
    with pytest.raises(SchemaValidationError, match="declared label"):
        validate_counterfactual_pair(s)


def test_missing_action_parameter_is_explicit_error():
    s = numerical_revision_pair()
    bad_action = action(fields=())
    malformed = replace(s, action=bad_action)

    with pytest.raises(SchemaValidationError, match="missing for active requirement"):
        evaluate_history(malformed, malformed.histories[0].history_id)


def test_action_value_type_must_match_public_tool_schema():
    s = numerical_revision_pair()
    bad_action = action(fields=(ActionField("price", "not-a-price"),))

    with pytest.raises(SchemaValidationError, match="type disagrees with the public tool schema"):
        replace(s, action=bad_action)


def test_binary_float_action_value_is_rejected_at_schema_boundary():
    with pytest.raises(SchemaValidationError, match="unsupported type"):
        ActionField("price", 0.1)
