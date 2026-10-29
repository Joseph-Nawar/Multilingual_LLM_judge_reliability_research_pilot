"""Small deterministic utilities for the P2A local authoring preflight.

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
    """A local P2A prototype, coverage map, or review record is invalid."""


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
    linguistic_quality_agreement: float | None
    issue_code_exact_agreement: float | None
    checklist_item_agreement: dict[str, float]


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
    "example_id",
    "example_sha256",
    "reviewer_id",
    "semantic_relation",
    "linguistic_quality",
    "issue_codes",
    "checklist",
    "notes",
}
_ADJUDICATION_OUTCOMES = {"retain", "revise", "exclude", "unresolved"}
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def variant_sha256(variant: object) -> str:
    """Hash the typed variant record with P1's deterministic canonical encoding."""
    return hashlib.sha256(stable_json(variant).encode("utf-8")).hexdigest()


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
    """Check that every formal target maps to localized spans in its required user turn.

    This is a deterministic alignment check only. It deliberately does not
    assign semantic correctness or human-validation status.
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
                segment.kind is TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE for segment in selected
            ):
                raise PreflightValidationError(f"{key[0]}:{key[1]} is mapped only to invariant literals, not natural language")
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
        "initial_states": [
            {
                "history_id": history.history_id,
                "requirements": [canonical_value(row) for row in history.initial_state.requirements],
                "permissions": [canonical_value(row) for row in history.initial_state.grants],
            }
            for history in scenario.histories
        ],
        "events": [
            {
                "history_id": history.history_id,
                "decisive_turn_index": history.decisive_turn_index,
                "action_turn_index": history.action_turn_index,
                "events": [canonical_value(event) for event in history.events],
            }
            for history in scenario.histories
        ],
    }


def export_reviewer_packets(
    scenarios: Iterable[CanonicalScenario],
    output_root: Path,
    *,
    reviewer_ids: tuple[str, str] = ("reviewer_1", "reviewer_2"),
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
                "human_validation_status": "not_started",
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
                "packet_version": "p2a-review-1",
                "reviewer_id": reviewer_id,
                "scenario_id": scenario.scenario_id,
                "instruction": "Review independently. Do not view or discuss model-judge predictions. Draft language is machine-assisted and not human validated.",
                "canonical_spec": _formal_review_spec(scenario),
                "language_variants": variants,
                "annotations": "Submit one independent annotation per derivative using the P2A rubric.",
            }
            path = directory / f"{scenario.scenario_id}.json"
            path.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            written.append(path)
    return tuple(written)


def _validate_annotation_record(record: dict, expected_hashes: dict[str, str]) -> None:
    if not isinstance(record, dict):
        raise PreflightValidationError("annotation record must be a JSON object")
    forbidden = _FORBIDDEN_ANNOTATION_FIELDS & set(record)
    if forbidden:
        raise PreflightValidationError(f"prohibited annotation fields: {', '.join(sorted(forbidden))}")
    if not _ANNOTATION_REQUIRED_FIELDS <= set(record):
        raise PreflightValidationError("annotation record is missing required fields")
    example_id = record["example_id"]
    if example_id not in expected_hashes or record["example_sha256"] != expected_hashes[example_id]:
        raise PreflightValidationError("annotation references an unknown or changed example hash")
    if not isinstance(record["reviewer_id"], str) or not record["reviewer_id"].strip():
        raise PreflightValidationError("annotation reviewer ID is required")
    if record["semantic_relation"] not in _ANNOTATION_RELATIONS:
        raise PreflightValidationError("annotation semantic_relation is invalid")
    if record["linguistic_quality"] not in _LINGUISTIC_QUALITIES:
        raise PreflightValidationError("annotation linguistic_quality is invalid")
    issues = record["issue_codes"]
    if not isinstance(issues, list) or len(issues) != len(set(issues)) or not set(issues) <= _ANNOTATION_ISSUES:
        raise PreflightValidationError("annotation issue_codes are invalid")
    checklist = record["checklist"]
    if not isinstance(checklist, dict) or set(checklist) != _CHECKLIST_FIELDS or any(
        not isinstance(value, bool) for value in checklist.values()
    ):
        raise PreflightValidationError("annotation checklist must contain every required boolean check")
    if not isinstance(record["notes"], str):
        raise PreflightValidationError("annotation notes must be text")


def summarize_annotations(records: Iterable[dict], expected_hashes: dict[str, str]) -> AnnotationAudit:
    """Validate independent annotation rows and summarize completeness/agreement."""
    by_example: dict[str, dict[str, dict]] = defaultdict(dict)
    reviewer_ids: set[str] = set()
    for record in records:
        _validate_annotation_record(record, expected_hashes)
        example_id, reviewer_id = record["example_id"], record["reviewer_id"]
        if reviewer_id in by_example[example_id]:
            raise PreflightValidationError(f"duplicate annotation by reviewer {reviewer_id} for {example_id}")
        by_example[example_id][reviewer_id] = record
        reviewer_ids.add(reviewer_id)

    complete = len(reviewer_ids) == 2 and all(set(by_example.get(example_id, {})) == reviewer_ids for example_id in expected_hashes)
    agreement: float | None = None
    kappa: float | None = None
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
        linguistic_quality_agreement=linguistic_agreement,
        issue_code_exact_agreement=issue_agreement,
        checklist_item_agreement=checklist_agreement,
    )


def validate_adjudication_records(adjudications: Iterable[dict], annotations: Iterable[dict]) -> int:
    """Require a hash-bound adjudication for each disagreement between two reviews."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for annotation in annotations:
        if not isinstance(annotation, dict) or "example_id" not in annotation:
            raise PreflightValidationError("cannot group malformed annotation records")
        grouped[annotation["example_id"]].append(annotation)

    expected: set[str] = set()
    for example_id, rows in grouped.items():
        if len(rows) != 2:
            raise PreflightValidationError(f"adjudication audit requires two annotations for {example_id}")
        comparable = ("semantic_relation", "linguistic_quality", "issue_codes", "checklist")
        if any(rows[0].get(field) != rows[1].get(field) for field in comparable):
            expected.add(example_id)

    observed: dict[str, dict] = {}
    for record in adjudications:
        if not isinstance(record, dict):
            raise PreflightValidationError("adjudication record must be a JSON object")
        required = {"example_id", "example_sha256", "reviewer_ids", "adjudicator_id", "outcome", "rationale"}
        if not required <= set(record) or set(record) - (required | {"revision_sha256"}):
            raise PreflightValidationError("adjudication record has missing or unknown fields")
        example_id = record["example_id"]
        if example_id not in expected or example_id in observed:
            raise PreflightValidationError("adjudication must reference one unresolved disagreement exactly once")
        rows = grouped[example_id]
        if record["example_sha256"] != rows[0].get("example_sha256"):
            raise PreflightValidationError("adjudication example hash does not match annotations")
        if set(record["reviewer_ids"]) != {row.get("reviewer_id") for row in rows}:
            raise PreflightValidationError("adjudication reviewer IDs do not match independent annotations")
        if not record["adjudicator_id"] or not record["rationale"] or record["outcome"] not in _ADJUDICATION_OUTCOMES:
            raise PreflightValidationError("adjudication needs an adjudicator, rationale, and valid outcome")
        if record["outcome"] == "revise" and not _HEX_SHA256.fullmatch(record.get("revision_sha256", "")):
            raise PreflightValidationError("revised examples require their new content hash")
        observed[example_id] = record

    missing = expected - set(observed)
    if missing:
        raise PreflightValidationError(f"missing adjudication for disagreement(s): {', '.join(sorted(missing))}")
    return len(observed)


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
    return f"""# P2A development-only preflight report

**Status:** Deterministic preflight complete; independent bilingual validation has not been performed.

## Scope and structure

- Four local, ignored primary development prototypes; no locked scenarios or auxiliary-control study examples.
- Four canonical scenarios × two histories × four language conditions per history = {result.language_variant_count} history-language variants and {result.item_count} development-only items.
- Prototype domain-transition cells:
{cells}
- Aggregate deterministic oracle labels: {result.label_counts.get('valid', 0)} valid and {result.label_counts.get('invalid', 0)} invalid items. No per-scenario labels or reference records are included in this report.
- Structural semantic-coverage map: {result.semantic_coverage_target_count} formal targets are linked to judge-visible spans in the expected user turns. Initial requirements, grants, and decisive events include localized natural-language spans; this link check does not verify meaning.

## Deterministic validation

- P1 typed schema, counterfactual oracle, language-condition coverage, and action chronology checks passed for all four records.
- Each pair has the same structured action and oracle-established opposite labels.
- Exact duplicate groups: {result.exact_duplicate_group_count}; normalized text duplicate groups: {result.normalized_duplicate_group_count}. Semantic near-duplicates were not machine-verified.
- Recorded template IDs: {template_total} distinct with {template_reuse} repeated assignments; recipe IDs: {recipe_total} distinct with {recipe_reuse} repeated assignments. IDs are provisional, semantic/template-family overlap has not been independently audited, and development-only data cannot establish cross-partition separation.

## Feasibility assessment

The preflight demonstrates that P1's bounded schema and oracle can support the formal structures, condition coverage, chronology, and provenance checks needed for these four development prototypes. It does not establish full-study authoring throughput, human-review capacity, naturalness, or semantic equivalence; those remain owner-review and P2B/P2C questions.

## Human review status

All English and MSA conversations are Codex-authored, machine-assisted drafts marked **not independently validated**. No bilingual reviewer annotations or adjudications exist. Two independent qualified bilingual reviewers must review every variant against the formal specification without access to judge predictions; substantive corrections require re-review and a new content hash.

A local editorial check identified and corrected one MSA wording issue in the booking numerical-revision draft (refundable versus cancellable wording and the duration phrase). The prior record and hashes are retained in the ignored revision history. This correction is still unvalidated by bilingual reviewers; whether other drafts need correction remains unknown until independent review.

## Remaining surface-feature risks

Four scenarios are insufficient to establish that labels are not predictable from surface features. The permission-revocation prototype necessarily contains explicit consent withdrawal on its invalid side; numeric and temporal boundary values also determine validity by design. Explicit confirmations, negation, event direction, length, turn count, magnitude, time expressions, and critical-information position require a pre-freeze, human-coded audit across the full planned dataset. Do not force unnatural wording or claim statistical balance from this preflight.

## Data handling

Canonical records, translations, coverage maps, reference labels, review packets, annotations, and adjudications remain under ignored local `.research-data/` paths. Only this aggregate redacted report is public.
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
    parser = argparse.ArgumentParser(description="P2A local prototype and bilingual-review utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="run deterministic checks and render a redacted report")
    validate_parser.add_argument("--development-root", type=Path, default=Path(".research-data/p2a/development"))
    validate_parser.add_argument("--output", type=Path, help="optional output path for the redacted aggregate report")
    packet_parser = subparsers.add_parser("review-packets", help="export local, label-free bilingual review packets")
    packet_parser.add_argument("--development-root", type=Path, default=Path(".research-data/p2a/development"))
    packet_parser.add_argument("--output-root", type=Path, default=Path(".research-data/p2a/review-packets"))
    annotation_parser = subparsers.add_parser("audit-annotations", help="check local annotation and adjudication records")
    annotation_parser.add_argument("--development-root", type=Path, default=Path(".research-data/p2a/development"))
    annotation_parser.add_argument("--annotations", type=Path, default=Path(".research-data/p2a/annotations/annotations.jsonl"))
    annotation_parser.add_argument("--adjudications", type=Path, default=Path(".research-data/p2a/adjudications/adjudications.jsonl"))
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
    annotations = _read_jsonl(args.annotations)
    audit = summarize_annotations(annotations, expected_hashes)
    adjudications = _read_jsonl(args.adjudications)
    grouped_annotations: dict[str, list[dict]] = defaultdict(list)
    for record in annotations:
        grouped_annotations[record["example_id"]].append(record)
    complete_annotation_pairs = [
        record
        for rows in grouped_annotations.values()
        if len(rows) == 2
        for record in rows
    ]
    adjudication_count = validate_adjudication_records(adjudications, complete_annotation_pairs)
    print(json.dumps({
        "expected_examples": audit.expected_example_count,
        "annotated_examples": audit.annotated_example_count,
        "reviewer_count": audit.reviewer_count,
        "complete_two_reviewer_coverage": audit.complete,
        "missing_annotation_rows": max(0, 2 * len(expected_hashes) - len(annotations)),
        "semantic_relation_percent_agreement": audit.raw_semantic_agreement,
        "cohen_kappa": audit.cohen_kappa,
        "linguistic_quality_percent_agreement": audit.linguistic_quality_agreement,
        "issue_code_exact_percent_agreement": audit.issue_code_exact_agreement,
        "checklist_item_agreement": audit.checklist_item_agreement,
        "adjudication_count": adjudication_count,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
