"""Synthetic-only tests for the P2C full-study pipeline."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from multilingual_judge_pilot.p2c_review import (
    ReviewValidationError,
    build_disagreement_report,
    ingest_submission,
    parse_submission_jsonl,
)


def _annotation(item_id: str, slot: str, *, example_hash: str | None = None, semantic: str = "equivalent"):
    return {
        "annotation_schema_version": "p2b1-annotation-2",
        "example_id": item_id,
        "example_sha256": example_hash or ("a" * 64),
        "canonical_scenario_sha256": "b" * 64,
        "reviewer_id": slot,
        "semantic_relation": semantic,
        "linguistic_quality": "natural",
        "decisive_update_dependence": "yes",
        "decisive_update_dependence_rationale": "Synthetic rationale for the visible revision.",
        "whole_action_dependence": "no",
        "whole_action_dependence_rationale": "Synthetic rationale for the complete action evidence.",
        "issue_codes": [],
        "checklist": {
            "matches_formal_spec": True,
            "preserves_cross_language_meaning": True,
            "initial_requirements_communicated": True,
            "decisive_turn_expresses_event": True,
            "counterfactual_differences_controlled": True,
            "action_interpretation_preserved": True,
            "no_post_action_information": True,
            "msa_natural_and_unambiguous": True,
        },
        "notes": "",
    }


def _maps(item_ids: tuple[str, ...] = ("synthetic-a", "synthetic-b")):
    return (
        {item_id: "a" * 64 for item_id in item_ids},
        {item_id: "b" * 64 for item_id in item_ids},
    )


def _jsonl(rows) -> bytes:
    return ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()


def test_submission_parser_rejects_missing_rows_and_preserves_complete_records():
    expected_hashes, scenario_hashes = _maps()
    row = _annotation("synthetic-a", "reviewer_slot_1")

    with pytest.raises(ReviewValidationError, match="complete expected item set"):
        parse_submission_jsonl(_jsonl([row]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    complete = [_annotation(item_id, "reviewer_slot_1") for item_id in expected_hashes]
    parsed = parse_submission_jsonl(_jsonl(complete), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)
    assert [row["example_id"] for row in parsed] == list(expected_hashes)


def test_submission_parser_rejects_duplicate_ids_duplicate_json_keys_wrong_slot_and_stale_hash():
    expected_hashes, scenario_hashes = _maps()
    row = _annotation("synthetic-a", "reviewer_slot_1")

    with pytest.raises(ReviewValidationError, match="duplicate annotation"):
        parse_submission_jsonl(_jsonl([row, row, _annotation("synthetic-b", "reviewer_slot_1")]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    duplicate_key = b'{"example_id":"synthetic-a","example_id":"synthetic-b"}\n'
    with pytest.raises(ReviewValidationError, match="duplicate JSON key"):
        parse_submission_jsonl(duplicate_key, reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    wrong_slot = [_annotation(item_id, "reviewer_slot_2") for item_id in expected_hashes]
    with pytest.raises(ReviewValidationError, match="reviewer slot"):
        parse_submission_jsonl(_jsonl(wrong_slot), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    stale = [_annotation("synthetic-a", "reviewer_slot_1", example_hash="c" * 64), _annotation("synthetic-b", "reviewer_slot_1")]
    with pytest.raises(ReviewValidationError, match="unknown or changed example hash"):
        parse_submission_jsonl(_jsonl(stale), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    corrupt_id = [_annotation("synthetic-a", "reviewer_slot_1"), _annotation("synthetic-b", "reviewer_slot_1")]
    corrupt_id[0]["example_id"] = ["synthetic-a"]
    with pytest.raises(ReviewValidationError, match="example IDs must be strings"):
        parse_submission_jsonl(_jsonl(corrupt_id), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)


def test_submission_requires_explanation_for_detected_problems():
    expected_hashes, scenario_hashes = _maps(("synthetic-a",))
    row = _annotation("synthetic-a", "reviewer_slot_1", semantic="meaning_changed")

    with pytest.raises(ReviewValidationError, match="require an explanatory note"):
        parse_submission_jsonl(_jsonl([row]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    row["notes"] = "Synthetic wording changes the intended meaning."
    assert len(parse_submission_jsonl(_jsonl([row]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)) == 1


def test_disagreement_report_identifies_categorical_difference_without_resolving_it():
    reviewer_a = [_annotation(item_id, "reviewer_slot_1") for item_id in _maps()[0]]
    reviewer_b = [_annotation(item_id, "reviewer_slot_2", semantic="ambiguous" if item_id == "synthetic-b" else "equivalent") for item_id in _maps()[0]]

    report = build_disagreement_report(
        {"reviewer_slot_1": reviewer_a, "reviewer_slot_2": reviewer_b},
        expected_hashes=_maps()[0],
    )

    assert report["disagreement_count"] == 1
    assert report["disagreements"] == [{
        "example_id": "synthetic-b",
        "fields": {"semantic_relation": {"reviewer_slot_1": "equivalent", "reviewer_slot_2": "ambiguous"}},
    }]


def test_submission_import_is_immutable_and_hash_bound(tmp_path: Path):
    expected_hashes, scenario_hashes = _maps()
    source = tmp_path / "review-export.jsonl"
    original = _jsonl([_annotation(item_id, "reviewer_slot_1") for item_id in expected_hashes])
    source.write_bytes(original)

    imported = ingest_submission(
        "reviewer_slot_1",
        source,
        tmp_path / "state",
        expected_hashes=expected_hashes,
        expected_scenario_hashes=scenario_hashes,
    )

    archived = tmp_path / "state" / str(imported["archived_path"])
    assert archived.read_bytes() == original
    assert imported["source_sha256"] == hashlib.sha256(original).hexdigest()
    revised = [_annotation(item_id, "reviewer_slot_1", semantic="equivalent") for item_id in expected_hashes]
    revised[0]["notes"] = "Synthetic export revision."
    source.write_bytes(_jsonl(revised))
    assert archived.read_bytes() == original
    with pytest.raises(ReviewValidationError, match="revision reason"):
        ingest_submission(
            "reviewer_slot_1",
            source,
            tmp_path / "state",
            expected_hashes=expected_hashes,
            expected_scenario_hashes=scenario_hashes,
        )
