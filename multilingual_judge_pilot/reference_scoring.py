"""Reference-label scoring, separated from ordinary inference and run records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .judge_inference import ParseStatus, RunResult, Verdict


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
