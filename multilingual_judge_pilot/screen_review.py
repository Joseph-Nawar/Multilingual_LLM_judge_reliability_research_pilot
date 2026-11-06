"""Small offline bilingual QC page for the private competence-screen package."""

from __future__ import annotations

import json
import re
from typing import Mapping, Sequence

from .judge_inference import ContractError
from .qualification import item_sha256, verify_input_manifest


REVIEW_EXPORT_VERSION = "p3-screen-review-export-1"

_FIELDS = {
    "naturalness": [
        ("natural", "Natural"),
        ("minor_issue", "Minor wording issue"),
        ("major_issue", "Unnatural or unclear"),
        ("unclear", "Uncertain"),
    ],
    "interpretation": [("correct", "Correctly expressed"), ("issue", "Issue"), ("unclear", "Uncertain")],
    "action_tool": [("correct", "Correct"), ("issue", "Issue"), ("unclear", "Uncertain")],
    "independent_verdict": [("valid", "Valid"), ("invalid", "Invalid"), ("unclear", "Unclear")],
    "constraint_consistency": [
        ("consistent", "Consistent"),
        ("issue", "Issue"),
        ("not_applicable", "Not applicable"),
        ("unclear", "Uncertain"),
    ],
    "ambiguity": [("no", "No missing or ambiguous information"), ("yes", "Problem found"), ("unclear", "Uncertain")],
    "context_distinct": [("yes", "Clearly distinct"), ("no", "Too similar"), ("unclear", "Uncertain")],
}
_REFERENCE_FIELD = [("correct", "Reference label is correct"), ("incorrect", "Reference label is incorrect"), ("unclear", "Uncertain")]
_REQUIRED_FIELDS = tuple(_FIELDS)
_ID = re.compile(r"[A-Za-z0-9_.-]{1,120}")


def _safe_json_script(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_review_html(
    items: Sequence[Mapping[str, object]],
    reference_labels: Mapping[str, Mapping[str, object] | bool],
    input_manifest: Mapping[str, object],
) -> str:
    """Render a single-file, offline reviewer interface with label reveal gate."""
    verify_input_manifest(items, input_manifest)
    item_ids = [row.get("item_id") for row in items]
    if any(not isinstance(item_id, str) or not _ID.fullmatch(item_id) for item_id in item_ids):
        raise ContractError("screen item IDs must use the reviewer-package safe character set")
    if len(item_ids) != len(set(item_ids)) or set(reference_labels) != set(item_ids):
        raise ContractError("reviewer inputs and reference key must have matching unique item IDs")
    labels: dict[str, bool] = {}
    for item_id, row in reference_labels.items():
        value = row.get("expected_valid") if isinstance(row, Mapping) else row
        if type(value) is not bool:
            raise ContractError("reference key must contain one boolean label per screen item")
        labels[item_id] = value

    safe_items = []
    for row in items:
        lang = "ar" if str(row["language_condition"]).startswith("AR") else "en"
        safe_items.append({**row, "display_language": lang, "source_sha256": item_sha256(row)})

    items_data = _safe_json_script(safe_items)
    labels_data = _safe_json_script(labels)
    manifest_data = _safe_json_script(input_manifest)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>English/MSA competence screen quality check</title>
<style>
:root {{ color-scheme: light; font: 16px/1.45 system-ui, -apple-system, sans-serif; color:#182230; background:#f4f6f8; }}
body {{ margin:0; }} header, main {{ max-width:1000px; margin:0 auto; padding:18px; }}
header {{ background:#17324d; color:white; max-width:none; }} header > div {{ max-width:1000px; margin:auto; }}
h1 {{ font-size:1.35rem; margin:0 0 6px; }} h2 {{ font-size:1.12rem; }}
.bar, .card, fieldset {{ background:white; border:1px solid #d4dce4; border-radius:10px; padding:14px; margin:12px 0; }}
.nav {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }} button {{ border:1px solid #60758a; background:#fff; border-radius:7px; padding:8px 12px; font:inherit; cursor:pointer; }}
button.primary {{ background:#17324d; color:white; }} button:disabled {{ opacity:.5; cursor:not-allowed; }}
.turn {{ border-left:4px solid #91a9c0; padding:9px 12px; margin:8px 0; background:#f8fafc; }}
.turn.rtl {{ direction:rtl; text-align:right; border-left:0; border-right:4px solid #91a9c0; }}
.label {{ font-weight:650; margin-bottom:4px; }} pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#f7f8fa; padding:10px; border-radius:6px; margin:6px 0; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; }}
fieldset {{ padding:10px; margin:4px 0; }} legend {{ font-weight:650; padding:0 4px; }}
label.option {{ display:block; margin:5px 0; }} textarea, input[type=text], select {{ box-sizing:border-box; width:100%; max-width:100%; border:1px solid #aab7c4; border-radius:6px; padding:8px; font:inherit; }}
.muted {{ color:#526273; font-size:.92rem; }} .status {{ min-height:1.4em; color:#174d34; }} .error {{ color:#9b1c1c; }}
.hidden {{ display:none !important; }} .rtltext {{ direction:rtl; text-align:right; unicode-bidi:plaintext; }}
@media(max-width:600px) {{ header, main {{ padding:12px; }} }}
</style>
</head>
<body>
<header><div><h1>English/MSA competence screen quality check</h1><div>Offline reviewer copy · 48 items · labels appear only after independent judgments are locked</div></div></header>
<main>
<section class="bar" id="declaration">
<h2>Reviewer declaration</h2>
<div class="grid">
<label>English proficiency<input id="decl-en" type="text" autocomplete="off"></label>
<label>Modern Standard Arabic proficiency<input id="decl-ar" type="text" autocomplete="off"></label>
<label>Relevant review experience<input id="decl-exp" type="text" autocomplete="off"></label>
<label>Conflicts of interest<input id="decl-conflicts" type="text" autocomplete="off" placeholder="State none or describe"></label>
<label>Prior exposure to this screen/dataset<input id="decl-exposure" type="text" autocomplete="off" placeholder="State none or describe"></label>
</div>
<label class="option"><input id="decl-independent" type="checkbox"> I completed this assessment independently and did not consult another reviewer or model-generated answers.</label>
<p class="muted">These declarations are private and are included only in the review export.</p>
</section>
<section class="bar"><div class="nav"><button id="previous">Previous</button><button id="next">Next</button><span id="progress"></span></div><progress id="progressbar" max="48" value="1" aria-label="Review progress" style="width:100%"></progress><div class="status" id="save-status"></div></section>
<section class="card" id="item"></section>
<section class="bar">
<button class="primary" id="lock-reveal">Lock independent judgments and reveal reference labels</button>
<button class="primary" id="export">Export JSON</button>
<label>Import JSON<input id="import" type="file" accept="application/json,.json"></label>
<p class="muted">Export drafts at any time. To reveal reference labels, complete the independent assessments for all 48 items first. Notes are optional for clean items; a short explanation is required for any flagged problem or uncertainty.</p>
<div class="status" id="page-status" role="status"></div>
</section>
</main>
<script id="screen-items" type="application/json">{items_data}</script>
<script id="screen-labels" type="application/json">{labels_data}</script>
<script id="screen-manifest" type="application/json">{manifest_data}</script>
<script>
"use strict";
const items = JSON.parse(document.getElementById("screen-items").textContent);
const referenceLabels = JSON.parse(document.getElementById("screen-labels").textContent);
const inputManifest = JSON.parse(document.getElementById("screen-manifest").textContent);
const storageKey = "p3-screen-review-" + inputManifest.manifest_sha256;
const fieldSpecs = {_safe_json_script(_FIELDS)};
const referenceSpec = {_safe_json_script(_REFERENCE_FIELD)};
let index = 0;
let data = {{
  schema_version: "{REVIEW_EXPORT_VERSION}",
  input_manifest_sha256: inputManifest.manifest_sha256,
  locked_before_label_reveal: false,
  reviewer_declaration: {{ english_proficiency:"", msa_proficiency:"", relevant_review_experience:"", conflicts_of_interest:"", prior_dataset_exposure:"", independent:false }},
  items: items.map(item => ({{ item_id:item.item_id, source_sha256:item.source_sha256, answers:{{}} }}))
}};
function byId(id) {{ return document.getElementById(id); }}
function save() {{
  data.reviewer_declaration = {{
    english_proficiency:byId("decl-en").value, msa_proficiency:byId("decl-ar").value,
    relevant_review_experience:byId("decl-exp").value, conflicts_of_interest:byId("decl-conflicts").value,
    prior_dataset_exposure:byId("decl-exposure").value, independent:byId("decl-independent").checked
  }};
  try {{ localStorage.setItem(storageKey, JSON.stringify(data)); byId("save-status").textContent="Draft saved on this device."; }}
  catch (_) {{ byId("save-status").textContent="Local autosave is unavailable here; use Export JSON to preserve the draft."; }}
}}
function restore() {{
  try {{ const raw=localStorage.getItem(storageKey); if(raw) loadData(JSON.parse(raw)); }} catch (_) {{ byId("save-status").textContent="Could not load local draft; import a saved JSON export."; }}
}}
function make(tag, text, cls) {{ const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(cls) el.className=cls; return el; }}
function makeChoices(parent, field, options, selected, disabled=false) {{
  const set=document.createElement("fieldset"); const legend=make("legend", field.replaceAll("_"," ")); set.appendChild(legend);
  for(const [value,title] of options) {{
    const label=make("label",undefined,"option"); const input=document.createElement("input"); input.type="radio"; input.name=field; input.value=value; input.checked=selected===value; input.disabled=disabled;
    input.addEventListener("change",()=>{{ data.items[index].answers[field]=value; save(); render(); }});
    label.append(input,document.createTextNode(" "+title)); set.appendChild(label);
  }} parent.appendChild(set);
}}
function fieldComplete(answers) {{ return {_safe_json_script(list(_REQUIRED_FIELDS))}.every(k=>typeof answers[k]==="string"&&answers[k].length>0); }}
function issueFlag(answers) {{
  return answers.naturalness!==undefined && answers.naturalness!=="natural" ||
    answers.interpretation!==undefined && answers.interpretation!=="correct" ||
    answers.action_tool!==undefined && answers.action_tool!=="correct" ||
    ["issue","unclear"].includes(answers.constraint_consistency) ||
    ["yes","unclear"].includes(answers.ambiguity) ||
    ["no","unclear"].includes(answers.context_distinct) ||
    ["incorrect","unclear"].includes(answers.reference_label_review);
}}
function render() {{
  const item=items[index], answerRecord=data.items[index], answers=answerRecord.answers;
  byId("progress").textContent=`Item ${{index+1}} of ${{items.length}} · ${{item.item_id}} · ${{item.language_condition}}`;
  byId("progressbar").value=index+1;
  byId("previous").disabled=index===0; byId("next").disabled=index===items.length-1;
  byId("lock-reveal").disabled=data.locked_before_label_reveal;
  const host=byId("item"); host.replaceChildren();
  host.appendChild(make("h2",item.item_id+" · "+(item.display_language==="ar"?"Modern Standard Arabic":"English")));
  const conversation=make("section"); conversation.appendChild(make("h3","Conversation before the proposed action"));
  for(const turn of item.conversation) {{
    const direction=turn.language.startsWith("ar")?"rtl":"ltr"; const card=make("div",undefined,"turn"+(direction==="rtl"?" rtl":""));
    card.setAttribute("dir",direction); card.setAttribute("lang",direction==="rtl"?"ar":"en");
    card.appendChild(make("div",turn.speaker+" · turn "+turn.turn_index,"label")); card.appendChild(make("div",turn.content)); conversation.appendChild(card);
  }} host.appendChild(conversation);
  host.appendChild(make("h3","Proposed structured action")); host.appendChild(make("pre",JSON.stringify(item.action,null,2)));
  host.appendChild(make("h3","Public tool contract")); host.appendChild(make("pre",JSON.stringify(item.public_tool_schema,null,2)));
  const assessments=make("div",undefined,"grid");
  for(const field of {_safe_json_script(list(_REQUIRED_FIELDS))}) makeChoices(assessments,field,fieldSpecs[field],answers[field],data.locked_before_label_reveal);
  host.appendChild(assessments);
  if(data.locked_before_label_reveal) {{
    const expected=referenceLabels[item.item_id]?"valid":"invalid";
    const reveal=make("section",undefined,"bar"); reveal.appendChild(make("h3","Author reference label: "+expected));
    makeChoices(reveal,"reference_label_review",referenceSpec,answers.reference_label_review,false); host.appendChild(reveal);
  }}
  const noteLabel=make("label","Issue note (required when any assessment is flagged)");
  const notes=document.createElement("textarea"); notes.rows=3; notes.value=answers.issue_note||""; notes.addEventListener("input",()=>{{answers.issue_note=notes.value;save();}}); noteLabel.appendChild(notes); host.appendChild(noteLabel);
  byId("page-status").textContent=data.locked_before_label_reveal?"Independent judgments are locked. Review each revealed reference label and note any error or uncertainty.":"Assess each item independently. The author reference labels remain hidden.";
}}
function declarationComplete() {{
  const d=data.reviewer_declaration; return Boolean(d.english_proficiency.trim()&&d.msa_proficiency.trim()&&d.relevant_review_experience.trim()&&d.conflicts_of_interest.trim()&&d.prior_dataset_exposure.trim()&&d.independent===true);
}}
function readyForReveal() {{ return declarationComplete() && data.items.every(row=>fieldComplete(row.answers)); }}
function reviewComplete() {{ return readyForReveal() && data.locked_before_label_reveal && data.items.every(row=>typeof row.answers.reference_label_review==="string"&&row.answers.reference_label_review.length>0&&(!issueFlag(row.answers)||String(row.answers.issue_note||"").trim().length>=4)); }}
function exportData() {{
  save(); data.review_complete=reviewComplete(); data.reference_labels_revealed=data.locked_before_label_reveal; data.exported_at=new Date().toISOString();
  const blob=new Blob([JSON.stringify(data,null,2)+"\\n"],{{type:"application/json"}}); const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url; a.download="p3-competence-screen-review.json"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}}
function loadData(imported) {{
  if(imported.schema_version!=="{REVIEW_EXPORT_VERSION}"||imported.input_manifest_sha256!==inputManifest.manifest_sha256||!Array.isArray(imported.items)||imported.items.length!==items.length) throw new Error("Review export version or source manifest does not match.");
  if(Object.keys(imported).some(k=>!["schema_version","input_manifest_sha256","locked_before_label_reveal","reference_labels_revealed","exported_at","reviewer_declaration","items","review_complete"].includes(k))) throw new Error("Unknown export field.");
  if(imported.exported_at!==undefined&&(typeof imported.exported_at!=="string"||!imported.exported_at.endsWith("Z"))) throw new Error("Invalid export timestamp.");
  for(let i=0;i<items.length;i++) {{
    const row=imported.items[i]; if(!row||Object.keys(row).sort().join(",")!=="answers,item_id,source_sha256"||row.item_id!==items[i].item_id||row.source_sha256!==items[i].source_sha256||typeof row.answers!=="object"||row.answers===null) throw new Error("Item ID or source hash mismatch at position "+(i+1)+".");
    const allowed=[...Object.keys(fieldSpecs),"reference_label_review","issue_note"];
    for(const [key,value] of Object.entries(row.answers)) {{
      if(!allowed.includes(key)||typeof value!=="string") throw new Error("Unknown answer field or value type.");
      if(key==="issue_note") continue;
      const choices=key==="reference_label_review"?referenceSpec:fieldSpecs[key]; if(!choices||!choices.some(option=>option[0]===value)) throw new Error("Unknown assessment value.");
      if(key==="reference_label_review"&&!imported.locked_before_label_reveal) throw new Error("Reference-label assessment appears before labels were revealed.");
    }}
  }}
  if(typeof imported.locked_before_label_reveal!=="boolean"||typeof imported.reviewer_declaration!=="object"||imported.reviewer_declaration===null) throw new Error("Review export is incomplete or malformed.");
  if(imported.reference_labels_revealed!==undefined&&imported.reference_labels_revealed!==imported.locked_before_label_reveal) throw new Error("Reference-label reveal flag is inconsistent.");
  for(const key of ["english_proficiency","msa_proficiency","relevant_review_experience","conflicts_of_interest","prior_dataset_exposure"]) if(imported.reviewer_declaration[key]!==undefined&&typeof imported.reviewer_declaration[key]!=="string") throw new Error("Reviewer declaration has an invalid field.");
  if(imported.reviewer_declaration.independent!==undefined&&typeof imported.reviewer_declaration.independent!=="boolean") throw new Error("Reviewer independence declaration must be boolean.");
  if(imported.locked_before_label_reveal&&(!["english_proficiency","msa_proficiency","relevant_review_experience","conflicts_of_interest","prior_dataset_exposure"].every(k=>typeof imported.reviewer_declaration[k]==="string"&&imported.reviewer_declaration[k].trim())||imported.reviewer_declaration.independent!==true||!imported.items.every(row=>fieldComplete(row.answers)))) throw new Error("Reference labels can be revealed only after the complete independent-review gate.");
  data=imported; const d=data.reviewer_declaration;
  byId("decl-en").value=d.english_proficiency||""; byId("decl-ar").value=d.msa_proficiency||""; byId("decl-exp").value=d.relevant_review_experience||"";
  byId("decl-conflicts").value=d.conflicts_of_interest||""; byId("decl-exposure").value=d.prior_dataset_exposure||""; byId("decl-independent").checked=d.independent===true;
  save();
}}
byId("previous").addEventListener("click",()=>{{index=Math.max(0,index-1);render();}});
byId("next").addEventListener("click",()=>{{index=Math.min(items.length-1,index+1);render();}});
for(const id of ["decl-en","decl-ar","decl-exp","decl-conflicts","decl-exposure"]) byId(id).addEventListener("input",save);
byId("decl-independent").addEventListener("change",save);
byId("lock-reveal").addEventListener("click",()=>{{
  save(); if(!readyForReveal()) {{byId("page-status").textContent="Complete all seven independent assessments for every item and the reviewer declaration before revealing labels.";return;}}
  data.locked_before_label_reveal=true; save(); render();
}});
byId("export").addEventListener("click",exportData);
byId("import").addEventListener("change",async event=>{{try{{const file=event.target.files[0]; if(file){{loadData(JSON.parse(await file.text()));render();}}}}catch(error){{byId("page-status").textContent=error.message;byId("page-status").className="status error";}}}});
restore(); render();
</script>
</body>
</html>
'''


def validate_review_export(
    export: Mapping[str, object],
    items: Sequence[Mapping[str, object]],
    input_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Check source/hash bindings and shape without inventing reviewer answers."""
    verify_input_manifest(items, input_manifest)
    if not isinstance(export, Mapping):
        raise ValueError("review export must be an object")
    allowed_top = {
        "schema_version",
        "input_manifest_sha256",
        "locked_before_label_reveal",
        "reference_labels_revealed",
        "exported_at",
        "reviewer_declaration",
        "items",
        "review_complete",
    }
    if set(export) - allowed_top:
        raise ValueError("review export contains unknown fields")
    if export.get("schema_version") != REVIEW_EXPORT_VERSION:
        raise ValueError("unsupported review export version")
    if export.get("input_manifest_sha256") != input_manifest.get("manifest_sha256"):
        raise ValueError("review export source manifest hash mismatch")
    rows = export.get("items")
    if not isinstance(rows, list) or len(rows) != len(items):
        raise ValueError("review export must contain one row per screen item")
    expected = {item["item_id"]: item_sha256(item) for item in items}
    seen: set[str] = set()
    allowed_answers = set(_FIELDS) | {"reference_label_review", "issue_note"}
    choices = {name: {value for value, _label in values} for name, values in _FIELDS.items()}
    choices["reference_label_review"] = {value for value, _label in _REFERENCE_FIELD}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"item_id", "source_sha256", "answers"}:
            raise ValueError("review export item row has missing or unknown fields")
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or item_id not in expected or item_id in seen:
            raise ValueError("review export item IDs are missing, unknown, or duplicated")
        if row.get("source_sha256") != expected[item_id]:
            raise ValueError("review export item source hash mismatch")
        if not isinstance(row.get("answers"), Mapping):
            raise ValueError("review export answers must be an object")
        answers = row["answers"]
        if set(answers) - allowed_answers:
            raise ValueError("review export contains an unknown assessment field")
        for field, value in answers.items():
            if not isinstance(value, str):
                raise ValueError("review export assessment values must be text")
            if field == "issue_note":
                continue
            if value not in choices[field]:
                raise ValueError("review export contains an unknown assessment value")
            if field == "reference_label_review" and export.get("locked_before_label_reveal") is not True:
                raise ValueError("reference-label assessment appears before labels were revealed")
        seen.add(item_id)
    if seen != set(expected):
        raise ValueError("review export does not cover every source item")
    declaration = export.get("reviewer_declaration")
    if not isinstance(declaration, Mapping):
        raise ValueError("reviewer declaration must be an object")
    if type(export.get("locked_before_label_reveal")) is not bool:
        raise ValueError("review export label gate status must be boolean")
    if export.get("reference_labels_revealed", export["locked_before_label_reveal"]) is not export["locked_before_label_reveal"]:
        raise ValueError("review export reference-label reveal flags are inconsistent")
    if "exported_at" in export and (not isinstance(export["exported_at"], str) or not export["exported_at"].endswith("Z")):
        raise ValueError("review export timestamp must be an ISO UTC value")
    declaration = export["reviewer_declaration"]
    if set(declaration) - {
        "english_proficiency",
        "msa_proficiency",
        "relevant_review_experience",
        "conflicts_of_interest",
        "prior_dataset_exposure",
        "independent",
    }:
        raise ValueError("reviewer declaration contains unknown fields")
    if any(not isinstance(declaration.get(field, ""), str) for field in (
        "english_proficiency", "msa_proficiency", "relevant_review_experience", "conflicts_of_interest", "prior_dataset_exposure"
    )) or type(declaration.get("independent", False)) is not bool:
        raise ValueError("reviewer declaration contains invalid values")
    if export["locked_before_label_reveal"]:
        if any(not str(declaration.get(field, "")).strip() for field in (
            "english_proficiency", "msa_proficiency", "relevant_review_experience", "conflicts_of_interest", "prior_dataset_exposure"
        )) or declaration.get("independent") is not True:
            raise ValueError("reference labels cannot be revealed before the reviewer declaration is complete")
        if any(any(not isinstance(row["answers"].get(field), str) or not row["answers"][field] for field in _REQUIRED_FIELDS) for row in rows):
            raise ValueError("reference labels cannot be revealed before all independent item assessments are complete")
    if export.get("review_complete") is True:
        if not export["locked_before_label_reveal"] or any(
            not str(declaration.get(field, "")).strip()
            for field in ("english_proficiency", "msa_proficiency", "relevant_review_experience", "conflicts_of_interest", "prior_dataset_exposure")
        ) or declaration.get("independent") is not True:
            raise ValueError("review cannot be complete without the declaration and label-review stage")
        for row in rows:
            answers = row["answers"]
            if any(not isinstance(answers.get(field), str) or not answers[field] for field in _REQUIRED_FIELDS):
                raise ValueError("complete review is missing an item assessment")
            if not isinstance(answers.get("reference_label_review"), str) or not answers["reference_label_review"]:
                raise ValueError("complete review is missing a reference-label assessment")
            issue = (
                answers["naturalness"] != "natural"
                or answers["interpretation"] != "correct"
                or answers["action_tool"] != "correct"
                or answers["constraint_consistency"] in {"issue", "unclear"}
                or answers["ambiguity"] in {"yes", "unclear"}
                or answers["context_distinct"] in {"no", "unclear"}
                or answers["reference_label_review"] in {"incorrect", "unclear"}
            )
            if issue and len(str(answers.get("issue_note", "")).strip()) < 4:
                raise ValueError("flagged item requires a short issue note")
    return {
        "valid": True,
        "item_count": len(rows),
        "source_manifest_sha256": input_manifest["manifest_sha256"],
        "locked_before_label_reveal": export["locked_before_label_reveal"],
        "review_complete": export.get("review_complete") is True,
    }
