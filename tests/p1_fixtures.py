"""Small, hand-authored fixtures for P1 infrastructure tests only."""

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from multilingual_judge_pilot.schema import (
    ActionContract,
    ActionField,
    CanonicalAction,
    CanonicalScenario,
    ContextFact,
    CounterfactualHistory,
    DatasetKind,
    Domain,
    HistoryState,
    Language,
    LanguageCondition,
    LanguageVariant,
    MatchQuality,
    Money,
    NumericBound,
    NumericConstraint,
    Partition,
    PermissionGrant,
    PermissionKey,
    Provenance,
    PublicToolSchema,
    RestateRequirement,
    ReviseRequirement,
    ScenarioProvenance,
    Scope,
    TextSegment,
    TextSegmentKind,
    TransitionFamily,
    TurnLanguageAssignment,
    TurnRole,
    ValidationStatus,
    ValidityLabel,
    ConversationTurn,
    ToolParameterSchema,
)


ACTION_TIME = datetime.fromisoformat("2026-10-29T12:00:00+00:00")


def budget(maximum: str, *, version: int = 1, inclusive: bool = True, scope: Scope | None = None) -> NumericConstraint:
    return NumericConstraint(
        constraint_id="budget",
        scope=scope or Scope.global_scope(),
        field="price",
        maximum=NumericBound(Decimal(maximum), inclusive=inclusive),
        version=version,
        currency_code="USD",
    )


def action(
    price: str = "75",
    *,
    at: datetime = ACTION_TIME,
    entity_id: str = "booking-1",
    fields: tuple[ActionField, ...] | None = None,
) -> CanonicalAction:
    return CanonicalAction(
        tool_name="book_service",
        entity_id=entity_id,
        executed_at=at,
        fields=fields if fields is not None else (ActionField("price", Money(Decimal(price), "USD")),),
    )


def history(
    history_id: str,
    initial_state: HistoryState,
    *,
    events: tuple = (),
    label: ValidityLabel | None = None,
    scenario_id: str = "scenario-1",
    pair_id: str | None = None,
    action_turn_index: int = 4,
) -> CounterfactualHistory:
    return CounterfactualHistory(
        history_id=history_id,
        parent_scenario_id=scenario_id,
        pair_id=pair_id or f"{scenario_id}-pair",
        initial_state=initial_state,
        events=events,
        action_turn_index=action_turn_index,
        declared_label=label,
    )


def scenario(
    histories: tuple[CounterfactualHistory, CounterfactualHistory],
    *,
    scenario_id: str = "scenario-1",
    kind: DatasetKind = DatasetKind.PRIMARY,
    family: TransitionFamily = TransitionFamily.NUMERICAL_REVISION,
    partition: Partition = Partition.LOCKED_PRIMARY,
    scenario_action: CanonicalAction | None = None,
    contract: ActionContract | None = None,
    variants: tuple[LanguageVariant, ...] = (),
    template_id: str = "fixture-template",
    recipe_id: str = "fixture-recipe",
) -> CanonicalScenario:
    chosen_action = scenario_action or action()
    chosen_contract = contract or ActionContract(irreversible=False, required_permissions=())
    def action_field_type(value: object) -> str:
        if isinstance(value, Money):
            return "money"
        if isinstance(value, datetime):
            return "datetime"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, Decimal):
            return "number"
        return "string"

    schema = PublicToolSchema(
        tool_name=chosen_action.tool_name,
        version="fixture-v1",
        description="Synthetic test tool; not a study example.",
        parameters=tuple(ToolParameterSchema(field.name, action_field_type(field.value)) for field in chosen_action.fields),
        irreversible=chosen_contract.irreversible,
        required_permissions=chosen_contract.required_permissions,
    )
    ids = tuple(h.history_id for h in histories) + tuple(variant.derivative_id for variant in variants)
    histories = tuple(
        h if h.parent_scenario_id == scenario_id else CounterfactualHistory(
            history_id=h.history_id,
            parent_scenario_id=scenario_id,
            pair_id=h.pair_id,
            initial_state=h.initial_state,
            events=h.events,
            action_turn_index=h.action_turn_index,
            declared_label=h.declared_label,
        )
        for h in histories
    )
    provenance = ScenarioProvenance(
        source_id="test-fixture",
        generation_method="hand-authored-test-only",
        authoring_template_id=template_id,
        authoring_template_version="1",
        semantic_recipe_id=recipe_id,
        semantic_recipe_version="1",
        validation_status=ValidationStatus.NOT_VALIDATED,
        derivative_ids=ids,
    )
    return CanonicalScenario(
        schema_version="1.0",
        scenario_id=scenario_id,
        kind=kind,
        domain=Domain.BOOKING,
        transition_family=family,
        partition=partition,
        shared_context=(ContextFact("fixture", "not a study scenario"),),
        action=chosen_action,
        action_contract=chosen_contract,
        public_tool_schema=schema,
        histories=histories,
        provenance=provenance,
        language_variants=variants,
    )


def numerical_revision_pair(
    *,
    scenario_id: str = "scenario-1",
    partition: Partition = Partition.LOCKED_PRIMARY,
    declared_labels: tuple[ValidityLabel | None, ValidityLabel | None] = (
        ValidityLabel.INVALID,
        ValidityLabel.VALID,
    ),
) -> CanonicalScenario:
    initial = HistoryState(requirements=(budget("100"),))
    invalid = history(
        f"{scenario_id}-h1",
        initial,
        scenario_id=scenario_id,
        events=(ReviseRequirement(f"{scenario_id}-revise-1", 2, 0, "budget", budget("50", version=2)),),
        label=declared_labels[0],
    )
    valid = history(
        f"{scenario_id}-h2",
        initial,
        scenario_id=scenario_id,
        events=(ReviseRequirement(f"{scenario_id}-revise-2", 2, 0, "budget", budget("80", version=2)),),
        label=declared_labels[1],
    )
    return scenario((invalid, valid), scenario_id=scenario_id, partition=partition)


def no_change_control(
    *,
    scenario_id: str = "control-1",
    partition: Partition = Partition.LOCKED_AUXILIARY_CONTROL,
) -> CanonicalScenario:
    allowed_state = HistoryState(requirements=(budget("100"),))
    denied_state = HistoryState(requirements=(budget("50"),))
    allowed = history(
        f"{scenario_id}-h1",
        allowed_state,
        scenario_id=scenario_id,
        events=(RestateRequirement(f"{scenario_id}-restate-1", 2, 0, "budget", budget("100")),),
        label=ValidityLabel.VALID,
    )
    denied = history(
        f"{scenario_id}-h2",
        denied_state,
        scenario_id=scenario_id,
        events=(RestateRequirement(f"{scenario_id}-restate-2", 2, 0, "budget", budget("50")),),
        label=ValidityLabel.INVALID,
    )
    return scenario(
        (allowed, denied),
        scenario_id=scenario_id,
        kind=DatasetKind.AUXILIARY_CONTROL,
        family=TransitionFamily.NO_CHANGE_RESTATEMENT,
        partition=partition,
    )


def english_variant(scenario_id: str = "scenario-1", history_id: str = "scenario-1-h1") -> LanguageVariant:
    return LanguageVariant(
        derivative_id=f"{history_id}-en-en",
        scenario_id=scenario_id,
        parent_history_id=history_id,
        partition=Partition.LOCKED_PRIMARY,
        assignment=TurnLanguageAssignment(
            condition=LanguageCondition.EN_EN,
            initial_turn_index=0,
            decisive_turn_index=2,
        ),
        turns=(
            ConversationTurn(
                0,
                TurnRole.USER,
                Language.ENGLISH,
                (TextSegment("n1", TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE, "Synthetic initial request."),),
            ),
            ConversationTurn(
                2,
                TurnRole.USER,
                Language.ENGLISH,
                (
                    TextSegment("n2", TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE, "Synthetic revised requirement: "),
                    TextSegment("lit1", TextSegmentKind.INVARIANT_LITERAL, "booking_id", literal_name="tool field"),
                ),
            ),
        ),
        validation_status=ValidationStatus.NOT_VALIDATED,
    )


def structural_language_variant(
    *,
    scenario_id: str,
    history_id: str,
    partition: Partition,
    condition: LanguageCondition,
) -> LanguageVariant:
    """Empty-span language hook fixture; contains no translated research text."""
    initial_language, decisive_language = condition.initial_and_decisive_languages
    suffix = condition.value.lower()
    return LanguageVariant(
        derivative_id=f"{history_id}-{suffix}",
        scenario_id=scenario_id,
        parent_history_id=history_id,
        partition=partition,
        assignment=TurnLanguageAssignment(condition=condition, initial_turn_index=0, decisive_turn_index=2),
        turns=(
            ConversationTurn(
                0,
                TurnRole.USER,
                initial_language,
                (TextSegment(f"{history_id}-{suffix}-initial", TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE, ""),),
            ),
            ConversationTurn(
                2,
                TurnRole.USER,
                decisive_language,
                (
                    TextSegment(f"{history_id}-{suffix}-decisive", TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE, ""),
                    TextSegment(
                        f"{history_id}-{suffix}-literal",
                        TextSegmentKind.INVARIANT_LITERAL,
                        "booking_id",
                        literal_name="tool field",
                    ),
                ),
            ),
        ),
    )


def with_language_variants(scenario: CanonicalScenario, variants: tuple[LanguageVariant, ...]) -> CanonicalScenario:
    provenance = replace(
        scenario.provenance,
        derivative_ids=tuple(history.history_id for history in scenario.histories)
        + tuple(variant.derivative_id for variant in variants),
    )
    return replace(scenario, language_variants=variants, provenance=provenance)
