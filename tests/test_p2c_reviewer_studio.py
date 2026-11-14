"""Synthetic tests for standalone P2C reviewer workspaces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from multilingual_judge_pilot.p2c_review import (
    REVIEWER_SLOTS,
    ReviewValidationError,
    parse_submission_jsonl,
)
from multilingual_judge_pilot.preflight import blank_annotation_record

from scripts.generate_p2c_reviewer_workspaces import (
    WorkspaceBuildError,
    build_workspace_html,
    generate_workspaces,
    source_fingerprint,
)


CONDITIONS = ("EN-EN", "AR-AR", "EN-AR", "AR-EN")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _synthetic_source(slot: str = "reviewer_slot_2") -> str:
    del slot
    return ("""<!doctype html>
<html><head><meta charset="utf-8"><title>Bilingual review workspace · Reviewer 2</title>
<style>body{{font-family:system-ui}}</style></head><body>
<header><h1>Reviewer slot 2 · English + Modern Standard Arabic</h1></header>
<div class="setup-panel"><h3>Export setup</h3><p>For a final, ingestion-compatible JSONL export, attach your original 448-row annotation template and the 56 reviewer packet JSON files. You can review first and attach them later.</p>
<label>1 · Select <code>annotation-template.jsonl</code><input type="file" accept=".jsonl" id="template-file"/></label>
<label>2 · Select reviewer packet folder (56 JSON files)<input type="file" accept=".json" id="packet-folder" webkitdirectory multiple/></label>
<div class="setup-state" id="binding-state">Not linked to source hashes</div>
<div class="bottom-tools"><button class="btn" id="load-draft">Restore checkpoint</button><button class="btn btn-green" id="export-jsonl" disabled>Export final JSONL</button></div>
<input id="draft-file" type="file" accept=".json" class="hide"/></div>
<div id="assessment-fields"></div><button id="draft-btn">Save checkpoint</button>
<p>When all 448 are complete, attach the original template and packet folder to export a verified JSONL file for the researcher.</p>
<p>You can mark all eight as passing after inspection, or flag individual problems.</p>
<script type="application/json" id="embedded-scenarios">[]</script>
<script>
'use strict';
const SOURCE = JSON.parse(document.getElementById('embedded-scenarios').textContent);
const SLOT = 'reviewer_slot_2';
const SOURCE_FINGERPRINT = '__ZERO_SHA__';
const LANGS = ['EN-EN','AR-AR','EN-AR','AR-EN'];
const CK = [['matches_formal_spec','Matches the intended formal specification']];
const ISSUE_CODES = [['incorrect_number','Incorrect number']];
const KEY_FIELDS=['semantic_relation','linguistic_quality','decisive_update_dependence','decisive_update_dependence_rationale','whole_action_dependence','whole_action_dependence_rationale','issue_codes','checklist','notes'];
const $ = id => document.getElementById(id);
const localKey='p2c-reviewer-workspace-slot2-v1-'+SOURCE_FINGERPRINT;
const ui={scenario:0,history:0,condition:0,answers:{},template:null,packets:null,bindings:null,fromSource:false};
const ITEMS=[];
SOURCE.forEach((sc,si)=>sc.histories.forEach((h,hi)=>LANGS.forEach((c,ci)=>ITEMS.push({key:`${{sc.id}}|${{h.id}}|${{c}}`,si,hi,ci}))));
function emptyAnswer(){{return {{semantic_relation:'',linguistic_quality:'',decisive_update_dependence:'',decisive_update_dependence_rationale:'',whole_action_dependence:'',whole_action_dependence_rationale:'',issue_codes:[],checklist:{{matches_formal_spec:null}},notes:''}}}}
function answer(){{const key=`${{SOURCE[ui.scenario].id}}|${{SOURCE[ui.scenario].histories[ui.history].id}}|${{LANGS[ui.condition]}}`;if(!ui.answers[key])ui.answers[key]=emptyAnswer();return ui.answers[key]}}
function issuesNeedNote(a){{return a.semantic_relation!=='equivalent'||a.linguistic_quality==='unnatural_or_unclear'||a.issue_codes.length>0||Object.values(a.checklist).some(v=>v===false)}}
function problems(a){{return !a.semantic_relation||!a.linguistic_quality||!a.decisive_update_dependence||!a.decisive_update_dependence_rationale||!a.whole_action_dependence||!a.whole_action_dependence_rationale||!Object.values(a.checklist).every(v=>typeof v==='boolean')||(issuesNeedNote(a)&&!a.notes)}}
function counts(){{return ITEMS.filter(x=>ui.answers[x.key]&&!problems(ui.answers[x.key])).length}}
function updateGlobal(){{$('export-jsonl').disabled=counts()!==448||!ui.bindings}}
function renderAll(){{updateGlobal()}}
function bindSource(){{ui.bindings=new Map();ui.fromSource=true;$('binding-state').textContent='Verified';updateGlobal()}}
function exportComplete(){{}}
function restore(data){{if(data.format!=='p2c-review-draft-1'||data.slot!==SLOT||data.source_fingerprint!==SOURCE_FINGERPRINT)throw Error('Wrong checkpoint format or reviewer slot.');ui.answers=data.answers||{{}}}}
function updateGlobal(){{}}
function renderForm(){{const a=answer();$('assessment-fields').innerHTML=`<textarea data-field="decisive_update_dependence_rationale">${{a.decisive_update_dependence_rationale}}</textarea><button type="button" class="mini-btn" data-copy-rationale="decisive_update_dependence_rationale">Copy earlier rationale for this history (review before using)</button><textarea data-field="whole_action_dependence_rationale"></textarea><button type="button" class="mini-btn" data-copy-rationale="whole_action_dependence_rationale">Copy earlier rationale for this history (review before using)</button><p class="helper">If every check is satisfactory after inspecting, use the shortcut below.</p><button type="button" class="mini-btn" data-all-pass="1">✓ Mark all eight checks as passing</button>`}}
$('assessment-fields').addEventListener('click',e=>{{if(e.target.closest('[data-all-pass]')){{return}}const copy=e.target.closest('[data-copy-rationale]');if(copy){{answer()[copy.dataset.copyRationale]='copied'}}}});
$('save-next').addEventListener('click',()=>{{}});
function renderAction(sc){{const tool=sc.tool,pars=tool.action?.parameters||{{}};$('action-card').innerHTML=`${{tool.required_permissions?.length?'Requires permission: '+escapeHtml(tool.required_permissions.join(', ')):''}}`}}
function bindingFailure(e){{$('binding-state').textContent='Cannot link source package: '+e.message}}
function bindSource(){{$('binding-state').textContent='✓ Verified: 56 packets + 448 template rows · hashes aligned'}}
function exportComplete(){{if(!src||used.has(b.example_id))throw Error('Binding mismatch during export.');}}
$('template-file').addEventListener('change',()=>{{}});$('packet-folder').addEventListener('change',()=>{{}});
(function init(){{try{{const raw=localStorage.getItem(localKey);if(raw){{const saved=JSON.parse(raw);if(saved.format==='p2c-review-draft-1'&&saved.slot===SLOT&&saved.source_fingerprint===SOURCE_FINGERPRINT){{ui.answers=saved.answers||{{}};ui.scenario=saved.position?.[0]||0;ui.history=saved.position?.[1]||0;ui.condition=saved.position?.[2]||0}}}}renderAll()}}catch(_){{}}renderAll()}})();
</script></body></html>""").replace("{{", "{").replace("}}", "}").replace("__ZERO_SHA__", "0" * 64)


def _synthetic_package(slot: str = "reviewer_slot_2") -> tuple[list[dict], list[dict]]:
    packets: list[dict] = []
    templates: list[dict] = []
    for scenario_index in range(56):
        scenario_id = f"synthetic-scenario-{scenario_index:02d}"
        scenario_hash = _sha(scenario_id)
        history_ids = (scenario_id + "-history-a", scenario_id + "-history-b")
        histories = [
            {
                "history_id": history_id,
                "initial_state": {"$type": "HistoryState", "requirements": [], "grants": []},
                "events": [],
                "action_turn_index": 3,
                "decisive_turn_index": 2,
            }
            for history_id in history_ids
        ]
        variants = []
        for history_index, history_id in enumerate(history_ids):
            for condition in CONDITIONS:
                derivative_id = f"{scenario_id}-{history_index}-{condition.lower()}"
                variant_hash = _sha(derivative_id)
                language = "ar" if condition.endswith("AR") else "en"
                turns = [
                    {"turn_index": 1, "speaker": "user", "language": language, "segments": [{"type": "text", "text": f"Synthetic opening {scenario_index}."}]},
                    {"turn_index": 2, "speaker": "user", "language": language, "segments": [{"type": "text", "text": f"Synthetic update {history_index}."}]},
                ]
                variants.append({
                    "derivative_id": derivative_id,
                    "history_id": history_id,
                    "condition": condition,
                    "example_sha256": variant_hash,
                    "turns": turns,
                })
                templates.append(blank_annotation_record(derivative_id, variant_hash, scenario_hash))
        canonical_spec = {
            "schema_version": "synthetic-canonical-1",
            "scenario_id": scenario_id,
            "dataset_kind": "primary",
            "domain": "booking",
            "transition_family": "introduction",
            "shared_context": [],
            "action": {
                "$type": "StructuredAction",
                "entity_id": f"ENTITY-{scenario_index:02d}",
                "tool_name": "confirm_record",
                "executed_at": {"$datetime": "2026-11-14T10:00:00+00:00"},
                "fields": [{"$type": "ActionField", "name": "record_id", "value": f"REC-{scenario_index:02d}"}],
            },
            "action_contract": {"$type": "ActionContract", "required_permissions": [], "irreversible": True},
            "public_tool_schema": {
                "$type": "PublicToolSchema",
                "tool_name": "confirm_record",
                "description": "Confirm the synthetic record.",
                "parameters": [{"$type": "Parameter", "name": "record_id", "value_type": "string", "required": True}],
                "required_permissions": [],
                "irreversible": True,
            },
            "histories": histories,
        }
        packets.append({
            "packet_version": "p2c-review-packet-1",
            "annotation_schema_version": "p2b1-annotation-2",
            "reviewer_slot": slot,
            "scenario_id": scenario_id,
            "canonical_scenario_sha256": scenario_hash,
            "canonical_spec": canonical_spec,
            "language_variants": variants,
        })
    return packets, templates


def test_workspace_embeds_assigned_packets_and_exact_template_hashes():
    slot = "reviewer_slot_1"
    packets, template = _synthetic_package(slot)
    html = build_workspace_html(_synthetic_source(), slot, packets, template, package_manifest_sha256="c" * 64)

    assert "reviewer_slot_1" in html
    assert 'id="embedded-review-data"' in html
    assert 'id="embedded-scenarios"' in html
    assert 'Expected 448 template rows' not in html
    assert "Source package verified: 56 scenarios · 448 variants" in html
    assert "Tool contract:" in html
    assert html.count('"example_id"') == 448


def test_workspace_fingerprint_changes_when_source_packet_changes():
    slot = "reviewer_slot_2"
    packets, template = _synthetic_package(slot)
    first = source_fingerprint(_synthetic_source(), slot, packets, template, package_manifest_sha256="c" * 64)
    packets[0]["language_variants"][0]["turns"][0]["segments"][0]["text"] = "Changed synthetic source."
    second = source_fingerprint(_synthetic_source(), slot, packets, template, package_manifest_sha256="c" * 64)

    assert first != second


def test_workspace_rejects_a_packet_from_another_reviewer_slot():
    packets, template = _synthetic_package("reviewer_slot_2")
    with pytest.raises(WorkspaceBuildError, match="reviewer slot"):
        build_workspace_html(_synthetic_source(), "reviewer_slot_1", packets, template, package_manifest_sha256="c" * 64)


def test_workspace_rejects_empty_variant_ids():
    packets, template = _synthetic_package()
    packets[0]["language_variants"][0]["derivative_id"] = ""

    with pytest.raises(WorkspaceBuildError, match="unique non-empty"):
        build_workspace_html(_synthetic_source(), "reviewer_slot_2", packets, template, package_manifest_sha256="c" * 64)


def test_workspace_rejects_duplicate_or_stale_hash_bound_template_rows():
    packets, template = _synthetic_package()
    template[0]["example_sha256"] = "d" * 64

    with pytest.raises(WorkspaceBuildError, match="template.*hash"):
        build_workspace_html(_synthetic_source(), "reviewer_slot_2", packets, template, package_manifest_sha256="c" * 64)


def test_workspace_rejects_reference_only_packet_fields():
    packets, template = _synthetic_package()
    packets[0]["canonical_spec"]["oracle_label"] = "synthetic-invalid"

    with pytest.raises(WorkspaceBuildError, match="reference-only"):
        build_workspace_html(_synthetic_source(), "reviewer_slot_2", packets, template, package_manifest_sha256="c" * 64)


def test_workspace_rejects_templates_with_incomplete_checklist_schema():
    packets, template = _synthetic_package()
    template[0]["checklist"].pop("matches_formal_spec")

    with pytest.raises(WorkspaceBuildError, match="template must remain completely blank"):
        build_workspace_html(_synthetic_source(), "reviewer_slot_2", packets, template, package_manifest_sha256="c" * 64)


def test_workspace_rejects_html_that_uses_external_network_access():
    packets, template = _synthetic_package()

    with pytest.raises(WorkspaceBuildError, match="network communication"):
        build_workspace_html(_synthetic_source().replace("</body>", "<script>fetch('/remote')</script></body>"), "reviewer_slot_2", packets, template, package_manifest_sha256="c" * 64)


def test_workspace_generation_refuses_public_output_roots(tmp_path):
    with pytest.raises(WorkspaceBuildError, match="under .research-data/"):
        generate_workspaces(Path("unused-owner-shell.html"), tmp_path)


def test_workspace_does_not_offer_cross_variant_response_copying():
    packets, template = _synthetic_package()
    html = build_workspace_html(_synthetic_source(), "reviewer_slot_2", packets, template, package_manifest_sha256="c" * 64)

    assert "data-copy-rationale" not in html
    assert "Copy earlier rationale" not in html
    assert "data-all-pass" not in html
    assert "Mark all eight checks as passing" not in html


def test_synthetic_completed_jsonl_is_accepted_by_existing_p2c_validator():
    slot = REVIEWER_SLOTS[0]
    _packets, template = _synthetic_package(slot)
    expected_hashes = {row["example_id"]: row["example_sha256"] for row in template}
    scenario_hashes = {row["example_id"]: row["canonical_scenario_sha256"] for row in template}
    completed = []
    for row in template:
        completed.append({
            **row,
            "reviewer_id": slot,
            "semantic_relation": "equivalent",
            "linguistic_quality": "natural",
            "decisive_update_dependence": "unclear",
            "decisive_update_dependence_rationale": "Synthetic independent rationale for this exact variant.",
            "whole_action_dependence": "no",
            "whole_action_dependence_rationale": "Synthetic independent rationale for this exact variant.",
            "checklist": {key: True for key in row["checklist"]},
            "issue_codes": [],
            "notes": "",
        })
    raw = ("\n".join(json.dumps(row, sort_keys=True) for row in completed) + "\n").encode()

    rows = parse_submission_jsonl(raw, reviewer_slot=slot, expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    assert len(rows) == 448
    assert all(row["decisive_update_dependence"] == "unclear" for row in rows)
    with pytest.raises(ReviewValidationError):
        parse_submission_jsonl(raw + raw.splitlines()[0] + b"\n", reviewer_slot=slot, expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)
