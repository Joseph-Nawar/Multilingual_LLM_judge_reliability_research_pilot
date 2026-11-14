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


LANGUAGE_CONDITIONS = ("EN-EN", "AR-AR", "EN-AR", "AR-EN")
EXPECTED_SCENARIOS = 56
EXPECTED_VARIANTS = 448
WORKSPACE_VERSION = "p2c-bilingual-review-studio-3"
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
        "reviewer_slot": reviewer_slot,
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "package_manifest_sha256": package_manifest_sha256,
        "studio_html_sha256": _sha256(source_html.encode("utf-8")),
        "packet_file_sha256": dict(sorted(packet_sha256.items())) if packet_sha256 is not None else {
            scenario_id: _sha256(_canonical_json(packet).encode("utf-8"))
            for scenario_id, packet in sorted(packet_map.items())
        },
        "template_file_sha256": template_sha256 or _sha256(_canonical_json(list(template_rows)).encode("utf-8")),
    }
    return _sha256(_canonical_json(body).encode("utf-8"))


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
    matches = [m for m in _SCRIPT.finditer(html) if "const SOURCE = JSON.parse(document.getElementById('embedded-scenarios').textContent);" in m.group("body")]
    if len(matches) != 1:
        raise WorkspaceBuildError("owner HTML app script is missing or ambiguous")
    match = matches[0]
    app = match.group("body")

    source_binding = re.compile(
        r"const SOURCE = JSON.parse\(document\.getElementById\('embedded-scenarios'\)\.textContent\);\s*"
        r"const SLOT = ['\"]reviewer_slot_2['\"];\s*"
        r"const SOURCE_FINGERPRINT = ['\"][0-9a-f]{64}['\"]\s*;"
    )
    app, source_count = source_binding.subn(
        "const SOURCE = JSON.parse(document.getElementById('embedded-scenarios').textContent);\n"
        "const REVIEW_DATA = JSON.parse(document.getElementById('embedded-review-data').textContent);\n"
        "const SLOT = REVIEW_DATA.reviewer_slot;\nconst SOURCE_FINGERPRINT = REVIEW_DATA.source_fingerprint;",
        app,
    )
    if source_count != 1:
        raise WorkspaceBuildError("owner HTML source-binding declarations differ from the approved version")
    replacements = (
        ("const localKey='p2c-reviewer-workspace-slot2-v1-'+SOURCE_FINGERPRINT;", "const localKey='p2c-reviewer-workspace-'+SLOT+'-'+SOURCE_FINGERPRINT;"),
        ("const ui={scenario:0,history:0,condition:0,answers:{},template:null,packets:null,bindings:null,fromSource:false};", "const ui={scenario:0,history:0,condition:0,answers:{},template:REVIEW_DATA.template,packets:REVIEW_DATA.packets,bindings:null,fromSource:true};"),
    )
    for old, new in replacements:
        if app.count(old) != 1:
            raise WorkspaceBuildError(f"owner HTML app version lacks expected binding: {old[:40]}")
        app = app.replace(old, new, 1)

    restore_block = re.compile(r"function restore\(data\)\{.*?(?=\nfunction updateGlobal\(\))", re.DOTALL)
    hardened_restore = """function validateDraftAnswers(answers){
if(!answers||typeof answers!=='object'||Array.isArray(answers))throw Error('Checkpoint answers must be an object.');
const validIds=new Set(ITEMS.map(x=>x.key));
const answerFields=['semantic_relation','linguistic_quality','decisive_update_dependence','decisive_update_dependence_rationale','whole_action_dependence','whole_action_dependence_rationale','issue_codes','checklist','notes'];
for(const [key,a] of Object.entries(answers)){
 if(!validIds.has(key)||!a||typeof a!=='object'||Array.isArray(a)||Object.keys(a).length!==answerFields.length||answerFields.some(f=>!(f in a)))throw Error('Checkpoint contains an unknown item ID or malformed answer.');
 if(!['','equivalent','meaning_changed','ambiguous'].includes(a.semantic_relation)||!['','natural','acceptable_variation','unnatural_or_unclear'].includes(a.linguistic_quality)||!['','yes','no','unclear'].includes(a.decisive_update_dependence)||!['','yes','no','unclear'].includes(a.whole_action_dependence))throw Error('Checkpoint contains an unsupported assessment value.');
 for(const f of ['decisive_update_dependence_rationale','whole_action_dependence_rationale','notes'])if(typeof a[f]!=='string')throw Error('Checkpoint contains malformed text fields.');
 if(!Array.isArray(a.issue_codes)||a.issue_codes.some(x=>!ISSUE_CODES.some(([code])=>code===x))||new Set(a.issue_codes).size!==a.issue_codes.length)throw Error('Checkpoint contains invalid issue codes.');
 if(!a.checklist||typeof a.checklist!=='object'||Array.isArray(a.checklist)||Object.keys(a.checklist).length!==CK.length||CK.some(([k])=>!(k in a.checklist)||!(a.checklist[k]===null||typeof a.checklist[k]==='boolean')))throw Error('Checkpoint contains malformed checklist answers.');
}
return answers}
function restore(data){if(!data||data.format!=='p2c-review-draft-1'||data.slot!==SLOT||data.source_fingerprint!==SOURCE_FINGERPRINT)throw Error('Wrong checkpoint format, reviewer slot, or source package version.');
const answers=validateDraftAnswers(data.answers);const p=data.position;if(!Array.isArray(p)||p.length!==3||p.some(x=>!Number.isInteger(x)))throw Error('Checkpoint navigation position is malformed.');
ui.answers=answers;ui.scenario=Math.max(0,Math.min(SOURCE.length-1,p[0]));ui.history=Math.max(0,Math.min(1,p[1]));ui.condition=Math.max(0,Math.min(3,p[2]));save();renderAll()}"""
    if restore_block.search(app):
        app, restore_count = restore_block.subn(hardened_restore, app)
        if restore_count != 1:
            raise WorkspaceBuildError("owner HTML draft restore logic differs from the approved version")
    else:
        raise WorkspaceBuildError("owner HTML draft restore function is missing or has changed")
    old_local_restore = "ui.answers=saved.answers||{};ui.scenario=saved.position?.[0]||0;ui.history=saved.position?.[1]||0;ui.condition=saved.position?.[2]||0"
    new_local_restore = "ui.answers=validateDraftAnswers(saved.answers);ui.scenario=Number.isInteger(saved.position?.[0])?Math.max(0,Math.min(SOURCE.length-1,saved.position[0])):0;ui.history=saved.position?.[1]===1?1:0;ui.condition=Number.isInteger(saved.position?.[2])?Math.max(0,Math.min(3,saved.position[2])):0"
    if app.count(old_local_restore) != 1:
        raise WorkspaceBuildError("owner HTML local draft recovery differs from the approved version")
    app = app.replace(old_local_restore, new_local_restore, 1)
    app = app.replace("async function bindSource()", "function bindSource()", 1)
    if "async function bindSource()" in app:
        raise WorkspaceBuildError("could not make embedded source binding synchronous")

    rationale_button = re.compile(r'<button type="button" class="mini-btn" data-copy-rationale="[^"]+">Copy earlier rationale for this history \(review before using\)</button>')
    app, removed_rationales = rationale_button.subn("", app)
    if removed_rationales != 2:
        raise WorkspaceBuildError("owner HTML must contain the two cross-variant rationale copy controls")
    all_pass_button = re.compile(r'<button type="button" class="mini-btn" data-all-pass="1">✓ Mark all eight checks as passing</button>')
    app, removed_bulk_pass = all_pass_button.subn("", app)
    if removed_bulk_pass != 1:
        raise WorkspaceBuildError("owner HTML must contain exactly one all-checks shortcut")
    app = app.replace("If every check is satisfactory after inspecting, use the shortcut below.", "Answer every checklist item independently for this variant.", 1)
    if "If every check is satisfactory after inspecting, use the shortcut below." in app:
        raise WorkspaceBuildError("review checklist shortcut text was not removed")

    click_handler = re.compile(r"\$\('assessment-fields'\)\.addEventListener\('click'.*?(?=\n\$\('save-next'\)\.addEventListener)", re.DOTALL)
    app, click_count = click_handler.subn("", app)
    if click_count != 1:
        raise WorkspaceBuildError("owner HTML click-handler block differs from the approved version")

    for loader_pattern in (
        re.compile(r"async function handleTemplate\(.*?(?=\nasync function handlePackets\()", re.DOTALL),
        re.compile(r"async function handlePackets\(.*?(?=\nfunction exportComplete\()", re.DOTALL),
    ):
        if loader_pattern.search(app):
            app, loader_count = loader_pattern.subn("", app)
            if loader_count != 1:
                raise WorkspaceBuildError("owner HTML external source-loader function differs from the approved version")

    # Each app handler lives on a single line in the supplied, versioned UI shell.
    lines = app.splitlines()
    lines = [
        line for line in lines
        if not line.startswith("$('template-file').addEventListener(")
        and not line.startswith("$('packet-folder').addEventListener(")
    ]
    app = "\n".join(lines)
    init_old = "}catch(_){}renderAll()})();"
    if app.count(init_old) != 1:
        raise WorkspaceBuildError("owner HTML startup sequence differs from the approved transformation anchor")
    app = app.replace(init_old, "}catch(_){}try{bindSource()}catch(e){bindingFailure(e)}renderAll()})();", 1)
    app = app.replace(
        "Select your 448-row template and 56 source packets first.",
        "The embedded 448-row template and 56 source packets failed binding.",
        1,
    )
    app = app.replace(
        "You can now export the final JSONL once the source package is linked.",
        "You can now export the final JSONL.",
        1,
    )
    export_binding = "if(!src||used.has(b.example_id))throw Error('Binding mismatch during export.');"
    if app.count(export_binding) != 1:
        raise WorkspaceBuildError("owner HTML export hash validation differs from the approved version")
    app = app.replace(
        export_binding,
        "if(!src||used.has(b.example_id)||src.example_sha256!==b.example_sha256||src.canonical_scenario_sha256!==b.canonical_scenario_sha256)throw Error('Binding or source hash mismatch during export.');",
        1,
    )
    app = app.replace(
        "✓ Verified: 56 packets + 448 template rows · hashes aligned",
        "Source package verified: 56 scenarios · 448 variants · hashes aligned",
        1,
    )
    old_permission_fragment = "const tool=sc.tool,pars=tool.action?.parameters||{};"
    new_permission_fragment = "const tool=sc.tool,pars=tool.action?.parameters||{},schemaText=(tool.parameters||[]).map(p=>`${p.name}: ${p.type}${p.required?' (required)':' (optional)'}`).join('; '),permText=(tool.required_permission_details||[]).map(p=>`${p.permission}${p.scope?.entity_id?` · scope ${p.scope.entity_id}`:''}`).join(', ');"
    if app.count(old_permission_fragment) != 1:
        raise WorkspaceBuildError("owner HTML action renderer differs from the approved transformation anchor")
    app = app.replace(old_permission_fragment, new_permission_fragment, 1)
    old_permission_render = "tool.required_permissions?.length?'Requires permission: '+escapeHtml(tool.required_permissions.join(', ')):''"
    if app.count(old_permission_render) != 1:
        raise WorkspaceBuildError("owner HTML permission renderer differs from the approved transformation anchor")
    app = app.replace(
        old_permission_render,
        "(schemaText?'Tool contract: '+escapeHtml(schemaText)+'. ':'')+(permText?'Requires permission: '+escapeHtml(permText):'')",
        1,
    )
    if "data-copy-rationale" in app or "data-all-pass" in app or "template-file" in app or "packet-folder" in app:
        remaining = {token: app.count(token) for token in ("data-copy-rationale", "data-all-pass", "template-file", "packet-folder") if token in app}
        raise WorkspaceBuildError(f"a removed reviewer shortcut or external-file dependency remains in the app script: {remaining}")
    return html[:match.start("body")] + app + html[match.end("body"):]


def _rewrite_static_markup(html: str, reviewer_slot: str) -> str:
    reviewer_number = reviewer_slot.rsplit("_", 1)[-1]
    html = html.replace("<title>Bilingual review workspace · Reviewer 2</title>", f"<title>Bilingual review workspace · Reviewer {reviewer_number}</title>", 1)
    html = html.replace("Reviewer slot 2 · English + Modern Standard Arabic", f"Reviewer slot {reviewer_number} · English + Modern Standard Arabic", 1)
    if html.count("<title>Bilingual review workspace · Reviewer ") != 1:
        raise WorkspaceBuildError("owner HTML title is not recognized")

    setup_intro = re.compile(
        r'<p>For a final, ingestion-compatible JSONL export, attach your original 448-row annotation template and the 56 reviewer packet JSON files\. You can review first and attach them later\.</p>\s*'
        r'<label>1 · Select <code>annotation-template\.jsonl</code><input type="file" accept="\.jsonl" id="template-file"\s*/?></label>\s*'
        r'<label>2 · Select reviewer packet folder \(56 JSON files\)<input type="file" accept="\.json" id="packet-folder" webkitdirectory multiple\s*/?></label>\s*'
        r'<div class="setup-state" id="binding-state">Not linked to source hashes</div>',
        re.DOTALL,
    )
    html, count = setup_intro.subn(
        '<p>Your assigned 56 source packets and blank 448-row annotation template are embedded in this page. No additional files are needed. Save a checkpoint JSON to continue in a later session.</p>\n'
        '<div class="setup-state" id="binding-state">Checking embedded source package…</div>',
        html,
    )
    if count != 1:
        raise WorkspaceBuildError("owner HTML source-package panel differs from the approved transformation anchor")
    html = html.replace("<h3>Export setup</h3>", "<h3>Source package and export</h3>", 1)
    html = html.replace("Be independent.", "Be independent.", 1)
    html = html.replace(
        "When all 448 are complete, attach the original template and packet folder to export a verified JSONL file for the researcher.",
        "When all 448 are complete, export the verified JSONL file directly from this page. The export contains only your own answers.",
        1,
    )
    html = html.replace(
        "You can mark all eight as passing after inspection, or flag individual problems.",
        "Answer each of the eight checklist items separately for every variant, or flag individual problems.",
        1,
    )
    guide_text = "Each must receive its own assessment."
    if guide_text in html:
        html = html.replace(guide_text, guide_text + " Answers and rationales are never copied to another variant.", 1)
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
) -> str:
    """Build one self-contained, independently assigned HTML review page."""
    packet_map, template_map, bindings = _validate_packet_and_template(reviewer_slot, packets, template_rows)
    fingerprint = source_fingerprint(
        source_html,
        reviewer_slot,
        packets,
        template_rows,
        package_manifest_sha256=package_manifest_sha256,
        packet_sha256=packet_sha256,
        template_sha256=template_sha256,
    )
    network_apis = r"(?:fetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon\s*\(|importScripts\s*\()"
    if re.search(network_apis, source_html, re.IGNORECASE):
        raise WorkspaceBuildError("reviewer HTML shell must not contain network communication")
    remote_assets = r"(?:<(?:script|link|img|iframe|source)\b[^>]*\b(?:src|href)\s*=\s*['\"]\s*https?://|@import\s+(?:url\()?\s*['\"]?https?://|url\(\s*['\"]?https?://)"
    if re.search(remote_assets, source_html, re.IGNORECASE):
        raise WorkspaceBuildError("reviewer HTML shell must not depend on remote scripts or assets")

    scenarios = _source_scenarios(packet_map)
    review_data = {
        "format": "p2c-embedded-review-package-1",
        "workspace_version": WORKSPACE_VERSION,
        "reviewer_slot": reviewer_slot,
        "source_fingerprint": fingerprint,
        "package_manifest_sha256": package_manifest_sha256,
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
        html = build_workspace_html(
            source_html,
            slot,
            packets,
            template_rows,
            package_manifest_sha256=package_sha,
            packet_sha256=packet_hashes,
            template_sha256=_sha256(template_raw),
        )
        output_path = review_root / slot / "bilingual-review-studio.html"
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
