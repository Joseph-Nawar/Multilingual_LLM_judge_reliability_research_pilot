"""Synthetic tests for standalone P2C reviewer workspaces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

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


def _run_js_logic(method: str, *args):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable for the standalone browser-logic parity check")
    from multilingual_judge_pilot.p2c_reason_taxonomy import reason_taxonomy_data

    runner = """
const create = require('./scripts/p2c_review_logic.js');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
try {
  const logic = create(input.taxonomy);
  process.stdout.write(JSON.stringify(logic[input.method](...input.args)));
} catch (error) {
  process.stdout.write(JSON.stringify({error: String(error.message || error)}));
}
"""
    result = subprocess.run(
        [node, "-e", runner],
        input=json.dumps({"taxonomy": reason_taxonomy_data(), "method": method, "args": args}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


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
<p>Be independent.</p>
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


def test_workspace_fingerprint_is_stable_when_regenerated_from_current_workspace():
    packets, template = _synthetic_package("reviewer_slot_2")
    first = build_workspace_html(
        _synthetic_source(), "reviewer_slot_2", packets, template,
        package_manifest_sha256="c" * 64,
    )
    second = build_workspace_html(
        first, "reviewer_slot_2", packets, template,
        package_manifest_sha256="c" * 64,
    )
    first_data = json.loads(first.split('id="embedded-review-data">', 1)[1].split("</script>", 1)[0])
    second_data = json.loads(second.split('id="embedded-review-data">', 1)[1].split("</script>", 1)[0])

    assert second_data["source_fingerprint"] == first_data["source_fingerprint"]

    regenerated = build_workspace_html(
        first, "reviewer_slot_2", packets, template,
        package_manifest_sha256="c" * 64,
        legacy_source_fingerprints=[first_data["source_fingerprint"]],
    )
    assert _sha(regenerated) == _sha(first)


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
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_rationale

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
            "decisive_update_dependence": "no",
            "decisive_update_dependence_rationale": build_rationale("q3", "no", {
                "reasons": ["earlier_numeric_needed", "earlier_permission_needed"],
                "supporting_turns": [1, 2],
                "fields": ["amount", "permission state"],
                "explanation": "",
            }),
            "whole_action_dependence": "no",
            "whole_action_dependence_rationale": build_rationale("q4", "no", {
                "reasons": ["earlier_permission_information_needed"],
                "supporting_turns": [1],
                "fields": ["permission state"],
                "explanation": "",
            }),
            "checklist": {key: True for key in row["checklist"]},
            "issue_codes": [],
            "notes": "",
        })
    raw = ("\n".join(json.dumps(row, sort_keys=True) for row in completed) + "\n").encode()

    rows = parse_submission_jsonl(raw, reviewer_slot=slot, expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    assert len(rows) == 448
    assert all(row["decisive_update_dependence"] == "no" for row in rows)
    assert all("Earlier numeric value needed" in row["decisive_update_dependence_rationale"] for row in rows)
    assert all("Earlier permission information needed" in row["whole_action_dependence_rationale"] for row in rows)
    assert all(set(row) == set(template[0]) for row in rows)
    assert {row["example_id"]: row["example_sha256"] for row in rows} == expected_hashes
    assert {row["example_id"]: row["canonical_scenario_sha256"] for row in rows} == scenario_hashes
    with pytest.raises(ReviewValidationError):
        parse_submission_jsonl(raw + raw.splitlines()[0] + b"\n", reviewer_slot=slot, expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)


def test_q3_reason_choices_follow_the_selected_polarity_without_defaults():
    from multilingual_judge_pilot.p2c_reason_taxonomy import allowed_reasons

    assert allowed_reasons("q3", "yes") == (
        "explicit_numeric",
        "explicit_temporal",
        "explicit_permission",
        "complete_restatement",
        "other",
    )
    assert allowed_reasons("q3", "no") == (
        "earlier_numeric_needed",
        "earlier_temporal_needed",
        "earlier_permission_needed",
        "earlier_referent_scope_needed",
        "multiple_earlier_turns_needed",
        "other",
    )
    assert allowed_reasons("q3", "unclear") == ("ambiguous_or_conflicting", "other")


def test_q4_reason_choices_are_independent_and_follow_the_selected_polarity():
    from multilingual_judge_pilot.p2c_reason_taxonomy import allowed_reasons

    assert allowed_reasons("q4", "yes") == (
        "decisive_instruction_invalidity",
        "all_requirements_available",
        "other",
    )
    assert allowed_reasons("q4", "no") == (
        "earlier_numeric_constraint_needed",
        "earlier_temporal_constraint_needed",
        "earlier_permission_information_needed",
        "earlier_unrelated_requirements_needed",
        "multiple_earlier_requirements_needed",
        "other",
    )
    assert allowed_reasons("q4", "unclear") == ("ambiguous_or_conflicting_information", "other")
    assert "explicit_numeric" not in allowed_reasons("q4", "no")
    assert "earlier_permission_information_needed" not in allowed_reasons("q3", "no")


def test_each_taxonomy_reason_generates_its_selected_reason_and_turn():
    from multilingual_judge_pilot.p2c_reason_taxonomy import allowed_reasons, build_rationale

    mapping = {
        ("q3", "yes"): {
            "explicit_numeric": "Explicit numeric requirement",
            "explicit_temporal": "Explicit temporal requirement",
            "explicit_permission": "Explicit permission state",
            "complete_restatement": "Complete restatement",
            "other": "Other / not covered",
        },
        ("q3", "no"): {
            "earlier_numeric_needed": "Earlier numeric value needed",
            "earlier_temporal_needed": "Earlier temporal value needed",
            "earlier_permission_needed": "Earlier permission state needed",
            "earlier_referent_scope_needed": "Earlier referent or scope needed",
            "multiple_earlier_turns_needed": "Multiple earlier turns needed",
            "other": "Other / not covered",
        },
        ("q3", "unclear"): {
            "ambiguous_or_conflicting": "Ambiguous or conflicting interpretation",
            "other": "Other / not covered",
        },
        ("q4", "yes"): {
            "decisive_instruction_invalidity": "The decisive instruction alone establishes invalidity",
            "all_requirements_available": "All relevant requirements are available",
            "other": "Other / not covered",
        },
        ("q4", "no"): {
            "earlier_numeric_constraint_needed": "Earlier numerical constraint needed",
            "earlier_temporal_constraint_needed": "Earlier temporal constraint needed",
            "earlier_permission_information_needed": "Earlier permission information needed",
            "earlier_unrelated_requirements_needed": "Earlier unrelated requirements needed",
            "multiple_earlier_requirements_needed": "Multiple earlier requirements needed",
            "other": "Other / not covered",
        },
        ("q4", "unclear"): {
            "ambiguous_or_conflicting_information": "Ambiguous or conflicting information",
            "other": "Other / not covered",
        },
    }
    for (question, answer), labels in mapping.items():
        assert set(allowed_reasons(question, answer)) == set(labels)
        for reason_id, label in labels.items():
            selection = {
                "reasons": [reason_id],
                "supporting_turns": [4, 5] if question == "q3" and reason_id == "multiple_earlier_turns_needed" else [4],
                "fields": ["booking_window", "permission state"] if reason_id == "multiple_earlier_requirements_needed" else ["booking_window"] if "temporal" in reason_id else ["amount"],
                "explanation": "The selected turn gives the specific evidence for this choice." if reason_id in {
                    "other", "ambiguous_or_conflicting", "ambiguous_or_conflicting_information"
                } else "",
            }
            rationale = build_rationale(question, answer, selection)
            assert label in rationale
            assert "4" in rationale
            if reason_id == "multiple_earlier_turns_needed":
                assert "5" in rationale


def test_multiple_reasons_turns_and_fields_are_rendered_without_losing_q3_q4_separation():
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_rationale

    q3 = build_rationale("q3", "no", {
        "reasons": ["earlier_numeric_needed", "earlier_permission_needed"],
        "supporting_turns": [1, 3],
        "fields": ["amount", "permission state"],
        "explanation": "",
    })
    q4 = build_rationale("q4", "yes", {
        "reasons": ["decisive_instruction_invalidity"],
        "supporting_turns": [4],
        "fields": ["maximum amount"],
        "explanation": "",
    })
    q4_multiple_requirements_same_turn = build_rationale("q4", "no", {
        "reasons": ["multiple_earlier_requirements_needed"],
        "supporting_turns": [2],
        "fields": ["booking window", "permission state"],
        "explanation": "",
    })

    assert q3 == "Earlier numeric value needed; Earlier permission state needed. Supporting turn(s): 1, 3. Requirement/field: amount, permission state."
    assert q4 == "The decisive instruction alone establishes invalidity. Supporting turn(s): 4. Requirement/field: maximum amount."
    assert "Earlier permission state needed" not in q4
    assert "The decisive instruction alone establishes invalidity" not in q3
    assert "Multiple earlier requirements needed" in q4_multiple_requirements_same_turn
    assert "Supporting turn(s): 2." in q4_multiple_requirements_same_turn
    assert "Requirement/field: booking window, permission state." in q4_multiple_requirements_same_turn


def test_rationale_rejects_missing_incompatible_duplicate_and_unsupported_evidence():
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_rationale

    base = {"reasons": ["explicit_numeric"], "supporting_turns": [2], "fields": [], "explanation": ""}
    with pytest.raises(ValueError, match="at least one compatible reason"):
        build_rationale("q3", "yes", {**base, "reasons": []})
    with pytest.raises(ValueError, match="incompatible"):
        build_rationale("q3", "no", base)
    with pytest.raises(ValueError, match="unique"):
        build_rationale("q3", "yes", {**base, "reasons": ["explicit_numeric", "explicit_numeric"]})
    with pytest.raises(ValueError, match="supporting turn"):
        build_rationale("q3", "yes", {**base, "supporting_turns": []})
    with pytest.raises(ValueError, match="two distinct"):
        build_rationale("q3", "no", {
            "reasons": ["multiple_earlier_turns_needed"],
            "supporting_turns": [2],
            "fields": [],
            "explanation": "",
        })
    with pytest.raises(ValueError, match="two selected requirement/field"):
        build_rationale("q4", "no", {
            "reasons": ["multiple_earlier_requirements_needed"],
            "supporting_turns": [2],
            "fields": ["permission state"],
            "explanation": "",
        })
    assert "earlier supporting turn" in _run_js_logic("buildRationale", "q3", "no", {
        "reasons": ["earlier_numeric_needed"], "supporting_turns": [4], "fields": ["amount"], "explanation": "",
    }, [2, 4], 4)["error"]
    assert "two earlier turns" in _run_js_logic("buildRationale", "q3", "no", {
        "reasons": ["multiple_earlier_turns_needed"], "supporting_turns": [2, 4], "fields": [], "explanation": "",
    }, [2, 4], 4)["error"]
    assert "earlier supporting turn" in _run_js_logic("buildRationale", "q4", "no", {
        "reasons": ["earlier_permission_information_needed"], "supporting_turns": [4], "fields": ["permission state"], "explanation": "",
    }, [2, 4], 4)["error"]
    with pytest.raises(ValueError, match="explanation"):
        build_rationale("q3", "unclear", {
            "reasons": ["ambiguous_or_conflicting"],
            "supporting_turns": [2],
            "fields": [],
            "explanation": "",
        })


def test_structured_issue_notes_identify_code_turn_field_and_expected_observed_values():
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_issue_notes

    reports = [
        {
            "type": "incorrect_number",
            "turn_index": 4,
            "field": "maximum amount",
            "expected": "$80",
            "observed": "$90",
            "explanation": "",
        },
        {
            "type": "other",
            "turn_index": 6,
            "field": "permission scope",
            "expected": "",
            "observed": "",
            "explanation": "The wording changes which account the approval applies to.",
        },
    ]

    assert build_issue_notes(reports) == (
        'Incorrect number (turn 4; field "maximum amount"): expected "$80"; observed "$90".\n'
        'Other / not covered (turn 6; field "permission scope"): The wording changes which account the approval applies to.'
    )
    assert build_issue_notes([]) == ""


def test_structured_issue_notes_reject_generic_or_incomplete_problem_explanations():
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_issue_notes

    with pytest.raises(ValueError, match="turn"):
        build_issue_notes([{"type": "incorrect_time", "field": "start time", "expected": "09:00", "observed": "10:00", "explanation": ""}])
    with pytest.raises(ValueError, match="expected and observed"):
        build_issue_notes([{"type": "incorrect_number", "turn_index": 2, "field": "amount", "expected": "", "observed": "90", "explanation": ""}])
    with pytest.raises(ValueError, match="generic placeholder"):
        build_issue_notes([{"type": "incorrect_number", "turn_index": 2, "field": "problem", "expected": "$80", "observed": "$90", "explanation": ""}])
    with pytest.raises(ValueError, match="generic placeholder"):
        build_issue_notes([{"type": "incorrect_number", "turn_index": 2, "field": "amount", "expected": "wrong", "observed": "$90", "explanation": ""}])
    with pytest.raises(ValueError, match="specific explanation"):
        build_issue_notes([{"type": "other", "turn_index": 2, "field": "scope", "expected": "", "observed": "", "explanation": "Wrong."}])


def test_complex_categorized_issue_requires_and_records_an_additional_explanation():
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_issue_notes

    report = {
        "type": "incorrect_number",
        "turn_index": 2,
        "field": "deposit amount",
        "expected": "80 dollars",
        "observed": "90 dollars",
        "explanation": "The number also changes which party is responsible for the deposit.",
        "explanation_required": True,
    }
    rendered = build_issue_notes([report])

    assert 'expected "80 dollars"; observed "90 dollars"' in rendered
    assert "Additional explanation: The number also changes which party is responsible for the deposit." in rendered
    with pytest.raises(ValueError, match="specific explanation"):
        build_issue_notes([{**report, "explanation": ""}])


def test_javascript_issue_notes_require_adequate_evidence_for_every_issue_type():
    from multilingual_judge_pilot.p2c_reason_taxonomy import build_issue_notes, reason_taxonomy_data

    taxonomy = reason_taxonomy_data()
    for issue_type, label in taxonomy["issue_types"].items():
        report = {
            "type": issue_type,
            "turn_index": 4,
            "field": "permission scope",
            "expected": "approval applies to account A",
            "observed": "approval applies to every account",
            "explanation": "The wording changes which account the approval applies to.",
            "explanation_required": False,
        }
        if issue_type in taxonomy["value_pair_types"]:
            report["explanation"] = ""
        else:
            report["expected"] = ""
            report["observed"] = ""
        rendered = _run_js_logic("buildIssueNotes", [report])
        assert rendered == build_issue_notes([report])
        assert label in rendered
        assert "turn 4" in rendered
        assert "permission scope" in rendered
        if issue_type in taxonomy["value_pair_types"]:
            assert "expected" in rendered and "observed" in rendered
        else:
            assert "The wording changes" in rendered
    generic_field = _run_js_logic("buildIssueNotes", [{
        "type": "incorrect_number", "turn_index": 4, "field": "problem", "expected": "$80",
        "observed": "$90", "explanation": "", "explanation_required": False,
    }])
    assert "generic placeholder" in generic_field["error"]


def test_workspace_embeds_the_versioned_taxonomy_and_replaces_free_text_rationale_fields():
    from multilingual_judge_pilot.p2c_reason_taxonomy import REASON_TAXONOMY_VERSION

    packets, template = _synthetic_package()
    html = build_workspace_html(
        _synthetic_source(),
        "reviewer_slot_2",
        packets,
        template,
        package_manifest_sha256="c" * 64,
    )
    review_data = json.loads(html.split('id="embedded-review-data">', 1)[1].split("</script>", 1)[0])

    assert review_data["reason_taxonomy"]["version"] == REASON_TAXONOMY_VERSION
    assert review_data["reason_taxonomy"]["q3"]["yes"][0] == "explicit_numeric"
    assert review_data["reason_taxonomy"]["q4"]["no"][2] == "earlier_permission_information_needed"
    assert "p2c-review-logic" in html
    assert "p2c-review-app" in html
    assert 'data-field="decisive_update_dependence_rationale"' not in html
    assert 'data-field="whole_action_dependence_rationale"' not in html
    assert 'data-field="notes"' not in html
    assert "const answerField=question==='q3'?'decisive_update_dependence':'whole_action_dependence'" in html
    assert "answerChoices(answerField,[['yes','Yes'],['no','No'],['unclear','Unclear']])" in html
    assert 'id="choice-${field}-${value}"' in html
    assert 'id="check-${key}-no"' in html
    assert "Unclear means the distinction cannot be established reliably" in html
    assert "needsPair&&record.explanation_required" in html
    assert "Copy earlier rationale" not in html
    assert "Mark all eight checks as passing" not in html


def test_javascript_rationale_generation_matches_python_for_every_reason_category():
    from multilingual_judge_pilot.p2c_reason_taxonomy import (
        Q3_REASONS,
        Q4_REASONS,
        allowed_reasons,
        build_rationale,
    )

    for question, catalog in (("q3", Q3_REASONS), ("q4", Q4_REASONS)):
        for answer in ("yes", "no", "unclear"):
            for reason in allowed_reasons(question, answer):
                selection = {
                    "reasons": [reason],
                    "supporting_turns": [2, 5] if question == "q3" and reason == "multiple_earlier_turns_needed" else [2],
                    "fields": ["booking_window", "permission state"] if reason == "multiple_earlier_requirements_needed" else ["booking_window"],
                    "explanation": "The selected turn shows the specific information behind this choice."
                    if reason == "other" or reason.startswith("ambiguous_or_conflicting")
                    else "",
                }
                expected = build_rationale(question, answer, selection)
                assert catalog[reason] in expected
                assert _run_js_logic("buildRationale", question, answer, selection) == expected


def test_javascript_answer_validation_rejects_incomplete_reasons_and_issue_evidence():
    from multilingual_judge_pilot.p2c_reason_taxonomy import reason_taxonomy_data

    keys = ["matches_formal_spec", "preserves_cross_language_meaning", "initial_requirements_communicated", "decisive_turn_expresses_event", "counterfactual_differences_controlled", "action_interpretation_preserved", "no_post_action_information", "msa_natural_and_unambiguous"]
    complete = {
        "semantic_relation": "equivalent",
        "linguistic_quality": "natural",
        "decisive_update_dependence": "yes",
        "whole_action_dependence": "no",
        "q3_selection": {"reasons": ["explicit_numeric"], "supporting_turns": [3], "fields": ["amount"], "explanation": ""},
        "q4_selection": {"reasons": ["earlier_permission_information_needed"], "supporting_turns": [1], "fields": ["permission grant"], "explanation": ""},
        "issue_codes": [],
        "checklist": {key: True for key in keys},
        "issue_reports": {},
        "other_issue": False,
    }
    assert _run_js_logic("problems", complete, keys) == []
    assert "Decisive-update rationale" in _run_js_logic("problems", {
        **complete,
        "q3_selection": {"reasons": [], "supporting_turns": [], "fields": [], "explanation": ""},
    }, keys)[0]
    missing_report = _run_js_logic("problems", {
        **complete,
        "issue_codes": ["incorrect_number"],
        "issue_reports": {},
    }, keys)
    assert any("issue report" in problem.lower() for problem in missing_report)

    number_report = {
        "type": "incorrect_number",
        "turn_index": 4,
        "field": "maximum amount",
        "expected": "$80",
        "observed": "$90",
        "explanation": "",
        "explanation_required": False,
    }
    with_issue = {**complete, "issue_codes": ["incorrect_number"], "issue_reports": {"issue_code:incorrect_number": [number_report]}}
    assert _run_js_logic("problems", with_issue, keys) == []
    assert _run_js_logic("problems", with_issue, keys, {}, [1, 3, 4], 3) == []
    assert any("issue report" in problem.lower() for problem in _run_js_logic("problems", with_issue, keys, {}, [1, 3], 3))
    assert _run_js_logic("buildIssueNotes", [number_report]) == 'Incorrect number (turn 4; field "maximum amount"): expected "$80"; observed "$90".'
    detailed_number = {
        **number_report,
        "explanation_required": True,
        "explanation": "The amount also changes who is responsible for the deposit.",
    }
    assert "Additional explanation:" in _run_js_logic("buildIssueNotes", [detailed_number])
    assert "specific explanation" in _run_js_logic("buildIssueNotes", [{**detailed_number, "explanation": ""}])["error"]

    other_field_report = {
        "turn_index": 2,
        "field": "Other / not covered",
        "field_other": "permission scope",
        "expected": "approval applies only to account A",
        "observed": "approval wording covers all accounts",
        "explanation": "",
        "explanation_required": False,
    }
    other_field_answer = {
        **complete,
        "semantic_relation": "meaning_changed",
        "issue_reports": {"semantic_meaning_changed": [other_field_report]},
    }
    assert _run_js_logic("problems", other_field_answer, keys) == []
    assert "permission scope" in _run_js_logic("buildIssueNotes", [{
        "type": "semantic_meaning_changed",
        "turn_index": other_field_report["turn_index"],
        "field": other_field_report["field_other"],
        "expected": other_field_report["expected"],
        "observed": other_field_report["observed"],
        "explanation": other_field_report["explanation"],
        "explanation_required": other_field_report["explanation_required"],
    }])

    failed_checklist = {
        **complete,
        "checklist": {**complete["checklist"], "matches_formal_spec": False},
        "issue_reports": {"checklist:matches_formal_spec": [{
            "turn_index": 4,
            "field": "Numeric requirement: deposit amount",
            "field_other": "",
            "expected": "$80",
            "observed": "$90",
            "explanation": "",
            "explanation_required": False,
        }]},
    }
    labels = {
        "matches_formal_spec": "Matches the intended formal specification",
        "preserves_cross_language_meaning": "Same intended meaning across languages",
        "initial_requirements_communicated": "Initial requirements and permissions are stated",
        "decisive_turn_expresses_event": "Final update expresses the intended change",
        "counterfactual_differences_controlled": "H1/H2 differ only as intended",
        "action_interpretation_preserved": "Action and tool mean the same thing",
        "no_post_action_information": "No information appears after the action point",
        "msa_natural_and_unambiguous": "MSA wording is natural (compare Arabic variants)",
    }
    failed_report = _run_js_logic("reportRecords", failed_checklist, keys, labels)
    assert "Failed checklist: Matches the intended formal specification" in failed_report[0]["field"]
    failed_notes = _run_js_logic("buildIssueNotes", failed_report)
    assert "Failed checklist: Matches the intended formal specification" in failed_notes
    assert 'expected "$80"; observed "$90"' in failed_notes
    for field_other in ("", "problem"):
        generic_checklist_field = {
            **failed_checklist,
            "issue_reports": {"checklist:matches_formal_spec": [{
                "turn_index": 4,
                "field": "Other / not covered",
                "field_other": field_other,
                "expected": "$80",
                "observed": "$90",
                "explanation": "",
                "explanation_required": False,
            }]},
        }
        rejected = _run_js_logic("reportRecords", generic_checklist_field, keys, labels)
        assert "generic placeholder" in rejected["error"]


def test_new_answer_has_no_preselected_reasons_and_requires_each_checklist_item_independently():
    keys = [
        "matches_formal_spec", "preserves_cross_language_meaning", "initial_requirements_communicated",
        "decisive_turn_expresses_event", "counterfactual_differences_controlled", "action_interpretation_preserved",
        "no_post_action_information", "msa_natural_and_unambiguous",
    ]
    empty = _run_js_logic("emptyAnswer", keys)
    assert empty["q3_selection"]["reasons"] == []
    assert empty["q4_selection"]["reasons"] == []
    assert set(empty["checklist"].values()) == {None}

    complete = {
        **empty,
        "semantic_relation": "equivalent",
        "linguistic_quality": "natural",
        "decisive_update_dependence": "yes",
        "whole_action_dependence": "yes",
        "q3_selection": {"reasons": ["explicit_numeric"], "supporting_turns": [2], "fields": ["amount"], "explanation": ""},
        "q4_selection": {"reasons": ["all_requirements_available"], "supporting_turns": [2], "fields": [], "explanation": ""},
        "checklist": {key: True for key in keys},
    }
    assert _run_js_logic("problems", complete, keys) == []
    one_unanswered = {**complete, "checklist": {**complete["checklist"], "matches_formal_spec": None}}
    assert "1 checklist answer(s)" in _run_js_logic("problems", one_unanswered, keys)


def test_javascript_checkpoint_restore_preserves_legacy_text_without_preselecting_reasons_or_crossing_reviewers():
    from multilingual_judge_pilot.p2c_reason_taxonomy import REASON_TAXONOMY_VERSION

    old_fingerprint = "d" * 64
    old_answer = {
        "semantic_relation": "equivalent",
        "linguistic_quality": "natural",
        "decisive_update_dependence": "no",
        "decisive_update_dependence_rationale": "Earlier turn 2 supplies the original amount.",
        "whole_action_dependence": "yes",
        "whole_action_dependence_rationale": "Turn 4 alone establishes invalidity.",
        "issue_codes": [],
        "checklist": {key: True for key in ["matches_formal_spec", "preserves_cross_language_meaning", "initial_requirements_communicated", "decisive_turn_expresses_event", "counterfactual_differences_controlled", "action_interpretation_preserved", "no_post_action_information", "msa_natural_and_unambiguous"]},
        "notes": "",
    }
    legacy = {
        "format": "p2c-review-draft-1",
        "slot": "reviewer_slot_2",
        "source_fingerprint": old_fingerprint,
        "answers": {"item-1": old_answer},
        "position": [0, 0, 0],
    }
    config = {
        "slot": "reviewer_slot_2",
        "source_fingerprint": "e" * 64,
        "legacy_source_fingerprints": [old_fingerprint],
        "valid_item_ids": ["item-1", "item-2"],
        "checklist_keys": list(old_answer["checklist"]),
        "reason_taxonomy_version": REASON_TAXONOMY_VERSION,
        "scenario_count": 56,
    }
    restored = _run_js_logic("restoreCheckpoint", legacy, config)

    assert restored["legacyImported"] is True
    carried = restored["answers"]["item-1"]
    assert carried["decisive_update_dependence"] == "no"
    assert carried["legacy_rationales"]["q3"] == old_answer["decisive_update_dependence_rationale"]
    assert carried["legacy_rationales"]["q4"] == old_answer["whole_action_dependence_rationale"]
    assert carried["q3_selection"]["reasons"] == []
    assert carried["q4_selection"]["reasons"] == []
    assert carried["issue_codes"] == []
    assert carried["checklist"] == old_answer["checklist"]
    assert restored["position"] == [0, 0, 0]

    wrong_slot = _run_js_logic("restoreCheckpoint", {**legacy, "slot": "reviewer_slot_1"}, config)
    wrong_source = _run_js_logic("restoreCheckpoint", {**legacy, "source_fingerprint": "f" * 64}, config)
    assert "reviewer slot" in wrong_slot["error"]
    assert "source fingerprint" in wrong_source["error"]

    current = {
        "format": "p2c-review-draft-3",
        "reason_taxonomy_version": REASON_TAXONOMY_VERSION,
        "legacy_imported": False,
        "slot": "reviewer_slot_2",
        "source_fingerprint": config["source_fingerprint"],
        "answers": {"item-2": _run_js_logic("emptyAnswer", config["checklist_keys"])},
        "position": [0, 0, 0],
    }
    restored_current = _run_js_logic("restoreCheckpoint", current, config)
    assert restored_current["legacyImported"] is False
    assert restored_current["answers"]["item-2"]["q3_selection"]["reasons"] == []
    assert "reviewer slot" in _run_js_logic("restoreCheckpoint", {**current, "slot": "reviewer_slot_1"}, config)["error"]
    prior_structured = _run_js_logic("restoreCheckpoint", {**current, "source_fingerprint": old_fingerprint}, config)
    assert prior_structured["legacyImported"] is False
    assert "approved matching prior source" in _run_js_logic(
        "restoreCheckpoint", {**current, "source_fingerprint": "f" * 64}, config
    )["error"]

    prior_report_answer = _run_js_logic("emptyAnswer", config["checklist_keys"])
    prior_report_answer["issue_codes"] = ["incorrect_number"]
    prior_report_answer["issue_reports"] = {
        "issue_code:incorrect_number": [{
            "turn_index": 2,
            "field": "amount",
            "field_other": "",
            "expected": "$80",
            "observed": "$90",
            "explanation": "",
        }]
    }
    prior_v2 = _run_js_logic("restoreCheckpoint", {
        **current,
        "format": "p2c-review-draft-2",
        "source_fingerprint": old_fingerprint,
        "answers": {"item-2": prior_report_answer},
    }, config)
    migrated_report = prior_v2["answers"]["item-2"]["issue_reports"]["issue_code:incorrect_number"][0]
    assert migrated_report["explanation_required"] is False
    assert migrated_report["expected"] == "$80"

    valid_turns = {**config, "valid_turns_by_item": {"item-1": [1, 2, 3], "item-2": [1, 2, 3]}}
    invalid_issue_turn_answer = _run_js_logic("emptyAnswer", valid_turns["checklist_keys"])
    invalid_issue_turn_answer["issue_codes"] = ["incorrect_number"]
    invalid_issue_turn_answer["issue_reports"] = {"issue_code:incorrect_number": [{
        "turn_index": 99,
        "field": "amount",
        "field_other": "",
        "expected": "$80",
        "observed": "$90",
        "explanation": "",
        "explanation_required": False,
    }]}
    invalid_issue_checkpoint = {**current, "answers": {"item-2": invalid_issue_turn_answer}}
    assert "issue report turn" in _run_js_logic("restoreCheckpoint", invalid_issue_checkpoint, valid_turns)["error"]

    with_supported_turn = _run_js_logic("emptyAnswer", valid_turns["checklist_keys"])
    with_supported_turn["decisive_update_dependence"] = "yes"
    with_supported_turn["q3_selection"] = {
        "reasons": ["explicit_numeric"], "supporting_turns": [2], "fields": ["amount"], "explanation": ""
    }
    valid_checkpoint = {
        **current,
        "answers": {"item-2": with_supported_turn},
    }
    assert "error" not in _run_js_logic("restoreCheckpoint", valid_checkpoint, valid_turns)
    invalid_turn_checkpoint = json.loads(json.dumps(valid_checkpoint))
    invalid_turn_checkpoint["answers"]["item-2"]["q3_selection"]["supporting_turns"] = [99]
    assert "supporting turn" in _run_js_logic("restoreCheckpoint", invalid_turn_checkpoint, valid_turns)["error"]


def test_legacy_workspace_fingerprints_are_trusted_only_when_slot_and_all_bindings_match():
    import scripts.generate_p2c_reviewer_workspaces as generator
    helper = getattr(generator, "legacy_source_fingerprints_from_workspace", None)
    assert callable(helper), "legacy workspace fingerprint compatibility check is missing"

    packets, template = _synthetic_package("reviewer_slot_2")
    old_html = build_workspace_html(
        _synthetic_source(),
        "reviewer_slot_2",
        packets,
        template,
        package_manifest_sha256="c" * 64,
    )
    old_data = json.loads(old_html.split('id="embedded-review-data">', 1)[1].split("</script>", 1)[0])

    assert helper(old_html, "reviewer_slot_2", old_data["bindings"]) == (old_data["source_fingerprint"],)
    changed = json.loads(json.dumps(old_data["bindings"]))
    first_id = next(iter(changed))
    changed[first_id]["example_sha256"] = "f" * 64
    assert helper(old_html, "reviewer_slot_2", changed) == ()
    assert helper(old_html, "reviewer_slot_1", old_data["bindings"]) == ()
