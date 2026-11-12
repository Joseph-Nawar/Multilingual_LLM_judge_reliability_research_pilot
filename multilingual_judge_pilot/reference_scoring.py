"""Reference-label scoring, separated from ordinary inference and run records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .judge_inference import ConstraintAssessment, ParseResult, ParseStatus, RunResult, Verdict


@dataclass(frozen=True)
class ScoredRun:
    run_id: str
    configuration_hash: str
    execution_id: str
    terminal_stage: str
    item_id: str
    response_status: ParseStatus
    predicted_verdict: Verdict | None
    reference_verdict: Verdict
    is_correct: bool | None
    scoring_policy_version: str = "parsed-verdict-only-1"


def score_run(run: RunResult, reference_labels: Mapping[str, Verdict]) -> ScoredRun:
    """Score only a retained parsed verdict; preserve other statuses as unscored.

    The treatment of malformed/refused outputs in a study-level primary score
    remains a future owner-approved analysis policy. This function never sends
    reference labels back to an inference request.
    """
    if run.item_id not in reference_labels:
        raise KeyError(f"reference label missing for item {run.item_id}")
    reference = reference_labels[run.item_id]
    if not isinstance(reference, Verdict):
        reference = Verdict(reference)
    predicted = run.final_result.verdict
    correct = predicted is reference if run.final_result.status is ParseStatus.PARSED else None
    return ScoredRun(
        run_id=run.run_id,
        configuration_hash=run.configuration_hash,
        execution_id=run.execution_id,
        terminal_stage=run.terminal_stage,
        item_id=run.item_id,
        response_status=run.final_result.status,
        predicted_verdict=predicted,
        reference_verdict=reference,
        is_correct=correct,
    )


@dataclass(frozen=True)
class ConstraintCoverageScore:
    """Post-inference coverage of reference requirements by reported assessments.

    Evidence overlap links each reported row to at most one reference
    requirement. Constraint-type correctness, satisfied/violated correctness,
    and exact source-turn agreement are then scored independently on those
    evidence-linked pairs. This metric never edits a verdict or supplies an
    omitted requirement to an inference request.
    """

    parsed: bool
    evidence_covered_requirement_ids: tuple[str, ...]
    evidence_omitted_requirement_ids: tuple[str, ...]
    correct_constraint_type_requirement_ids: tuple[str, ...]
    correct_assessment_requirement_ids: tuple[str, ...]
    unmatched_prediction_indices: tuple[int, ...]
    exact_turn_match_requirement_ids: tuple[str, ...]
    evidence_coverage_fraction: float | None
    constraint_type_accuracy_fraction: float | None
    assessment_accuracy_fraction: float | None
    exact_turn_match_fraction: float | None
    metric_version: str = "post-inference-constraint-coverage-2"


def score_constraint_coverage(
    result: ParseResult,
    reference_requirements: Sequence[Mapping[str, object]],
) -> ConstraintCoverageScore:
    """Score whether parsed rows cover applicable reference constraints.

    A prediction can evidence-cover a requirement when its cited turns
    overlap an allowed supporting turn, regardless of its reported type or
    assessment. Matching is one-to-one. Type and assessment correctness are
    evaluated independently on each matched pair; exact turn-set equality is
    a separate descriptive measure. Unparsed outputs remain unscored rather
    than being repaired.
    """
    if not isinstance(result, ParseResult):
        raise TypeError("constraint coverage requires a ParseResult")
    requirements: list[tuple[str, str, str, tuple[int, ...]]] = []
    seen_ids: set[str] = set()
    for row in reference_requirements:
        if not isinstance(row, Mapping):
            raise TypeError("reference requirements must be mappings")
        requirement_id = row.get("requirement_id")
        constraint_type = row.get("constraint_type")
        assessment = row.get("assessment")
        turns = row.get("source_turn_indices")
        if not isinstance(requirement_id, str) or not requirement_id.strip() or requirement_id in seen_ids:
            raise ValueError("requirement IDs must be unique, non-empty strings")
        if constraint_type not in {"numerical", "temporal", "permission", "other"}:
            raise ValueError("unsupported reference constraint type")
        if assessment not in {"satisfied", "violated"}:
            raise ValueError("reference assessments must be satisfied or violated")
        if not isinstance(turns, (tuple, list)) or not turns or any(type(index) is not int or index < 0 for index in turns):
            raise ValueError("reference supporting turns must be non-empty non-negative integer indices")
        normalized_turns = tuple(turns)
        if tuple(sorted(set(normalized_turns))) != normalized_turns:
            raise ValueError("reference supporting turns must be unique and sorted")
        seen_ids.add(requirement_id)
        requirements.append((requirement_id, constraint_type, assessment, normalized_turns))

    if result.status is not ParseStatus.PARSED:
        return ConstraintCoverageScore(False, (), (), (), (), (), (), None, None, None, None)

    predictions: tuple[ConstraintAssessment, ...] = result.structured_assessments
    adjacency = [
        [
            req_index
            for req_index, (_, _, _, turns) in enumerate(requirements)
            if set(prediction.source_turn_indices).intersection(turns)
        ]
        for prediction in predictions
    ]
    requirement_to_prediction: dict[int, int] = {}

    def assign(prediction_index: int, visited: set[int]) -> bool:
        for requirement_index in adjacency[prediction_index]:
            if requirement_index in visited:
                continue
            visited.add(requirement_index)
            existing = requirement_to_prediction.get(requirement_index)
            if existing is None or assign(existing, visited):
                requirement_to_prediction[requirement_index] = prediction_index
                return True
        return False

    for prediction_index in range(len(predictions)):
        assign(prediction_index, set())

    prediction_to_requirement = {prediction: requirement for requirement, prediction in requirement_to_prediction.items()}
    covered_indices = sorted(requirement_to_prediction)
    omitted_indices = [index for index in range(len(requirements)) if index not in requirement_to_prediction]
    type_correct_indices = [
        requirement_index
        for requirement_index, prediction_index in requirement_to_prediction.items()
        if predictions[prediction_index].constraint_type == requirements[requirement_index][1]
    ]
    assessment_correct_indices = [
        requirement_index
        for requirement_index, prediction_index in requirement_to_prediction.items()
        if predictions[prediction_index].assessment == requirements[requirement_index][2]
    ]
    exact_ids = tuple(
        requirements[requirement_index][0]
        for requirement_index, prediction_index in sorted(requirement_to_prediction.items())
        if tuple(predictions[prediction_index].source_turn_indices) == requirements[requirement_index][3]
    )
    matched_count = len(covered_indices)
    evidence_coverage = (matched_count / len(requirements)) if requirements else None
    type_accuracy = (len(type_correct_indices) / matched_count) if matched_count else None
    assessment_accuracy = (len(assessment_correct_indices) / matched_count) if matched_count else None
    exact_fraction = (len(exact_ids) / matched_count) if matched_count else None
    return ConstraintCoverageScore(
        True,
        tuple(requirements[index][0] for index in covered_indices),
        tuple(requirements[index][0] for index in omitted_indices),
        tuple(requirements[index][0] for index in sorted(type_correct_indices)),
        tuple(requirements[index][0] for index in sorted(assessment_correct_indices)),
        tuple(index for index in range(len(predictions)) if index not in prediction_to_requirement),
        exact_ids,
        evidence_coverage,
        type_accuracy,
        assessment_accuracy,
        exact_fraction,
    )
