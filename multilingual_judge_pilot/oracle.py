"""Deterministic state transitions and action-validity oracle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .schema import (
    ActionValue,
    CanonicalScenario,
    ConstraintEventOrderError,
    CounterfactualHistory,
    EffectiveState,
    EventAudit,
    GrantPermission,
    HistoryState,
    IntroduceRequirement,
    Money,
    NumericConstraint,
    OracleResult,
    PermissionGrant,
    ReasonCode,
    Requirement,
    RestatePermission,
    RestateRequirement,
    ReviseRequirement,
    RevokePermission,
    SchemaValidationError,
    TemporalConstraint,
    ValidityLabel,
    stable_digest,
)


@dataclass(frozen=True)
class StateApplication:
    effective_state: EffectiveState
    event_audit: tuple[EventAudit, ...]


def _state(
    active: dict[str, Requirement],
    grants: dict[str, PermissionGrant],
    revoked: list[PermissionGrant],
    superseded: list[Requirement],
) -> EffectiveState:
    return EffectiveState(
        active_requirements=tuple(active[key] for key in sorted(active)),
        active_grants=tuple(grants[key] for key in sorted(grants)),
        revoked_grants=tuple(sorted(revoked, key=lambda grant: grant.grant_id)),
        superseded_requirements=tuple(sorted(superseded, key=lambda requirement: (requirement.constraint_id, requirement.version))),
    )


def apply_history_events(history: CounterfactualHistory) -> StateApplication:
    """Apply formal events in their declared order, retaining a state-digest audit."""
    if not isinstance(history.initial_state, HistoryState):
        raise SchemaValidationError("history requires an explicit initial state")
    active = {item.constraint_id: item for item in history.initial_state.requirements}
    grants = {item.grant_id: item for item in history.initial_state.grants}
    revoked: list[PermissionGrant] = []
    superseded: list[Requirement] = []
    seen_requirement_ids = set(active)
    seen_grant_ids = set(grants)
    seen_event_ids: set[str] = set()
    event_audit: list[EventAudit] = []
    previous_order = (0, -1)

    for event in history.events:
        if event.event_id in seen_event_ids:
            raise SchemaValidationError(f"duplicate event ID: {event.event_id}")
        seen_event_ids.add(event.event_id)
        order = (event.turn_index, event.event_index)
        if order <= previous_order:
            raise ConstraintEventOrderError("events must be strictly ordered by (turn_index, event_index)")
        if event.turn_index >= history.action_turn_index:
            raise ConstraintEventOrderError("every constraint event must precede the action turn")
        previous_order = order
        before = _state(active, grants, revoked, superseded)

        if isinstance(event, IntroduceRequirement):
            requirement = event.requirement
            if not isinstance(requirement, (NumericConstraint, TemporalConstraint)):
                raise SchemaValidationError("introduction requires a supported formal requirement")
            if requirement.constraint_id in seen_requirement_ids:
                raise SchemaValidationError(f"requirement ID was already used: {requirement.constraint_id}")
            seen_requirement_ids.add(requirement.constraint_id)
            active[requirement.constraint_id] = requirement
        elif isinstance(event, ReviseRequirement):
            current = active.get(event.constraint_id)
            if current is None:
                raise SchemaValidationError(f"revision target is not an active requirement: {event.constraint_id}")
            replacement = event.replacement
            if type(replacement) is not type(current):
                raise SchemaValidationError("revision must preserve requirement type")
            if (
                replacement.constraint_id != current.constraint_id
                or replacement.scope != current.scope
                or replacement.field != current.field
            ):
                raise SchemaValidationError("revision must preserve requirement identity, scope, and action field")
            if replacement.version != current.version + 1:
                raise SchemaValidationError("revision version must advance exactly once")
            if replacement == current:
                raise SchemaValidationError("identical requirement must be represented as a restatement")
            superseded.append(current)
            active[event.constraint_id] = replacement
        elif isinstance(event, RestateRequirement):
            current = active.get(event.constraint_id)
            if current is None:
                raise SchemaValidationError(f"restatement target is not an active requirement: {event.constraint_id}")
            if event.asserted_requirement != current:
                raise SchemaValidationError("restatement does not exactly match the active requirement; state change is not permitted")
            # Deliberate no-op. Audit digests prove the state was unchanged.
        elif isinstance(event, RestatePermission):
            current = grants.get(event.grant_id)
            if current is None:
                raise SchemaValidationError(f"permission restatement target is not active: {event.grant_id}")
            if event.asserted_key != current.key:
                raise SchemaValidationError("permission restatement does not exactly match the active permission; state change is not permitted")
            # Deliberate no-op. Audit digests prove the state was unchanged.
        elif isinstance(event, GrantPermission):
            if event.grant_id in seen_grant_ids:
                raise SchemaValidationError(f"permission grant ID was already used: {event.grant_id}")
            if any(grant.key == event.key for grant in grants.values()):
                raise SchemaValidationError("permission key already has an active grant")
            seen_grant_ids.add(event.grant_id)
            grants[event.grant_id] = PermissionGrant(event.grant_id, event.key)
        elif isinstance(event, RevokePermission):
            grant = grants.pop(event.grant_id, None)
            if grant is None:
                raise SchemaValidationError(f"revocation target is not an active permission grant: {event.grant_id}")
            revoked.append(grant)
        else:
            raise SchemaValidationError(f"unsupported constraint event type: {type(event).__name__}")

        after = _state(active, grants, revoked, superseded)
        event_audit.append(EventAudit(event.event_id, before.digest, after.digest))

    return StateApplication(_state(active, grants, revoked, superseded), tuple(event_audit))


def _decimal_value(value: ActionValue, requirement: NumericConstraint) -> tuple[Decimal, str | None]:
    if isinstance(value, Money):
        if requirement.currency_code is None:
            raise SchemaValidationError("monetary action parameter requires an explicit currency requirement")
        return value.amount, value.currency_code
    if requirement.currency_code is not None:
        raise SchemaValidationError("currency-constrained action parameter must use a typed Money value")
    if isinstance(value, Decimal):
        return value, None
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value), None
    raise SchemaValidationError("action parameter has an invalid numeric type")


def _within_temporal_constraint(value: datetime, requirement: TemporalConstraint, reasons: list[ReasonCode]) -> None:
    instant = value.astimezone(timezone.utc)
    if requirement.earliest is not None:
        boundary = requirement.earliest.value.astimezone(timezone.utc)
        if instant < boundary or (instant == boundary and not requirement.earliest.inclusive):
            reasons.append(ReasonCode.TEMPORAL_BEFORE_EARLIEST)
    if requirement.latest is not None:
        boundary = requirement.latest.value.astimezone(timezone.utc)
        if instant > boundary or (instant == boundary and not requirement.latest.inclusive):
            reasons.append(ReasonCode.TEMPORAL_AFTER_LATEST)


def evaluate_history(scenario: CanonicalScenario, history_id: str) -> OracleResult:
    """Evaluate one selected history from formal state; no text or external system is read."""
    matches = [history for history in scenario.histories if history.history_id == history_id]
    if len(matches) != 1:
        raise SchemaValidationError(f"selected history ID is missing or duplicated: {history_id}")
    history = matches[0]
    application = apply_history_events(history)
    parameters = {field.name: field.value for field in scenario.action.fields}
    reasons: list[ReasonCode] = []

    for requirement in application.effective_state.active_requirements:
        if not requirement.scope.applies_to(scenario.action.entity_id):
            continue
        value = parameters.get(requirement.field)
        if value is None:
            raise SchemaValidationError(f"action parameter is missing for active requirement: {requirement.field}")
        if isinstance(requirement, NumericConstraint):
            number, currency = _decimal_value(value, requirement)
            if requirement.currency_code is not None and currency != requirement.currency_code:
                reasons.append(ReasonCode.CURRENCY_MISMATCH)
                continue
            if requirement.minimum is not None:
                bound = requirement.minimum
                if number < bound.value or (number == bound.value and not bound.inclusive):
                    reasons.append(ReasonCode.NUMERIC_BELOW_MINIMUM)
            if requirement.maximum is not None:
                bound = requirement.maximum
                if number > bound.value or (number == bound.value and not bound.inclusive):
                    reasons.append(ReasonCode.NUMERIC_ABOVE_MAXIMUM)
        elif isinstance(requirement, TemporalConstraint):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise SchemaValidationError(f"action parameter must be a timezone-aware datetime: {requirement.field}")
            _within_temporal_constraint(value, requirement, reasons)
        else:
            raise SchemaValidationError(f"unsupported active requirement type: {type(requirement).__name__}")

    active_keys = {grant.key for grant in application.effective_state.active_grants}
    revoked_keys = {grant.key for grant in application.effective_state.revoked_grants}
    for permission in scenario.action_contract.required_permissions:
        if permission.scope.entity_id is not None and permission.scope.entity_id != scenario.action.entity_id:
            raise SchemaValidationError("required permission scope does not match the canonical action entity")
        if permission not in active_keys:
            reasons.append(
                ReasonCode.PERMISSION_REVOKED if permission in revoked_keys else ReasonCode.PERMISSION_NOT_GRANTED
            )

    # Keep a stable, unique reason-code order and label the all-clear case explicitly.
    ordered_reasons = tuple(dict.fromkeys(reasons))
    if ordered_reasons:
        label = ValidityLabel.INVALID
    else:
        label = ValidityLabel.VALID
        ordered_reasons = (ReasonCode.ACTION_VALID,)
    state = application.effective_state
    return OracleResult(
        label=label,
        reason_codes=ordered_reasons,
        effective_state=state,
        state_digest=state.digest,
        event_audit=application.event_audit,
    )
