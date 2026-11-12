import pytest

from multilingual_judge_pilot.external_dst import (
    flatten_multiwoz_state,
    make_state_output_schema,
    parse_state_output,
    normalize_state_mapping,
    score_state_maps,
)


SLOTS = ("train-arriveby", "train-day", "train-leaveat", "train-book people", "hotel-area", "hotel-book people")


def test_multiwoz_state_flattens_semis_and_booking_constraints_without_system_booking_results():
    state = {
        "train": {
            "semi": {"arriveBy": "18:00", "day": "Monday", "leaveAt": "not mentioned"},
            "book": {"people": "2", "booked": [{"reference": "system-result"}]},
        },
        "hotel": {"semi": {"area": "dontcare"}, "book": {"people": ""}},
    }
    normalized = flatten_multiwoz_state(state, SLOTS)
    assert normalized == {
        "train-arriveby": "18:00",
        "train-day": "monday",
        "train-book people": "2",
        "hotel-area": "dontcare",
    }


def test_time_normalization_accepts_equivalent_24h_12h_and_arabic_forms():
    assert normalize_state_mapping({"train-arriveby": "6:00 PM"}, SLOTS)["train-arriveby"] == "18:00"
    assert normalize_state_mapping({"train-arriveby": "٦:٠٠ مساءً"}, SLOTS)["train-arriveby"] == "18:00"


def test_state_schema_is_sparse_and_rejects_unknown_or_null_values():
    schema = make_state_output_schema(SLOTS)
    assert schema["properties"]["state"]["additionalProperties"] is False
    assert set(schema["properties"]["state"]["properties"]) == set(SLOTS)
    assert normalize_state_mapping({"hotel-area": "North"}, SLOTS) == {"hotel-area": "north"}
    with pytest.raises(ValueError, match="unknown_slot"):
        normalize_state_mapping({"hotel-unknown": "x"}, SLOTS)
    with pytest.raises(ValueError, match="invalid_slot_value"):
        normalize_state_mapping({"hotel-area": None}, SLOTS)


def test_gold_state_rejects_annotations_outside_the_declared_slot_inventory():
    with pytest.raises(ValueError, match="unknown_gold_slot"):
        flatten_multiwoz_state({"hotel": {"semi": {"area": "north"}}}, ())


def test_gold_state_ignores_untracked_fields_when_the_source_marks_them_absent():
    assert flatten_multiwoz_state(
        {"bus": {"semi": {"leaveAt": ""}}}, ()
    ) == {}


def test_state_output_parser_accepts_only_unique_strict_json():
    assert parse_state_output('{"state":{"hotel-area":"North"}}', SLOTS) == {
        "hotel-area": "north"
    }
    with pytest.raises(ValueError, match="duplicate_json_key"):
        parse_state_output('{"state":{"hotel-area":"north","hotel-area":"south"}}', SLOTS)
    with pytest.raises(ValueError, match="invalid_response_keys"):
        parse_state_output('{"state":{},"verdict":"valid"}', SLOTS)


def test_state_scoring_separates_slot_accuracy_joint_goal_and_active_value_f1():
    metrics = score_state_maps(
        {"train-day": "monday", "hotel-area": "north"},
        {"train-day": "Monday", "hotel-area": "south", "train-arriveby": "18:00"},
        SLOTS,
    )
    assert metrics == {
        "slot_correct": 4,
        "slot_total": 6,
        "slot_accuracy": 4 / 6,
        "joint_goal_correct": False,
        "true_positive": 1,
        "false_positive": 2,
        "false_negative": 1,
        "active_value_precision": 1 / 3,
        "active_value_recall": 1 / 2,
        "active_value_f1": 0.4,
    }
