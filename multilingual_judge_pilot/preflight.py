"""Small deterministic utilities for P2A/P2B-1 local authoring review.

These checks establish schema, oracle, chronology, and span-reference coverage.
They cannot establish that a language span faithfully expresses its formal target.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Iterable

from .integrity import (
    audit_duplicates,
    validate_counterfactual_pair,
    validate_language_variant_coverage,
    validate_scenario_collection,
)
from .schema import (
    CanonicalScenario,
    DatasetKind,
    Domain,
    LanguageCondition,
    Partition,
    TextSegmentKind,
    TransitionFamily,
    TurnRole,
    ValidityLabel,
    canonical_value,
    stable_json,
)
from .serialization import scenario_from_json


class PreflightValidationError(ValueError):
    """A local prototype, coverage map, annotation, or adjudication record is invalid."""


@dataclass(frozen=True)
class SemanticCoverageAudit:
    scenario_id: str
    variant_count: int
    mapped_target_count: int
    human_validation_status: str = "not_performed"


@dataclass(frozen=True)
class DataIsolationAudit:
    all_private_paths_ignored: bool
    ignored_paths: tuple[str, ...]
    tracked_private_paths: tuple[str, ...]


@dataclass(frozen=True)
class AnnotationAudit:
    expected_example_count: int
    annotated_example_count: int
    reviewer_count: int
    reviewer_ids: tuple[str, ...]
    complete: bool
    raw_semantic_agreement: float | None
    cohen_kappa: float | None
    decisive_update_dependence_agreement: float | None
    whole_action_dependence_agreement: float | None
    linguistic_quality_agreement: float | None
    issue_code_exact_agreement: float | None
    checklist_item_agreement: dict[str, float]


@dataclass(frozen=True)
class AdjudicationAudit:
    required_count: int
    adjudication_count: int
    unresolved_count: int
    incomplete_pair_count: int
    complete: bool


@dataclass(frozen=True)
class PrototypePreflight:
    scenario_count: int
    language_variant_count: int
    item_count: int
    label_counts: dict[str, int]
    domain_family_cells: tuple[str, ...]
    template_counts: dict[str, int]
    recipe_counts: dict[str, int]
    exact_duplicate_group_count: int
    normalized_duplicate_group_count: int
    semantic_coverage_target_count: int
    variant_hashes: dict[str, str]


_EXPECTED_PROTOTYPE_CELLS = {
    (Domain.BOOKING, TransitionFamily.NUMERICAL_REVISION),
    (Domain.BOOKING, TransitionFamily.INTRODUCTION),
    (Domain.CUSTOMER_OPERATIONS, TransitionFamily.PERMISSION_REVOCATION),
    (Domain.SCHEDULING, TransitionFamily.TEMPORAL_REVISION),
}
_EXPECTED_FAMILIES = {
    TransitionFamily.INTRODUCTION,
    TransitionFamily.NUMERICAL_REVISION,
    TransitionFamily.PERMISSION_REVOCATION,
    TransitionFamily.TEMPORAL_REVISION,
}
_COVERAGE_TARGET_TYPES = {
    "context_fact",
    "action_field",
    "initial_requirement",
    "initial_permission",
    "event",
}
_ANNOTATION_RELATIONS = {"equivalent", "meaning_changed", "ambiguous"}
_LINGUISTIC_QUALITIES = {"natural", "acceptable_variation", "unnatural_or_unclear"}
_DEPENDENCE_CATEGORIES = {"yes", "no", "unclear"}
ANNOTATION_SCHEMA_VERSION = "p2b1-annotation-2"
ADJUDICATION_SCHEMA_VERSION = "p2b1-adjudication-2"
REVIEW_PACKET_VERSION = "p2b1-review-3"
_ANNOTATION_ISSUES = {
    "incorrect_number",
    "incorrect_time",
    "incorrect_unit",
    "incorrect_permission",
    "incorrect_technical_literal",
    "missing_decision_relevant_information",
    "incorrect_conversational_chronology",
}
_CHECKLIST_FIELDS = {
    "matches_formal_spec",
    "preserves_cross_language_meaning",
    "initial_requirements_communicated",
    "decisive_turn_expresses_event",
    "counterfactual_differences_controlled",
    "action_interpretation_preserved",
    "no_post_action_information",
    "msa_natural_and_unambiguous",
}
_FORBIDDEN_ANNOTATION_FIELDS = {
    "gold_label",
    "oracle_label",
    "reference_label",
    "validity_label",
    "judge_prediction",
    "judge_response",
}
_ANNOTATION_REQUIRED_FIELDS = {
    "annotation_schema_version",
    "example_id",
    "example_sha256",
    "canonical_scenario_sha256",
    "reviewer_id",
    "semantic_relation",
    "linguistic_quality",
    "decisive_update_dependence",
    "decisive_update_dependence_rationale",
    "whole_action_dependence",
    "whole_action_dependence_rationale",
    "issue_codes",
    "checklist",
    "notes",
}
_ADJUDICATION_OUTCOMES = {"retain", "revise", "exclude", "unresolved"}
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def variant_sha256(variant: object) -> str:
    """Hash the typed variant record with P1's deterministic canonical encoding."""
    return hashlib.sha256(stable_json(variant).encode("utf-8")).hexdigest()


def canonical_scenario_sha256(scenario: CanonicalScenario) -> str:
    """Hash the formal scenario record reviewed alongside each language variant."""
    return hashlib.sha256(stable_json(scenario).encode("utf-8")).hexdigest()


def blank_annotation_record(example_id: str, example_hash: str, scenario_hash: str) -> dict:
    """Create an unfilled, versioned annotation row bound to both reviewed objects."""
    if not isinstance(example_id, str) or not example_id.strip():
        raise PreflightValidationError("annotation example ID is required")
    if not isinstance(example_hash, str) or not _HEX_SHA256.fullmatch(example_hash):
        raise PreflightValidationError("annotation example hash must be a lowercase SHA-256 digest")
    if not isinstance(scenario_hash, str) or not _HEX_SHA256.fullmatch(scenario_hash):
        raise PreflightValidationError("annotation canonical-scenario hash must be a lowercase SHA-256 digest")
    return {
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "example_id": example_id,
        "example_sha256": example_hash,
        "canonical_scenario_sha256": scenario_hash,
        "reviewer_id": "",
        "semantic_relation": "",
        "linguistic_quality": "",
        "decisive_update_dependence": "",
        "decisive_update_dependence_rationale": "",
        "whole_action_dependence": "",
        "whole_action_dependence_rationale": "",
        "issue_codes": [],
        "checklist": {field: None for field in sorted(_CHECKLIST_FIELDS)},
        "notes": "",
    }


def _expected_coverage_targets(scenario: CanonicalScenario, history) -> dict[tuple[str, str], int]:
    expected: dict[tuple[str, str], int] = {}
    initial_turn = next(
        (
            variant.assignment.initial_turn_index
            for variant in scenario.language_variants
            if variant.parent_history_id == history.history_id
        ),
        None,
    )
    if initial_turn is None:
        raise PreflightValidationError(f"history {history.history_id} has no language variant")
    for fact in scenario.shared_context:
        expected[("context_fact", fact.key)] = initial_turn
    for field in scenario.action.fields:
        expected[("action_field", field.name)] = initial_turn
    for requirement in history.initial_state.requirements:
        expected[("initial_requirement", requirement.constraint_id)] = initial_turn
    for grant in history.initial_state.grants:
        expected[("initial_permission", grant.grant_id)] = initial_turn
    for event in history.events:
        expected[("event", event.event_id)] = event.turn_index
    return expected


def validate_semantic_coverage(
    scenario: CanonicalScenario,
    coverage_document: dict,
) -> SemanticCoverageAudit:
    """Check that every formal target maps to spans in its required user turn.

    This is a deterministic alignment check only. It deliberately does not
    assign semantic correctness or human-validation status. Decision-relevant
    requirements and events must include non-whitespace localized text.
    """
    if coverage_document.get("schema_version") != "p2a-coverage-1":
        raise PreflightValidationError("unsupported semantic-coverage schema version")
    if coverage_document.get("scenario_id") != scenario.scenario_id:
        raise PreflightValidationError("semantic-coverage scenario ID does not match canonical record")
    if coverage_document.get("draft_status") != "machine_assisted_unvalidated":
        raise PreflightValidationError("language drafts must remain marked machine-assisted and unvalidated")
    coverage_by_variant = coverage_document.get("variants")
    expected_variant_ids = {variant.derivative_id for variant in scenario.language_variants}
    if not isinstance(coverage_by_variant, dict) or set(coverage_by_variant) != expected_variant_ids:
        raise PreflightValidationError("semantic-coverage variant IDs must exactly match canonical derivatives")

    histories = {history.history_id: history for history in scenario.histories}
    mapped_count = 0
    for variant in scenario.language_variants:
        variant_map = coverage_by_variant[variant.derivative_id]
        if not isinstance(variant_map, dict) or not isinstance(variant_map.get("targets"), list):
            raise PreflightValidationError(f"coverage targets are malformed for {variant.derivative_id}")
        if variant_map.get("human_validation_status") not in {"not_started", "pending_independent_review"}:
            raise PreflightValidationError("P2A draft variants cannot be marked human validated")
        history = histories[variant.parent_history_id]
        expected = _expected_coverage_targets(scenario, history)
        observed: dict[tuple[str, str], list[str]] = {}
        for target in variant_map["targets"]:
            if not isinstance(target, dict) or set(target) != {"target_type", "target_id", "segment_ids"}:
                raise PreflightValidationError(f"malformed semantic-coverage target for {variant.derivative_id}")
            target_type, target_id = target["target_type"], target["target_id"]
            if target_type not in _COVERAGE_TARGET_TYPES or not isinstance(target_id, str) or not target_id:
                raise PreflightValidationError("semantic-coverage target type or ID is invalid")
            key = (target_type, target_id)
            if key in observed:
                raise PreflightValidationError(f"duplicate semantic-coverage target {target_type}:{target_id}")
            segment_ids = target["segment_ids"]
            if not isinstance(segment_ids, list) or not segment_ids or any(not isinstance(row, str) for row in segment_ids):
                raise PreflightValidationError(f"semantic-coverage target {target_type}:{target_id} requires span IDs")
            if len(segment_ids) != len(set(segment_ids)):
                raise PreflightValidationError("duplicate span ID in semantic-coverage target")
            observed[key] = segment_ids

        missing = set(expected) - set(observed)
        extra = set(observed) - set(expected)
        if missing:
            display = ", ".join(f"{kind}:{identifier}" for kind, identifier in sorted(missing))
            raise PreflightValidationError(f"missing semantic coverage for {display}")
        if extra:
            display = ", ".join(f"{kind}:{identifier}" for kind, identifier in sorted(extra))
            raise PreflightValidationError(f"semantic coverage has unresolved target(s): {display}")

        turns = {turn.turn_index: turn for turn in variant.turns}
        segments = {segment.segment_id: (turn, segment) for turn in variant.turns for segment in turn.segments}
        for key, segment_ids in observed.items():
            required_turn = expected[key]
            selected = []
            for segment_id in segment_ids:
                if segment_id not in segments:
                    raise PreflightValidationError(f"semantic-coverage span ID is absent: {segment_id}")
                turn, segment = segments[segment_id]
                if turn.turn_index != required_turn or turn.role is not TurnRole.USER:
                    raise PreflightValidationError(f"{key[0]}:{key[1]} must map to user turn {required_turn}")
                selected.append(segment)
            if key[0] in {"initial_requirement", "initial_permission", "event"} and not any(
                segment.kind is TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE and segment.text.strip()
                for segment in selected
            ):
                raise PreflightValidationError(
                    f"{key[0]}:{key[1]} requires non-whitespace localized natural-language text"
                )
            mapped_count += 1

    return SemanticCoverageAudit(scenario.scenario_id, len(scenario.language_variants), mapped_count)


def _formal_review_spec(scenario: CanonicalScenario) -> dict:
    """Build reviewer-facing reference context without verdict or declared-label fields."""
    return {
        "schema_version": scenario.schema_version,
        "scenario_id": scenario.scenario_id,
        "dataset_kind": scenario.kind.value,
        "domain": scenario.domain.value,
        "transition_family": scenario.transition_family.value,
        "shared_context": [canonical_value(row) for row in scenario.shared_context],
        "action": canonical_value(scenario.action),
        "action_contract": canonical_value(scenario.action_contract),
        "public_tool_schema": canonical_value(scenario.public_tool_schema),
        "histories": [
            {
                "history_id": history.history_id,
                "initial_state": canonical_value(history.initial_state),
                "events": [canonical_value(event) for event in history.events],
                "decisive_event_ids": list(history.decisive_event_ids),
                "decisive_turn_index": history.decisive_turn_index,
                "action_turn_index": history.action_turn_index,
            }
            for history in scenario.histories
        ],
    }


def export_reviewer_packets(
    scenarios: Iterable[CanonicalScenario],
    output_root: Path,
    *,
    reviewer_ids: tuple[str, str] = ("reviewer_slot_1", "reviewer_slot_2"),
    coverage_documents: dict[str, dict] | None = None,
) -> tuple[Path, ...]:
    """Write two independent local review packets per scenario, without labels."""
    if len(reviewer_ids) != 2 or len(set(reviewer_ids)) != 2:
        raise PreflightValidationError("exactly two distinct reviewer IDs are required")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", reviewer_id) for reviewer_id in reviewer_ids):
        raise PreflightValidationError("reviewer IDs may contain only letters, digits, underscores, and hyphens")

    written: list[Path] = []
    for scenario in scenarios:
        from .integrity import validate_scenario

        validate_scenario(scenario)
        variants = []
        coverage_document = (coverage_documents or {}).get(scenario.scenario_id)
        for variant in scenario.language_variants:
            row = {
                "derivative_id": variant.derivative_id,
                "history_id": variant.parent_history_id,
                "condition": variant.assignment.condition.value,
                "example_sha256": variant_sha256(variant),
                "draft_status": "machine_assisted_unvalidated",
                "human_validation_status": "fresh_independent_review_required",
                "turns": [
                    {
                        "turn_index": turn.turn_index,
                        "speaker": turn.role.value,
                        "language": turn.language.value,
                        "segments": [canonical_value(segment) for segment in turn.segments],
                    }
                    for turn in variant.turns
                ],
            }
            if coverage_document is not None:
                row["semantic_coverage"] = coverage_document["variants"][variant.derivative_id]["targets"]
            variants.append(row)

        for reviewer_id in reviewer_ids:
            directory = output_root / reviewer_id
            directory.mkdir(parents=True, exist_ok=True)
            packet = {
                "packet_version": REVIEW_PACKET_VERSION,
                "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
                "adjudication_schema_version": ADJUDICATION_SCHEMA_VERSION,
                "reviewer_slot": reviewer_id,
                "scenario_id": scenario.scenario_id,
                "instruction": "Review independently. Do not view or discuss model-judge predictions. Explicit oracle verdicts and gold-label fields are omitted. This is machine-assisted draft language and is not independently validated.",
                "canonical_spec": _formal_review_spec(scenario),
                "canonical_scenario_sha256": canonical_scenario_sha256(scenario),
                "language_variants": variants,
                "annotation_template_file": "annotation-template.jsonl",
            }
            path = directory / f"{scenario.scenario_id}.json"
            path.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            written.append(path)
    return tuple(written)


def _validate_annotation_record(
    record: dict,
    expected_hashes: dict[str, str],
    expected_scenario_hashes: dict[str, str],
) -> None:
    if not isinstance(record, dict):
        raise PreflightValidationError("annotation record must be a JSON object")
    forbidden = _FORBIDDEN_ANNOTATION_FIELDS & set(record)
    if forbidden:
        raise PreflightValidationError(f"prohibited annotation fields: {', '.join(sorted(forbidden))}")
    missing = _ANNOTATION_REQUIRED_FIELDS - set(record)
    unknown = set(record) - _ANNOTATION_REQUIRED_FIELDS
    if missing:
        raise PreflightValidationError("annotation record is missing required fields")
    if unknown:
        raise PreflightValidationError(f"annotation record has unknown fields: {', '.join(sorted(unknown))}")
    if record["annotation_schema_version"] != ANNOTATION_SCHEMA_VERSION:
        raise PreflightValidationError("annotation schema version is unsupported")
    example_id = record["example_id"]
    if not isinstance(example_id, str) or not example_id.strip():
        raise PreflightValidationError("annotation example ID is required")
    if not isinstance(record["reviewer_id"], str) or not record["reviewer_id"].strip():
        raise PreflightValidationError("annotation reviewer ID is required")
    for field in ("example_sha256", "canonical_scenario_sha256"):
        if not isinstance(record[field], str) or not _HEX_SHA256.fullmatch(record[field]):
            raise PreflightValidationError(f"annotation {field} must be a lowercase SHA-256 digest")
    if example_id not in expected_hashes or record["example_sha256"] != expected_hashes[example_id]:
        raise PreflightValidationError("annotation references an unknown or changed example hash")
    if example_id not in expected_scenario_hashes or record["canonical_scenario_sha256"] != expected_scenario_hashes[example_id]:
        raise PreflightValidationError("annotation canonical_scenario_sha256 does not match the reviewed formal scenario")
    if not isinstance(record["semantic_relation"], str) or record["semantic_relation"] not in _ANNOTATION_RELATIONS:
        raise PreflightValidationError("annotation semantic_relation is invalid")
    if not isinstance(record["linguistic_quality"], str) or record["linguistic_quality"] not in _LINGUISTIC_QUALITIES:
        raise PreflightValidationError("annotation linguistic_quality is invalid")
    for field in ("decisive_update_dependence", "whole_action_dependence"):
        if not isinstance(record[field], str) or record[field] not in _DEPENDENCE_CATEGORIES:
            raise PreflightValidationError(f"annotation {field} is invalid")
    for field in ("decisive_update_dependence_rationale", "whole_action_dependence_rationale"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise PreflightValidationError(f"annotation {field} is required")
    issues = record["issue_codes"]
    if not isinstance(issues, list) or any(not isinstance(issue, str) for issue in issues):
        raise PreflightValidationError("annotation issue_codes are invalid")
    if len(issues) != len(set(issues)) or not set(issues) <= _ANNOTATION_ISSUES:
        raise PreflightValidationError("annotation issue_codes are invalid")
    checklist = record["checklist"]
    if not isinstance(checklist, dict) or set(checklist) != _CHECKLIST_FIELDS or any(
        not isinstance(value, bool) for value in checklist.values()
    ):
        raise PreflightValidationError("annotation checklist must contain every required boolean check")
    if not isinstance(record["notes"], str):
        raise PreflightValidationError("annotation notes must be text")


def summarize_annotations(
    records: Iterable[dict],
    expected_hashes: dict[str, str],
    expected_scenario_hashes: dict[str, str],
) -> AnnotationAudit:
    """Validate independent annotation rows and summarize completeness/agreement."""
    by_example: dict[str, dict[str, dict]] = defaultdict(dict)
    reviewer_ids: set[str] = set()
    for record in records:
        _validate_annotation_record(record, expected_hashes, expected_scenario_hashes)
        example_id, reviewer_id = record["example_id"], record["reviewer_id"]
        if reviewer_id in by_example[example_id]:
            raise PreflightValidationError(f"duplicate annotation by reviewer {reviewer_id} for {example_id}")
        by_example[example_id][reviewer_id] = record
        reviewer_ids.add(reviewer_id)

    complete = len(reviewer_ids) == 2 and all(set(by_example.get(example_id, {})) == reviewer_ids for example_id in expected_hashes)
    agreement: float | None = None
    kappa: float | None = None
    decisive_update_agreement: float | None = None
    whole_action_agreement: float | None = None
    linguistic_agreement: float | None = None
    issue_agreement: float | None = None
    checklist_agreement: dict[str, float] = {}
    if complete and expected_hashes:
        reviewer_a, reviewer_b = sorted(reviewer_ids)
        rows = [
            (by_example[example_id][reviewer_a], by_example[example_id][reviewer_b])
            for example_id in expected_hashes
        ]
        pairs = [(left["semantic_relation"], right["semantic_relation"]) for left, right in rows]
        agreement = sum(left == right for left, right in pairs) / len(pairs)
        categories = _ANNOTATION_RELATIONS
        observed = agreement
        expected = sum(
            sum(left == category for left, _ in pairs)
            / len(pairs)
            * sum(right == category for _, right in pairs)
            / len(pairs)
            for category in categories
        )
        kappa = (observed - expected) / (1 - expected) if expected < 1 else None
        decisive_update_agreement = sum(
            left["decisive_update_dependence"] == right["decisive_update_dependence"]
            for left, right in rows
        ) / len(rows)
        whole_action_agreement = sum(
            left["whole_action_dependence"] == right["whole_action_dependence"]
            for left, right in rows
        ) / len(rows)
        linguistic_agreement = sum(
            left["linguistic_quality"] == right["linguistic_quality"] for left, right in rows
        ) / len(rows)
        issue_agreement = sum(set(left["issue_codes"]) == set(right["issue_codes"]) for left, right in rows) / len(rows)
        checklist_agreement = {
            field: sum(left["checklist"][field] == right["checklist"][field] for left, right in rows) / len(rows)
            for field in sorted(_CHECKLIST_FIELDS)
        }

    return AnnotationAudit(
        expected_example_count=len(expected_hashes),
        annotated_example_count=len(by_example),
        reviewer_count=len(reviewer_ids),
        reviewer_ids=tuple(sorted(reviewer_ids)),
        complete=complete,
        raw_semantic_agreement=agreement,
        cohen_kappa=kappa,
        decisive_update_dependence_agreement=decisive_update_agreement,
        whole_action_dependence_agreement=whole_action_agreement,
        linguistic_quality_agreement=linguistic_agreement,
        issue_code_exact_agreement=issue_agreement,
        checklist_item_agreement=checklist_agreement,
    )


def validate_adjudication_records(
    adjudications: Iterable[dict], annotations: Iterable[dict]
) -> AdjudicationAudit:
    """Validate hash-bound adjudications for disagreements in complete reviewer pairs."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for annotation in annotations:
        if not isinstance(annotation, dict) or not isinstance(annotation.get("example_id"), str):
            raise PreflightValidationError("cannot group malformed annotation records")
        grouped[annotation["example_id"]].append(annotation)

    expected: dict[str, list[dict]] = {}
    incomplete_pair_count = 0
    for example_id, rows in grouped.items():
        if len(rows) == 1:
            row = rows[0]
            _validate_annotation_record(
                row,
                {example_id: row.get("example_sha256")},
                {example_id: row.get("canonical_scenario_sha256")},
            )
            incomplete_pair_count += 1
            continue
        if len(rows) != 2:
            raise PreflightValidationError(f"adjudication audit requires at most two annotations for {example_id}")

        first = rows[0]
        expected_hashes = {example_id: first.get("example_sha256")}
        expected_scenario_hashes = {example_id: first.get("canonical_scenario_sha256")}
        for row in rows:
            _validate_annotation_record(row, expected_hashes, expected_scenario_hashes)
        if rows[0]["reviewer_id"] == rows[1]["reviewer_id"]:
            raise PreflightValidationError(f"adjudication audit requires two distinct reviewers for {example_id}")

        comparable = (
            "semantic_relation",
            "linguistic_quality",
            "decisive_update_dependence",
            "whole_action_dependence",
            "issue_codes",
            "checklist",
        )
        if any(rows[0].get(field) != rows[1].get(field) for field in comparable):
            expected[example_id] = rows

    observed: dict[str, dict] = {}
    for record in adjudications:
        if not isinstance(record, dict):
            raise PreflightValidationError("adjudication record must be a JSON object")
        required = {
            "adjudication_schema_version",
            "example_id",
            "example_sha256",
            "canonical_scenario_sha256",
            "reviewer_ids",
            "adjudicator_id",
            "outcome",
            "rationale",
        }
        if not required <= set(record) or set(record) - (required | {"revision_sha256"}):
            raise PreflightValidationError("adjudication record has missing or unknown fields")
        if record["adjudication_schema_version"] != ADJUDICATION_SCHEMA_VERSION:
            raise PreflightValidationError("adjudication schema version is unsupported")
        example_id = record["example_id"]
        if not isinstance(example_id, str) or not example_id.strip():
            raise PreflightValidationError("adjudication example ID is required")
        if example_id not in expected or example_id in observed:
            raise PreflightValidationError("adjudication must reference one unresolved disagreement exactly once")
        rows = expected[example_id]
        for field in ("example_sha256", "canonical_scenario_sha256"):
            digest = record[field]
            if not isinstance(digest, str) or not _HEX_SHA256.fullmatch(digest):
                raise PreflightValidationError(f"adjudication {field} must be a lowercase SHA-256 digest")
            if any(digest != row[field] for row in rows):
                raise PreflightValidationError(f"adjudication {field} does not match both annotations")
        reviewer_ids = record["reviewer_ids"]
        if (
            not isinstance(reviewer_ids, list)
            or len(reviewer_ids) != 2
            or any(not isinstance(reviewer_id, str) or not reviewer_id.strip() for reviewer_id in reviewer_ids)
            or len(set(reviewer_ids)) != 2
        ):
            raise PreflightValidationError("adjudication reviewer IDs must be two distinct non-empty strings")
        if set(reviewer_ids) != {row["reviewer_id"] for row in rows}:
            raise PreflightValidationError("adjudication reviewer IDs do not match independent annotations")
        if (
            not isinstance(record["adjudicator_id"], str)
            or not record["adjudicator_id"].strip()
            or not isinstance(record["rationale"], str)
            or not record["rationale"].strip()
            or not isinstance(record["outcome"], str)
            or record["outcome"] not in _ADJUDICATION_OUTCOMES
        ):
            raise PreflightValidationError("adjudication needs an adjudicator, rationale, and valid outcome")
        if "revision_sha256" in record and (
            not isinstance(record["revision_sha256"], str) or not _HEX_SHA256.fullmatch(record["revision_sha256"])
        ):
            raise PreflightValidationError("adjudication revision_sha256 must be a lowercase SHA-256 digest")
        if record["outcome"] == "revise" and not _HEX_SHA256.fullmatch(record.get("revision_sha256", "")):
            raise PreflightValidationError("revised examples require their new content hash")
        observed[example_id] = record

    missing = set(expected) - set(observed)
    if missing:
        raise PreflightValidationError(f"missing adjudication for disagreement(s): {', '.join(sorted(missing))}")
    unresolved_count = sum(record["outcome"] == "unresolved" for record in observed.values())
    return AdjudicationAudit(
        required_count=len(expected),
        adjudication_count=len(observed),
        unresolved_count=unresolved_count,
        incomplete_pair_count=incomplete_pair_count,
        complete=not incomplete_pair_count and not unresolved_count,
    )


def append_jsonl_record(data_root: Path, relative_path: str, record: dict) -> Path:
    """Append one deterministic JSON object beneath the ignored local-data root."""
    root = data_root.resolve()
    destination = (root / relative_path).resolve()
    if not destination.is_relative_to(root):
        raise PreflightValidationError("record path must remain inside the research-data root")
    if not isinstance(record, dict):
        raise PreflightValidationError("JSONL record must be an object")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
    return destination


_PRIVATE_PATH_PROBES = (
    ".research-data/p2a/development/prototypes/_ignore_probe.json",
    ".research-data/p2a/development/coverage/_ignore_probe.json",
    ".research-data/p2a/review-packets/reviewer_1/_ignore_probe.json",
    ".research-data/p2a/annotations/annotations.jsonl",
    ".research-data/p2a/adjudications/adjudications.jsonl",
    ".research-data/p2b-1/revisions/prototype.json",
    ".research-data/p2b-1/review-packets/reviewer_slot_1/prototype.json",
    ".research-data/p2b-1/annotations/reviewer_slot_1.jsonl",
    ".research-data/p2b-1/review-materials/bilingual-side-by-side.md",
)
_PRIVATE_TRACKED_PREFIXES = (".research-data/", "data/private/", "data/locked/", "data/reference/")


def verify_research_data_exclusion(repo_root: Path) -> DataIsolationAudit:
    """Check ignore behavior and existing Git index membership; ignore rules alone are insufficient."""
    ignored: list[str] = []
    for relative in _PRIVATE_PATH_PROBES:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", relative],
            cwd=repo_root,
            check=False,
        )
        if result.returncode == 0:
            ignored.append(relative)
        elif result.returncode != 1:
            raise PreflightValidationError("git check-ignore could not verify private research-data paths")
    tracked_result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo_root, check=True, capture_output=True
    )
    tracked = tuple(
        sorted(
            path
            for path in tracked_result.stdout.decode("utf-8").split("\0")
            if path and any(path.startswith(prefix) for prefix in _PRIVATE_TRACKED_PREFIXES)
        )
    )
    if len(ignored) != len(_PRIVATE_PATH_PROBES):
        missing = sorted(set(_PRIVATE_PATH_PROBES) - set(ignored))
        raise PreflightValidationError(f"private research-data paths are not ignored: {', '.join(missing)}")
    if tracked:
        raise PreflightValidationError(f"private research data is already tracked by Git: {', '.join(tracked)}")
    return DataIsolationAudit(True, tuple(ignored), tracked)


def run_prototype_preflight(development_root: Path) -> tuple[PrototypePreflight, tuple[CanonicalScenario, ...]]:
    """Validate exactly four local development prototypes and their coverage maps."""
    prototype_dir = development_root / "prototypes"
    coverage_dir = development_root / "coverage"
    scenario_paths = tuple(sorted(prototype_dir.glob("*.json"))) if prototype_dir.is_dir() else ()
    coverage_paths = tuple(sorted(coverage_dir.glob("*.json"))) if coverage_dir.is_dir() else ()
    if len(scenario_paths) != 4:
        raise PreflightValidationError(f"P2A requires exactly four local canonical prototypes; found {len(scenario_paths)}")

    scenarios: list[CanonicalScenario] = []
    coverage_count = 0
    variant_hashes: dict[str, str] = {}
    for path in scenario_paths:
        scenario = scenario_from_json(path.read_text(encoding="utf-8"))
        if path.stem != scenario.scenario_id:
            raise PreflightValidationError("prototype filename must match its canonical scenario ID")
        if scenario.kind is not DatasetKind.PRIMARY or scenario.partition is not Partition.DEVELOPMENT:
            raise PreflightValidationError("P2A prototypes must be primary development records")
        if (
            scenario.provenance.validation_status.value != "not_validated"
            or "machine-assisted" not in scenario.provenance.generation_method.lower()
        ):
            raise PreflightValidationError("prototype provenance must identify machine-assisted drafts as unvalidated")
        if any(variant.validation_status.value != "not_validated" for variant in scenario.language_variants):
            raise PreflightValidationError("P2A language drafts cannot be marked human validated")
        validate_language_variant_coverage(scenario)
        scenarios.append(scenario)

        coverage_path = coverage_dir / f"{scenario.scenario_id}.json"
        if not coverage_path.is_file():
            raise PreflightValidationError(f"semantic-coverage map is missing for {scenario.scenario_id}")
        coverage_document = json.loads(coverage_path.read_text(encoding="utf-8"))
        coverage_count += validate_semantic_coverage(scenario, coverage_document).mapped_target_count
        for variant in scenario.language_variants:
            if variant.derivative_id in variant_hashes:
                raise PreflightValidationError("language derivative ID is duplicated across prototypes")
            variant_hashes[variant.derivative_id] = variant_sha256(variant)

    expected_coverage_paths = {f"{scenario.scenario_id}.json" for scenario in scenarios}
    observed_coverage_paths = {path.name for path in coverage_paths}
    if expected_coverage_paths != observed_coverage_paths:
        raise PreflightValidationError("semantic-coverage directory must contain exactly one map per prototype")
    if len(variant_hashes) != 32:
        raise PreflightValidationError(f"four prototypes must produce exactly 32 language variants; found {len(variant_hashes)}")

    validate_scenario_collection(scenarios)
    cells = {(scenario.domain, scenario.transition_family) for scenario in scenarios}
    if cells != _EXPECTED_PROTOTYPE_CELLS or len(cells) != 4:
        raise PreflightValidationError("prototypes must occupy the four approved distinct domain-transition cells")

    labels = Counter()
    for scenario in scenarios:
        pair = validate_counterfactual_pair(scenario)
        if set(pair.labels) != {ValidityLabel.VALID, ValidityLabel.INVALID}:
            raise PreflightValidationError("oracle must establish one valid and one invalid history per prototype")
        for history, label in zip(scenario.histories, pair.labels, strict=True):
            labels[label.value] += sum(variant.parent_history_id == history.history_id for variant in scenario.language_variants)
    if labels != Counter({"valid": 16, "invalid": 16}):
        raise PreflightValidationError("four prototypes must yield 16 valid and 16 invalid derived items")

    duplicate_audit = audit_duplicates(scenarios)
    if duplicate_audit.exact_duplicate_groups or duplicate_audit.normalized_text_duplicate_groups:
        raise PreflightValidationError("exact or normalized duplicate candidates require review before preflight acceptance")
    if len(scenario_paths) != len(scenarios):
        raise PreflightValidationError("prototype records were not all parsed")

    result = PrototypePreflight(
        scenario_count=len(scenarios),
        language_variant_count=len(variant_hashes),
        item_count=len(variant_hashes),
        label_counts=dict(sorted(labels.items())),
        domain_family_cells=tuple(sorted(f"{domain.value}/{family.value}" for domain, family in cells)),
        template_counts=duplicate_audit.template_counts,
        recipe_counts=duplicate_audit.recipe_counts,
        exact_duplicate_group_count=len(duplicate_audit.exact_duplicate_groups),
        normalized_duplicate_group_count=len(duplicate_audit.normalized_text_duplicate_groups),
        semantic_coverage_target_count=coverage_count,
        variant_hashes=variant_hashes,
    )
    return result, tuple(scenarios)


def render_redacted_preflight_report(result: PrototypePreflight) -> str:
    """Render aggregate public metadata only; never include IDs, utterances, or per-item labels."""
    cells = "\n".join(f"- `{cell}`" for cell in result.domain_family_cells)
    template_total = len(result.template_counts)
    recipe_total = len(result.recipe_counts)
    template_reuse = sum(max(0, count - 1) for count in result.template_counts.values())
    recipe_reuse = sum(max(0, count - 1) for count in result.recipe_counts.values())
    return f"""# P2A/P2B-1 development-only preflight report

**Status:** Deterministic preflight complete; independent bilingual validation has not been performed.

## Scope and structure

- Four local, ignored primary development prototypes; no locked scenarios or auxiliary-control study examples.
- Four canonical scenarios × two histories × four language conditions per history = {result.language_variant_count} history-language variants and {result.item_count} development-only items.
- Prototype domain-transition cells:
{cells}
- Deterministic counterfactual validation passed for each pair. Reference validity labels and oracle outputs are omitted from this public report.
- Structural semantic-coverage map: {result.semantic_coverage_target_count} formal targets are linked to judge-visible spans in the expected user turns. Initial requirements, grants, and decisive events include localized natural-language spans; this link check does not verify meaning.

## Deterministic validation

- P1 typed schema, counterfactual oracle, language-condition coverage, and action chronology checks passed for all four records.
- Counterfactual pair-integrity checks passed for all four scenarios; pair-level verdicts are not reported.
- Exact duplicate groups: {result.exact_duplicate_group_count}; normalized text duplicate groups: {result.normalized_duplicate_group_count}. Semantic near-duplicates were not machine-verified.
- Recorded template IDs: {template_total} distinct with {template_reuse} repeated assignments; recipe IDs: {recipe_total} distinct with {recipe_reuse} repeated assignments. IDs are provisional, semantic/template-family overlap has not been independently audited, and development-only data cannot establish cross-partition separation.

## Feasibility assessment

The preflight demonstrates that P1's bounded schema and oracle can support the formal structures, condition coverage, chronology, and provenance checks needed for these four development prototypes. It does not establish full-study authoring throughput, human-review capacity, naturalness, or semantic equivalence; these remain owner-review and later-milestone questions.

## P2B-1 draft-correction status

The four existing drafts were revised after independent content-audit findings. Wording was clarified, one public tool description was aligned with its intended operation, and relative numerical and temporal revision forms were adopted to exercise earlier-state reconstruction. Formal effective constraints and counterfactual oracle relationships were preserved. These changes remain unvalidated natural-language drafts. Author-side provisional assessments of decisive-update and whole-action dependence are withheld from independent reviewers and are not human annotations.

## Human review status

All English and MSA conversations are Codex-authored, machine-assisted drafts marked **not independently validated**. Completed independent annotations: 0 of 64 expected; adjudications: 0. Two qualified bilingual reviewers must review every variant against the formal specification without access to judge predictions. Each annotation records decisive-update dependence and whole-action dependence separately, with a separate rationale for each; disagreement on either category requires hash-bound adjudication. Substantive corrections require re-review against new variant and canonical-scenario hashes. Reviewer slots and blank templates are preparation materials, not reviewer records.

## Remaining surface-feature risks

Four scenarios are insufficient to establish that labels are not predictable from surface features. Permission wording, numeric bound polarity and revision direction, values and action margins, earliest/latest temporal expressions, explicit confirmations, negation, length, turn count, magnitude, and critical-information position may correlate with validity by design. These properties require a pre-freeze, human-coded, label-association audit across the full planned dataset. Do not force unnatural wording or claim statistical balance from this preflight.

## Data handling

Canonical records, translations, coverage maps, reference labels, prior versions, review packets, blank annotation templates, annotations, and adjudications remain under ignored local `.research-data/` paths. No locked examples, auxiliary-control examples, judge predictions, or model outputs were created. Only this aggregate redacted report is public.
"""


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise PreflightValidationError(f"blank JSONL record at line {line_number}")
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise PreflightValidationError(f"invalid JSONL record at line {line_number}") from error
    return records


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Local prototype preflight and bilingual-review preparation utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="run deterministic checks and render a redacted report")
    validate_parser.add_argument("--development-root", type=Path, default=Path(".research-data/p2a/development"))
    validate_parser.add_argument("--output", type=Path, help="optional output path for the redacted aggregate report")
    packet_parser = subparsers.add_parser("review-packets", help="export local, label-free bilingual review packets")
    packet_parser.add_argument("--development-root", type=Path, default=Path(".research-data/p2a/development"))
    packet_parser.add_argument("--output-root", type=Path, default=Path(".research-data/p2b-1/review-packets"))
    annotation_parser = subparsers.add_parser("audit-annotations", help="check local annotation and adjudication records")
    annotation_parser.add_argument("--development-root", type=Path, default=Path(".research-data/p2a/development"))
    annotation_parser.add_argument("--annotations", type=Path, default=Path(".research-data/p2b-1/annotations/annotations.jsonl"))
    annotation_parser.add_argument("--adjudications", type=Path, default=Path(".research-data/p2b-1/adjudications/adjudications.jsonl"))
    subparsers.add_parser("isolation", help="verify private research-data ignore and tracked-file status")
    args = parser.parse_args()

    if args.command == "isolation":
        audit = verify_research_data_exclusion(Path.cwd())
        print(json.dumps({
            "all_private_paths_ignored": audit.all_private_paths_ignored,
            "tracked_private_paths": list(audit.tracked_private_paths),
        }, sort_keys=True))
        return 0

    result, scenarios = run_prototype_preflight(args.development_root)
    if args.command == "validate":
        report = render_redacted_preflight_report(result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        print(report, end="")
        return 0
    if args.command == "review-packets":
        coverage = {
            scenario.scenario_id: json.loads(
                (args.development_root / "coverage" / f"{scenario.scenario_id}.json").read_text(encoding="utf-8")
            )
            for scenario in scenarios
        }
        paths = export_reviewer_packets(scenarios, args.output_root, coverage_documents=coverage)
        print(json.dumps({"packet_count": len(paths), "output_root": str(args.output_root)}, sort_keys=True))
        return 0

    expected_hashes = {
        variant.derivative_id: variant_sha256(variant)
        for scenario in scenarios
        for variant in scenario.language_variants
    }
    expected_scenario_hashes = {
        variant.derivative_id: canonical_scenario_sha256(scenario)
        for scenario in scenarios
        for variant in scenario.language_variants
    }
    annotations = _read_jsonl(args.annotations)
    audit = summarize_annotations(annotations, expected_hashes, expected_scenario_hashes)
    adjudications = _read_jsonl(args.adjudications)
    adjudication_audit = validate_adjudication_records(adjudications, annotations)
    print(json.dumps({
        "expected_examples": audit.expected_example_count,
        "annotated_examples": audit.annotated_example_count,
        "reviewer_count": audit.reviewer_count,
        "complete_two_reviewer_coverage": audit.complete,
        "missing_annotation_rows": max(0, 2 * len(expected_hashes) - len(annotations)),
        "semantic_relation_percent_agreement": audit.raw_semantic_agreement,
        "cohen_kappa": audit.cohen_kappa,
        "decisive_update_dependence_percent_agreement": audit.decisive_update_dependence_agreement,
        "whole_action_dependence_percent_agreement": audit.whole_action_dependence_agreement,
        "linguistic_quality_percent_agreement": audit.linguistic_quality_agreement,
        "issue_code_exact_percent_agreement": audit.issue_code_exact_agreement,
        "checklist_item_agreement": audit.checklist_item_agreement,
        "adjudications_required": adjudication_audit.required_count,
        "adjudications_recorded": adjudication_audit.adjudication_count,
        "unresolved_adjudications": adjudication_audit.unresolved_count,
        "incomplete_annotation_pairs": adjudication_audit.incomplete_pair_count,
        "adjudication_complete": adjudication_audit.complete,
        "review_process_complete": audit.complete and adjudication_audit.complete,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
