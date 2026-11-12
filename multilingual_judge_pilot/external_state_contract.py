"""Versioned constraint-state response contract for prospective H2 diagnostics.

This module does not read study or benchmark data. Temporal and numerical
constraints use separate arrays so currency is structurally impossible on a
temporal row; the normalizer enforces the same required keys and boundary
rules as the schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any


NUMERIC_PATTERN = r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
TEMPORAL_PATTERN = (
    r"^(?:000[1-9]|00[1-9]\d|0[1-9]\d{2}|[1-9]\d{3})-"
    r"(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T"
    r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


def _boundary_schema(*, temporal: bool) -> dict[str, Any]:
    value_schema = {"type": "string"}
    if temporal:
        value_schema.update({"format": "date-time", "pattern": TEMPORAL_PATTERN})
    else:
        value_schema["pattern"] = NUMERIC_PATTERN
    return {
        "type": ["object", "null"],
        "properties": {
            "value": value_schema,
            "inclusive": {"type": "boolean"},
        },
        "required": ["value", "inclusive"],
        "additionalProperties": False,
    }


def _bounded_constraint_schema(*, numerical: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "field": {"type": "string", "minLength": 1, "pattern": r".*\S.*"},
        "scope_entity": {"type": ["string", "null"]},
        "lower_bound": _boundary_schema(temporal=not numerical),
        "upper_bound": _boundary_schema(temporal=not numerical),
    }
    required = ["field", "scope_entity", "lower_bound", "upper_bound"]
    if numerical:
        properties["currency_code"] = {"type": ["string", "null"], "pattern": r"^[A-Za-z]{3}$"}
        required.append("currency_code")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
        "anyOf": [
            {"properties": {"lower_bound": {"type": "object"}}},
            {"properties": {"upper_bound": {"type": "object"}}},
        ],
    }


STATE_EXTRACTION_SCHEMA_V2: dict[str, Any] = {
    "type": "object",
    "properties": {
        "numerical_constraints": {
            "type": "array",
            "items": _bounded_constraint_schema(numerical=True),
        },
        "temporal_constraints": {
            "type": "array",
            "items": _bounded_constraint_schema(numerical=False),
        },
        "active_permissions": {
            "type": "array",
            "uniqueItems": True,
            "items": {
                "type": "object",
                "properties": {
                    "permission": {"type": "string", "minLength": 1, "pattern": r".*\S.*"},
                    "scope_entity": {"type": ["string", "null"]},
                },
                "required": ["permission", "scope_entity"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["numerical_constraints", "temporal_constraints", "active_permissions"],
    "additionalProperties": False,
}


def _normalize_boundary(value: Any, *, temporal: bool) -> tuple[str, bool] | None:
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"value", "inclusive"}
        or not isinstance(value["value"], str)
        or type(value["inclusive"]) is not bool
    ):
        raise ValueError("invalid_boundary")
    if not temporal:
        if re.fullmatch(NUMERIC_PATTERN[1:-1], value["value"]) is None:
            raise ValueError("invalid_numeric_boundary")
        try:
            amount = Decimal(value["value"])
        except InvalidOperation:
            raise ValueError("invalid_numeric_boundary") from None
        if not amount.is_finite():
            raise ValueError("invalid_numeric_boundary")
        normalized = str(amount.normalize()) if amount else "0"
    else:
        if re.fullmatch(TEMPORAL_PATTERN[1:-1], value["value"]) is None:
            raise ValueError("invalid_temporal_boundary")
        try:
            parsed = datetime.fromisoformat(value["value"].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid_temporal_boundary") from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("naive_temporal_boundary")
        normalized = parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return normalized, value["inclusive"]


def _normalize_constraint_rows(
    rows: Any, *, temporal: bool
) -> set[tuple[Any, ...]]:
    if not isinstance(rows, list):
        raise ValueError("invalid_constraint_list")
    expected_keys = {"field", "scope_entity", "lower_bound", "upper_bound"}
    if not temporal:
        expected_keys.add("currency_code")
    normalized: list[tuple[Any, ...]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise ValueError("invalid_constraint_keys")
        field = row["field"]
        scope = row["scope_entity"]
        if not isinstance(field, str) or not field.strip():
            raise ValueError("invalid_constraint_field")
        field = field.strip()
        if scope is not None and not isinstance(scope, str):
            raise ValueError("invalid_scope")
        lower = _normalize_boundary(row["lower_bound"], temporal=temporal)
        upper = _normalize_boundary(row["upper_bound"], temporal=temporal)
        if lower is None and upper is None:
            raise ValueError("constraint_without_bound")
        if temporal:
            normalized.append((field, scope, lower, upper))
        else:
            currency = row["currency_code"]
            if currency is not None and (
                not isinstance(currency, str) or re.fullmatch(r"[A-Za-z]{3}", currency) is None
            ):
                raise ValueError("invalid_currency")
            normalized.append((field, scope, lower, upper, currency.upper() if currency else None))
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate_constraint")
    return set(normalized)


def normalize_constraint_state_v2(state: Any) -> dict[str, set[tuple[Any, ...]]]:
    """Validate and normalize a v2 active-constraint state.

    Temporal boundaries are timezone-aware ISO-8601 strings and normalize to
    UTC. Numeric boundaries are finite decimal strings. Permission rows mean
    active grants only; a revoked permission must not appear in this array.
    """
    if not isinstance(state, dict) or set(state) != {
        "numerical_constraints",
        "temporal_constraints",
        "active_permissions",
    }:
        raise ValueError("invalid_state_keys")
    numerical = _normalize_constraint_rows(state["numerical_constraints"], temporal=False)
    temporal = _normalize_constraint_rows(state["temporal_constraints"], temporal=True)
    permissions_raw = state["active_permissions"]
    if not isinstance(permissions_raw, list):
        raise ValueError("invalid_permission_list")
    permissions: list[tuple[str, str | None]] = []
    for row in permissions_raw:
        if (
            not isinstance(row, dict)
            or set(row) != {"permission", "scope_entity"}
            or not isinstance(row["permission"], str)
            or not row["permission"].strip()
        ):
            raise ValueError("invalid_permission")
        permission = row["permission"].strip()
        scope = row["scope_entity"]
        if scope is not None and not isinstance(scope, str):
            raise ValueError("invalid_permission_scope")
        permissions.append((permission, scope))
    if len(permissions) != len(set(permissions)):
        raise ValueError("duplicate_permission")
    return {
        "numerical_constraints": numerical,
        "temporal_constraints": temporal,
        "active_permissions": set(permissions),
    }
