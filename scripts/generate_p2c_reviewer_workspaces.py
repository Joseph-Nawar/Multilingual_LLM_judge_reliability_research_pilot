#!/usr/bin/env python3
"""Generate standalone, slot-specific P2C reviewer workspaces from private packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multilingual_judge_pilot.p2c_review import REVIEWER_SLOTS
from multilingual_judge_pilot.preflight import ANNOTATION_SCHEMA_VERSION, blank_annotation_record
from multilingual_judge_pilot.p2c_reason_taxonomy import REASON_TAXONOMY_VERSION, reason_taxonomy_data


LANGUAGE_CONDITIONS = ("EN-EN", "AR-AR", "EN-AR", "AR-EN")
EXPECTED_SCENARIOS = 56
EXPECTED_VARIANTS = 448
WORKSPACE_VERSION = "p2c-bilingual-review-studio-8"
REVIEW_LOGIC_JS = REPO_ROOT / "scripts" / "p2c_review_logic.js"
REVIEW_APP_JS = REPO_ROOT / "scripts" / "p2c_reviewer_studio_app.js"
REQUIRED_CHECKLIST_FIELDS = set(blank_annotation_record("workspace-check", "0" * 64, "0" * 64)["checklist"])
FORBIDDEN_PACKET_KEYS = {
    "reference_verdict",
    "reference_label",
    "reference_outcome",
    "oracle_verdict",
    "oracle_result",
    "oracle_label",
    "oracle_outcome",
    "gold_label",
    "validity_label",
    "expected_label",
    "declared_label",
    "model_prediction",
    "judge_prediction",
    "judge_response",
    "judge_output",
    "effective_state",
    "canonical_effective_state",
}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SCRIPT = re.compile(r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_ATTR_ID = re.compile(r"\bid\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)
COMPATIBILITY_COPY = (
    "Q3 and Q4 are separate. Choose Yes, No, or Unclear, then select compatible reason(s) and supporting turn(s); no answer or reason is preselected. The generated rationales show your selected reasons and evidence. "
    "Version 3 checkpoints retain structured selections. Earlier draft checkpoints import only when the reviewer slot and every source hash match; imported text stays visible and is not converted to reason selections. A mismatched checkpoint is rejected without changing the file."
)
PREVIOUS_COMPATIBILITY_COPY = (
    "Q3 and Q4 are separate. Choose Yes, No, or Unclear, then select compatible reason(s) and supporting turn(s); no answer or reason is preselected. The generated rationales show your selected reasons and evidence. "
    "Version 2 checkpoints retain structured selections. Earlier draft checkpoints import only when the reviewer slot and every source hash match; imported text stays visible and is not converted to reason selections. A mismatched checkpoint is rejected without changing the file."
)
STRUCTURED_REVIEW_CSS = """
/* Structured annotation controls */
.reason-fieldset{border:0;border-top:1px solid #e6ebe6;padding:12px 0 0;margin:12px 0 0;min-width:0}
.reason-fieldset legend{font-size:12px;font-weight:760;color:#52625d;padding:0 4px 0 0}
.structured-choices,.reason-options{display:grid;gap:6px;margin-top:8px}
.requirement-field-choices{max-height:220px;overflow:auto}
.structured-choice,.turn-choice{display:flex;align-items:flex-start;gap:9px;padding:7px 8px;border:1px solid #e2e8e2;border-radius:6px;background:#fff;font-size:12px;line-height:1.5;cursor:pointer}
.structured-choice input,.turn-choice input{margin:2px 0 0;accent-color:var(--accent);flex:0 0 auto}
.structured-choice:has(input:checked),.turn-choice:has(input:checked){border-color:var(--accent);background:#f1f7f1}
.reason-incompatible{border-color:#dcb6a2;background:#fff8f3;color:#8f421d}
.turn-choices{display:grid;gap:5px;max-height:190px;overflow:auto;margin-top:8px}
.turn-choice span{min-width:0;overflow-wrap:anywhere}.turn-choice b{white-space:nowrap}
.field-label{display:grid;gap:5px;margin-top:10px;font-size:12px;font-weight:700;color:#44554d}
.field-label input,.field-label select{min-width:0;width:100%;padding:9px 10px;border:1px solid #d9e3db;border-radius:6px;background:#fff;font-size:12px;color:var(--ink)}
.generated-rationale{margin-top:10px;padding:9px 11px;border-left:3px solid var(--accent);background:#f4f8f2;font-size:12px;line-height:1.55;overflow-wrap:anywhere}
.generated-rationale p{margin:4px 0 0}.legacy-evidence{margin-top:9px;padding:8px 10px;border:1px solid #ead7b7;border-radius:6px;background:#fffaf0;font-size:12px;overflow-wrap:anywhere}
.legacy-evidence summary{cursor:pointer;font-weight:700}.legacy-evidence p{margin:8px 0 0}
.issue-trigger{padding:11px 0;border-top:1px solid #edf0ec}.issue-trigger h4{font-size:12px;margin:0 0 8px}.issue-report{padding:10px;border:1px solid #dfe7df;border-radius:7px;background:#fafcf9;margin:8px 0}
.issue-report-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:12px}.evidence-pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.clean-note{padding:8px;background:#f5f8f4;border-radius:6px}
"""


class WorkspaceBuildError(ValueError):
    """The owner UI shell or current private reviewer package is invalid."""


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkspaceBuildError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str):
    raise WorkspaceBuildError(f"unsupported JSON constant: {value}")


def _loads_json(raw: str | bytes, description: str):
    try:
        return json.loads(raw, object_pairs_hook=_unique_json_object, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, WorkspaceBuildError) as exc:
        raise WorkspaceBuildError(f"{description} is not valid strict JSON") from exc


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _script_json(value: object) -> str:
    """Escape HTML-sensitive characters so packet text cannot close a script tag."""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _walk_keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _validate_packet_and_template(
    reviewer_slot: str,
    packets: Sequence[Mapping[str, object]],
    template_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, str]]:
    if reviewer_slot not in REVIEWER_SLOTS:
        raise WorkspaceBuildError("unknown reviewer slot")
    if len(packets) != EXPECTED_SCENARIOS:
        raise WorkspaceBuildError(f"expected {EXPECTED_SCENARIOS} scenario packets")
    if len(template_rows) != EXPECTED_VARIANTS:
        raise WorkspaceBuildError(f"expected {EXPECTED_VARIANTS} blank template rows")

    packet_by_scenario: dict[str, dict] = {}
    bindings: dict[str, dict] = {}
    for raw in packets:
        if not isinstance(raw, Mapping):
            raise WorkspaceBuildError("scenario packet must be a JSON object")
        packet = dict(raw)
        scenario_id = packet.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip() or scenario_id in packet_by_scenario:
            raise WorkspaceBuildError("scenario packet IDs must be unique non-empty strings")
        if packet.get("reviewer_slot") != reviewer_slot:
            raise WorkspaceBuildError("scenario packet reviewer slot does not match the assigned workspace")
        if packet.get("annotation_schema_version") != ANNOTATION_SCHEMA_VERSION:
            raise WorkspaceBuildError("scenario packet annotation schema is unsupported")
        if not isinstance(packet.get("packet_version"), str) or not packet["packet_version"]:
            raise WorkspaceBuildError("scenario packet version is missing")
        if not _valid_hash(packet.get("canonical_scenario_sha256")):
            raise WorkspaceBuildError("scenario packet canonical hash is invalid")
        spec = packet.get("canonical_spec")
        variants = packet.get("language_variants")
        if not isinstance(spec, dict) or spec.get("scenario_id") != scenario_id:
            raise WorkspaceBuildError("scenario packet formal specification is missing or mismatched")
        if not isinstance(variants, list) or len(variants) != 8:
            raise WorkspaceBuildError("every scenario packet must contain eight variants")
        if FORBIDDEN_PACKET_KEYS.intersection(_walk_keys(packet)):
            raise WorkspaceBuildError("review packet contains a prohibited reference-only field")
        if not isinstance(spec.get("histories"), list) or len(spec["histories"]) != 2:
            raise WorkspaceBuildError("every scenario packet must contain two canonical histories")

        seen: set[tuple[str, str]] = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise WorkspaceBuildError("packet variant must be a JSON object")
            history_id, condition, derivative_id = (
                variant.get("history_id"),
                variant.get("condition"),
                variant.get("derivative_id"),
            )
            if history_id not in {h.get("history_id") for h in spec["histories"]}:
                raise WorkspaceBuildError("packet variant refers to an unknown history")
            if condition not in LANGUAGE_CONDITIONS or (history_id, condition) in seen:
                raise WorkspaceBuildError("packet variant language-condition mapping is duplicate or invalid")
            if not isinstance(derivative_id, str) or not derivative_id.strip() or derivative_id in bindings:
                raise WorkspaceBuildError("packet derivative IDs must be unique non-empty strings")
            if not _valid_hash(variant.get("example_sha256")):
                raise WorkspaceBuildError("packet variant hash is invalid")
            turns = variant.get("turns")
            if not isinstance(turns, list) or not turns:
                raise WorkspaceBuildError("packet variant has no conversation turns")
            turn_indices = []
            for turn in turns:
                if (
                    not isinstance(turn, dict)
                    or type(turn.get("turn_index")) is not int
                    or turn["turn_index"] < 0
                    or turn.get("speaker") not in {"user", "assistant", "tool"}
                    or turn.get("language") not in {"en", "ar", "ar-MSA"}
                    or not isinstance(turn.get("segments"), list)
                    or any(not isinstance(segment, dict) or not isinstance(segment.get("text"), str) for segment in turn["segments"])
                ):
                    raise WorkspaceBuildError("packet conversation turn is malformed")
                turn_indices.append(turn["turn_index"])
            if turn_indices != sorted(set(turn_indices)):
                raise WorkspaceBuildError("packet conversation chronology is not strictly increasing")
            if variant.get("canonical_scenario_sha256", packet["canonical_scenario_sha256"]) != packet["canonical_scenario_sha256"]:
                raise WorkspaceBuildError("packet variant canonical hash differs from its scenario")
            seen.add((history_id, condition))
            bindings[derivative_id] = {
                "scenario_id": scenario_id,
                "history_id": history_id,
                "condition": condition,
                "example_sha256": variant["example_sha256"],
                "canonical_scenario_sha256": packet["canonical_scenario_sha256"],
            }
        if len(seen) != 8 or {h for h, _ in seen} != {h["history_id"] for h in spec["histories"]}:
            raise WorkspaceBuildError("packet must represent two histories in all four language conditions")
        packet_by_scenario[scenario_id] = packet

    template_by_id: dict[str, dict] = {}
    required_template_fields = {
        "annotation_schema_version",
        "canonical_scenario_sha256",
        "checklist",
        "decisive_update_dependence",
        "decisive_update_dependence_rationale",
        "example_id",
        "example_sha256",
        "issue_codes",
        "linguistic_quality",
        "notes",
        "reviewer_id",
        "semantic_relation",
        "whole_action_dependence",
        "whole_action_dependence_rationale",
    }
    for raw in template_rows:
        if not isinstance(raw, Mapping):
            raise WorkspaceBuildError("annotation template row must be an object")
        row = dict(raw)
        item_id = row.get("example_id")
        if not isinstance(item_id, str) or item_id in template_by_id:
            raise WorkspaceBuildError("annotation template IDs must be unique non-empty strings")
        if set(row) != required_template_fields or row.get("annotation_schema_version") != ANNOTATION_SCHEMA_VERSION:
            raise WorkspaceBuildError("annotation template schema differs from p2b1-annotation-2")
        if row.get("reviewer_id") != "" or any(row.get(field) != "" for field in (
            "semantic_relation",
            "linguistic_quality",
            "decisive_update_dependence",
            "decisive_update_dependence_rationale",
            "whole_action_dependence",
            "whole_action_dependence_rationale",
            "notes",
        )) or row.get("issue_codes") != [] or not isinstance(row.get("checklist"), dict) or set(row["checklist"]) != REQUIRED_CHECKLIST_FIELDS or any(v is not None for v in row["checklist"].values()):
            raise WorkspaceBuildError("reviewer template must remain completely blank")
        template_by_id[item_id] = row

    if set(template_by_id) != set(bindings):
        raise WorkspaceBuildError("template IDs do not match packet derivative IDs")
    for item_id, binding in bindings.items():
        row = template_by_id[item_id]
        if (
            row.get("example_sha256") != binding["example_sha256"]
            or row.get("canonical_scenario_sha256") != binding["canonical_scenario_sha256"]
        ):
            raise WorkspaceBuildError("template variant or canonical hash does not match the packet")
    if len(bindings) != EXPECTED_VARIANTS:
        raise WorkspaceBuildError("review workspace must contain exactly 448 unique variants")
    return packet_by_scenario, template_by_id, bindings


def _value_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceBuildError("canonical source text fields must be non-empty strings")
    return value


def _source_scenarios(packets: Mapping[str, Mapping[str, object]]) -> list[dict]:
    scenarios = []
    for scenario_id in sorted(packets):
        packet = packets[scenario_id]
        spec = packet["canonical_spec"]
        action = spec.get("action")
        contract = spec.get("action_contract")
        schema = spec.get("public_tool_schema")
        if not isinstance(action, dict) or not isinstance(contract, dict) or not isinstance(schema, dict):
            raise WorkspaceBuildError("formal action or public tool contract is incomplete")
        parameters: dict[str, object] = {}
        for field in action.get("fields", []):
            if not isinstance(field, dict) or not isinstance(field.get("name"), str) or field["name"] in parameters:
                raise WorkspaceBuildError("canonical action fields are malformed or duplicated")
            parameters[field["name"]] = field.get("value")
        public_parameters = schema.get("parameters")
        if not isinstance(public_parameters, list):
            raise WorkspaceBuildError("public tool parameter list is missing")
        tool_parameters = []
        for row in public_parameters:
            if not isinstance(row, dict) or type(row.get("required")) is not bool:
                raise WorkspaceBuildError("public tool parameter requirements are malformed")
            tool_parameters.append({
                "name": _value_text(row.get("name")),
                "type": _value_text(row.get("value_type")),
                "required": row["required"],
            })
        required_permission_details = contract.get("required_permissions", [])
        if not isinstance(required_permission_details, list):
            raise WorkspaceBuildError("public permission requirements are malformed")
        tool = {
            "tool_name": _value_text(schema.get("tool_name")),
            "tool_description": _value_text(schema.get("description")),
            "parameters": tool_parameters,
            "irreversible": contract.get("irreversible"),
            "required_permissions": [row.get("permission", "") for row in required_permission_details if isinstance(row, dict)],
            "required_permission_details": required_permission_details,
            "public_tool_schema": schema,
            "action_contract": contract,
            "action": {
                "entity_id": action.get("entity_id"),
                "executed_at": action.get("executed_at"),
                "parameters": parameters,
            },
        }
        histories = []
        history_ids = []
        for history in spec["histories"]:
            history_id = history["history_id"]
            history_ids.append(history_id)
            histories.append({
                "history_id": history_id,
                "initial_state": history.get("initial_state", {}),
                "events_in_order": history.get("events", []),
                "action_turn_index": history.get("action_turn_index"),
                "decisive_turn_index": history.get("decisive_turn_index"),
            })
        variants_by_history = {history_id: {} for history_id in history_ids}
        for variant in packet["language_variants"]:
            turns = []
            for turn in variant["turns"]:
                turns.append({
                    "index": turn["turn_index"],
                    "role": turn["speaker"],
                    "lang": turn["language"],
                    "text": "".join(segment["text"] for segment in turn["segments"]),
                })
            variants_by_history[variant["history_id"]][variant["condition"]] = turns
        scenarios.append({
            "id": scenario_id,
            "kind": spec.get("dataset_kind", "primary"),
            "domain": _value_text(spec.get("domain")),
            "family": _value_text(spec.get("transition_family")),
            "tool": tool,
            "formal": {"shared_context": spec.get("shared_context", []), "histories": histories},
            "histories": [
                {"id": history_id, "variants": variants_by_history[history_id]}
                for history_id in history_ids
            ],
        })
    return scenarios


def source_fingerprint(
    source_html: str,
    reviewer_slot: str,
    packets: Sequence[Mapping[str, object]],
    template_rows: Sequence[Mapping[str, object]],
    *,
    package_manifest_sha256: str,
    packet_sha256: Mapping[str, str] | None = None,
    template_sha256: str | None = None,
) -> str:
    """Bind saved work to the exact UI shell, package, slot, packets, and template."""
    packet_map, _template, _bindings = _validate_packet_and_template(reviewer_slot, packets, template_rows)
    if not _valid_hash(package_manifest_sha256):
        raise WorkspaceBuildError("private package manifest hash must be a lowercase SHA-256 digest")
    if packet_sha256 is not None and (set(packet_sha256) != set(packet_map) or any(not _valid_hash(x) for x in packet_sha256.values())):
        raise WorkspaceBuildError("packet file hash inventory is malformed")
    if template_sha256 is not None and not _valid_hash(template_sha256):
        raise WorkspaceBuildError("template file hash is malformed")
    body = {
        "workspace_version": WORKSPACE_VERSION,
        "reason_taxonomy_version": REASON_TAXONOMY_VERSION,
        "reviewer_slot": reviewer_slot,
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "package_manifest_sha256": package_manifest_sha256,
        "studio_html_sha256": _sha256(_fingerprint_shell_html(source_html).encode("utf-8")),
        "packet_file_sha256": dict(sorted(packet_sha256.items())) if packet_sha256 is not None else {
            scenario_id: _sha256(_canonical_json(packet).encode("utf-8"))
            for scenario_id, packet in sorted(packet_map.items())
        },
        "template_file_sha256": template_sha256 or _sha256(_canonical_json(list(template_rows)).encode("utf-8")),
    }
    return _sha256(_canonical_json(body).encode("utf-8"))


def _fingerprint_shell_html(html: str) -> str:
    """Hash stable presentation markup plus the explicit workspace version.

    Generated packet payloads and generated JavaScript are replaced before
    hashing. The workspace version covers application behavior, so regenerating
    from the current standalone page keeps the fingerprint stable while a new
    version still invalidates incompatible workspaces.
    """
    html = _canonical_shell_markup(html)
    output = []
    position = 0
    app_count = 0
    for match in _SCRIPT.finditer(html):
        output.append(html[position:match.start()])
        id_match = _ATTR_ID.search(match.group("attrs"))
        script_id = id_match.group(2) if id_match else ""
        body = match.group("body")
        if script_id == "embedded-review-data" or script_id == "p2c-review-logic":
            output.append("")
        elif script_id == "embedded-scenarios":
            output.append(match.group(0)[:match.start("body") - match.start()] + "[]" + match.group(0)[match.end("body") - match.start():])
        elif script_id == "p2c-review-app" or "const SOURCE = JSON.parse(document.getElementById('embedded-scenarios').textContent);" in body:
            app_count += 1
            output.append("<!-- versioned review application -->")
        else:
            output.append(match.group(0))
        position = match.end()
    output.append(html[position:])
    if app_count != 1:
        raise WorkspaceBuildError("reviewer HTML must contain exactly one review application script")
    return re.sub(r"\n{2,}", "\n", "".join(output))


def _canonical_shell_markup(html: str) -> str:
    """Remove generator-owned copy and style changes before hashing the shell."""
    html = re.sub(
        r"\s*/\* Structured annotation controls \*/.*?\.clean-note\{[^}]*\}\s*",
        "",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = re.sub(r"Reviewer slot [12] · English \+ Modern Standard Arabic", "Reviewer slot N · English + Modern Standard Arabic", html)
    html = re.sub(r"(<title>Bilingual review workspace · Reviewer )[12](</title>)", r"\1N\2", html)
    html = _replace_setup_panel_with_fingerprint_marker(html)
    for copy in (
        "When all 448 are complete, attach the original template and the 56 reviewer packet JSON files. You can review first and attach them later.",
        "When all 448 are complete, attach the original template and packet folder to export a verified JSONL file for the researcher.",
        "When all 448 variants are complete, export the verified JSONL directly from this page. The export contains only your answers.",
        "Save a checkpoint JSON periodically. When all 448 are complete, export the verified JSONL file directly from this page. The export contains only your own answers.",
        "Save a checkpoint JSON periodically. When all 448 variants are complete, export the verified JSONL file directly from this page. The export contains only your own answers.",
    ):
        html = html.replace(copy, "__P2C_EXPORT_GUIDANCE__")
    for copy in (
        "You can mark all eight as passing after inspection, or flag individual problems.",
        "Answer each of the eight checklist items separately for every variant, or flag individual problems. Add notes when anything is wrong or uncertain.",
        "Answer all eight checklist items independently. Clean variants need no notes; flagged problems require structured evidence.",
        "Answer all eight checklist items separately for every variant. Clean variants need no notes; flagged problems require specific structured evidence and the page generates the notes field.",
    ):
        html = html.replace(copy, "__P2C_CHECKLIST_GUIDANCE__")
    html = html.replace(
        "Each must receive its own assessment. Answers, reasons, and rationales are never copied to another variant.",
        "__P2C_INDEPENDENCE_GUIDANCE__",
    ).replace(
        "Each must receive its own assessment. Answers and rationales are never copied to another variant.",
        "__P2C_INDEPENDENCE_GUIDANCE__",
    )
    html = html.replace("Be independent. " + COMPATIBILITY_COPY, "Be independent.")
    html = html.replace("Be independent. " + PREVIOUS_COMPATIBILITY_COPY, "Be independent.")
    return html.replace(COMPATIBILITY_COPY, "").replace(PREVIOUS_COMPATIBILITY_COPY, "")


def _replace_setup_panel_with_fingerprint_marker(html: str) -> str:
    """Normalize the setup panel whose copy and controls the generator replaces."""
    start_pattern = re.compile(
        r"<div\b(?=[^>]*\bclass\s*=\s*(['\"])[^'\"]*\bsetup-panel\b[^'\"]*\1)[^>]*>",
        re.IGNORECASE,
    )
    match = start_pattern.search(html)
    if match is None:
        return html
    depth = 0
    for token in re.finditer(r"</?div\b[^>]*>", html[match.start():], re.IGNORECASE):
        is_close = token.group(0).lstrip().startswith("</")
        depth += -1 if is_close else 1
        if depth == 0:
            end = match.start() + token.end()
            return html[:match.start()] + '<div class="setup-panel">__P2C_SETUP_PANEL__</div>' + html[end:]
    raise WorkspaceBuildError("reviewer setup panel markup is unbalanced")


def legacy_source_fingerprints_from_workspace(
    previous_html: str,
    reviewer_slot: str,
    current_bindings: Mapping[str, Mapping[str, object]],
) -> tuple[str, ...]:
    """Allow prior checkpoints only when the prior page has identical bindings."""
    matches = []
    for script in _SCRIPT.finditer(previous_html):
        id_match = _ATTR_ID.search(script.group("attrs"))
        if id_match and id_match.group(2) == "embedded-review-data":
            matches.append(script)
    if len(matches) != 1:
        return ()
    try:
        data = _loads_json(matches[0].group("body"), "previous embedded review package")
    except WorkspaceBuildError:
        return ()
    if (
        data.get("reviewer_slot") != reviewer_slot
        or data.get("format") not in {"p2c-embedded-review-package-1", "p2c-embedded-review-package-2"}
        or data.get("bindings") != dict(current_bindings)
    ):
        return ()
    candidates = [data.get("source_fingerprint"), *(data.get("legacy_source_fingerprints", []))]
    return tuple(dict.fromkeys(value for value in candidates if _valid_hash(value)))


def _replace_script(html: str, script_id: str, body: str, *, append_scripts: Sequence[tuple[str, str]] = ()) -> str:
    matches = []
    for match in _SCRIPT.finditer(html):
        attrs = match.group("attrs")
        id_match = _ATTR_ID.search(attrs)
        if id_match and id_match.group(2) == script_id:
            matches.append(match)
    if len(matches) != 1:
        raise WorkspaceBuildError(f"owner HTML must contain exactly one script with id {script_id}")
    match = matches[0]
    suffix = "".join(f'<script type="application/json" id="{name}">{payload}</script>' for name, payload in append_scripts)
    return html[:match.start("body")] + body + html[match.end("body"):match.end()] + suffix + html[match.end():]


def _rewrite_app_script(html: str) -> str:
    """Replace the shell application with the versioned offline review UI."""
    for match in reversed(list(_SCRIPT.finditer(html))):
        id_match = _ATTR_ID.search(match.group("attrs"))
        if id_match and id_match.group(2) == "p2c-review-logic":
            end = match.end()
            if html[end:end + 2] == "\r\n":
                end += 2
            elif html[end:end + 1] == "\n":
                end += 1
            html = html[:match.start()] + html[end:]

    matches = [
        match for match in _SCRIPT.finditer(html)
        if (id_match := _ATTR_ID.search(match.group("attrs")))
        and id_match.group(2) == "p2c-review-app"
        or "const SOURCE = JSON.parse(document.getElementById('embedded-scenarios').textContent);" in match.group("body")
    ]
    if len(matches) != 1:
        raise WorkspaceBuildError("owner HTML must contain exactly one replaceable reviewer application script")
    match = matches[0]
    try:
        logic = REVIEW_LOGIC_JS.read_text(encoding="utf-8")
        app = REVIEW_APP_JS.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkspaceBuildError("versioned reviewer JavaScript source is missing") from exc
    if "window.createP2CReviewLogic" not in logic or "p2c-review-draft-3" not in logic:
        raise WorkspaceBuildError("review logic source does not expose the expected checkpoint contract")
    if "const REVIEW_DATA = JSON.parse" not in app or "logic.restoreCheckpoint" not in app:
        raise WorkspaceBuildError("review app must bind the embedded package and delegate checkpoint validation")

    replacement = f'<script id="p2c-review-app">\n{app}\n</script>'
    html = html[:match.start()] + replacement + html[match.end():]
    app_start = html.index('<script id="p2c-review-app">')
    logic_script = f'<script id="p2c-review-logic">\n{logic}\n</script>\n'
    return html[:app_start] + logic_script + html[app_start:]

def _rewrite_static_markup(html: str, reviewer_slot: str) -> str:
    """Update visible instructions and add compact styling for structured evidence."""
    reviewer_number = reviewer_slot.rsplit("_", 1)[-1]
    html, title_count = re.subn(
        r"<title>Bilingual review workspace · Reviewer [12]</title>",
        f"<title>Bilingual review workspace · Reviewer {reviewer_number}</title>",
        html,
        count=1,
    )
    if title_count != 1:
        raise WorkspaceBuildError("owner HTML title is not recognized")
    html = re.sub(
        r"Reviewer slot [12] · English \+ Modern Standard Arabic",
        f"Reviewer slot {reviewer_number} · English + Modern Standard Arabic",
        html,
        count=1,
    )

    old_panel = re.compile(
        r'<p>For a final, ingestion-compatible JSONL export, attach your original 448-row annotation template and the 56 reviewer packet JSON files\. You can review first and attach them later\.</p>\s*'
        r'<label>1 · Select <code>annotation-template\.jsonl</code><input type="file" accept="\.jsonl" id="template-file"\s*/?></label>\s*'
        r'<label>2 · Select reviewer packet folder \(56 JSON files\)<input type="file" accept="\.json" id="packet-folder" webkitdirectory multiple\s*/?></label>\s*'
        r'<div class="setup-state" id="binding-state">Not linked to source hashes</div>',
        re.DOTALL,
    )
    html, old_count = old_panel.subn(
        '<p>Your assigned 56 source packets and blank 448-row annotation template are embedded in this page. No additional files are needed. Save a checkpoint JSON to continue in a later session.</p>\n'
        '<div class="setup-state" id="binding-state">Checking embedded source package…</div>',
        html,
        count=1,
    )
    if old_count == 0 and 'id="binding-state"' not in html:
        raise WorkspaceBuildError("owner HTML is missing its source-package status panel")
    html = html.replace("<h3>Export setup</h3>", "<h3>Source package and export</h3>", 1)
    html = html.replace(
        "When all 448 are complete, attach the original template and packet folder to export a verified JSONL file for the researcher.",
        "When all 448 variants are complete, export the verified JSONL directly from this page. The export contains only your answers.",
        1,
    )
    html = html.replace(
        "Save a checkpoint JSON periodically. When all 448 are complete, export the verified JSONL file directly from this page. The export contains only your own answers.",
        "Save a checkpoint JSON periodically. When all 448 variants are complete, export the verified JSONL file directly from this page. The export contains only your own answers.",
        1,
    )
    html = html.replace(
        "You can mark all eight as passing after inspection, or flag individual problems.",
        "Answer all eight checklist items independently. Clean variants need no notes; flagged problems require structured evidence.",
        1,
    )
    html = html.replace(
        "Answer each of the eight checklist items separately for every variant, or flag individual problems. Add notes when anything is wrong or uncertain.",
        "Answer all eight checklist items separately for every variant. Clean variants need no notes; flagged problems require specific structured evidence and the page generates the notes field.",
        1,
    )
    html = html.replace(
        "Each must receive its own assessment. Answers and rationales are never copied to another variant.",
        "Each must receive its own assessment. Answers, reasons, and rationales are never copied to another variant.",
        1,
    )
    marker = "Be independent."
    html = html.replace(PREVIOUS_COMPATIBILITY_COPY, COMPATIBILITY_COPY)
    if marker in html and COMPATIBILITY_COPY not in html:
        html = html.replace(marker, marker + " " + COMPATIBILITY_COPY, 1)

    if "/* Structured annotation controls */" not in html:
        if "</style>" in html:
            html = html.replace("</style>", STRUCTURED_REVIEW_CSS + "</style>", 1)
        else:
            html = html.replace("</head>", f"<style>{STRUCTURED_REVIEW_CSS}</style></head>", 1)
    return html

def _clear_embedded_package_data(html: str) -> str:
    """Remove prior private payloads before binding the current reviewer package."""
    scenarios = []
    for match in _SCRIPT.finditer(html):
        id_match = _ATTR_ID.search(match.group("attrs"))
        if id_match and id_match.group(2) == "embedded-scenarios":
            scenarios.append(match)
    if len(scenarios) != 1:
        raise WorkspaceBuildError("owner HTML must contain exactly one embedded scenario data script")

    for match in reversed(list(_SCRIPT.finditer(html))):
        id_match = _ATTR_ID.search(match.group("attrs"))
        if not id_match:
            continue
        script_id = id_match.group(2)
        if script_id == "embedded-review-data":
            html = html[:match.start()] + html[match.end():]
        elif script_id == "embedded-scenarios":
            html = html[:match.start("body")] + "[]" + html[match.end("body"):]
    return html


def build_workspace_html(
    source_html: str,
    reviewer_slot: str,
    packets: Sequence[Mapping[str, object]],
    template_rows: Sequence[Mapping[str, object]],
    *,
    package_manifest_sha256: str,
    packet_sha256: Mapping[str, str] | None = None,
    template_sha256: str | None = None,
    legacy_source_fingerprints: Sequence[str] = (),
) -> str:
    """Build one self-contained, independently assigned HTML review page."""
    packet_map, template_map, bindings = _validate_packet_and_template(reviewer_slot, packets, template_rows)
    network_apis = r"(?:fetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon\s*\(|importScripts\s*\()"
    if re.search(network_apis, source_html, re.IGNORECASE):
        raise WorkspaceBuildError("reviewer HTML shell must not contain network communication")
    remote_assets = r"(?:<(?:script|link|img|iframe|source)\b[^>]*\b(?:src|href)\s*=\s*['\"]\s*https?://|@import\s+(?:url\()?\s*['\"]?https?://|url\(\s*['\"]?https?://)"
    if re.search(remote_assets, source_html, re.IGNORECASE):
        raise WorkspaceBuildError("reviewer HTML shell must not depend on remote scripts or assets")

    source_html = _clear_embedded_package_data(source_html)
    fingerprint = source_fingerprint(
        source_html,
        reviewer_slot,
        packets,
        template_rows,
        package_manifest_sha256=package_manifest_sha256,
        packet_sha256=packet_sha256,
        template_sha256=template_sha256,
    )
    if any(not _valid_hash(value) for value in legacy_source_fingerprints) or len(set(legacy_source_fingerprints)) != len(legacy_source_fingerprints):
        raise WorkspaceBuildError("legacy checkpoint fingerprints must be unique SHA-256 digests")
    compatible_legacy_fingerprints = [value for value in legacy_source_fingerprints if value != fingerprint]

    scenarios = _source_scenarios(packet_map)
    review_data = {
        "format": "p2c-embedded-review-package-2",
        "workspace_version": WORKSPACE_VERSION,
        "reviewer_slot": reviewer_slot,
        "source_fingerprint": fingerprint,
        "package_manifest_sha256": package_manifest_sha256,
        "reason_taxonomy": reason_taxonomy_data(),
        "legacy_source_fingerprints": compatible_legacy_fingerprints,
        "bindings": {key: bindings[key] for key in sorted(bindings)},
        "template": [template_map[key] for key in sorted(template_map)],
        "packets": [packet_map[key] for key in sorted(packet_map)],
    }
    script_matches = [m for m in _SCRIPT.finditer(source_html) if (match := _ATTR_ID.search(m.group("attrs"))) and match.group(2) == "embedded-scenarios"]
    if len(script_matches) != 1:
        raise WorkspaceBuildError("owner HTML must contain exactly one embedded scenario data script")
    source_match = script_matches[0]
    source_html = source_html[:source_match.start("body")] + _script_json(scenarios) + source_html[source_match.end("body"):]
    # Re-scan after replacing the source script and insert the fully assigned package immediately after it.
    script_matches = [m for m in _SCRIPT.finditer(source_html) if (match := _ATTR_ID.search(m.group("attrs"))) and match.group(2) == "embedded-scenarios"]
    source_match = script_matches[0]
    source_html = source_html[:source_match.end()] + f'<script type="application/json" id="embedded-review-data">{_script_json(review_data)}</script>' + source_html[source_match.end():]

    source_html = _rewrite_app_script(source_html)
    source_html = _rewrite_static_markup(source_html, reviewer_slot)
    if source_html.count('id="embedded-review-data"') != 1 or source_html.count('"source_fingerprint"') != 1:
        raise WorkspaceBuildError("generated workspace did not embed one hash-bound review package")
    if "<script src=" in source_html or "fetch(" in source_html or "XMLHttpRequest" in source_html:
        raise WorkspaceBuildError("generated workspace is not offline")
    return source_html


def _read_json_file(path: Path, description: str) -> dict:
    try:
        value = _loads_json(path.read_bytes(), description)
    except OSError as exc:
        raise WorkspaceBuildError(f"{description} is unavailable") from exc
    if not isinstance(value, dict):
        raise WorkspaceBuildError(f"{description} must be a JSON object")
    return value


def _read_jsonl_file(path: Path, description: str) -> list[dict]:
    try:
        lines = path.read_bytes().decode("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise WorkspaceBuildError(f"{description} is unavailable or not UTF-8") from exc
    if not lines or any(not line.strip() for line in lines):
        raise WorkspaceBuildError(f"{description} is empty or contains a blank line")
    rows = [_loads_json(line, f"{description} line {index}") for index, line in enumerate(lines, 1)]
    if any(not isinstance(row, dict) for row in rows):
        raise WorkspaceBuildError(f"{description} rows must be JSON objects")
    return rows


def _atomic_private_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def generate_workspaces(studio_html_path: Path, package_root: Path) -> dict[str, dict[str, object]]:
    """Validate the private package and write one current standalone page per slot."""
    package_root = _private_path(Path(package_root))
    review_root = package_root / "review-package"
    manifest_path = package_root / "manifest.json"
    manifest_sidecar = package_root / "manifest.json.sha256"
    manifest_raw = manifest_path.read_bytes()
    manifest_sha = _sha256(manifest_raw)
    sidecar_text = manifest_sidecar.read_text(encoding="ascii").strip().split()
    if not sidecar_text or sidecar_text[0] != manifest_sha:
        raise WorkspaceBuildError("private package manifest checksum sidecar does not match")
    manifest = _loads_json(manifest_raw, "private package manifest")
    package_sha = manifest.get("package_sha256") if isinstance(manifest, dict) else None
    if not _valid_hash(package_sha):
        raise WorkspaceBuildError("private package manifest lacks a valid package SHA-256")
    file_records = manifest.get("files")
    if not isinstance(file_records, list):
        raise WorkspaceBuildError("private package manifest lacks its file hash inventory")
    manifest_files: dict[str, dict] = {}
    for record in file_records:
        if not isinstance(record, dict):
            raise WorkspaceBuildError("private package manifest file entry is malformed")
        relative = record.get("path")
        if not isinstance(relative, str) or not relative or relative in manifest_files:
            raise WorkspaceBuildError("private package manifest file paths must be unique")
        if not _valid_hash(record.get("sha256")) or type(record.get("bytes")) is not int or record["bytes"] < 0:
            raise WorkspaceBuildError("private package manifest file hash/size entry is malformed")
        manifest_files[relative] = record

    def verify_manifest_file(path: Path, raw: bytes) -> None:
        try:
            relative = path.resolve().relative_to(package_root).as_posix()
        except ValueError as exc:
            raise WorkspaceBuildError("private source symlink resolves outside the package root") from exc
        record = manifest_files.get(relative)
        if not record or record["sha256"] != _sha256(raw) or record["bytes"] != len(raw):
            raise WorkspaceBuildError(f"current private source differs from its package manifest: {relative}")

    source_html = Path(studio_html_path).read_text(encoding="utf-8")
    results = {}
    for slot in REVIEWER_SLOTS:
        packet_dir = review_root / "packets" / slot
        packet_files = sorted(p for p in packet_dir.glob("*.json") if p.is_file() and not p.name.startswith("."))
        if len(packet_files) != EXPECTED_SCENARIOS:
            raise WorkspaceBuildError(f"{slot} must have exactly 56 existing reviewer packet JSON files")
        packets = []
        packet_hashes = {}
        for path in packet_files:
            raw = path.read_bytes()
            verify_manifest_file(path, raw)
            packet = _loads_json(raw, f"{slot} scenario packet")
            if packet.get("scenario_id") != path.stem:
                raise WorkspaceBuildError("scenario packet filename does not match its scenario ID")
            packets.append(packet)
            packet_hashes[path.stem] = _sha256(raw)
        template_path = review_root / slot / "annotation-template.jsonl"
        template_raw = template_path.read_bytes()
        verify_manifest_file(template_path, template_raw)
        template_rows = _read_jsonl_file(template_path, f"{slot} annotation template")
        _packet_map, _template_map, current_bindings = _validate_packet_and_template(slot, packets, template_rows)
        output_path = review_root / slot / "bilingual-review-studio.html"
        prior_html = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        legacy_fingerprints = legacy_source_fingerprints_from_workspace(prior_html, slot, current_bindings)
        html = build_workspace_html(
            source_html,
            slot,
            packets,
            template_rows,
            package_manifest_sha256=package_sha,
            packet_sha256=packet_hashes,
            template_sha256=_sha256(template_raw),
            legacy_source_fingerprints=legacy_fingerprints,
        )
        _atomic_private_write(output_path, html)
        results[slot] = {
            "path": str(output_path),
            "scenario_count": len(packets),
            "variant_count": len(template_rows),
            "source_fingerprint": source_fingerprint(
                source_html,
                slot,
                packets,
                template_rows,
                package_manifest_sha256=package_sha,
                packet_sha256=packet_hashes,
                template_sha256=_sha256(template_raw),
            ),
            "html_sha256": _sha256(html.encode("utf-8")),
        }
    return results


def _private_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    private_root = (REPO_ROOT / ".research-data").resolve()
    if not resolved.is_relative_to(private_root):
        raise WorkspaceBuildError("private reviewer content and generated HTML must remain under .research-data/")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-html", type=Path, required=True, help="research-owner supplied standalone Reviewer 2 HTML shell")
    parser.add_argument("--package-root", type=Path, default=REPO_ROOT / ".research-data" / "p2c-full", help="private P2C full dataset package")
    args = parser.parse_args(argv)
    try:
        _private_path(args.package_root)
        results = generate_workspaces(args.studio_html, args.package_root)
    except (OSError, WorkspaceBuildError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
