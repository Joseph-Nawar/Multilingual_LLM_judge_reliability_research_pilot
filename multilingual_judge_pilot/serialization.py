"""Strict canonical JSON codec and allowlisted judge-facing projection."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
import re
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from . import schema
from .integrity import validate_scenario
from .schema import (
    CanonicalScenario,
    CanonicalAction,
    PublicToolSchema,
    SchemaValidationError,
    SCHEMA_VERSION,
)


@dataclass(frozen=True)
class JudgeConversationTurn:
    speaker: str
    content: str


@dataclass(frozen=True)
class JudgeFacingItem:
    """Allowlisted judge input; reference-only fields have no representation here."""

    item_id: str
    conversation: tuple[JudgeConversationTurn, ...]
    action: CanonicalAction
    public_tool_schema: PublicToolSchema


def _encode(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise SchemaValidationError("non-finite Decimal cannot be serialized")
        return {"$decimal": str(value)}
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise SchemaValidationError("timezone-naive datetime cannot be serialized")
        other_fold = value.replace(fold=1 - value.fold)
        if other_fold.utcoffset() != value.utcoffset():
            raise SchemaValidationError("ambiguous local datetime cannot be serialized")
        return {"$datetime": value.isoformat(timespec="microseconds")}
    if is_dataclass(value):
        return {"$type": type(value).__name__, **{field.name: _encode(getattr(value, field.name)) for field in fields(value)}}
    if isinstance(value, (tuple, list)):
        return [_encode(child) for child in value]
    if isinstance(value, dict):
        return {str(key): _encode(value[key]) for key in sorted(value, key=str)}
    if value is None or type(value) in (str, int, bool):
        return value
    raise SchemaValidationError(f"unsupported JSON value type: {type(value).__name__}")


def _decode(value: object, expected: object) -> object:
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        candidates = [candidate for candidate in args if candidate is not type(None)]
        if isinstance(value, dict) and "$type" in value:
            tag = value["$type"]
            candidates = [candidate for candidate in candidates if isinstance(candidate, type) and candidate.__name__ == tag]
        errors = []
        for candidate in candidates:
            try:
                return _decode(value, candidate)
            except (SchemaValidationError, ValueError, TypeError) as exc:
                errors.append(str(exc))
        raise SchemaValidationError(f"value does not match declared union: {'; '.join(errors)}")
    if origin is tuple:
        if not isinstance(value, list):
            raise SchemaValidationError("tuple field must be encoded as a JSON array")
        if args and args[-1] is Ellipsis:
            return tuple(_decode(item, args[0]) for item in value)
        if args:
            if len(args) != len(value):
                raise SchemaValidationError("tuple has the wrong number of entries")
            return tuple(_decode(item, item_type) for item, item_type in zip(value, args, strict=True))
        return tuple(value)
    if origin is list:
        if not isinstance(value, list):
            raise SchemaValidationError("list field must be encoded as a JSON array")
        item_type = args[0] if args else Any
        return [_decode(item, item_type) for item in value]
    if expected is Any:
        return value
    if expected is Decimal:
        if not isinstance(value, dict) or set(value) != {"$decimal"} or not isinstance(value["$decimal"], str):
            raise SchemaValidationError("Decimal must use a tagged decimal string")
        try:
            number = Decimal(value["$decimal"])
        except InvalidOperation as exc:
            raise SchemaValidationError("invalid Decimal string") from exc
        if not number.is_finite():
            raise SchemaValidationError("non-finite Decimal is not allowed")
        return number
    if expected is datetime:
        if not isinstance(value, dict) or set(value) != {"$datetime"} or not isinstance(value["$datetime"], str):
            raise SchemaValidationError("datetime must use a tagged ISO 8601 string")
        raw = value["$datetime"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", raw):
            raise SchemaValidationError("datetime must be ISO 8601 with seconds and an explicit UTC offset")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SchemaValidationError("invalid ISO 8601 datetime") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise SchemaValidationError("datetime must include a UTC offset")
        return parsed
    if isinstance(expected, type) and issubclass(expected, Enum):
        if not isinstance(value, str):
            raise SchemaValidationError(f"{expected.__name__} must be a string enum value")
        try:
            return expected(value)
        except ValueError as exc:
            raise SchemaValidationError(f"unsupported {expected.__name__}: {value}") from exc
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict) or value.get("$type") != expected.__name__:
            raise SchemaValidationError(f"expected tagged {expected.__name__} record")
        allowed = {field.name for field in fields(expected)} | {"$type"}
        unknown = set(value) - allowed
        if unknown:
            raise SchemaValidationError(f"unknown field(s) in {expected.__name__}: {', '.join(sorted(unknown))}")
        hints = get_type_hints(expected)
        kwargs = {
            field.name: _decode(value[field.name], hints[field.name])
            for field in fields(expected)
            if field.name in value
        }
        required_fields = {
            field.name
            for field in fields(expected)
            if field.default is MISSING and field.default_factory is MISSING
        }
        absent = required_fields - set(kwargs)
        if absent:
            raise SchemaValidationError(f"missing required field(s) in {expected.__name__}: {', '.join(sorted(absent))}")
        try:
            return expected(**kwargs)
        except (TypeError, ValueError) as exc:
            if isinstance(exc, SchemaValidationError):
                raise
            raise SchemaValidationError(f"invalid {expected.__name__} record: {exc}") from exc
    if expected is str:
        if type(value) is not str:
            raise SchemaValidationError("expected string")
        return value
    if expected is bool:
        if type(value) is not bool:
            raise SchemaValidationError("expected boolean")
        return value
    if expected is int:
        if type(value) is not int:
            raise SchemaValidationError("expected integer")
        return value
    if value is None:
        return None
    if isinstance(expected, type) and isinstance(value, expected):
        return value
    raise SchemaValidationError(f"value does not match type {expected}")


def scenario_to_json(scenario: CanonicalScenario) -> str:
    validate_scenario(scenario)
    payload = {"schema_version": SCHEMA_VERSION, "scenario": _encode(scenario)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def scenario_from_json(text: str) -> CanonicalScenario:
    try:
        payload = json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON constant {value}")))
    except (json.JSONDecodeError, ValueError) as exc:
        raise SchemaValidationError(f"invalid canonical JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SchemaValidationError("scenario JSON root must be an object")
    allowed_root = {"schema_version", "scenario"}
    unknown_root = set(payload) - allowed_root
    if unknown_root:
        raise SchemaValidationError(f"unknown field(s) in scenario JSON: {', '.join(sorted(unknown_root))}")
    missing_root = allowed_root - set(payload)
    if missing_root:
        raise SchemaValidationError(f"missing scenario JSON field(s): {', '.join(sorted(missing_root))}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise SchemaValidationError(f"unsupported schema version: {payload['schema_version']}")
    result = _decode(payload["scenario"], CanonicalScenario)
    if not isinstance(result, CanonicalScenario):
        raise SchemaValidationError("scenario payload did not decode to a canonical scenario")
    validate_scenario(result)
    return result


def _field_to_public(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, schema.Money):
        return {"amount": str(value.amount), "currency": value.currency_code}
    return value


def build_judge_facing_item(
    scenario: CanonicalScenario,
    history_id: str,
    derivative_id: str,
    *,
    opaque_item_id: str,
) -> JudgeFacingItem:
    """Build a judge input using an explicit allowlist; never serialize the canonical record."""
    validate_scenario(scenario)
    history = next((row for row in scenario.histories if row.history_id == history_id), None)
    variant = next((row for row in scenario.language_variants if row.derivative_id == derivative_id), None)
    if history is None or variant is None or variant.parent_history_id != history_id:
        raise SchemaValidationError("judge projection history/variant relationship is unresolved")
    provenance = scenario.provenance
    internal_identifiers = {
        scenario.scenario_id,
        history.history_id,
        history.pair_id,
        derivative_id,
        provenance.source_id,
        provenance.authoring_template_id,
        provenance.authoring_template_version,
        provenance.semantic_recipe_id,
        provenance.semantic_recipe_version,
        provenance.source_scenario_id,
        provenance.parent_scenario_id,
        scenario.match_set_id,
        *(event.event_id for row in scenario.histories for event in row.events),
        *(record.revision_id for record in provenance.revisions),
        *(record.exclusion_id for record in provenance.exclusions),
    }
    if not opaque_item_id or opaque_item_id in internal_identifiers:
        raise SchemaValidationError("judge input requires a non-empty opaque item ID")
    if not variant.turns or any(not turn.content for turn in variant.turns):
        raise SchemaValidationError("judge-facing conversation turns must have non-empty content")

    return JudgeFacingItem(
        item_id=opaque_item_id,
        conversation=tuple(JudgeConversationTurn(turn.role.value, turn.content) for turn in variant.turns),
        action=scenario.action,
        public_tool_schema=scenario.public_tool_schema,
    )


def judge_facing_to_dict(item: JudgeFacingItem) -> dict:
    """Render only the documented judge-facing allowlist from immutable typed values."""
    if not isinstance(item, JudgeFacingItem):
        raise SchemaValidationError("judge serializer accepts only a JudgeFacingItem")
    action = item.action
    tool_schema = item.public_tool_schema
    return {
        "item_id": item.item_id,
        "conversation": [{"speaker": turn.speaker, "content": turn.content} for turn in item.conversation],
        "action": {
            "tool_name": action.tool_name,
            "entity_id": action.entity_id,
            "executed_at": action.executed_at.isoformat(timespec="microseconds"),
            "parameters": {field.name: _field_to_public(field.value) for field in action.fields},
        },
        "public_tool_schema": {
            "tool_name": tool_schema.tool_name,
            "version": tool_schema.version,
            "description": tool_schema.description,
            "parameters": [
                {"name": param.name, "type": param.value_type, "required": param.required}
                for param in tool_schema.parameters
            ],
            "irreversible": tool_schema.irreversible,
            "required_permissions": [
                {
                    "permission": permission.permission,
                    "scope": (
                        {"type": "global"}
                        if permission.scope.entity_id is None
                        else {"type": "entity", "entity_id": permission.scope.entity_id}
                    ),
                }
                for permission in tool_schema.required_permissions
            ],
        },
    }


def judge_facing_to_json(item: JudgeFacingItem) -> str:
    payload = judge_facing_to_dict(item)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
