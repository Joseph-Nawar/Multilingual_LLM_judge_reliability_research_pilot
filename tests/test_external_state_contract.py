import pytest

from multilingual_judge_pilot.external_state_contract import (
    STATE_EXTRACTION_SCHEMA_V2,
    normalize_constraint_state_v2,
)


def test_temporal_schema_omits_currency_and_normalizes_timezone_equivalent_values():
    assert "currency_code" not in STATE_EXTRACTION_SCHEMA_V2["properties"]["temporal_constraints"]["items"]["properties"]
    state = {
        "numerical_constraints": [],
        "temporal_constraints": [
            {
                "field": "appointment_time",
                "scope_entity": "booking-1",
                "lower_bound": {"value": "2026-11-12T14:00:00+02:00", "inclusive": True},
                "upper_bound": None,
            }
        ],
        "active_permissions": [],
    }
    normalized = normalize_constraint_state_v2(state)
    assert normalized["temporal_constraints"] == {
        ("appointment_time", "booking-1", ("2026-11-12T12:00:00.000000+00:00", True), None)
    }


def test_numeric_schema_and_normalizer_agree_on_currency_and_decimal_forms():
    numeric_schema = STATE_EXTRACTION_SCHEMA_V2["properties"]["numerical_constraints"]["items"]
    assert "currency_code" in numeric_schema["required"]
    state = {
        "numerical_constraints": [
            {
                "field": "price",
                "scope_entity": "booking-1",
                "lower_bound": None,
                "upper_bound": {"value": "025.00", "inclusive": False},
                "currency_code": "USD",
            }
        ],
        "temporal_constraints": [],
        "active_permissions": [],
    }
    normalized = normalize_constraint_state_v2(state)
    assert normalized["numerical_constraints"] == {
        ("price", "booking-1", None, ("25", False), "USD")
    }


def test_permissions_are_scoped_active_grants_and_duplicates_are_rejected():
    state = {
        "numerical_constraints": [],
        "temporal_constraints": [],
        "active_permissions": [
            {"permission": "send_confirmation", "scope_entity": "booking-1"}
        ],
    }
    assert normalize_constraint_state_v2(state)["active_permissions"] == {
        ("send_confirmation", "booking-1")
    }
    state["active_permissions"].append(state["active_permissions"][0])
    with pytest.raises(ValueError, match="duplicate_permission"):
        normalize_constraint_state_v2(state)


def test_schema_patterns_match_numeric_and_timezone_normalizer_requirements():
    numeric_boundary = STATE_EXTRACTION_SCHEMA_V2["properties"]["numerical_constraints"]["items"]["properties"]["upper_bound"]["properties"]["value"]
    temporal_boundary = STATE_EXTRACTION_SCHEMA_V2["properties"]["temporal_constraints"]["items"]["properties"]["upper_bound"]["properties"]["value"]
    numerical_row = STATE_EXTRACTION_SCHEMA_V2["properties"]["numerical_constraints"]["items"]
    assert numeric_boundary["pattern"] == r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
    assert temporal_boundary["pattern"] == r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
    assert numerical_row["properties"]["field"]["pattern"] == r".*\S.*"
    assert numerical_row["properties"]["currency_code"]["pattern"] == r"^[A-Za-z]{3}$"


def test_whitespace_fields_and_malformed_currency_codes_are_rejected():
    state = {
        "numerical_constraints": [
            {
                "field": "   ",
                "scope_entity": None,
                "lower_bound": None,
                "upper_bound": {"value": "5", "inclusive": True},
                "currency_code": "USD",
            }
        ],
        "temporal_constraints": [],
        "active_permissions": [],
    }
    with pytest.raises(ValueError, match="invalid_constraint_field"):
        normalize_constraint_state_v2(state)
    state["numerical_constraints"][0]["field"] = "price"
    state["numerical_constraints"][0]["currency_code"] = "us"
    with pytest.raises(ValueError, match="invalid_currency"):
        normalize_constraint_state_v2(state)


def test_empty_bounds_and_timezone_naive_times_are_rejected():
    empty_bound = {
        "numerical_constraints": [
            {
                "field": "price",
                "scope_entity": None,
                "lower_bound": None,
                "upper_bound": None,
                "currency_code": None,
            }
        ],
        "temporal_constraints": [],
        "active_permissions": [],
    }
    with pytest.raises(ValueError, match="constraint_without_bound"):
        normalize_constraint_state_v2(empty_bound)

    naive = {
        "numerical_constraints": [],
        "temporal_constraints": [
            {
                "field": "appointment_time",
                "scope_entity": None,
                "lower_bound": {"value": "2026-11-12T14:00:00", "inclusive": True},
                "upper_bound": None,
            }
        ],
        "active_permissions": [],
    }
    with pytest.raises(ValueError, match="invalid_temporal_boundary"):
        normalize_constraint_state_v2(naive)
