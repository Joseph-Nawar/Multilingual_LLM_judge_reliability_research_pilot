"""Counterfactual, partition, provenance, and duplicate validation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import unicodedata
import re

from .oracle import evaluate_history
from .schema import (
    CanonicalScenario,
    ConstraintEventOrderError,
    DatasetKind,
    Domain,
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


def _history_events_have_family(scenario: CanonicalScenario) -> bool:
    events = tuple(event for history in scenario.histories for event in history.events)
    family = scenario.transition_family
    if family is TransitionFamily.INTRODUCTION:
        return any(isinstance(event, IntroduceRequirement) for event in events)
    if family is TransitionFamily.NUMERICAL_REVISION:
        return any(isinstance(event, ReviseRequirement) and isinstance(event.replacement, NumericConstraint) for event in events)
    if family is TransitionFamily.PERMISSION_REVOCATION:
        return any(isinstance(event, RevokePermission) for event in events)
    if family is TransitionFamily.TEMPORAL_REVISION:
        return any(isinstance(event, ReviseRequirement) and isinstance(event.replacement, TemporalConstraint) for event in events)
    return False


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
    return tuple(evaluate_history(scenario, history.history_id) for history in scenario.histories)


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

    if scenario.kind is DatasetKind.PRIMARY:
        if not _history_events_have_family(scenario):
            raise SchemaValidationError("primary pair lacks an event for its consequential transition family")
        if results[0].state_digest == results[1].state_digest:
            raise SchemaValidationError("primary counterfactual histories must have different effective states")
    else:
        if any(not history.events for history in scenario.histories):
            raise SchemaValidationError("each no-change control history requires a later restatement")
        for history, result in zip(scenario.histories, results, strict=True):
            if not all(isinstance(event, (RestateRequirement, RestatePermission)) for event in history.events):
                raise SchemaValidationError("no-change controls cannot contain state-changing events")
            if not result.event_audit or any(step.before_digest != step.after_digest for step in result.event_audit):
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
