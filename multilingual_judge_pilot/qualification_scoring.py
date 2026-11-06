"""Separate post-inference scoring for the private English/MSA competence screen."""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

from .judge_inference import ContractError, JudgeFacingInput, Verdict
from .qualification import QUALIFICATION_THRESHOLDS, QUALIFICATION_SCORING_VERSION


_OUTCOME_COLUMNS = ("valid", "invalid", "invalid_or_unparseable", "technical_missing")


def score_qualification_results(
    items: Sequence[Mapping[str, object]],
    outcome_records: Sequence[Mapping[str, object]],
    reference_labels: Mapping[str, Mapping[str, object] | bool],
) -> dict[str, object]:
    """Score exactly 48 items; do not repair, infer, or retry missing outputs."""
    if len(items) != 48:
        raise ContractError("competence scoring requires exactly 48 screen items")
    parsed_items = [JudgeFacingInput.from_mapping(item) for item in items]
    item_map = {item.item_id: item for item in parsed_items}
    if len(item_map) != 48:
        raise ContractError("competence screen item IDs must be unique")
    if any(item.language_condition not in {"EN-EN", "AR-AR"} for item in parsed_items):
        raise ContractError("qualification screen is limited to EN-EN and AR-AR items")
    if set(reference_labels) != set(item_map):
        raise ContractError("reference key IDs do not exactly match the competence screen")

    labels: dict[str, bool] = {}
    for item_id, raw in reference_labels.items():
        value = raw.get("expected_valid") if isinstance(raw, Mapping) else raw
        if type(value) is not bool:
            raise ContractError("each qualification reference label must contain a boolean expected_valid value")
        labels[item_id] = value

    output_by_id: dict[str, Mapping[str, object]] = {}
    for row in outcome_records:
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or item_id not in item_map:
            raise ContractError("qualification output contains an unknown item ID")
        if item_id in output_by_id:
            raise ContractError("qualification output contains duplicate item results")
        output_by_id[item_id] = row

    language_counts = Counter("en" if item.language_condition == "EN-EN" else "ar" for item in parsed_items)
    class_counts = Counter(("en" if item.language_condition == "EN-EN" else "ar", labels[item.item_id]) for item in parsed_items)
    if language_counts != {"en": 24, "ar": 24} or class_counts != {
        ("en", True): 12,
        ("en", False): 12,
        ("ar", True): 12,
        ("ar", False): 12,
    }:
        raise ContractError("qualification screen must have 24 items and 12 per class in each language")

    language_rows: dict[str, list[dict[str, object]]] = {"en": [], "ar": []}
    invalid_output_count = 0
    technical_missing = 0
    provider_failure_attempts = 0
    retry_attempts = 0
    for item in parsed_items:
        language = "en" if item.language_condition == "EN-EN" else "ar"
        row = output_by_id.get(item.item_id)
        status = "technical_missing"
        prediction = None
        if row is not None:
            run_result = row.get("run_result")
            final = run_result.get("final_result") if isinstance(run_result, Mapping) else None
            if not isinstance(final, Mapping):
                status = "technical_missing"
            else:
                raw_status = final.get("status")
                raw_verdict = final.get("verdict")
                if raw_status == "provider_failure":
                    status = "technical_missing"
                elif raw_status == "parsed" and isinstance(raw_verdict, str) and raw_verdict in {"valid", "invalid"}:
                    status = raw_verdict
                    prediction = raw_verdict
                elif raw_status in {"invalid_output", "missing", "refused"} or raw_status == "parsed":
                    status = "invalid_or_unparseable"
                else:
                    raise ContractError("qualification output has an unsupported parser or provider status")
            steps = run_result.get("steps", []) if isinstance(run_result, Mapping) else []
            if isinstance(steps, list):
                for step in steps:
                    attempts = step.get("attempts", []) if isinstance(step, Mapping) else []
                    if not isinstance(attempts, list):
                        continue
                    for attempt in attempts:
                        if not isinstance(attempt, Mapping):
                            continue
                        if attempt.get("call_status") == "provider_failure":
                            provider_failure_attempts += 1
                        if type(attempt.get("attempt_number")) is int and attempt["attempt_number"] > 1:
                            retry_attempts += 1
        if status == "technical_missing":
            technical_missing += 1
        elif status == "invalid_or_unparseable":
            invalid_output_count += 1
        expected = "valid" if labels[item.item_id] else "invalid"
        language_rows[language].append(
            {
                "item_id": item.item_id,
                "expected": expected,
                "outcome": status,
                "correct": status == expected,
            }
        )

    language_results: dict[str, object] = {}
    all_thresholds_met = True
    for language in ("en", "ar"):
        rows = language_rows[language]
        matrix = {
            actual: {outcome: 0 for outcome in _OUTCOME_COLUMNS}
            for actual in ("valid", "invalid")
        }
        by_class: dict[str, object] = {}
        correct_total = 0
        for row in rows:
            matrix[row["expected"]][row["outcome"]] += 1
            if row["correct"]:
                correct_total += 1
        for actual in ("valid", "invalid"):
            class_rows = [row for row in rows if row["expected"] == actual]
            correct = sum(bool(row["correct"]) for row in class_rows)
            minimum = (
                QUALIFICATION_THRESHOLDS["minimum_valid_correct_per_language"]
                if actual == "valid"
                else QUALIFICATION_THRESHOLDS["minimum_invalid_correct_per_language"]
            )
            by_class[actual] = {
                "correct": correct,
                "total": len(class_rows),
                "accuracy": correct / len(class_rows),
                "minimum_correct": minimum,
                "threshold_met": correct >= minimum,
            }
            all_thresholds_met = all_thresholds_met and correct >= minimum
        overall_met = correct_total >= QUALIFICATION_THRESHOLDS["minimum_correct_per_language"]
        all_thresholds_met = all_thresholds_met and overall_met
        language_results[language] = {
            "correct": correct_total,
            "total": len(rows),
            "accuracy": correct_total / len(rows),
            "minimum_correct": QUALIFICATION_THRESHOLDS["minimum_correct_per_language"],
            "overall_threshold_met": overall_met,
            "by_validity_class": by_class,
            "confusion_matrix": matrix,
        }

    decision = "incomplete_not_qualified" if technical_missing else ("pass" if all_thresholds_met else "fail")
    return {
        "scoring_version": QUALIFICATION_SCORING_VERSION,
        "decision": decision,
        "qualified": decision == "pass",
        "decision_note": (
            "Technical missingness blocks a pass and is not counted as a model-produced invalid output."
            if technical_missing
            else "All outcomes were technically completed; fixed predeclared thresholds were applied."
        ),
        "languages": language_results,
        "invalid_or_unparseable_outputs": invalid_output_count,
        "technical_missingness": technical_missing,
        "provider_failure_attempts": provider_failure_attempts,
        "retry_attempts": retry_attempts,
        "requested_items": 48,
        "completed_item_records": len(output_by_id),
        "thresholds": dict(QUALIFICATION_THRESHOLDS),
    }
