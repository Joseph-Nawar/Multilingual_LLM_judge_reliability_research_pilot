import json
from dataclasses import replace

import pytest

from multilingual_judge_pilot.integrity import validate_scenario
from multilingual_judge_pilot.oracle import evaluate_history
from multilingual_judge_pilot.schema import (
    ActionContract,
    DatasetKind,
    HistoryState,
    Language,
    LanguageCondition,
    LanguageVariant,
    ExclusionRecord,
    PermissionKey,
    PermissionGrant,
    Partition,
    PublicToolSchema,
    RevisionRecord,
    Scope,
    SchemaValidationError,
    RestatePermission,
    TransitionFamily,
    ToolParameterSchema,
    TurnLanguageAssignment,
    TurnLanguageOverride,
    ValidationStatus,
)
from multilingual_judge_pilot.serialization import (
    build_judge_facing_item,
    JudgeConversationTurn,
    JudgeFacingItem,
    judge_facing_to_dict,
    judge_facing_to_json,
    scenario_from_json,
    scenario_to_json,
)
from p1_fixtures import action, english_variant, history, numerical_revision_pair, scenario, with_language_variants


def test_versioned_scenario_json_round_trips_and_is_byte_deterministic():
    s = numerical_revision_pair()
    encoded = scenario_to_json(s)
    decoded = scenario_from_json(encoded)

    assert decoded == s
    assert json.loads(encoded)["schema_version"] == "1.0"
    assert scenario_to_json(decoded) == encoded


def test_scenario_parser_rejects_unknown_fields_instead_of_ignoring_them():
    payload = json.loads(scenario_to_json(numerical_revision_pair()))
    payload["oracle_verdict"] = "valid"

    with pytest.raises(SchemaValidationError, match="unknown field"):
        scenario_from_json(json.dumps(payload))


def test_language_assignment_maps_initial_and_decisive_turns_without_translation_claim():
    assignment = TurnLanguageAssignment(
        condition=LanguageCondition.AR_EN,
        initial_turn_index=0,
        decisive_turn_index=3,
        approved_other_turn_overrides=(TurnLanguageOverride(2, Language.MSA, "Synthetic structural test override."),),
    )
    assignment.validate_turn_languages({0: Language.MSA, 1: Language.MSA, 2: Language.MSA, 3: Language.ENGLISH})
    with pytest.raises(SchemaValidationError, match="decisive turn language"):
        assignment.validate_turn_languages({0: Language.MSA, 1: Language.MSA, 2: Language.MSA, 3: Language.MSA})


def test_judge_projection_is_an_allowlist_and_excludes_reference_and_provenance_fields():
    s = numerical_revision_pair()
    variant = english_variant(history_id=s.histories[0].history_id)
    s = with_language_variants(s, (variant,))
    validate_scenario(s)
    item = build_judge_facing_item(
        s,
        s.histories[0].history_id,
        variant.derivative_id,
        opaque_item_id="item-opaque-fixture-001",
    )
    encoded = judge_facing_to_json(item)
    payload = json.loads(encoded)
    serialized = encoded.casefold()

    assert set(payload) == {"item_id", "conversation", "action", "public_tool_schema"}
    assert payload["action"]["tool_name"] == s.action.tool_name
    assert "synthetic revised requirement" in payload["conversation"][1]["content"].casefold()
    assert "booking_id" in payload["conversation"][1]["content"]
    for forbidden in (
        "scenario_id",
        "history_id",
        "pair_id",
        "declared_label",
        "validity",
        "effective_state",
        "oracle",
        "reason_code",
        "template_id",
        "semantic_recipe",
        "provenance",
        "action_contract",
        "superseded_requirements",
    ):
        assert forbidden not in serialized


def test_judge_projection_rejects_an_item_id_equal_to_internal_template_metadata():
    from p1_fixtures import with_language_variants

    s = numerical_revision_pair()
    variant = english_variant(history_id=s.histories[0].history_id)
    s = with_language_variants(s, (variant,))

    with pytest.raises(SchemaValidationError, match="opaque item ID"):
        build_judge_facing_item(
            s,
            s.histories[0].history_id,
            variant.derivative_id,
            opaque_item_id=s.provenance.authoring_template_id,
        )


def test_repeated_oracle_serialization_is_identical_and_does_not_use_randomness():
    s = numerical_revision_pair()
    encoded = scenario_to_json(s)
    first = evaluate_history(s, s.histories[0].history_id)
    second = evaluate_history(s, s.histories[0].history_id)

    assert scenario_to_json(s) == encoded
    assert scenario_from_json(encoded) == scenario_from_json(encoded)
    assert first == second
    assert first.state_digest == second.state_digest


def test_schema_does_not_mark_language_variants_as_semantically_validated_by_itself():
    s = numerical_revision_pair()
    variant = english_variant(history_id=s.histories[0].history_id)
    assert variant.validation_status is ValidationStatus.NOT_VALIDATED
    assert Language.MSA.value == "ar-MSA"
    with pytest.raises(ValueError):
        Language("Arabizi")


def test_revision_and_exclusion_provenance_round_trip_as_typed_records():
    s = numerical_revision_pair()
    provenance = replace(
        s.provenance,
        validation_status=ValidationStatus.EXCLUDED,
        revisions=(RevisionRecord("revision-1", "Synthetic test revision", ("action.price",), "a" * 64),),
        exclusions=(ExclusionRecord("exclusion-1", "Synthetic test exclusion", "p1-test"),),
    )
    record = replace(s, provenance=provenance)

    assert scenario_from_json(scenario_to_json(record)) == record


def test_permission_restatement_event_round_trips_as_a_typed_no_op():
    required = PermissionKey("cancel", Scope.entity("booking-1"))
    other = PermissionKey("view", Scope.entity("booking-1"))
    first = history(
        "permission-json-valid",
        HistoryState(grants=(PermissionGrant("grant-valid", required),)),
        scenario_id="permission-json",
        events=(RestatePermission("restate-valid", 2, 0, "grant-valid", required),),
    )
    second = history(
        "permission-json-invalid",
        HistoryState(grants=(PermissionGrant("grant-invalid", other),)),
        scenario_id="permission-json",
        events=(RestatePermission("restate-invalid", 2, 0, "grant-invalid", other),),
    )
    control = scenario(
        (first, second),
        scenario_id="permission-json",
        kind=DatasetKind.AUXILIARY_CONTROL,
        family=TransitionFamily.NO_CHANGE_RESTATEMENT,
        partition=Partition.LOCKED_AUXILIARY_CONTROL,
        contract=ActionContract(irreversible=True, required_permissions=(required,)),
    )

    assert scenario_from_json(scenario_to_json(control)) == control


def test_judge_projection_keeps_global_and_entity_permission_scopes_distinct():
    permissions = (
        PermissionKey("approve", Scope.global_scope()),
        PermissionKey("approve", Scope.entity("GLOBAL")),
    )
    tool = PublicToolSchema(
        tool_name="book_service",
        version="fixture-v1",
        description="Synthetic test schema.",
        parameters=(ToolParameterSchema("price", "money"),),
        irreversible=False,
        required_permissions=permissions,
    )
    projection = JudgeFacingItem(
        item_id="opaque-fixture-id",
        conversation=(JudgeConversationTurn("user", "Synthetic request."),),
        action=action(),
        public_tool_schema=tool,
    )

    scopes = [row["scope"] for row in judge_facing_to_dict(projection)["public_tool_schema"]["required_permissions"]]

    assert scopes == [{"type": "global"}, {"type": "entity", "entity_id": "GLOBAL"}]
