"""Versioned structured reasons for the prospective P2 bilingual review form.

These helpers turn explicit reviewer selections into the legacy rationale and
notes strings required by ``p2b1-annotation-2``. They do not make or infer
judgments.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence

REASON_TAXONOMY_VERSION = "paper2-structured-reasons-v1"

Q3_REASONS: dict[str, str] = {
    "explicit_numeric": "Explicit numeric requirement",
    "explicit_temporal": "Explicit temporal requirement",
    "explicit_permission": "Explicit permission state",
    "complete_restatement": "Complete restatement",
    "earlier_numeric_needed": "Earlier numeric value needed",
    "earlier_temporal_needed": "Earlier temporal value needed",
    "earlier_permission_needed": "Earlier permission state needed",
    "earlier_referent_scope_needed": "Earlier referent or scope needed",
    "multiple_earlier_turns_needed": "Multiple earlier turns needed",
    "ambiguous_or_conflicting": "Ambiguous or conflicting interpretation",
    "other": "Other / not covered",
}

Q4_REASONS: dict[str, str] = {
    "decisive_instruction_invalidity": "The decisive instruction alone establishes invalidity",
    "all_requirements_available": "All relevant requirements are available",
    "earlier_numeric_constraint_needed": "Earlier numerical constraint needed",
    "earlier_temporal_constraint_needed": "Earlier temporal constraint needed",
    "earlier_permission_information_needed": "Earlier permission information needed",
    "earlier_unrelated_requirements_needed": "Earlier unrelated requirements needed",
    "multiple_earlier_requirements_needed": "Multiple earlier requirements needed",
    "ambiguous_or_conflicting_information": "Ambiguous or conflicting information",
    "other": "Other / not covered",
}

_ALLOWED: dict[tuple[str, str], tuple[str, ...]] = {
    ("q3", "yes"): (
        "explicit_numeric",
        "explicit_temporal",
        "explicit_permission",
        "complete_restatement",
        "other",
    ),
    ("q3", "no"): (
        "earlier_numeric_needed",
        "earlier_temporal_needed",
        "earlier_permission_needed",
        "earlier_referent_scope_needed",
        "multiple_earlier_turns_needed",
        "other",
    ),
    ("q3", "unclear"): ("ambiguous_or_conflicting", "other"),
    ("q4", "yes"): (
        "decisive_instruction_invalidity",
        "all_requirements_available",
        "other",
    ),
    ("q4", "no"): (
        "earlier_numeric_constraint_needed",
        "earlier_temporal_constraint_needed",
        "earlier_permission_information_needed",
        "earlier_unrelated_requirements_needed",
        "multiple_earlier_requirements_needed",
        "other",
    ),
    ("q4", "unclear"): ("ambiguous_or_conflicting_information", "other"),
}

ISSUE_TYPES: dict[str, str] = {
    "incorrect_number": "Incorrect number",
    "incorrect_time": "Incorrect time",
    "incorrect_unit": "Incorrect unit",
    "incorrect_permission": "Incorrect permission",
    "incorrect_technical_literal": "Incorrect technical literal",
    "missing_decision_relevant_information": "Missing decision-relevant information",
    "incorrect_conversational_chronology": "Incorrect conversational chronology",
    "semantic_meaning_changed": "Meaning changed",
    "semantic_ambiguity": "Ambiguous meaning",
    "linguistic_defect": "Unnatural or unclear language",
    "failed_checklist_item": "Checklist item failed",
    "other": "Other / not covered",
}

_VALUE_PAIR_TYPES = {
    "incorrect_number",
    "incorrect_time",
    "incorrect_unit",
    "incorrect_permission",
    "incorrect_technical_literal",
    "missing_decision_relevant_information",
    "incorrect_conversational_chronology",
    "semantic_meaning_changed",
    "failed_checklist_item",
}
_EXPLANATION_TYPES = {"semantic_ambiguity", "linguistic_defect", "other"}
_GENERIC_EXPLANATIONS = {"wrong", "unclear", "problem", "issue", "other", "not covered", "bad"}


def allowed_reasons(question: str, answer: str) -> tuple[str, ...]:
    """Return only reason IDs compatible with the independently selected answer."""
    try:
        return _ALLOWED[(question, answer)]
    except KeyError as exc:
        raise ValueError("question must be q3/q4 and answer must be yes/no/unclear") from exc


def _selection_list(value: object, name: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must be a list of non-empty strings")
    result = [item.strip() for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must contain unique values")
    if not allow_empty and not result:
        raise ValueError(f"at least one {name} is required")
    return result


def _specific_explanation(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} requires a specific explanation")
    cleaned = " ".join(value.split())
    if len(cleaned) < 20 or cleaned.casefold().rstrip(".!?") in _GENERIC_EXPLANATIONS:
        raise ValueError(f"{label} requires a specific explanation of at least 20 characters")
    return cleaned


def build_rationale(question: str, answer: str, selection: Mapping[str, object]) -> str:
    """Render one substantive legacy rationale from explicit choices and evidence."""
    allowed = allowed_reasons(question, answer)
    if not isinstance(selection, Mapping) or set(selection) != {"reasons", "supporting_turns", "fields", "explanation"}:
        raise ValueError("reason selection must contain reasons, supporting_turns, fields, and explanation")
    reasons = _selection_list(selection["reasons"], "compatible reason", allow_empty=False)
    if any(reason not in allowed for reason in reasons):
        raise ValueError("selected reason is incompatible with the selected answer")

    turns = selection["supporting_turns"]
    if not isinstance(turns, (list, tuple)) or any(type(turn) is not int or turn < 0 for turn in turns):
        raise ValueError("supporting turns must be non-negative integer turn indices")
    if len(turns) != len(set(turns)):
        raise ValueError("supporting turns must be unique")
    if not turns:
        raise ValueError("at least one supporting turn is required")
    if any(reason.startswith("multiple_") for reason in reasons) and len(turns) < 2:
        raise ValueError("multiple-turn reasons require at least two distinct supporting turns")

    fields = _selection_list(selection["fields"], "requirement/field", allow_empty=True)
    explanations = ""
    if any(reason == "other" or reason.startswith("ambiguous_or_conflicting") for reason in reasons):
        explanations = _specific_explanation(selection["explanation"], "Other or ambiguous reasons")
    elif selection["explanation"] not in ("", None):
        explanations = _specific_explanation(selection["explanation"], "Free-text explanation")

    catalog = Q3_REASONS if question == "q3" else Q4_REASONS
    parts = ["; ".join(catalog[reason] for reason in reasons) + "."]
    parts.append("Supporting turn(s): " + ", ".join(str(turn) for turn in turns) + ".")
    if fields:
        parts.append("Requirement/field: " + ", ".join(fields) + ".")
    if explanations:
        parts.append("Explanation: " + explanations)
    return " ".join(parts)


def build_issue_notes(reports: Sequence[Mapping[str, object]]) -> str:
    """Render specific issue evidence for the existing ``notes`` field.

    Each record needs a report type, conversation turn, and affected field. Value
    discrepancies include expected and observed values; ambiguity, language,
    and uncategorized issues need an explanation that describes the problem.
    """
    if not isinstance(reports, (list, tuple)):
        raise ValueError("issue reports must be a list")
    rendered: list[str] = []
    required = {"type", "turn_index", "field", "expected", "observed", "explanation"}
    for report in reports:
        if not isinstance(report, Mapping) or set(report) != required:
            raise ValueError("each issue report must include type, turn_index, field, expected, observed, and explanation")
        kind = report["type"]
        if kind not in ISSUE_TYPES:
            raise ValueError("issue report type is not covered by the available options")
        turn = report["turn_index"]
        if type(turn) is not int or turn < 0:
            raise ValueError("every issue report needs a valid supporting turn index")
        field = report["field"]
        if not isinstance(field, str) or not field.strip():
            raise ValueError("every issue report needs an affected field or requirement")
        field = " ".join(field.split())
        expected = report["expected"]
        observed = report["observed"]
        explanation = report["explanation"]
        if not isinstance(expected, str) or not isinstance(observed, str) or not isinstance(explanation, str):
            raise ValueError("issue evidence fields must be text")

        details = f"{ISSUE_TYPES[kind]} (turn {turn}; field {json.dumps(field, ensure_ascii=False)})"
        if kind in _VALUE_PAIR_TYPES:
            if not expected.strip() or not observed.strip():
                raise ValueError("this issue type requires expected and observed values")
            details += f": expected {json.dumps(expected.strip(), ensure_ascii=False)}; observed {json.dumps(observed.strip(), ensure_ascii=False)}."
        elif kind in _EXPLANATION_TYPES:
            details += ": " + _specific_explanation(explanation, ISSUE_TYPES[kind])
        else:
            raise ValueError("issue report type is not covered by the available options")
        rendered.append(details)
    return "\n".join(rendered)
