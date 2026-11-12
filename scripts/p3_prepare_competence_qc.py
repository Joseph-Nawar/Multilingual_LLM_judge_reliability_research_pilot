#!/usr/bin/env python3
"""Verify the private screen and build its concise offline bilingual QC page."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multilingual_judge_pilot.judge_inference import ContractError, JudgeFacingInput
from multilingual_judge_pilot.qualification import build_input_manifest, item_sha256
from multilingual_judge_pilot.screen_review import render_review_html


EXPECTED_SOURCE_FILES = (
    "README.md",
    "screen_inference_items.json",
    "screen_reference_key.json",
    "screen_design_metadata.json",
    "screen_bilingual_qc_packet.json",
    "screen_qc_response_template.csv",
)
REQUIRED_FAMILY_NAMES = {
    "tool_contract",
    "numerical",
    "temporal",
    "permission",
    "revision_preservation",
    "combined_constraints",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path.name}")
    return value


def _matches_type(value: object, name: str) -> bool:
    checks = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: type(v) is int,
        "number": lambda v: type(v) in {int, float},
        "boolean": lambda v: type(v) is bool,
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
    }
    return checks.get(name, lambda _v: False)(value)


def _public_contract_is_well_formed(schema: object) -> bool:
    if not isinstance(schema, dict) or set(schema) != {"tool_name", "parameters"}:
        return False
    if not isinstance(schema.get("tool_name"), str) or not schema["tool_name"].strip():
        return False
    rows = schema.get("parameters")
    if not isinstance(rows, list):
        return False
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {"name", "type", "required", "enum", "minimum", "maximum"}:
            return False
        if not {"name", "type", "required"} <= set(row):
            return False
        name, type_name = row.get("name"), row.get("type")
        if not isinstance(name, str) or not name or name in names or type_name not in {"string", "integer", "number", "boolean", "object", "array"}:
            return False
        if type(row.get("required")) is not bool:
            return False
        if "enum" in row and (not isinstance(row["enum"], list) or any(not _matches_type(value, type_name) for value in row["enum"])):
            return False
        for bound in ("minimum", "maximum"):
            if bound in row and (type(row[bound]) not in {int, float} or type_name not in {"integer", "number"}):
                return False
        if "minimum" in row and "maximum" in row and row["minimum"] > row["maximum"]:
            return False
        names.add(name)
    return True


def _action_matches_public_contract(item: dict) -> bool:
    action, schema = item.get("action"), item.get("public_tool_schema")
    if not isinstance(action, dict) or not isinstance(schema, dict):
        return False
    if not _public_contract_is_well_formed(schema) or action.get("tool_name") != schema.get("tool_name"):
        return False
    parameter_rows = schema.get("parameters")
    if not isinstance(parameter_rows, list):
        return False
    parameters: dict[str, dict] = {}
    for row in parameter_rows:
        if not isinstance(row, dict) or not {"name", "type", "required"} <= set(row):
            return False
        name = row.get("name")
        if not isinstance(name, str) or not name or type(row.get("required")) is not bool or name in parameters:
            return False
        parameters[name] = row
    action_fields = set(action) - {"tool_name"}
    if action_fields - set(parameters):
        return False
    if any(row["required"] and name not in action for name, row in parameters.items()):
        return False
    for name, value in action.items():
        if name == "tool_name":
            continue
        rule = parameters[name]
        if not _matches_type(value, rule.get("type")):
            return False
        if "enum" in rule and value not in rule["enum"]:
            return False
        if type(value) in {int, float}:
            if "minimum" in rule and value < rule["minimum"]:
                return False
            if "maximum" in rule and value > rule["maximum"]:
                return False
    return True


def verify_screen_package(source_dir: Path) -> tuple[list[dict], dict, dict]:
    sums = _read_json(source_dir / "SHA256SUMS.json")
    hashes = sums.get("files")
    if not isinstance(hashes, dict) or set(hashes) != set(EXPECTED_SOURCE_FILES):
        raise ValueError("screen source manifest inventory differs from the recorded six-file package")
    for relative_path, expected in hashes.items():
        path = source_dir / relative_path
        if not path.is_file() or _sha256(path.read_bytes()) != expected:
            raise ValueError(f"screen source hash mismatch: {relative_path}")

    item_document = _read_json(source_dir / "screen_inference_items.json")
    items = item_document.get("items")
    key = _read_json(source_dir / "screen_reference_key.json").get("labels")
    families = _read_json(source_dir / "screen_design_metadata.json").get("families")
    if not isinstance(items, list) or len(items) != 48 or not isinstance(key, dict) or not isinstance(families, dict):
        raise ValueError("screen package has an incorrect item, label, or family inventory")
    ids = [item.get("item_id") for item in items if isinstance(item, dict)]
    if len(ids) != 48 or len(ids) != len(set(ids)) or set(ids) != set(key) or set(ids) != set(families):
        raise ValueError("screen IDs are missing, duplicated, or inconsistent across source files")

    languages = Counter()
    classes = Counter()
    family_counts = Counter()
    family_classes = Counter()
    action_contract_violations = Counter()
    action_contract_violation_families = Counter()
    malformed_contract_schemas = 0
    label_derivation_errors = []
    malformed_requirements = []
    for item in items:
        projection = JudgeFacingInput.from_mapping(item)
        language = projection.language_condition
        if language not in {"EN-EN", "AR-AR"}:
            raise ValueError("screen contains a non-monolingual language condition")
        languages[language] += 1
        family = families[item["item_id"]]
        if family not in REQUIRED_FAMILY_NAMES:
            raise ValueError("screen contains an unplanned content family")
        family_counts[(language, family)] += 1
        turns = {turn.turn_index for turn in projection.conversation}
        if [turn.turn_index for turn in projection.conversation] != list(range(projection.action_turn_index)):
            raise ValueError("conversation is missing a pre-action turn or has a turn at/after the action decision point")
        label = key[item["item_id"]]
        if set(label) != {"tool_contract_satisfied", "active_requirements", "expected_valid", "justification"}:
            raise ValueError("reference-key record has an unexpected schema")
        if not _public_contract_is_well_formed(item.get("public_tool_schema")):
            malformed_contract_schemas += 1
        contract_valid = _action_matches_public_contract(item)
        if label["tool_contract_satisfied"] is not contract_valid:
            action_contract_violations["reference_disagreement"] += 1
        elif not contract_valid:
            action_contract_violations["intentionally_invalid_action_and_label_agree"] += 1
            action_contract_violation_families[family] += 1
        requirements = label["active_requirements"]
        if not isinstance(requirements, list):
            malformed_requirements.append(item["item_id"])
            requirements = []
        for requirement in requirements:
            if (
                not isinstance(requirement, dict)
                or not isinstance(requirement.get("constraint_type"), str)
                or type(requirement.get("satisfied")) is not bool
                or not isinstance(requirement.get("description"), str)
                or not isinstance(requirement.get("source_turn_indices"), list)
                or not requirement["source_turn_indices"]
                or any(type(turn_index) is not int or turn_index not in turns for turn_index in requirement["source_turn_indices"])
            ):
                malformed_requirements.append(item["item_id"])
        derived = contract_valid and all(row.get("satisfied") is True for row in requirements if isinstance(row, dict))
        if type(label["expected_valid"]) is not bool or label["expected_valid"] is not derived:
            label_derivation_errors.append(item["item_id"])
        classes[(language, label["expected_valid"])] += 1
        family_classes[(language, family, label["expected_valid"])] += 1

    if languages != {"EN-EN": 24, "AR-AR": 24}:
        raise ValueError("screen must contain 24 English and 24 MSA items")
    if classes != {
        ("EN-EN", True): 12,
        ("EN-EN", False): 12,
        ("AR-AR", True): 12,
        ("AR-AR", False): 12,
    }:
        raise ValueError("screen must contain 12 valid and 12 invalid items in each language")
    expected_family_counts = {(language, family): 4 for language in ("EN-EN", "AR-AR") for family in REQUIRED_FAMILY_NAMES}
    if family_counts != expected_family_counts:
        raise ValueError("screen does not cover all six families with the fixed per-language allocation")
    if any(count != 2 for count in family_classes.values()) or len(family_classes) != 24:
        raise ValueError("each language/family cell must contain two valid and two invalid items")
    if malformed_contract_schemas or action_contract_violations.get("reference_disagreement") or label_derivation_errors or malformed_requirements:
        raise ValueError("screen action-contract/reference derivation or requirement evidence checks failed")
    if action_contract_violation_families and set(action_contract_violation_families) != {"tool_contract"}:
        raise ValueError("a tool-contract-inconsistent action falls outside the planned tool-contract content family")
    return items, key, {
        "report_version": "p3-screen-structural-validation-1",
        "screen_item_count": 48,
        "language_counts": dict(languages),
        "validity_counts": {"EN-EN": {"valid": 12, "invalid": 12}, "AR-AR": {"valid": 12, "invalid": 12}},
        "content_families": sorted(REQUIRED_FAMILY_NAMES),
        "items_per_family_per_language": 4,
        "valid_and_invalid_per_family_per_language": 2,
        "action_tool_contract_conformance_matches_reference": True,
        "public_contract_schemas_well_formed": 48 - malformed_contract_schemas,
        "contract_nonconforming_action_items": action_contract_violations.get("intentionally_invalid_action_and_label_agree", 0),
        "contract_nonconforming_item_family_counts": dict(action_contract_violation_families),
        "deterministic_label_derivation_matches": True,
        "reference_source_turns_complete": True,
        "judge_facing_items_are_allowlisted": True,
        "source_file_hashes_verified": len(EXPECTED_SOURCE_FILES),
        "semantic_and_linguistic_quality_independently_validated": False,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _sha_manifest(directory: Path, files: tuple[str, ...]) -> dict:
    return {
        "manifest_version": "p3-reviewer-delivery-manifest-1",
        "files": {name: _sha256((directory / name).read_bytes()) for name in files},
    }


def prepare(source_dir: Path, private_output_dir: Path) -> dict:
    items, key, validation = verify_screen_package(source_dir)
    inference_file_hash = _sha256((source_dir / "screen_inference_items.json").read_bytes())
    input_manifest = build_input_manifest(items, source_file_sha256=inference_file_hash)

    delivery = private_output_dir / "reviewer-delivery"
    delivery.mkdir(parents=True, exist_ok=True)
    _write_json(delivery / "qualification-input-manifest.json", input_manifest)
    (delivery / "review.html").write_text(render_review_html(items, key, input_manifest), encoding="utf-8")
    instructions = """# English/MSA competence-screen quality check

Open `review.html` directly in a current browser. It is self-contained and works offline. Review all 48 items independently, reading each conversation, action, and public tool contract.

For each item, assess naturalness, conversation interpretation, action/tool semantics, an independent valid/invalid/unclear judgment, numerical/temporal/permission consistency, ambiguity or missing information, and whether the context is clearly distinct. The independent judgments must be completed for all items before reference labels can be revealed. Then check each author reference label. A valid action conforms to the public tool contract and every effective user requirement; any violation makes it invalid. The tool contract and user authorization are separate.

Use “unclear” when the evidence does not support a definite assessment. Leave notes blank for clean examples; a short note is required when an item is flagged. Complete the private reviewer declaration. The page autosaves a local draft where the browser permits it; export JSON regularly. Use Import JSON to resume a saved draft. The export is bound to the item and manifest hashes shown in the page. Send the completed export through the separately arranged private channel.

Do not consult model-generated answers or another reviewer. This package contains no study examples. Keep the review declaration and export private.
"""
    (delivery / "reviewer-instructions.md").write_text(instructions, encoding="utf-8")
    package_files = ("review.html", "reviewer-instructions.md", "qualification-input-manifest.json")
    _write_json(delivery / "SHA256SUMS.json", _sha_manifest(delivery, package_files))
    _write_json(private_output_dir / "screen-structural-validation.json", validation)
    return {
        "screen_item_count": 48,
        "reviewer_delivery_files": list(package_files) + ["SHA256SUMS.json"],
        "reviewer_delivery_sha256": _sha256((delivery / "SHA256SUMS.json").read_bytes()),
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "structural_validation": validation,
        "output_directory": str(delivery),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path(".research-data/p3-local-method-stabilization/competence-screen"))
    parser.add_argument("--output-dir", type=Path, default=Path(".research-data/p3-local-method-stabilization/competence-screen-review"))
    args = parser.parse_args()
    result = prepare(args.source_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
