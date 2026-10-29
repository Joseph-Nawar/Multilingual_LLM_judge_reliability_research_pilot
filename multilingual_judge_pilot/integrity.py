"""Counterfactual, partition, provenance, and duplicate validation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import unicodedata
import re

from .oracle import apply_history_events, evaluate_history
from .schema import (
    CanonicalScenario,
    ConstraintEventOrderError,
    DatasetKind,
    Domain,
    EffectiveState,
    GrantPermission,
    IntroduceRequirement,
    LanguageCondition,
    LanguageVariant,
    MatchRecord,
    MatchQuality,
    NumericConstraint,
    Partition,
    PartitionAssignment,
    PartitionSubject,
    PermissionGrant,
    PermissionKey,
    ReasonCode,
    Requirement,
    RestatePermission,
    RestateRequirement,
    ReviseRequirement,
    RevokePermission,
    ScenarioProvenance,
    SchemaValidationError,
    TemporalConstraint,
    TextSegmentKind,
    TransitionFamily,
    ValidityLabel,
    stable_digest,
)


class DuplicateIdentifierError(SchemaValidationError):
    pass


class PartitionIntegrityError(SchemaValidationError):
    pass


class ProvenanceError(SchemaValidationError):
    pass


@dataclass(frozen=True)
class PairValidation:
    labels: tuple[ValidityLabel, ValidityLabel]
    history_ids: tuple[str, str]
    action_fingerprint: str


@dataclass(frozen=True)
class DuplicateGroup:
    fingerprint: str
    scenario_ids: tuple[str, ...]
    derivative_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DuplicateAudit:
    exact_duplicate_groups: tuple[DuplicateGroup, ...]
    normalized_text_duplicate_groups: tuple[DuplicateGroup, ...]
    template_counts: dict[str, int]
    recipe_counts: dict[str, int]
    cross_partition_templates: tuple[str, ...]
    cross_partition_recipes: tuple[str, ...]
    semantic_equivalence_was_assessed: bool = False


def _bound_signature(bound) -> tuple | None:
    if bound is None:
        return None
    value = bound.value
    if isinstance(value, datetime):
        value = value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    else:
        value = str(value)
    return value, bound.inclusive


def _requirement_identity(requirement: Requirement) -> tuple:
    """Identity of a requirement, excluding IDs, versions, and bound values."""
    return type(requirement).__name__, requirement.scope.entity_id or "", requirement.field, getattr(requirement, "currency_code", None) or ""


def _requirement_signature(requirement: Requirement) -> tuple:
    if isinstance(requirement, NumericConstraint):
        values = (_bound_signature(requirement.minimum), _bound_signature(requirement.maximum), requirement.currency_code or "")
    elif isinstance(requirement, TemporalConstraint):
        values = (_bound_signature(requirement.earliest), _bound_signature(requirement.latest))
    else:
        raise SchemaValidationError(f"unsupported formal requirement: {type(requirement).__name__}")
    return (*_requirement_identity(requirement), *values)


def _permission_signature(key: PermissionKey) -> tuple[str, str]:
    return key.permission, key.scope.entity_id or ""


def _active_state_signature(state: EffectiveState) -> tuple:
    requirements = tuple(sorted((_requirement_signature(row) for row in state.active_requirements), key=repr))
    grants = tuple(sorted((_permission_signature(row.key) for row in state.active_grants), key=repr))
    return requirements, grants


def _initial_state_signature(history) -> tuple:
    requirements = tuple(sorted((_requirement_signature(row) for row in history.initial_state.requirements), key=repr))
    grants = tuple(sorted((_permission_signature(row.key) for row in history.initial_state.grants), key=repr))
    return requirements, grants


def _decision_and_unrelated_signatures(state: EffectiveState, scenario: CanonicalScenario) -> tuple[tuple, tuple]:
    action_fields = {row.name for row in scenario.action.fields}
    required_permissions = set(scenario.action_contract.required_permissions)
    relevant_requirements = []
    unrelated_requirements = []
    for requirement in state.active_requirements:
        relevant = requirement.field in action_fields and requirement.scope.applies_to(scenario.action.entity_id)
        (relevant_requirements if relevant else unrelated_requirements).append(_requirement_signature(requirement))
    active_keys = {grant.key for grant in state.active_grants}
    decision_permissions = tuple(
        sorted((_permission_signature(key), key in active_keys) for key in required_permissions)
    )
    unrelated_grants = tuple(
        sorted((_permission_signature(grant.key) for grant in state.active_grants if grant.key not in required_permissions), key=repr)
    )
    decision = (
        tuple(sorted(relevant_requirements, key=repr)),
        decision_permissions,
    )
    unrelated = (
        tuple(sorted(unrelated_requirements, key=repr)),
        unrelated_grants,
    )
    return decision, unrelated


def _transition_signature(transition) -> tuple:
    event = transition.event
    return (
        event.turn_index,
        event.event_index,
        type(event).__name__,
        _active_state_signature(transition.before_state),
        _active_state_signature(transition.after_state),
    )


def _event_subject_signature(transition) -> tuple:
    event = transition.event
    if isinstance(event, IntroduceRequirement):
        return ("requirement", _requirement_identity(event.requirement))
    if isinstance(event, ReviseRequirement):
        current = next((row for row in transition.before_state.active_requirements if row.constraint_id == event.constraint_id), None)
        if current is None:
            raise SchemaValidationError("decisive revision has no active target in its pre-event state")
        return ("requirement", _requirement_identity(current))
    if isinstance(event, RestateRequirement):
        return ("requirement", _requirement_identity(event.asserted_requirement))
    if isinstance(event, GrantPermission):
        return ("permission", _permission_signature(event.key))
    if isinstance(event, RestatePermission):
        return ("permission", _permission_signature(event.asserted_key))
    if isinstance(event, RevokePermission):
        current = next((row for row in transition.before_state.active_grants if row.grant_id == event.grant_id), None)
        if current is None:
            raise SchemaValidationError("decisive revocation has no active grant in its pre-event state")
        return ("permission", _permission_signature(current.key))
    raise SchemaValidationError(f"unsupported decisive event type: {type(event).__name__}")


def _decisive_transitions(history, application):
    decisive_ids = set(history.decisive_event_ids)
    return tuple(transition for transition in application.transitions if transition.event.event_id in decisive_ids)


def _initial_state_digest(history) -> str:
    from .schema import EffectiveState

    state = EffectiveState(
        active_requirements=tuple(sorted(history.initial_state.requirements, key=lambda requirement: requirement.constraint_id)),
        active_grants=tuple(sorted(history.initial_state.grants, key=lambda grant: grant.grant_id)),
        revoked_grants=(),
        superseded_requirements=(),
    )
    return state.digest


def _validate_scenario_structure(scenario: CanonicalScenario) -> tuple:
    if len({history.history_id for history in scenario.histories}) != 2:
        raise DuplicateIdentifierError("counterfactual history IDs must be unique")
    if len({history.pair_id for history in scenario.histories}) != 1:
        raise SchemaValidationError("counterfactual histories must share one pair ID")
    for history in scenario.histories:
        if history.parent_scenario_id != scenario.scenario_id:
            raise ProvenanceError("history parent does not match its canonical scenario")
        if len(history.events) != len({event.event_id for event in history.events}):
            raise DuplicateIdentifierError("event ID is duplicated within a history")
        if history.decisive_turn_index >= history.action_turn_index:
            raise SchemaValidationError("decisive conversation turn must precede the action decision point")
        event_ids_at_decisive_turn = {event.event_id for event in history.events if event.turn_index == history.decisive_turn_index}
        if not history.decisive_event_ids or set(history.decisive_event_ids) != event_ids_at_decisive_turn:
            raise SchemaValidationError("decisive event IDs must identify exactly the formal event group on the decisive turn")
        if any(event.turn_index > history.decisive_turn_index for event in history.events):
            raise SchemaValidationError("formal constraint events cannot occur after the decisive turn")
        if any(event.turn_index >= history.action_turn_index for event in history.events):
            raise ConstraintEventOrderError("formal constraint events must precede the action decision point")
    event_ids = [event.event_id for history in scenario.histories for event in history.events]
    history_ids = [history.history_id for history in scenario.histories]
    pair_ids = [history.pair_id for history in scenario.histories]
    if len(event_ids) != len(set(event_ids)):
        raise DuplicateIdentifierError("event ID must be unique across a counterfactual pair")
    variants = scenario.language_variants
    variant_ids = [variant.derivative_id for variant in variants]
    if len(variant_ids) != len(set(variant_ids)):
        raise DuplicateIdentifierError("language derivative ID is duplicated")
    local_ids = [scenario.scenario_id, *history_ids, *set(pair_ids), *variant_ids, *event_ids]
    if len(local_ids) != len(set(local_ids)):
        raise DuplicateIdentifierError("scenario, history, pair, derivative, and event IDs must be distinct")
    valid_histories = {history.history_id for history in scenario.histories}
    seen_conditions: set[tuple[str, object]] = set()
    for variant in variants:
        if variant.scenario_id != scenario.scenario_id or variant.parent_history_id not in valid_histories:
            raise ProvenanceError("language derivative has unresolved scenario/history parent")
        if variant.partition is not scenario.partition:
            raise PartitionIntegrityError("derivative partition must match its canonical scenario partition")
        key = (variant.parent_history_id, variant.assignment.condition)
        if key in seen_conditions:
            raise SchemaValidationError("duplicate language condition for a history")
        seen_conditions.add(key)
        if not variant.turns:
            raise SchemaValidationError("language variant requires conversation turns")
        if len({segment.segment_id for turn in variant.turns for segment in turn.segments}) != sum(
            len(turn.segments) for turn in variant.turns
        ):
            raise DuplicateIdentifierError("text segment ID is duplicated in a language derivative")
        history = next(row for row in scenario.histories if row.history_id == variant.parent_history_id)
        if variant.assignment.decisive_turn_index != history.decisive_turn_index:
            raise SchemaValidationError("language variant decisive turn does not match the formal decisive event turn")
        turns_by_index = {turn.turn_index: turn for turn in variant.turns}
        post_action_turns = sorted(turn.turn_index for turn in variant.turns if turn.turn_index >= history.action_turn_index)
        if post_action_turns:
            raise SchemaValidationError(
                "judge-facing conversation contains turns at or after the action decision point "
                f"for one or more speaker roles: {post_action_turns}"
            )
        for event in history.events:
            event_turn = turns_by_index.get(event.turn_index)
            if event_turn is None or event_turn.role.value != "user":
                raise SchemaValidationError(
                    f"formal event turn {event.turn_index} requires a corresponding user conversation turn"
                )
    expected_derivatives = set(valid_histories) | set(variant_ids)
    if set(scenario.provenance.derivative_ids) != expected_derivatives:
        raise ProvenanceError("scenario derivative provenance must list all history and language derivative IDs exactly")

    # Literal order, names, and exact string values must remain invariant across
    # language renderings of the same history. Natural-language spans are not
    # compared here; this is a structural check, not semantic validation.
    literal_signatures: dict[str, tuple[tuple[str, str], ...]] = {}
    for variant in variants:
        signature = tuple(
            (segment.literal_name or "", segment.text)
            for turn in variant.turns
            for segment in turn.segments
            if segment.kind is TextSegmentKind.INVARIANT_LITERAL
        )
        previous = literal_signatures.setdefault(variant.parent_history_id, signature)
        if previous != signature:
            raise SchemaValidationError("invariant literal names, order, and text must match across language variants")
    if scenario.kind is DatasetKind.PRIMARY:
        left_history, right_history = scenario.histories
        if left_history.decisive_turn_index != right_history.decisive_turn_index:
            raise SchemaValidationError("primary pair histories must share the decisive turn")
        variants_by_history: dict[str, dict[object, LanguageVariant]] = defaultdict(dict)
        for variant in variants:
            variants_by_history[variant.parent_history_id][variant.assignment.condition] = variant
        left_variants = variants_by_history[left_history.history_id]
        right_variants = variants_by_history[right_history.history_id]

        def nondecisive_conversation_signature(variant: LanguageVariant) -> tuple:
            return tuple(
                (
                    turn.turn_index,
                    turn.role.value,
                    turn.language.value,
                    tuple((segment.kind.value, segment.literal_name, segment.text) for segment in turn.segments),
                )
                for turn in variant.turns
                if turn.turn_index != left_history.decisive_turn_index
            )

        for condition in sorted(left_variants.keys() & right_variants.keys(), key=lambda row: row.value):
            if nondecisive_conversation_signature(left_variants[condition]) != nondecisive_conversation_signature(
                right_variants[condition]
            ):
                raise SchemaValidationError(
                    "primary pair non-decisive conversation context must be structurally identical within a language condition"
                )
    return tuple(evaluate_history(scenario, history.history_id) for history in scenario.histories)


def _validate_primary_causal_pair(scenario: CanonicalScenario, results: tuple) -> None:
    first, second = scenario.histories
    if first.action_turn_index != second.action_turn_index or first.decisive_turn_index != second.decisive_turn_index:
        raise SchemaValidationError("counterfactual histories must share the decisive turn and action decision point")
    if _initial_state_signature(first) != _initial_state_signature(second):
        raise SchemaValidationError("primary histories must begin from semantically equivalent initial states")

    applications = tuple(apply_history_events(history) for history in scenario.histories)
    groups = tuple(_decisive_transitions(history, application) for history, application in zip(scenario.histories, applications, strict=True))
    if any(not group for group in groups):
        raise SchemaValidationError("each primary history requires an explicitly identified decisive event group")
    group_orders = tuple(tuple(row.event.event_index for row in group) for group in groups)
    if group_orders[0] != group_orders[1]:
        raise SchemaValidationError("counterfactual decisive event groups must have compatible event ordering")
    decisive_subjects = tuple(tuple(_event_subject_signature(row) for row in group) for group in groups)
    if decisive_subjects[0] != decisive_subjects[1]:
        raise SchemaValidationError("counterfactual decisive events must target semantically equivalent requirements or permissions")

    prefixes = tuple(
        replace(history, events=tuple(event for event in history.events if event.turn_index < history.decisive_turn_index), decisive_event_ids=())
        for history in scenario.histories
    )
    prefix_applications = tuple(apply_history_events(history) for history in prefixes)
    prefix_scenario = replace(scenario, histories=prefixes)
    prefix_labels = tuple(evaluate_history(prefix_scenario, history.history_id).label for history in prefixes)
    if prefix_labels[0] is not prefix_labels[1]:
        raise SchemaValidationError("validity labels must agree before the decisive transition")

    nondecisive = tuple(
        tuple(_transition_signature(row) for row in application.transitions if row.event.event_id not in set(history.decisive_event_ids))
        for history, application in zip(scenario.histories, applications, strict=True)
    )
    if nondecisive[0] != nondecisive[1]:
        raise SchemaValidationError("non-decisive formal events and state transitions must be semantically equivalent")

    prefix_signatures = tuple(_active_state_signature(application.effective_state) for application in prefix_applications)
    if prefix_signatures[0] != prefix_signatures[1]:
        raise SchemaValidationError("histories must have equivalent active decision-relevant state before the decisive change")

    family = scenario.transition_family
    event_groups = tuple(tuple(row.event for row in group) for group in groups)
    if family is TransitionFamily.INTRODUCTION:
        if any(not all(isinstance(event, IntroduceRequirement) for event in group) for group in event_groups):
            raise SchemaValidationError("introduction pair decisive groups must contain only requirement introductions")
    elif family is TransitionFamily.NUMERICAL_REVISION:
        if any(not group or not all(isinstance(event, ReviseRequirement) and isinstance(event.replacement, NumericConstraint) for event in group) for group in event_groups):
            raise SchemaValidationError("numerical-revision pair decisive groups must revise numeric requirements")
    elif family is TransitionFamily.TEMPORAL_REVISION:
        if any(not group or not all(isinstance(event, ReviseRequirement) and isinstance(event.replacement, TemporalConstraint) for event in group) for group in event_groups):
            raise SchemaValidationError("temporal-revision pair decisive groups must revise temporal requirements")
    elif family is TransitionFamily.PERMISSION_REVOCATION:
        revoke_sides = [index for index, group in enumerate(event_groups) if any(isinstance(event, RevokePermission) for event in group)]
        if len(revoke_sides) != 1:
            raise SchemaValidationError("permission-revocation pair requires one revoking history and one preserving history")
        preserve_side = 1 - revoke_sides[0]
        if not all(isinstance(event, (RevokePermission, RestatePermission)) for group in event_groups for event in group):
            raise SchemaValidationError("permission-revocation decisive groups may only revoke or explicitly restate permission")
        if not any(isinstance(event, RestatePermission) for event in event_groups[preserve_side]):
            raise SchemaValidationError("permission-preserving history requires an explicit permission restatement")
    else:
        raise SchemaValidationError("primary scenario has an unsupported transition family")

    pre_decision = tuple(_decision_and_unrelated_signatures(app.effective_state, scenario)[0] for app in prefix_applications)
    final_components = tuple(_decision_and_unrelated_signatures(result.effective_state, scenario) for result in results)
    if family is not TransitionFamily.PERMISSION_REVOCATION:
        if any(pre_decision[index] == final_components[index][0] for index in range(2)):
            raise SchemaValidationError("decisive transition must make a meaningful active-state change relevant to the action")
    else:
        revoke_side = next(index for index, group in enumerate(event_groups) if any(isinstance(event, RevokePermission) for event in group))
        if pre_decision[revoke_side] == final_components[revoke_side][0]:
            raise SchemaValidationError("permission revocation must change active decision-relevant authorization")

    if final_components[0][0] == final_components[1][0]:
        raise SchemaValidationError("decisive transition must produce different active decision-relevant states")
    if final_components[0][1] != final_components[1][1]:
        raise SchemaValidationError("unrelated active-state differences cannot explain the counterfactual label contrast")


def validate_counterfactual_pair(scenario: CanonicalScenario) -> PairValidation:
    """Compute both oracle labels and validate the pair; supplied labels are only assertions."""
    results = _validate_scenario_structure(scenario)
    first, second = scenario.histories
    labels = (results[0].label, results[1].label)
    if labels[0] is labels[1]:
        raise SchemaValidationError("oracle must establish opposite validity labels for the counterfactual pair")
    for history, result in zip(scenario.histories, results, strict=True):
        if history.declared_label is not None and history.declared_label is not result.label:
            raise SchemaValidationError(
                f"declared label disagrees with deterministic oracle for history {history.history_id}"
            )

    if scenario.histories[0].action_turn_index != scenario.histories[1].action_turn_index:
        raise SchemaValidationError("counterfactual histories must share the same action decision point")
    if scenario.histories[0].decisive_turn_index != scenario.histories[1].decisive_turn_index:
        raise SchemaValidationError("counterfactual histories must share the same decisive turn")

    if scenario.kind is DatasetKind.PRIMARY:
        _validate_primary_causal_pair(scenario, results)
    else:
        if any(not history.events for history in scenario.histories):
            raise SchemaValidationError("each no-change control history requires a later restatement")
        for history, result in zip(scenario.histories, results, strict=True):
            if not all(isinstance(event, (RestateRequirement, RestatePermission)) for event in history.events):
                raise SchemaValidationError("no-change controls cannot contain state-changing events")
            application = apply_history_events(history)
            if not application.transitions or any(
                _active_state_signature(step.before_state) != _active_state_signature(step.after_state)
                for step in application.transitions
            ):
                raise SchemaValidationError("no-change restatement changed effective state")
            if min(event.turn_index for event in history.events) <= 0:
                raise SchemaValidationError("control restatement must occur after the initial context")
        if _initial_state_digest(first) == _initial_state_digest(second):
            raise SchemaValidationError("opposite no-change labels must arise from different initial requirements")
        if results[0].state_digest == results[1].state_digest:
            raise SchemaValidationError("no-change histories must retain different effective requirements")

    return PairValidation(labels, (first.history_id, second.history_id), stable_digest(scenario.action))


def validate_scenario(scenario: CanonicalScenario) -> None:
    """Validate one scenario without repairing or normalizing source records."""
    if scenario.partition not in {Partition.DEVELOPMENT, Partition.LOCKED_PRIMARY, Partition.LOCKED_AUXILIARY_CONTROL}:
        raise PartitionIntegrityError("unknown scenario partition")
    if scenario.kind is DatasetKind.PRIMARY and scenario.partition is Partition.LOCKED_AUXILIARY_CONTROL:
        raise PartitionIntegrityError("primary scenario cannot be placed in the control partition")
    if scenario.kind is DatasetKind.AUXILIARY_CONTROL and scenario.partition is not Partition.LOCKED_AUXILIARY_CONTROL:
        raise PartitionIntegrityError("auxiliary control must remain in the locked control partition")
    validate_counterfactual_pair(scenario)


def validate_language_variant_coverage(scenario: CanonicalScenario) -> None:
    """Require all four approved conditions for every history before a dataset freeze."""
    validate_scenario(scenario)
    expected = set(LanguageCondition)
    by_history: dict[str, set[LanguageCondition]] = defaultdict(set)
    for variant in scenario.language_variants:
        by_history[variant.parent_history_id].add(variant.assignment.condition)
    for history in scenario.histories:
        observed = by_history[history.history_id]
        if observed != expected:
            missing = sorted(condition.value for condition in expected - observed)
            extra = sorted(condition.value for condition in observed - expected)
            raise SchemaValidationError(
                f"history {history.history_id} lacks complete four-condition coverage; missing={missing}, extra={extra}"
            )


def validate_scenario_collection(scenarios: tuple[CanonicalScenario, ...] | list[CanonicalScenario]) -> None:
    ids = [scenario.scenario_id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise DuplicateIdentifierError("scenario ID is duplicated")
    history_ids = [history.history_id for scenario in scenarios for history in scenario.histories]
    derivative_ids = [variant.derivative_id for scenario in scenarios for variant in scenario.language_variants]
    event_ids = [event.event_id for scenario in scenarios for history in scenario.histories for event in history.events]
    pair_ids = [scenario.histories[0].pair_id for scenario in scenarios]
    all_ids = ids + history_ids + derivative_ids + event_ids + pair_ids
    if len(all_ids) != len(set(all_ids)):
        raise DuplicateIdentifierError("canonical, history, language derivative, and event IDs must be globally unique")
    if len(pair_ids) != len(set(pair_ids)):
        raise DuplicateIdentifierError("counterfactual pair IDs must be unique across canonical scenarios")
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    for scenario in scenarios:
        validate_scenario(scenario)
        parent = scenario.provenance.parent_scenario_id
        source_scenario = scenario.provenance.source_scenario_id
        for referenced, label in ((parent, "parent"), (source_scenario, "source")):
            if referenced is not None and referenced not in by_id:
                raise ProvenanceError(f"unresolved {label} scenario reference: {referenced}")
            if referenced is not None and by_id[referenced].partition is not scenario.partition:
                raise PartitionIntegrityError(f"{label} scenario relationship crosses partitions")
        if parent == scenario.scenario_id or source_scenario == scenario.scenario_id:
            raise ProvenanceError("scenario cannot be its own parent or source")

    # Reject cycles in the in-repository parent graph.
    for scenario in scenarios:
        path: set[str] = set()
        current = scenario
        while current.provenance.parent_scenario_id is not None:
            parent_id = current.provenance.parent_scenario_id
            if parent_id in path or parent_id == scenario.scenario_id:
                raise ProvenanceError("cyclic scenario parent provenance")
            path.add(parent_id)
            current = by_id[parent_id]


def validate_match_records(
    scenarios: tuple[CanonicalScenario, ...] | list[CanonicalScenario], matches: tuple[MatchRecord, ...] | list[MatchRecord]
) -> None:
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    match_ids = [match.match_set_id for match in matches]
    control_ids = [match.control_scenario_id for match in matches]
    if len(match_ids) != len(set(match_ids)) or len(control_ids) != len(set(control_ids)):
        raise DuplicateIdentifierError("match-set or matched-control ID is duplicated")
    for match in matches:
        control = by_id.get(match.control_scenario_id)
        if control is None or control.kind is not DatasetKind.AUXILIARY_CONTROL:
            raise ProvenanceError("match record must resolve to an auxiliary control")
        if control.match_set_id != match.match_set_id and match.quality is not MatchQuality.UNMATCHED:
            raise ProvenanceError("control match-set ID disagrees with match record")
        if match.quality is MatchQuality.UNMATCHED:
            continue
        primary = by_id.get(match.primary_scenario_id or "")
        if primary is None or primary.kind is not DatasetKind.PRIMARY:
            raise ProvenanceError("matched primary-control record has no primary scenario")
        if primary.partition is not Partition.LOCKED_PRIMARY:
            raise PartitionIntegrityError("locked auxiliary controls may only match locked primary scenarios")
        if primary.match_set_id != match.match_set_id:
            raise ProvenanceError("primary match-set ID disagrees with match record")
        # A match is an analysis link only; each scenario retains its own assigned partition.


def assign_partitions(subjects: tuple[PartitionSubject, ...] | list[PartitionSubject], *, seed: str) -> tuple[PartitionAssignment, ...]:
    """Assign the approved 48+12 target deterministically using stable SHA-256 ordering."""
    if not seed:
        raise SchemaValidationError("partition assignment requires an explicit seed")
    ids = [subject.scenario_id for subject in subjects]
    if len(ids) != len(set(ids)):
        raise DuplicateIdentifierError("partition subject ID is duplicated")
    primary = [subject for subject in subjects if subject.kind is DatasetKind.PRIMARY]
    controls = [subject for subject in subjects if subject.kind is DatasetKind.AUXILIARY_CONTROL]
    if len(primary) != 48 or len(controls) != 12 or len(subjects) != 60:
        raise PartitionIntegrityError("full partition allocation requires 48 primary and 12 auxiliary-control scenarios")
    cells: dict[tuple[Domain, TransitionFamily], list[PartitionSubject]] = defaultdict(list)
    for subject in primary:
        if subject.transition_family is TransitionFamily.NO_CHANGE_RESTATEMENT:
            raise PartitionIntegrityError("primary subject cannot use no-change family")
        cells[(subject.domain, subject.transition_family)].append(subject)
    expected_cells = {
        (domain, family)
        for domain in Domain
        for family in (
            TransitionFamily.INTRODUCTION,
            TransitionFamily.NUMERICAL_REVISION,
            TransitionFamily.PERMISSION_REVOCATION,
            TransitionFamily.TEMPORAL_REVISION,
        )
    }
    if set(cells) != expected_cells or any(len(rows) != 4 for rows in cells.values()):
        raise PartitionIntegrityError("primary partition requires four scenarios in every domain-transition cell")
    assignments: list[PartitionAssignment] = []
    for subject in primary:
        key = (subject.domain, subject.transition_family)
        ordered = sorted(
            cells[key],
            key=lambda row: (hashlib.sha256(f"{seed}\0{row.scenario_id}".encode("utf-8")).hexdigest(), row.scenario_id),
        )
        chosen = next(index for index, row in enumerate(ordered) if row.scenario_id == subject.scenario_id)
        partition = Partition.DEVELOPMENT if chosen == 0 else Partition.LOCKED_PRIMARY
        assignments.append(PartitionAssignment(subject.scenario_id, subject.kind, subject.domain, subject.transition_family, partition))
    assignments.extend(
        PartitionAssignment(subject.scenario_id, subject.kind, subject.domain, subject.transition_family, Partition.LOCKED_AUXILIARY_CONTROL)
        for subject in controls
    )
    result = tuple(sorted(assignments, key=lambda row: row.scenario_id))
    validate_partition_manifest(subjects, result)
    return result


def validate_partition_manifest(
    subjects: tuple[PartitionSubject, ...] | list[PartitionSubject],
    assignments: tuple[PartitionAssignment, ...] | list[PartitionAssignment],
) -> None:
    subject_by_id = {subject.scenario_id: subject for subject in subjects}
    assignment_by_id = {assignment.scenario_id: assignment for assignment in assignments}
    if len(subject_by_id) != len(subjects) or len(assignment_by_id) != len(assignments):
        raise DuplicateIdentifierError("partition manifest contains duplicate scenario IDs")
    if set(subject_by_id) != set(assignment_by_id):
        raise PartitionIntegrityError("partition manifest must assign every scenario exactly once")
    for scenario_id, subject in subject_by_id.items():
        assignment = assignment_by_id[scenario_id]
        if (assignment.kind, assignment.domain, assignment.transition_family) != (
            subject.kind,
            subject.domain,
            subject.transition_family,
        ):
            raise PartitionIntegrityError("partition manifest changed scenario stratum")
        if subject.kind is DatasetKind.AUXILIARY_CONTROL:
            if assignment.partition is not Partition.LOCKED_AUXILIARY_CONTROL:
                raise PartitionIntegrityError("all auxiliary controls must remain locked")
        elif assignment.partition not in {Partition.DEVELOPMENT, Partition.LOCKED_PRIMARY}:
            raise PartitionIntegrityError("primary scenario has an invalid partition")
    primary = [row for row in assignments if row.kind is DatasetKind.PRIMARY]
    controls = [row for row in assignments if row.kind is DatasetKind.AUXILIARY_CONTROL]
    if len(primary) != 48 or len(controls) != 12:
        raise PartitionIntegrityError("partition manifest must contain 48 primary and 12 controls")
    dev = [row for row in primary if row.partition is Partition.DEVELOPMENT]
    locked = [row for row in primary if row.partition is Partition.LOCKED_PRIMARY]
    if len(dev) != 12 or len(locked) != 36:
        raise PartitionIntegrityError("partition manifest requires 12 development and 36 locked primary scenarios")
    for domain in Domain:
        for family in (
            TransitionFamily.INTRODUCTION,
            TransitionFamily.NUMERICAL_REVISION,
            TransitionFamily.PERMISSION_REVOCATION,
            TransitionFamily.TEMPORAL_REVISION,
        ):
            cell = [row for row in primary if row.domain is domain and row.transition_family is family]
            if len(cell) != 4 or sum(row.partition is Partition.DEVELOPMENT for row in cell) != 1:
                raise PartitionIntegrityError("primary stratification requires one development scenario per cell")


def partition_manifest_json(assignments: tuple[PartitionAssignment, ...] | list[PartitionAssignment], *, seed: str) -> str:
    payload = {
        "manifest_version": "1.0",
        "seed": seed,
        "assignments": [
            {
                "scenario_id": row.scenario_id,
                "kind": row.kind.value,
                "domain": row.domain.value,
                "transition_family": row.transition_family.value,
                "partition": row.partition.value,
            }
            for row in sorted(assignments, key=lambda row: row.scenario_id)
        ],
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["content_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _scenario_content(scenario: CanonicalScenario) -> dict:
    histories = []
    for history in scenario.histories:
        history_record = {
            "initial_state": history.initial_state,
            "events": [],
            "action_turn_index": history.action_turn_index,
        }
        for event in history.events:
            record = {"event_type": type(event).__name__, "turn_index": event.turn_index, "event_index": event.event_index}
            for field_name in event.__dataclass_fields__:
                if field_name not in {"event_id", "turn_index", "event_index"}:
                    record[field_name] = getattr(event, field_name)
            history_record["events"].append(record)
        histories.append(history_record)
    variants = [
        {
            "condition": variant.assignment.condition,
            "assignment": variant.assignment,
            "turns": tuple((turn.turn_index, turn.role, turn.language, turn.content) for turn in variant.turns),
        }
        for variant in scenario.language_variants
    ]
    return {
        "kind": scenario.kind,
        "domain": scenario.domain,
        "transition_family": scenario.transition_family,
        "shared_context": scenario.shared_context,
        "action": scenario.action,
        "action_contract": scenario.action_contract,
        "public_tool_schema": scenario.public_tool_schema,
        "histories": tuple(histories),
        "language_variants": tuple(variants),
    }


def _normalized_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def audit_duplicates(scenarios: tuple[CanonicalScenario, ...] | list[CanonicalScenario]) -> DuplicateAudit:
    exact: dict[str, list[str]] = defaultdict(list)
    text_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    templates: Counter[str] = Counter()
    recipes: Counter[str] = Counter()
    template_partitions: dict[str, set[Partition]] = defaultdict(set)
    recipe_partitions: dict[str, set[Partition]] = defaultdict(set)

    for scenario in scenarios:
        exact[stable_digest(_scenario_content(scenario))].append(scenario.scenario_id)
        provenance = scenario.provenance
        template_key = f"{provenance.authoring_template_id}@{provenance.authoring_template_version}"
        recipe_key = f"{provenance.semantic_recipe_id}@{provenance.semantic_recipe_version}"
        templates[template_key] += 1
        recipes[recipe_key] += 1
        template_partitions[template_key].add(scenario.partition)
        recipe_partitions[recipe_key].add(scenario.partition)
        for variant in scenario.language_variants:
            text = "\n".join(f"{turn.role.value}: {turn.content}" for turn in variant.turns)
            normalized = _normalized_text(text)
            if normalized:
                text_groups[normalized].append((scenario.scenario_id, variant.derivative_id))

    exact_groups = tuple(
        DuplicateGroup(key, tuple(sorted(ids)))
        for key, ids in sorted(exact.items())
        if len(ids) > 1
    )
    normalized_groups = tuple(
        DuplicateGroup(key, tuple(sorted({scenario_id for scenario_id, _derivative_id in values})), tuple(sorted(derivative_id for _scenario_id, derivative_id in values)))
        for key, values in sorted(text_groups.items())
        if len({scenario_id for scenario_id, _derivative_id in values}) > 1
    )
    return DuplicateAudit(
        exact_duplicate_groups=exact_groups,
        normalized_text_duplicate_groups=normalized_groups,
        template_counts=dict(sorted(templates.items())),
        recipe_counts=dict(sorted(recipes.items())),
        cross_partition_templates=tuple(sorted(key for key, parts in template_partitions.items() if len(parts) > 1)),
        cross_partition_recipes=tuple(sorted(key for key, parts in recipe_partitions.items() if len(parts) > 1)),
        semantic_equivalence_was_assessed=False,
    )
