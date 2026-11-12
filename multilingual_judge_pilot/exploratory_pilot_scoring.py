"""Provisional scoring for the one-pass, unvalidated local screen pilot."""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

from .exploratory_pilot import EXPLORATORY_STAGE
from .judge_inference import ContractError, JudgeFacingInput
from .qualification import QUALIFICATION_THRESHOLDS


_OUTCOMES = ("valid", "invalid", "invalid_or_unparseable", "technical_missing")


def _expected_label(value: Mapping[str, object] | bool) -> bool:
    expected = value.get("expected_valid") if isinstance(value, Mapping) else value
    if type(expected) is not bool:
        raise ContractError("each private reference record must contain a boolean expected_valid label")
    return expected


def _final_result(record: Mapping[str, object]) -> Mapping[str, object] | None:
    final = record.get("final_result")
    if isinstance(final, Mapping):
        return final
    run_result = record.get("run_result")
    if isinstance(run_result, Mapping):
        final = run_result.get("final_result")
        if isinstance(final, Mapping):
            return final
    return None


def _outcome_status(record: Mapping[str, object] | None) -> tuple[str, str | None]:
    if record is None:
        return "technical_missing", None
    final = _final_result(record)
    if final is None:
        status = record.get("final_status")
        verdict = record.get("verdict")
    else:
        status = final.get("status")
        verdict = final.get("verdict")
    if status == "provider_failure":
        return "technical_missing", None
    if status == "parsed" and isinstance(verdict, str) and verdict in {"valid", "invalid"}:
        return str(verdict), str(verdict)
    if status in {"invalid_output", "missing", "refused"} or status == "parsed":
        return "invalid_or_unparseable", None
    raise ContractError("pilot result has an unsupported response or failure status")


def _summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    total = len(rows)
    correct = sum(row["outcome"] == row["expected"] for row in rows)
    by_class = {}
    for expected in ("valid", "invalid"):
        selected = [row for row in rows if row["expected"] == expected]
        recall = sum(row["outcome"] == expected for row in selected) / len(selected) if selected else None
        by_class[expected] = {"correct": sum(row["outcome"] == expected for row in selected), "total": len(selected), "recall": recall}
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else None,
        "valid_class_recall": by_class["valid"]["recall"],
        "invalid_class_recall": by_class["invalid"]["recall"],
        "by_validity_class": by_class,
    }


def _sensitivity_summary(rows: Sequence[Mapping[str, object]], excluded: set[str]) -> dict[str, object]:
    retained = [row for row in rows if row["item_id"] not in excluded]
    result = _summary(retained)
    language = {}
    for condition, name in (("EN-EN", "en"), ("AR-AR", "ar")):
        language[name] = _summary([row for row in retained if row["language_condition"] == condition])
    return {"excluded_item_count": len(excluded), "excluded_item_ids": sorted(excluded), **result, "by_language": language}


def score_exploratory_pilot(
    items: Sequence[Mapping[str, object]],
    outcome_records: Sequence[Mapping[str, object]],
    reference_labels: Mapping[str, Mapping[str, object] | bool],
    families: Mapping[str, str],
    review_export: Mapping[str, object],
) -> dict[str, object]:
    """Score model predictions against unchanged private labels and report sensitivities."""
    if len(items) != 48:
        raise ContractError("exploratory pilot scoring requires the original 48-item screen")
    parsed = [JudgeFacingInput.from_mapping(row) for row in items]
    by_id = {item.item_id: item for item in parsed}
    if len(by_id) != 48 or set(reference_labels) != set(by_id) or set(families) != set(by_id):
        raise ContractError("items, private labels, and family metadata must share exactly 48 unique IDs")
    if any(item.language_condition not in {"EN-EN", "AR-AR"} for item in parsed):
        raise ContractError("exploratory competence screen must use the fixed English/MSA conditions")

    raw_outcomes = {}
    for record in outcome_records:
        item_id = record.get("item_id")
        if not isinstance(item_id, str) or item_id not in by_id or item_id in raw_outcomes:
            raise ContractError("pilot outputs contain an unknown or duplicate item identifier")
        raw_outcomes[item_id] = record

    review_rows = review_export.get("items")
    if not isinstance(review_rows, list) or len(review_rows) != 48:
        raise ContractError("the submitted reviewer export must contain all 48 pre-reveal responses")
    review_by_id = {row.get("item_id"): row.get("answers") for row in review_rows if isinstance(row, Mapping)}
    if len(review_by_id) != 48 or set(review_by_id) != set(by_id):
        raise ContractError("reviewer responses do not match the screen item identifiers")

    rows: list[dict[str, object]] = []
    invalid_outputs = 0
    technical_missing = 0
    provider_failure_attempts = 0
    retry_attempts = 0
    for item in parsed:
        item_id = item.item_id
        expected_bool = _expected_label(reference_labels[item_id])
        expected = "valid" if expected_bool else "invalid"
        outcome, prediction = _outcome_status(raw_outcomes.get(item_id))
        invalid_outputs += outcome == "invalid_or_unparseable"
        technical_missing += outcome == "technical_missing"
        record = raw_outcomes.get(item_id)
        run_result = record.get("run_result") if isinstance(record, Mapping) else None
        if isinstance(run_result, Mapping):
            steps = run_result.get("steps", [])
            if isinstance(steps, list):
                for step in steps:
                    attempts = step.get("attempts", []) if isinstance(step, Mapping) else []
                    if isinstance(attempts, list):
                        for attempt in attempts:
                            if not isinstance(attempt, Mapping):
                                continue
                            if attempt.get("call_status") == "provider_failure":
                                provider_failure_attempts += 1
                            if type(attempt.get("attempt_number")) is int and attempt["attempt_number"] > 1:
                                retry_attempts += 1
        answers = review_by_id[item_id]
        if not isinstance(answers, Mapping):
            raise ContractError("reviewer item answers are malformed")
        human = answers.get("independent_verdict")
        if human not in {"valid", "invalid", "unclear"}:
            raise ContractError("reviewer independent verdict is malformed")
        rows.append({
            "item_id": item_id,
            "language_condition": item.language_condition,
            "competency_family": families[item_id],
            "expected": expected,
            "outcome": outcome,
            "prediction": prediction,
            "correct": outcome == expected,
            "reviewer_verdict": human,
            "reviewer_agreement": human == expected if human != "unclear" else None,
        })

    condition_counts = Counter(row["language_condition"] for row in rows)
    label_counts = Counter((row["language_condition"], row["expected"]) for row in rows)
    if condition_counts != {"EN-EN": 24, "AR-AR": 24} or label_counts != {
        ("EN-EN", "valid"): 12, ("EN-EN", "invalid"): 12,
        ("AR-AR", "valid"): 12, ("AR-AR", "invalid"): 12,
    }:
        raise ContractError("screen must retain the balanced 24-item English/MSA reference allocation")

    language_results = {}
    matrices = {}
    for condition, name in (("EN-EN", "en"), ("AR-AR", "ar")):
        selected = [row for row in rows if row["language_condition"] == condition]
        language_results[name] = _summary(selected)
        matrix = {expected: {outcome: 0 for outcome in _OUTCOMES} for expected in ("valid", "invalid")}
        for row in selected:
            matrix[row["expected"]][row["outcome"]] += 1
        matrices[name] = matrix

    family_results = {}
    for condition, language_name in (("EN-EN", "en"), ("AR-AR", "ar")):
        for family in sorted(set(families.values())):
            key = f"{language_name}:{family}"
            family_rows = [row for row in rows if row["language_condition"] == condition and row["competency_family"] == family]
            family_results[key] = _summary(family_rows)

    reviewer_disagreements = {row["item_id"] for row in rows if row["reviewer_agreement"] is False}
    reviewer_unclear = {row["item_id"] for row in rows if row["reviewer_verdict"] == "unclear"}
    issue_items = {
        row["item_id"]
        for row in review_rows
        if isinstance(row, Mapping)
        and isinstance(row.get("answers"), Mapping)
        and row["answers"].get("constraint_consistency") == "issue"
    }
    issue_cross_tab = Counter(
        (row["expected"], row["reviewer_verdict"])
        for row in rows
        if row["item_id"] in issue_items
    )

    pass_by_language = {}
    all_thresholds_met = True
    for name in ("en", "ar"):
        result = language_results[name]
        valid_met = result["by_validity_class"]["valid"]["correct"] >= QUALIFICATION_THRESHOLDS["minimum_valid_correct_per_language"]
        invalid_met = result["by_validity_class"]["invalid"]["correct"] >= QUALIFICATION_THRESHOLDS["minimum_invalid_correct_per_language"]
        overall_met = result["correct"] >= QUALIFICATION_THRESHOLDS["minimum_correct_per_language"]
        pass_by_language[name] = {
            "overall_threshold_met": overall_met,
            "valid_class_threshold_met": valid_met,
            "invalid_class_threshold_met": invalid_met,
            "provisional_screen_thresholds_met": overall_met and valid_met and invalid_met,
        }
        all_thresholds_met = all_thresholds_met and overall_met and valid_met and invalid_met

    all_rows = list(rows)
    sensitivity = {
        "exclude_reviewer_unclear": _sensitivity_summary(all_rows, reviewer_unclear),
        "exclude_clear_reviewer_disagreements": _sensitivity_summary(all_rows, reviewer_disagreements),
        "exclude_human_disagreements_and_unclear": _sensitivity_summary(all_rows, reviewer_unclear | reviewer_disagreements),
    }
    determinate = [row for row in rows if row["reviewer_verdict"] != "unclear"]
    agreement_correct = sum(row["reviewer_agreement"] is True for row in determinate)
    return {
        "scoring_version": "p3-exploratory-screen-scoring-v1",
        "stage": EXPLORATORY_STAGE,
        "formal_qualification_claim": False,
        "reference_labels_modified": False,
        "scored_items": len(rows),
        "overall": _summary(rows),
        "prediction_distribution": {
            outcome: sum(row["outcome"] == outcome for row in rows)
            for outcome in _OUTCOMES
        },
        "languages": language_results,
        "confusion_matrices": matrices,
        "competency_families": family_results,
        "invalid_or_unparseable_outputs": invalid_outputs,
        "technical_missingness": technical_missing,
        "provider_failure_attempts": provider_failure_attempts,
        "retry_attempts": retry_attempts,
        "provisional_threshold_comparison": {
            "formal_qualification": False,
            "thresholds": dict(QUALIFICATION_THRESHOLDS),
            "by_language": pass_by_language,
            "both_languages_meet_all_thresholds": all_thresholds_met,
            "pilot_decision": (
                "provisional_incomplete"
                if technical_missing
                else "provisional_pass_pattern"
                if all_thresholds_met
                else "provisional_fail"
            ),
        },
        "reviewer_agreement": {
            "determinate_items": len(determinate),
            "agreements": agreement_correct,
            "disagreements": len(reviewer_disagreements),
            "unclear": len(reviewer_unclear),
            "agreement_fraction_among_determinate": agreement_correct / len(determinate) if determinate else None,
            "agreement_fraction_of_all_items": agreement_correct / len(rows),
            "clear_disagreement_item_ids": sorted(reviewer_disagreements),
            "unclear_item_ids": sorted(reviewer_unclear),
            "constraint_consistency_issue_count": len(issue_items),
            "constraint_consistency_issue_cross_tab": {
                f"{expected}|{human}": count for (expected, human), count in sorted(issue_cross_tab.items())
            },
        },
        "sensitivity": sensitivity,
        "per_item_scores": rows,
    }
