"""Versioned, typed records for canonical scenarios and judge-safe projections."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
from typing import TypeAlias


SCHEMA_VERSION = "1.0"


class SchemaValidationError(ValueError):
    """A canonical record is malformed or underspecified."""


class ConstraintEventOrderError(SchemaValidationError):
    """Constraint events are not in a unique chronological order."""


def _nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{field_name} must be a non-empty string")


def _tuple(value: object, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise SchemaValidationError(f"{field_name} must be an immutable tuple")


def _finite_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise SchemaValidationError(f"{field_name} must be a finite Decimal")


def _aware_datetime(value: datetime, field_name: str = "datetime") -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SchemaValidationError(f"{field_name} must be timezone-aware")
    other_fold = value.replace(fold=1 - value.fold)
    if other_fold.utcoffset() != value.utcoffset():
        raise SchemaValidationError(f"{field_name} is an ambiguous local time; provide an explicit ISO 8601 offset")


def canonical_value(value: object) -> object:
    """Convert supported values to a deterministic, type-preserving JSON value."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        _finite_decimal(value, "number")
        return {"$decimal": str(value)}
    if isinstance(value, datetime):
        _aware_datetime(value)
        return {"$datetime": value.isoformat(timespec="microseconds")}
    if is_dataclass(value):
        return {
            "$type": type(value).__name__,
            **{field.name: canonical_value(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, dict):
        return {str(k): canonical_value(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [canonical_value(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise SchemaValidationError(f"unsupported canonical value type: {type(value).__name__}")


def stable_json(value: object) -> str:
    return json.dumps(canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_digest(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


class Domain(str, Enum):
    BOOKING = "booking"
    CUSTOMER_OPERATIONS = "customer_operations"
    SCHEDULING = "scheduling"


class DatasetKind(str, Enum):
    PRIMARY = "primary"
    AUXILIARY_CONTROL = "auxiliary_control"


class TransitionFamily(str, Enum):
    INTRODUCTION = "introduction"
    NUMERICAL_REVISION = "numerical_revision"
    PERMISSION_REVOCATION = "permission_revocation"
    TEMPORAL_REVISION = "temporal_revision"
    NO_CHANGE_RESTATEMENT = "no_change_restatement"


class Partition(str, Enum):
    DEVELOPMENT = "development"
    LOCKED_PRIMARY = "locked_primary"
    LOCKED_AUXILIARY_CONTROL = "locked_auxiliary_control"


class ValidityLabel(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class ValidationStatus(str, Enum):
    NOT_VALIDATED = "not_validated"
    VALIDATED = "validated"
    NEEDS_ADJUDICATION = "needs_adjudication"
    EXCLUDED = "excluded"


class Language(str, Enum):
    ENGLISH = "en"
    MSA = "ar-MSA"


class LanguageCondition(str, Enum):
    EN_EN = "EN-EN"
    AR_AR = "AR-AR"
    EN_AR = "EN-AR"
    AR_EN = "AR-EN"

    @property
    def initial_and_decisive_languages(self) -> tuple[Language, Language]:
        return {
            LanguageCondition.EN_EN: (Language.ENGLISH, Language.ENGLISH),
            LanguageCondition.AR_AR: (Language.MSA, Language.MSA),
            LanguageCondition.EN_AR: (Language.ENGLISH, Language.MSA),
            LanguageCondition.AR_EN: (Language.MSA, Language.ENGLISH),
        }[self]


class TurnRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TextSegmentKind(str, Enum):
    LOCALIZED_NATURAL_LANGUAGE = "localized_natural_language"
    INVARIANT_LITERAL = "invariant_literal"


@dataclass(frozen=True)
class Scope:
    """A constraint scope; `entity_id=None` explicitly means global scope."""

    entity_id: str | None

    def __post_init__(self) -> None:
        if self.entity_id is not None:
            _nonempty(self.entity_id, "scope.entity_id")

    @classmethod
    def global_scope(cls) -> Scope:
        return cls(None)

    @classmethod
    def entity(cls, entity_id: str) -> Scope:
        return cls(entity_id)

    def applies_to(self, entity_id: str) -> bool:
        return self.entity_id is None or self.entity_id == entity_id


@dataclass(frozen=True)
class NumericBound:
    value: Decimal
    inclusive: bool

    def __post_init__(self) -> None:
        _finite_decimal(self.value, "numeric boundary")
        if not isinstance(self.inclusive, bool):
            raise SchemaValidationError("numeric boundary inclusivity must be boolean")


@dataclass(frozen=True)
class TemporalBound:
    value: datetime
    inclusive: bool

    def __post_init__(self) -> None:
        _aware_datetime(self.value, "temporal boundary")
        if not isinstance(self.inclusive, bool):
            raise SchemaValidationError("temporal boundary inclusivity must be boolean")


def _validate_interval(lower: NumericBound | TemporalBound | None, upper: NumericBound | TemporalBound | None) -> None:
    if lower is not None and not isinstance(lower, (NumericBound, TemporalBound)):
        raise SchemaValidationError("lower bound has an unsupported type")
    if upper is not None and not isinstance(upper, (NumericBound, TemporalBound)):
        raise SchemaValidationError("upper bound has an unsupported type")
    if lower is not None and upper is not None and type(lower) is not type(upper):
        raise SchemaValidationError("interval boundaries must have the same type")
    if lower is None and upper is None:
        raise SchemaValidationError("constraint interval must include at least one boundary")
    if lower is None or upper is None:
        return
    low = lower.value
    high = upper.value
    if isinstance(low, datetime):
        # Normalize explicit offsets to instants; never consult the machine's local zone.
        low, high = lower.value.astimezone(timezone.utc), upper.value.astimezone(timezone.utc)
    if low > high or (low == high and not (lower.inclusive and upper.inclusive)):
        raise SchemaValidationError("constraint interval is empty or reversed")


@dataclass(frozen=True)
class NumericConstraint:
    constraint_id: str
    scope: Scope
    field: str
    minimum: NumericBound | None = None
    maximum: NumericBound | None = None
    version: int = 1
    currency_code: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.constraint_id, "constraint_id")
        _nonempty(self.field, "constraint field")
        if not isinstance(self.scope, Scope):
            raise SchemaValidationError("constraint scope must be explicit")
        if self.minimum is not None and not isinstance(self.minimum, NumericBound):
            raise SchemaValidationError("numeric minimum must be a typed NumericBound")
        if self.maximum is not None and not isinstance(self.maximum, NumericBound):
            raise SchemaValidationError("numeric maximum must be a typed NumericBound")
        if type(self.version) is not int or self.version < 1:
            raise SchemaValidationError("constraint version must be positive")
        _validate_interval(self.minimum, self.maximum)
        if self.currency_code is not None and (not isinstance(self.currency_code, str) or not re.fullmatch(r"[A-Z]{3}", self.currency_code)):
            raise SchemaValidationError("currency code must have three-letter uppercase ISO 4217 shape")


@dataclass(frozen=True)
class TemporalConstraint:
    constraint_id: str
    scope: Scope
    field: str
    earliest: TemporalBound | None = None
    latest: TemporalBound | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _nonempty(self.constraint_id, "constraint_id")
        _nonempty(self.field, "constraint field")
        if not isinstance(self.scope, Scope):
            raise SchemaValidationError("constraint scope must be explicit")
        if self.earliest is not None and not isinstance(self.earliest, TemporalBound):
            raise SchemaValidationError("earliest time must be a typed TemporalBound")
        if self.latest is not None and not isinstance(self.latest, TemporalBound):
            raise SchemaValidationError("latest time must be a typed TemporalBound")
        if type(self.version) is not int or self.version < 1:
            raise SchemaValidationError("constraint version must be positive")
        _validate_interval(self.earliest, self.latest)


Requirement: TypeAlias = NumericConstraint | TemporalConstraint


@dataclass(frozen=True)
class PermissionKey:
    permission: str
    scope: Scope

    def __post_init__(self) -> None:
        _nonempty(self.permission, "permission")
        if not isinstance(self.scope, Scope):
            raise SchemaValidationError("permission scope must be explicit")


@dataclass(frozen=True)
class PermissionGrant:
    grant_id: str
    key: PermissionKey

    def __post_init__(self) -> None:
        _nonempty(self.grant_id, "grant_id")
        if not isinstance(self.key, PermissionKey):
            raise SchemaValidationError("permission grant requires an explicit typed permission key")


@dataclass(frozen=True)
class HistoryState:
    requirements: tuple[Requirement, ...] = ()
    grants: tuple[PermissionGrant, ...] = ()

    def __post_init__(self) -> None:
        _tuple(self.requirements, "initial requirements")
        _tuple(self.grants, "initial permission grants")
        if any(not isinstance(item, (NumericConstraint, TemporalConstraint)) for item in self.requirements):
            raise SchemaValidationError("initial state contains an unsupported requirement")
        if any(not isinstance(item, PermissionGrant) for item in self.grants):
            raise SchemaValidationError("initial state contains an unsupported permission grant")
        req_ids = [req.constraint_id for req in self.requirements]
        if len(req_ids) != len(set(req_ids)):
            raise SchemaValidationError("duplicate initial requirement ID")
        grant_ids = [grant.grant_id for grant in self.grants]
        grant_keys = [grant.key for grant in self.grants]
        if len(grant_ids) != len(set(grant_ids)):
            raise SchemaValidationError("duplicate initial permission grant ID")
        if len(grant_keys) != len(set(grant_keys)):
            raise SchemaValidationError("duplicate active initial permission key")


@dataclass(frozen=True)
class ConstraintEvent:
    event_id: str
    turn_index: int
    event_index: int

    def __post_init__(self) -> None:
        _nonempty(self.event_id, "event_id")
        if type(self.turn_index) is not int or type(self.event_index) is not int or self.turn_index < 1 or self.event_index < 0:
            raise SchemaValidationError("event order must use turn_index >= 1 and event_index >= 0")


@dataclass(frozen=True)
class IntroduceRequirement(ConstraintEvent):
    requirement: Requirement

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.requirement, (NumericConstraint, TemporalConstraint)):
            raise SchemaValidationError("introduction requires a typed numeric or temporal requirement")


@dataclass(frozen=True)
class ReviseRequirement(ConstraintEvent):
    constraint_id: str
    replacement: Requirement

    def __post_init__(self) -> None:
        super().__post_init__()
        _nonempty(self.constraint_id, "constraint_id")
        if not isinstance(self.replacement, (NumericConstraint, TemporalConstraint)):
            raise SchemaValidationError("revision requires a typed numeric or temporal replacement")


@dataclass(frozen=True)
class RestateRequirement(ConstraintEvent):
    constraint_id: str
    asserted_requirement: Requirement

    def __post_init__(self) -> None:
        super().__post_init__()
        _nonempty(self.constraint_id, "constraint_id")
        if not isinstance(self.asserted_requirement, (NumericConstraint, TemporalConstraint)):
            raise SchemaValidationError("restatement requires a typed numeric or temporal requirement")


@dataclass(frozen=True)
class RestatePermission(ConstraintEvent):
    grant_id: str
    asserted_key: PermissionKey

    def __post_init__(self) -> None:
        super().__post_init__()
        _nonempty(self.grant_id, "grant_id")
        if not isinstance(self.asserted_key, PermissionKey):
            raise SchemaValidationError("permission restatement requires an explicit typed permission key")


@dataclass(frozen=True)
class GrantPermission(ConstraintEvent):
    grant_id: str
    key: PermissionKey

    def __post_init__(self) -> None:
        super().__post_init__()
        _nonempty(self.grant_id, "grant_id")
        if not isinstance(self.key, PermissionKey):
            raise SchemaValidationError("permission grant event requires a typed permission key")


@dataclass(frozen=True)
class RevokePermission(ConstraintEvent):
    grant_id: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _nonempty(self.grant_id, "grant_id")


ConstraintEventType: TypeAlias = (
    IntroduceRequirement | ReviseRequirement | RestateRequirement | RestatePermission | GrantPermission | RevokePermission
)


@dataclass(frozen=True)
class CounterfactualHistory:
    history_id: str
    parent_scenario_id: str
    pair_id: str
    initial_state: HistoryState
    events: tuple[ConstraintEventType, ...]
    action_turn_index: int
    declared_label: ValidityLabel | None = None

    def __post_init__(self) -> None:
        _nonempty(self.history_id, "history_id")
        _nonempty(self.parent_scenario_id, "parent_scenario_id")
        _nonempty(self.pair_id, "pair_id")
        if not isinstance(self.initial_state, HistoryState):
            raise SchemaValidationError("history requires a typed initial state")
        _tuple(self.events, "constraint events")
        supported_events = (
            IntroduceRequirement,
            ReviseRequirement,
            RestateRequirement,
            RestatePermission,
            GrantPermission,
            RevokePermission,
        )
        if any(not isinstance(event, supported_events) for event in self.events):
            raise SchemaValidationError("history contains an unsupported constraint event")
        if type(self.action_turn_index) is not int or self.action_turn_index < 1:
            raise SchemaValidationError("action turn index must be positive")
        if self.declared_label is not None and not isinstance(self.declared_label, ValidityLabel):
            raise SchemaValidationError("declared validity must use a supported label")


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency_code: str

    def __post_init__(self) -> None:
        _finite_decimal(self.amount, "monetary amount")
        if not isinstance(self.currency_code, str) or not re.fullmatch(r"[A-Z]{3}", self.currency_code):
            raise SchemaValidationError("currency code must have three-letter uppercase ISO 4217 shape")


ActionValue: TypeAlias = str | bool | int | Decimal | datetime | Money


def _action_value_matches_tool_type(value: ActionValue, value_type: str) -> bool:
    if isinstance(value, Money):
        return value_type == "money"
    if isinstance(value, datetime):
        return value_type == "datetime"
    if isinstance(value, bool):
        return value_type == "boolean"
    if isinstance(value, int):
        return value_type in {"integer", "number"}
    if isinstance(value, Decimal):
        return value_type == "number"
    if isinstance(value, str):
        return value_type == "string"
    return False


@dataclass(frozen=True)
class ActionField:
    name: str
    value: ActionValue

    def __post_init__(self) -> None:
        _nonempty(self.name, "action parameter name")
        if isinstance(self.value, float) or self.value is None or not isinstance(self.value, (str, bool, int, Decimal, datetime, Money)):
            raise SchemaValidationError("action parameter has an unsupported type")
        if isinstance(self.value, Decimal):
            _finite_decimal(self.value, "action numeric parameter")
        if isinstance(self.value, datetime):
            _aware_datetime(self.value, "action datetime parameter")


@dataclass(frozen=True)
class CanonicalAction:
    tool_name: str
    entity_id: str
    executed_at: datetime
    fields: tuple[ActionField, ...]

    def __post_init__(self) -> None:
        _nonempty(self.tool_name, "tool_name")
        _nonempty(self.entity_id, "action entity_id")
        _aware_datetime(self.executed_at, "action execution time")
        _tuple(self.fields, "action fields")
        if any(not isinstance(field, ActionField) for field in self.fields):
            raise SchemaValidationError("action fields must be typed ActionField records")
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise SchemaValidationError("duplicate action parameter")

    def parameter(self, name: str) -> ActionValue | None:
        return next((field.value for field in self.fields if field.name == name), None)


@dataclass(frozen=True)
class ActionContract:
    irreversible: bool
    required_permissions: tuple[PermissionKey, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.irreversible, bool):
            raise SchemaValidationError("action irreversibility must be explicit")
        _tuple(self.required_permissions, "required permissions")
        if any(not isinstance(item, PermissionKey) for item in self.required_permissions):
            raise SchemaValidationError("required permissions must be typed PermissionKey records")
        if len(self.required_permissions) != len(set(self.required_permissions)):
            raise SchemaValidationError("duplicate required permission")
        if self.irreversible and not self.required_permissions:
            raise SchemaValidationError("irreversible action must declare required permission")


@dataclass(frozen=True)
class ToolParameterSchema:
    name: str
    value_type: str

    def __post_init__(self) -> None:
        _nonempty(self.name, "tool parameter name")
        if self.value_type not in {"string", "boolean", "integer", "number", "money", "datetime"}:
            raise SchemaValidationError("unsupported public tool parameter type")


@dataclass(frozen=True)
class PublicToolSchema:
    tool_name: str
    version: str
    description: str
    parameters: tuple[ToolParameterSchema, ...]
    irreversible: bool
    required_permissions: tuple[PermissionKey, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.tool_name, "public tool name")
        _nonempty(self.version, "public tool schema version")
        if not isinstance(self.description, str):
            raise SchemaValidationError("public tool description must be text")
        if not isinstance(self.irreversible, bool):
            raise SchemaValidationError("public tool irreversibility must be explicit")
        _tuple(self.parameters, "tool parameter schema")
        _tuple(self.required_permissions, "public tool permissions")
        if any(not isinstance(param, ToolParameterSchema) for param in self.parameters):
            raise SchemaValidationError("public tool parameters must be typed")
        if any(not isinstance(permission, PermissionKey) for permission in self.required_permissions):
            raise SchemaValidationError("public tool permissions must be typed")
        names = [param.name for param in self.parameters]
        if len(names) != len(set(names)):
            raise SchemaValidationError("duplicate public tool parameter")


@dataclass(frozen=True)
class ContextFact:
    key: str
    value: str

    def __post_init__(self) -> None:
        _nonempty(self.key, "context fact key")
        if not isinstance(self.value, str):
            raise SchemaValidationError("context fact value must be text")


@dataclass(frozen=True)
class RevisionRecord:
    revision_id: str
    reason: str
    changed_fields: tuple[str, ...]
    prior_content_sha256: str

    def __post_init__(self) -> None:
        _nonempty(self.revision_id, "revision_id")
        _nonempty(self.reason, "revision reason")
        _tuple(self.changed_fields, "revision changed_fields")
        if not self.changed_fields or any(not isinstance(name, str) or not name.strip() for name in self.changed_fields):
            raise SchemaValidationError("revision must identify changed fields")
        if not re.fullmatch(r"[0-9a-f]{64}", self.prior_content_sha256):
            raise SchemaValidationError("revision prior hash must be lowercase SHA-256")


@dataclass(frozen=True)
class ExclusionRecord:
    exclusion_id: str
    reason: str
    recorded_by: str

    def __post_init__(self) -> None:
        _nonempty(self.exclusion_id, "exclusion_id")
        _nonempty(self.reason, "exclusion reason")
        _nonempty(self.recorded_by, "exclusion recorded_by")


@dataclass(frozen=True)
class ScenarioProvenance:
    source_id: str
    generation_method: str
    authoring_template_id: str
    authoring_template_version: str
    semantic_recipe_id: str
    semantic_recipe_version: str
    validation_status: ValidationStatus
    derivative_ids: tuple[str, ...]
    source_scenario_id: str | None = None
    parent_scenario_id: str | None = None
    revisions: tuple[RevisionRecord, ...] = ()
    exclusions: tuple[ExclusionRecord, ...] = ()

    def __post_init__(self) -> None:
        for key, value in (
            ("source_id", self.source_id),
            ("generation_method", self.generation_method),
            ("authoring_template_id", self.authoring_template_id),
            ("authoring_template_version", self.authoring_template_version),
            ("semantic_recipe_id", self.semantic_recipe_id),
            ("semantic_recipe_version", self.semantic_recipe_version),
        ):
            _nonempty(value, key)
        if self.source_scenario_id is not None:
            _nonempty(self.source_scenario_id, "source_scenario_id")
        if self.parent_scenario_id is not None:
            _nonempty(self.parent_scenario_id, "parent_scenario_id")
        if not isinstance(self.validation_status, ValidationStatus):
            raise SchemaValidationError("validation status must be explicit")
        _tuple(self.derivative_ids, "provenance derivative IDs")
        _tuple(self.revisions, "provenance revisions")
        _tuple(self.exclusions, "provenance exclusions")
        if any(not isinstance(row, RevisionRecord) for row in self.revisions):
            raise SchemaValidationError("provenance revisions must be typed")
        if any(not isinstance(row, ExclusionRecord) for row in self.exclusions):
            raise SchemaValidationError("provenance exclusions must be typed")
        if any(not isinstance(identifier, str) or not identifier.strip() for identifier in self.derivative_ids):
            raise SchemaValidationError("provenance derivative IDs must be non-empty strings")
        if len(self.derivative_ids) != len(set(self.derivative_ids)):
            raise SchemaValidationError("duplicate provenance derivative ID")
        revision_ids = [revision.revision_id for revision in self.revisions]
        exclusion_ids = [record.exclusion_id for record in self.exclusions]
        if len(revision_ids) != len(set(revision_ids)) or len(exclusion_ids) != len(set(exclusion_ids)):
            raise SchemaValidationError("duplicate provenance revision or exclusion ID")
        if self.validation_status is ValidationStatus.EXCLUDED and not self.exclusions:
            raise SchemaValidationError("excluded record requires an exclusion record")


# Concise alias retained for fixture and consumer readability.
Provenance = ScenarioProvenance


@dataclass(frozen=True)
class TextSegment:
    segment_id: str
    kind: TextSegmentKind
    text: str
    literal_name: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.segment_id, "text segment ID")
        if not isinstance(self.kind, TextSegmentKind):
            raise SchemaValidationError("text segment kind must be explicit")
        if not isinstance(self.text, str):
            raise SchemaValidationError("text segment must contain text")
        if self.kind is TextSegmentKind.INVARIANT_LITERAL:
            _nonempty(self.literal_name or "", "invariant literal name")
        elif self.literal_name is not None:
            raise SchemaValidationError("natural-language span cannot have an invariant literal name")


@dataclass(frozen=True)
class ConversationTurn:
    turn_index: int
    role: TurnRole
    language: Language
    segments: tuple[TextSegment, ...]

    def __post_init__(self) -> None:
        if type(self.turn_index) is not int or self.turn_index < 0:
            raise SchemaValidationError("conversation turn index cannot be negative")
        if not isinstance(self.role, TurnRole) or not isinstance(self.language, Language):
            raise SchemaValidationError("conversation turn role and language must be typed")
        _tuple(self.segments, "conversation text spans")
        if any(not isinstance(segment, TextSegment) for segment in self.segments):
            raise SchemaValidationError("conversation spans must be typed TextSegment records")

    @property
    def content(self) -> str:
        return "".join(segment.text for segment in self.segments)


@dataclass(frozen=True)
class TurnLanguageOverride:
    turn_index: int
    language: Language
    reason: str

    def __post_init__(self) -> None:
        if type(self.turn_index) is not int or self.turn_index < 0:
            raise SchemaValidationError("override turn index cannot be negative")
        if not isinstance(self.language, Language):
            raise SchemaValidationError("override language must be explicit")
        _nonempty(self.reason, "language override reason")


@dataclass(frozen=True)
class TurnLanguageAssignment:
    condition: LanguageCondition
    initial_turn_index: int
    decisive_turn_index: int
    approved_other_turn_overrides: tuple[TurnLanguageOverride, ...] = ()
    judge_instruction_language: Language = Language.ENGLISH

    def __post_init__(self) -> None:
        if type(self.initial_turn_index) is not int or type(self.decisive_turn_index) is not int:
            raise SchemaValidationError("language turn indexes must be integers")
        if not isinstance(self.condition, LanguageCondition):
            raise SchemaValidationError("language condition must be one of the approved conditions")
        if not isinstance(self.judge_instruction_language, Language):
            raise SchemaValidationError("judge instruction language must be typed")
        _tuple(self.approved_other_turn_overrides, "approved language overrides")
        if any(not isinstance(override, TurnLanguageOverride) for override in self.approved_other_turn_overrides):
            raise SchemaValidationError("language overrides must be typed records with an explicit reason")
        if self.initial_turn_index < 0 or self.decisive_turn_index <= self.initial_turn_index:
            raise SchemaValidationError("decisive turn must follow the initial turn")
        override_indexes = [override.turn_index for override in self.approved_other_turn_overrides]
        if len(override_indexes) != len(set(override_indexes)):
            raise SchemaValidationError("duplicate language override turn")
        if self.initial_turn_index in override_indexes or self.decisive_turn_index in override_indexes:
            raise SchemaValidationError("initial and decisive turn languages cannot be overridden")

    def validate_turn_languages(self, languages: dict[int, Language]) -> None:
        if self.judge_instruction_language is not Language.ENGLISH:
            raise SchemaValidationError("judge instruction language must be fixed English")
        if self.initial_turn_index not in languages or self.decisive_turn_index not in languages:
            raise SchemaValidationError("initial or decisive turn is missing")
        first, second = self.condition.initial_and_decisive_languages
        if languages[self.initial_turn_index] is not first:
            raise SchemaValidationError("initial turn language does not match the condition")
        if languages[self.decisive_turn_index] is not second:
            raise SchemaValidationError("decisive turn language does not match the condition")
        overrides = {override.turn_index: override.language for override in self.approved_other_turn_overrides}
        if set(overrides) - set(languages):
            raise SchemaValidationError("approved language override refers to a missing conversation turn")
        for index, language in languages.items():
            if index in (self.initial_turn_index, self.decisive_turn_index):
                continue
            if language is not overrides.get(index, first):
                raise SchemaValidationError("other turn language requires an approved override")


@dataclass(frozen=True)
class LanguageVariant:
    derivative_id: str
    scenario_id: str
    parent_history_id: str
    partition: Partition
    assignment: TurnLanguageAssignment
    turns: tuple[ConversationTurn, ...]
    validation_status: ValidationStatus = ValidationStatus.NOT_VALIDATED

    def __post_init__(self) -> None:
        _nonempty(self.derivative_id, "language derivative_id")
        _nonempty(self.scenario_id, "language scenario_id")
        _nonempty(self.parent_history_id, "language parent_history_id")
        if not isinstance(self.partition, Partition) or not isinstance(self.assignment, TurnLanguageAssignment):
            raise SchemaValidationError("language derivative requires typed partition and assignment")
        if not isinstance(self.validation_status, ValidationStatus):
            raise SchemaValidationError("language validation status must be explicit")
        _tuple(self.turns, "conversation turns")
        if any(not isinstance(turn, ConversationTurn) for turn in self.turns):
            raise SchemaValidationError("language derivative turns must be typed")
        indexes = [turn.turn_index for turn in self.turns]
        if len(indexes) != len(set(indexes)) or indexes != sorted(indexes):
            raise SchemaValidationError("conversation turns must be uniquely and chronologically ordered")
        self.assignment.validate_turn_languages({turn.turn_index: turn.language for turn in self.turns})
        turns_by_index = {turn.turn_index: turn for turn in self.turns}
        if (
            turns_by_index[self.assignment.initial_turn_index].role is not TurnRole.USER
            or turns_by_index[self.assignment.decisive_turn_index].role is not TurnRole.USER
        ):
            raise SchemaValidationError("initial context and decisive constraint turns must be user turns")


@dataclass(frozen=True)
class CanonicalScenario:
    schema_version: str
    scenario_id: str
    kind: DatasetKind
    domain: Domain
    transition_family: TransitionFamily
    partition: Partition
    shared_context: tuple[ContextFact, ...]
    action: CanonicalAction
    action_contract: ActionContract
    public_tool_schema: PublicToolSchema
    histories: tuple[CounterfactualHistory, CounterfactualHistory]
    provenance: ScenarioProvenance
    match_set_id: str | None = None
    language_variants: tuple[LanguageVariant, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaValidationError(f"unsupported schema version: {self.schema_version}")
        _nonempty(self.scenario_id, "scenario_id")
        if not isinstance(self.kind, DatasetKind) or not isinstance(self.domain, Domain):
            raise SchemaValidationError("scenario kind and domain must use the versioned enums")
        if not isinstance(self.transition_family, TransitionFamily) or not isinstance(self.partition, Partition):
            raise SchemaValidationError("scenario transition family and partition must be explicit")
        _tuple(self.shared_context, "scenario shared_context")
        _tuple(self.histories, "scenario histories")
        _tuple(self.language_variants, "scenario language_variants")
        if any(not isinstance(fact, ContextFact) for fact in self.shared_context):
            raise SchemaValidationError("scenario shared context must use typed facts")
        context_keys = [fact.key for fact in self.shared_context]
        if len(context_keys) != len(set(context_keys)):
            raise SchemaValidationError("shared context fact keys must be unique")
        if any(not isinstance(history, CounterfactualHistory) for history in self.histories):
            raise SchemaValidationError("scenario histories must be typed records")
        if any(not isinstance(variant, LanguageVariant) for variant in self.language_variants):
            raise SchemaValidationError("scenario language variants must be typed records")
        if not isinstance(self.action, CanonicalAction) or not isinstance(self.action_contract, ActionContract):
            raise SchemaValidationError("scenario action and action contract must be typed")
        if not isinstance(self.public_tool_schema, PublicToolSchema) or not isinstance(self.provenance, ScenarioProvenance):
            raise SchemaValidationError("scenario tool schema and provenance must be typed")
        if self.kind is DatasetKind.PRIMARY:
            if self.partition is Partition.LOCKED_AUXILIARY_CONTROL:
                raise SchemaValidationError("primary scenario cannot use auxiliary-control partition")
            if self.transition_family is TransitionFamily.NO_CHANGE_RESTATEMENT:
                raise SchemaValidationError("primary scenario requires a consequential transition family")
        elif self.kind is DatasetKind.AUXILIARY_CONTROL:
            if self.partition is not Partition.LOCKED_AUXILIARY_CONTROL:
                raise SchemaValidationError("auxiliary control must use locked auxiliary-control partition")
            if self.transition_family is not TransitionFamily.NO_CHANGE_RESTATEMENT:
                raise SchemaValidationError("auxiliary control requires no-change transition family")
        if self.match_set_id is not None:
            _nonempty(self.match_set_id, "match_set_id")
        if len(self.histories) != 2:
            raise SchemaValidationError("canonical scenario must have exactly two counterfactual histories")
        if self.public_tool_schema.tool_name != self.action.tool_name:
            raise SchemaValidationError("canonical action tool must match the public tool schema")
        if self.public_tool_schema.irreversible != self.action_contract.irreversible:
            raise SchemaValidationError("action contract and public tool schema disagree on irreversibility")
        if self.public_tool_schema.required_permissions != self.action_contract.required_permissions:
            raise SchemaValidationError("action contract and public tool schema disagree on permissions")
        public_parameters = {parameter.name: parameter.value_type for parameter in self.public_tool_schema.parameters}
        for field in self.action.fields:
            expected_type = public_parameters.get(field.name)
            if expected_type is None:
                raise SchemaValidationError(f"action parameter is absent from the public tool schema: {field.name}")
            if not _action_value_matches_tool_type(field.value, expected_type):
                raise SchemaValidationError(f"action parameter type disagrees with the public tool schema: {field.name}")


class ReasonCode(str, Enum):
    ACTION_VALID = "ACTION_VALID"
    NUMERIC_BELOW_MINIMUM = "NUMERIC_BELOW_MINIMUM"
    NUMERIC_ABOVE_MAXIMUM = "NUMERIC_ABOVE_MAXIMUM"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    TEMPORAL_BEFORE_EARLIEST = "TEMPORAL_BEFORE_EARLIEST"
    TEMPORAL_AFTER_LATEST = "TEMPORAL_AFTER_LATEST"
    PERMISSION_NOT_GRANTED = "PERMISSION_NOT_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"


@dataclass(frozen=True)
class EffectiveState:
    active_requirements: tuple[Requirement, ...]
    active_grants: tuple[PermissionGrant, ...]
    revoked_grants: tuple[PermissionGrant, ...]
    superseded_requirements: tuple[Requirement, ...]

    @property
    def digest(self) -> str:
        return stable_digest(self)


@dataclass(frozen=True)
class EventAudit:
    event_id: str
    before_digest: str
    after_digest: str


@dataclass(frozen=True)
class OracleResult:
    label: ValidityLabel
    reason_codes: tuple[ReasonCode, ...]
    effective_state: EffectiveState
    state_digest: str
    event_audit: tuple[EventAudit, ...]


@dataclass(frozen=True)
class PartitionSubject:
    scenario_id: str
    kind: DatasetKind
    domain: Domain
    transition_family: TransitionFamily

    def __post_init__(self) -> None:
        _nonempty(self.scenario_id, "partition subject scenario_id")
        if not isinstance(self.kind, DatasetKind) or not isinstance(self.domain, Domain):
            raise SchemaValidationError("partition subject kind and domain must be typed")
        if not isinstance(self.transition_family, TransitionFamily):
            raise SchemaValidationError("partition subject transition family must be typed")
        if (self.kind is DatasetKind.PRIMARY) == (self.transition_family is TransitionFamily.NO_CHANGE_RESTATEMENT):
            raise SchemaValidationError("partition subject kind and transition family disagree")


@dataclass(frozen=True)
class PartitionAssignment:
    scenario_id: str
    kind: DatasetKind
    domain: Domain
    transition_family: TransitionFamily
    partition: Partition

    def __post_init__(self) -> None:
        _nonempty(self.scenario_id, "partition assignment scenario_id")
        if not isinstance(self.kind, DatasetKind) or not isinstance(self.domain, Domain):
            raise SchemaValidationError("partition assignment kind and domain must be typed")
        if not isinstance(self.transition_family, TransitionFamily) or not isinstance(self.partition, Partition):
            raise SchemaValidationError("partition assignment family and partition must be typed")
        if (self.kind is DatasetKind.PRIMARY) == (self.transition_family is TransitionFamily.NO_CHANGE_RESTATEMENT):
            raise SchemaValidationError("partition assignment kind and transition family disagree")


class MatchQuality(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class MatchRecord:
    match_set_id: str
    primary_scenario_id: str | None
    control_scenario_id: str
    quality: MatchQuality
    matched_dimensions: tuple[str, ...]
    note: str

    def __post_init__(self) -> None:
        _nonempty(self.match_set_id, "match_set_id")
        _nonempty(self.control_scenario_id, "control_scenario_id")
        _nonempty(self.note, "match note")
        _tuple(self.matched_dimensions, "matched dimensions")
        if not isinstance(self.quality, MatchQuality):
            raise SchemaValidationError("match quality must be explicit")
        if self.primary_scenario_id is not None:
            _nonempty(self.primary_scenario_id, "primary_scenario_id")
        required_dimensions = {"domain", "constraint_type", "final_state_pair", "action_complexity", "turn_structure"}
        if len(self.matched_dimensions) != len(set(self.matched_dimensions)) or not set(self.matched_dimensions) <= required_dimensions:
            raise SchemaValidationError("matched dimensions must be unique approved matching fields")
        if self.quality is MatchQuality.UNMATCHED:
            if self.primary_scenario_id is not None or self.matched_dimensions:
                raise SchemaValidationError("unmatched control cannot name a primary or matched dimensions")
        elif self.primary_scenario_id is None or not self.matched_dimensions:
            raise SchemaValidationError("matched control requires a primary and recorded matching dimensions")
        elif self.quality is MatchQuality.FULL and set(self.matched_dimensions) != required_dimensions:
            raise SchemaValidationError("full match requires every predeclared matching dimension")
        elif self.quality is MatchQuality.PARTIAL and set(self.matched_dimensions) == required_dimensions:
            raise SchemaValidationError("match with every dimension must be labeled full")
