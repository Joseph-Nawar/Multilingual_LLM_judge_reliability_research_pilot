'use strict';

const SOURCE = JSON.parse(document.getElementById('embedded-scenarios').textContent);
const REVIEW_DATA = JSON.parse(document.getElementById('embedded-review-data').textContent);
const SLOT = REVIEW_DATA.reviewer_slot;
const SOURCE_FINGERPRINT = REVIEW_DATA.source_fingerprint;
const TAXONOMY = REVIEW_DATA.reason_taxonomy;
const logic = window.createP2CReviewLogic(TAXONOMY);
const LANGS = ['EN-EN','AR-AR','EN-AR','AR-EN'];
const CK = [
 ['matches_formal_spec','Matches the intended formal specification'],
 ['preserves_cross_language_meaning','Same intended meaning across languages'],
 ['initial_requirements_communicated','Initial requirements and permissions are stated'],
 ['decisive_turn_expresses_event','Final update expresses the intended change'],
 ['counterfactual_differences_controlled','H1/H2 differ only as intended'],
 ['action_interpretation_preserved','Action and tool mean the same thing'],
 ['no_post_action_information','No information appears after the action point'],
 ['msa_natural_and_unambiguous','MSA wording is natural (compare Arabic variants)']
];
const ISSUE_CODES = TAXONOMY.issue_codes.map(code => [code, TAXONOMY.issue_types[code]]);
const KEY_FIELDS = ['semantic_relation','linguistic_quality','decisive_update_dependence','decisive_update_dependence_rationale','whole_action_dependence','whole_action_dependence_rationale','issue_codes','checklist','notes'];
const $ = id => document.getElementById(id);
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localKey = `p2c-reviewer-workspace-${SLOT}-${SOURCE_FINGERPRINT}`;
const ui = {scenario:0,history:0,condition:0,answers:{},template:REVIEW_DATA.template,packets:REVIEW_DATA.packets,bindings:null,legacyNotice:false};
const ITEMS = [];
SOURCE.forEach((sc,si)=>sc.histories.forEach((h,hi)=>LANGS.forEach((c,ci)=>ITEMS.push({key:`${sc.id}|${h.id}|${c}`,si,hi,ci}))));
const byKey = new Map(ITEMS.map((row,i)=>[row.key,i]));
const checklistKeys = CK.map(([key])=>key);
const checklistLabels = Object.fromEntries(CK);

function keyOf(si=ui.scenario,hi=ui.history,ci=ui.condition){return `${SOURCE[si].id}|${SOURCE[si].histories[hi].id}|${LANGS[ci]}`}
function emptyAnswer(){return logic.emptyAnswer(checklistKeys)}
function answer(){const key=keyOf();if(!ui.answers[key])ui.answers[key]=emptyAnswer();return ui.answers[key]}
function turnIndicesForKey(key){const index=byKey.get(key);if(index===undefined)return [];const item=ITEMS[index];return SOURCE[item.si].histories[item.hi].variants[LANGS[item.ci]].map(turn=>turn.index)}
function decisiveTurnIndexForKey(key){const index=byKey.get(key);if(index===undefined)return null;const item=ITEMS[index];return SOURCE[item.si].formal.histories[item.hi].decisive_turn_index}
function itemComplete(key){return ui.answers[key]&&logic.problems(ui.answers[key],checklistKeys,checklistLabels,turnIndicesForKey(key),decisiveTurnIndexForKey(key)).length===0}
function counts(){return ITEMS.filter(x=>itemComplete(x.key)).length}
function syncDerived(a,key=keyOf()){logic.problems(a,checklistKeys,checklistLabels,turnIndicesForKey(key),decisiveTurnIndexForKey(key));return a}
function problems(a){const key=keyOf();return logic.problems(a,checklistKeys,checklistLabels,turnIndicesForKey(key),decisiveTurnIndexForKey(key))}
function currentTurns(){const sc=SOURCE[ui.scenario],history=sc.histories[ui.history];return history.variants[LANGS[ui.condition]]||[]}
function requirementFieldOptions(){
 const sc=SOURCE[ui.scenario],tool=sc.tool,options=['Numeric requirement','Temporal requirement','Permission state','Earlier referent or scope','Earlier unrelated requirement','Tool or action contract','Conversation meaning','Language wording'];
 for(const param of tool.parameters||[])options.push(`Action field: ${param.name}`);
 for(const permission of tool.required_permissions||[])options.push(`Permission: ${permission}`);
 for(const row of referenceSummary(sc,ui.history))if(row.text)options.push(`${row.label}: ${row.text}`);
 return [...new Set(options)];
}
function answerChoices(field,opts){const a=answer();return `<div class="choices three">${opts.map(([value,label])=>`<label class="choice"><input id="choice-${field}-${value}" type="radio" name="${field}" data-answer="${field}" value="${value}" ${a[field]===value?'checked':''}><span>${escapeHtml(label)}</span></label>`).join('')}</div>`}
function selectionCheckboxes(question,property,options,selected,extraClass=''){
 return `<div class="structured-choices ${extraClass}">${options.map((value,i)=>`<label class="structured-choice"><input id="${question}-${property}-${i}" type="checkbox" data-${property}="${question}" value="${escapeHtml(value)}" ${selected.includes(value)?'checked':''}><span>${escapeHtml(value)}</span></label>`).join('')}</div>`;
}
function reasonOptions(question,answerValue,selection){
 const labels=question==='q3'?TAXONOMY.q3_labels:TAXONOMY.q4_labels;
 const allowed=['yes','no','unclear'].includes(answerValue)?logic.allowedReasons(question,answerValue):[];
 const incompatible=selection.reasons.filter(reason=>!allowed.includes(reason));
 const choices=allowed.map(reason=>({reason,label:labels[reason],incompatible:false}));
 for(const reason of incompatible)choices.push({reason,label:labels[reason]||`Unsupported saved reason (${reason})`,incompatible:true});
 return `<div class="reason-options" role="group" aria-label="${question.toUpperCase()} reason choices">${choices.map(({reason,label,incompatible:bad},i)=>`<label class="structured-choice ${bad?'reason-incompatible':''}"><input id="${question}-reason-${i}" type="checkbox" data-reason-question="${question}" value="${escapeHtml(reason)}" ${selection.reasons.includes(reason)?'checked':''}><span>${escapeHtml(label)}${bad?' · review or remove':''}</span></label>`).join('')||'<p class="helper">Choose the Yes/No/Unclear answer above to see compatible reasons.</p>'}</div>${incompatible.length?'<p class="notice">A saved reason no longer matches this answer. Remove it or change the answer before continuing.</p>':''}`;
}
function turnChoices(question,selection){
 return `<div class="turn-choices" role="group" aria-label="${question.toUpperCase()} supporting conversation turns">${currentTurns().map((turn,i)=>{
  const selected=selection.supporting_turns.includes(turn.index),short=String(turn.text||'').replace(/\s+/g,' ').trim().slice(0,140);
  return `<label class="turn-choice"><input id="${question}-turn-${i}" type="checkbox" data-support-turn="${question}" value="${turn.index}" ${selected?'checked':''}><span><b>Turn ${turn.index}</b> · ${escapeHtml(turn.role)}${short?`: ${escapeHtml(short)}${turn.text.length>140?'…':''}`:''}</span></label>`;
 }).join('')}</div>`;
}
function requirementChoices(question,selection){return selectionCheckboxes(question,'requirement-field',requirementFieldOptions(),selection.fields,'requirement-field-choices')}
function legacyText(a,question){
 const text=question==='q3'?a.legacy_rationales?.q3:a.legacy_rationales?.q4;
 if(!text)return '';
 return `<details class="legacy-evidence"><summary>Prior text retained from an earlier checkpoint</summary><p><b>Earlier ${question.toUpperCase()} rationale (not converted into a reason):</b><br>${escapeHtml(text)}</p></details>`;
}
function legacyNote(a){return a.legacy_notes?`<details class="legacy-evidence"><summary>Prior issue note (not converted into structured evidence)</summary><p>${escapeHtml(a.legacy_notes)}</p></details>`:''}
function reasonSection(question,number,title,description,answerValue,selection,a){
 const hasCustom=selection.reasons.some(reason=>reason==='other'||reason.startsWith('ambiguous_or_conflicting'));
 const explanationLabel=selection.reasons.includes('other')?'Explain the reason not covered above':'Describe the ambiguity or conflict';
 const answerField=question==='q3'?'decisive_update_dependence':'whole_action_dependence';
 const turnHelp=answerValue==='no'?'Because you answered No, select at least one turn before the decisive update. “Multiple earlier turns” requires two earlier turns.':question==='q3'?'Select the turn or turns that support this answer.':'Select a turn that supports this answer.';
 const rationale=question==='q3'?a.decisive_update_dependence_rationale:a.whole_action_dependence_rationale;
 return `<div class="qgroup reason-section"><h3 class="qtitle"><span class="qnum">${number}</span> ${title}</h3><div class="helper">${description}</div>
 ${answerChoices(answerField,[['yes','Yes'],['no','No'],['unclear','Unclear']])}<div class="helper">Unclear means the distinction cannot be established reliably.</div>
 <fieldset class="reason-fieldset"><legend>Reason(s) · choose one or more</legend>${reasonOptions(question,answerValue,selection)}</fieldset>
 <fieldset class="reason-fieldset"><legend>Supporting turn(s) · required</legend><div class="helper">${turnHelp} ${question==='q4'?'“Multiple earlier requirements” requires at least two requirement or field selections; they may occur in the same turn.':''}</div>${turnChoices(question,selection)}</fieldset>
 <fieldset class="reason-fieldset"><legend>Relevant requirement type or field · ${question==='q4'&&selection.reasons.includes('multiple_earlier_requirements_needed')?'select at least two for multiple earlier requirements':'optional when the reason is specific'}</legend>${requirementChoices(question,selection)}</fieldset>
 ${hasCustom?`<label class="field-label">${escapeHtml(explanationLabel)}<textarea class="note-input" data-reason-explanation="${question}" placeholder="Add a short, specific explanation…">${escapeHtml(selection.explanation)}</textarea></label>`:''}
 ${legacyText(a,question)}<div class="generated-rationale" aria-live="polite"><b>Generated rationale</b><p id="${question}-rationale-preview">${escapeHtml(rationale||'Select a compatible reason and supporting turn(s) to preview the rationale.')}</p></div></div>`;
}
function issueTriggers(a){
 const out=[];
 if(a.semantic_relation==='meaning_changed')out.push({key:'semantic_meaning_changed',type:'semantic_meaning_changed',label:'Meaning changed'});
 if(a.semantic_relation==='ambiguous')out.push({key:'semantic_ambiguity',type:'semantic_ambiguity',label:'Ambiguous meaning'});
 if(a.linguistic_quality==='unnatural_or_unclear')out.push({key:'linguistic_defect',type:'linguistic_defect',label:'Unnatural or unclear language'});
 for(const code of a.issue_codes)out.push({key:`issue_code:${code}`,type:code,label:TAXONOMY.issue_types[code]});
 for(const [key,label] of CK)if(a.checklist[key]===false)out.push({key:`checklist:${key}`,type:'failed_checklist_item',label:`Failed checklist: ${label}`});
 if(a.other_issue)out.push({key:'other',type:'other',label:'Other / not covered'});
 return out;
}
function reportFieldOptions(){return [...requirementFieldOptions(),'Other / not covered']}
function emptyIssueReport(){return {turn_index:'',field:'',field_other:'',expected:'',observed:'',explanation:'',explanation_required:false}}
function issueReportMarkup(trigger,record,index,total){
 const fieldValue=record.field||'',needsPair=TAXONOMY.value_pair_types.includes(trigger.type),needsExplanation=TAXONOMY.explanation_types.includes(trigger.type)||(needsPair&&record.explanation_required);
 const turnOptions=currentTurns().map(turn=>`<option value="${turn.index}" ${String(record.turn_index)===String(turn.index)?'selected':''}>Turn ${turn.index} · ${escapeHtml(turn.role)}</option>`).join('');
 const fields=reportFieldOptions().map(field=>`<option value="${escapeHtml(field)}" ${fieldValue===field?'selected':''}>${escapeHtml(field)}</option>`).join('');
 return `<div class="issue-report"><div class="issue-report-head"><b>${escapeHtml(trigger.label)} · detail ${index+1}</b>${total>1?`<button type="button" class="mini-btn" data-report-action="remove" data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}">Remove this detail</button>`:''}</div>
 <label class="field-label">Relevant conversation turn<select data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="turn_index"><option value="">Select a turn</option>${turnOptions}</select></label>
 <label class="field-label">Affected field or requirement<select data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="field"><option value="">Select a field or requirement</option>${fields}</select></label>
 ${fieldValue==='Other / not covered'?`<label class="field-label">Name the affected field or requirement<input type="text" data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="field_other" value="${escapeHtml(record.field_other)}" placeholder="Short field or requirement name"></label>`:''}
 ${needsPair?`<div class="evidence-pair"><label class="field-label">Expected meaning/value<input type="text" data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="expected" value="${escapeHtml(record.expected)}" placeholder="What should this turn say?"></label><label class="field-label">Observed meaning/value<input type="text" data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="observed" value="${escapeHtml(record.observed)}" placeholder="What does it say instead?"></label></div>`:''}
 ${needsPair?`<label class="issue-check"><input type="checkbox" data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="explanation_required" ${record.explanation_required?'checked':''}>This problem is complex or not fully captured above</label>`:''}
 ${needsExplanation?`<label class="field-label">${needsPair?'Additional specific explanation':'Specific explanation'}<textarea class="note-input" data-report-trigger="${escapeHtml(trigger.key)}" data-report-index="${index}" data-report-property="explanation" placeholder="Describe the ambiguity, language issue, or uncategorized problem…">${escapeHtml(record.explanation)}</textarea></label>`:''}</div>`;
}
function renderIssueReports(a){
 const triggers=issueTriggers(a);
 if(!triggers.length)return '<p class="helper clean-note">No issue note is needed for a clean variant.</p>';
 return triggers.map(trigger=>{
  const reports=a.issue_reports[trigger.key]||[emptyIssueReport()];
  return `<section class="issue-trigger"><h4>${escapeHtml(trigger.label)}</h4>${reports.map((record,index)=>issueReportMarkup(trigger,record,index,reports.length)).join('')}<button type="button" class="mini-btn" data-report-action="add" data-report-trigger="${escapeHtml(trigger.key)}">+ Add another detail</button></section>`;
 }).join('');
}
function renderForm(){
 const a=answer();syncDerived(a);
 $('assessment-fields').innerHTML=`${ui.legacyNotice?'<div class="notice legacy-import-notice" role="status">This checkpoint includes answers from an earlier workspace. Earlier rationales and notes remain visible as legacy text and were not converted into reason selections.</div>':''}<div class="qgroup"><h3 class="qtitle"><span class="qnum">01</span> Does the conversation preserve the intended meaning?</h3><div class="helper">Compare with the canonical specification. Check amounts, times, roles, permission changes and context.</div>${answerChoices('semantic_relation',[['equivalent','Equivalent'],['meaning_changed','Meaning changed'],['ambiguous','Ambiguous']])}</div>
 <div class="qgroup"><h3 class="qtitle"><span class="qnum">02</span> How natural is the language?</h3><div class="helper">Assess the actual language variant, not only whether you understand it.</div>${answerChoices('linguistic_quality',[['natural','Natural'],['acceptable_variation','Acceptable variation'],['unnatural_or_unclear','Unnatural or unclear']])}</div>
 ${reasonSection('q3','03','Can the decisive update be determined without earlier conversation?','Can the effective requirement introduced, revised, revoked, or preserved by the decisive turn be determined without referring to earlier conversational information? Yes means it can; No means earlier context is needed.',a.decisive_update_dependence,a.q3_selection,a)}
 ${reasonSection('q4','04','Can the whole-action validity be determined from the decisive turn, action, and public contract alone?','Consider every requirement needed to establish the verdict, including an independent violation or a separate earlier permission. Yes means the displayed decisive turn, action, and public contract are sufficient; No means earlier conversation is needed.',a.whole_action_dependence,a.q4_selection,a)}
 <div class="qgroup"><h3 class="qtitle"><span class="qnum">05</span> Quality-control checklist</h3><div class="helper">Answer all eight independently for this variant.</div>${CK.map(([key,label])=>`<div class="checkline"><span>${escapeHtml(label)}</span><div class="tiny-actions"><label><input id="check-${key}-yes" type="radio" name="ck_${key}" data-checklist="${key}" value="yes" ${a.checklist[key]===true?'checked':''}><span>Yes</span></label><label class="no"><input id="check-${key}-no" type="radio" name="ck_${key}" data-checklist="${key}" value="no" ${a.checklist[key]===false?'checked':''}><span>No</span></label></div></div>`).join('')}</div>
 <div class="qgroup"><h3 class="qtitle"><span class="qnum">06</span> Identify specific problems</h3><div class="helper">Select all existing issue codes that apply. A structured evidence form appears for each selected issue or failed item.</div><div class="issue-list">${ISSUE_CODES.map(([code,label])=>`<label class="issue-check"><input type="checkbox" data-issue-code="${code}" ${a.issue_codes.includes(code)?'checked':''}>${escapeHtml(label)}</label>`).join('')}<label class="issue-check"><input type="checkbox" data-other-issue ${a.other_issue?'checked':''}>Other / not covered</label></div></div>
 <div class="qgroup"><h3 class="qtitle"><span class="qnum">07</span> Structured issue evidence ${issueTriggers(a).length?'(required for each selected problem)':'(none needed for a clean variant)'}</h3><div class="helper">Identify the affected turn and field or requirement. Supply expected and observed meaning/value when requested. For complex categorized problems, select the additional-explanation option. Uncovered issues require a specific explanation.</div>${legacyNote(a)}${renderIssueReports(a)}<div id="notes-preview" class="generated-rationale" aria-live="polite" ${a.notes?'':'hidden'}><b>Notes in final export</b><p>${escapeHtml(a.notes)}</p></div></div>
 <p class="notice" id="form-warning" aria-live="polite"></p>`;
 $('form-warning').textContent='';
}
function valueText(v){if(v==null)return '—';if(typeof v==='string'||typeof v==='number')return String(v);if(v.$decimal!==undefined)return v.$decimal;if(v.$datetime!==undefined)return v.$datetime;if(v.$money!==undefined)return JSON.stringify(v.$money);if(v.amount!==undefined&&v.currency_code!==undefined)return `${valueText(v.amount)} ${v.currency_code}`;return JSON.stringify(v)}
function requirement(r){return `${r.kind||r.type||'requirement'}${r.value!==undefined?`: ${valueText(r.value)}`:''}${r.unit?` ${r.unit}`:''}`}
function referenceSummary(sc,hi){const h=sc.formal.histories[hi],out=[];for(const r of h.initial_state?.requirements||[])out.push({label:'Initially active',text:requirement(r)});for(const g of h.initial_state?.grants||[])out.push({label:'Initially permitted',text:`${g.key?.permission||g.grant_id} · ${g.key?.scope?.entity_id||'all contexts'}`});for(const e of h.events_in_order||h.events||[]){const t=e.$type||'Event';const msg=e.replacement||e.requirement?requirement(e.replacement||e.requirement):e.asserted_key?`permission ${e.asserted_key.permission}`:e.grant_id||e.constraint_id||'';out.push({label:t.replace(/([a-z])([A-Z])/g,'$1 $2'),text:msg})}return out}
function renderReading(){
 const sc=SOURCE[ui.scenario],history=sc.histories[ui.history],cond=LANGS[ui.condition];
 $('scenario-step').textContent=`SCENARIO ${String(ui.scenario+1).padStart(2,'0')} / ${SOURCE.length}`;$('scenario-domain').textContent=sc.domain.replace(/_/g,' ');$('scenario-name').textContent=sc.id;$('scenario-description').textContent=`${sc.kind.replace(/_/g,' ')} · ${sc.family.replace(/_/g,' ')} · Compare the intended content against the displayed conversation.`;
 $('hist-switcher').innerHTML=sc.histories.map((h,i)=>`<button type="button" data-history="${i}" class="${i===ui.history?'active':''}" aria-pressed="${i===ui.history}">History ${i+1}</button>`).join('');
 $('lang-switcher').innerHTML=LANGS.map((condition,i)=>`<button type="button" data-condition="${i}" class="${ui.condition===i?'active':''}" aria-pressed="${ui.condition===i}">${condition.replace('-','–')}</button>`).join('');
 const tool=sc.tool,pars=tool.action?.parameters||{},schemaText=(tool.parameters||[]).map(p=>`${p.name}: ${p.type}${p.required?' (required)':' (optional)'}`).join('; '),permText=(tool.required_permissions||[]).join(', ');
 $('action-card').innerHTML=`<div class="card-title">Action being assessed · same across both histories</div><div class="action-name">${escapeHtml(tool.tool_name)}</div><div class="action-desc">${escapeHtml(tool.tool_description)}</div><div class="params">${Object.entries(pars).map(([key,value])=>`<span class="param"><b>${escapeHtml(key)}</b> · ${escapeHtml(valueText(value))}</span>`).join('')}</div><p class="fine">${tool.irreversible?'Irreversible action. ':'Reversible or preparatory action. '}${schemaText?'Tool contract: '+escapeHtml(schemaText)+'. ':''}${permText?'Requires permission: '+escapeHtml(permText):''}</p>`;
 const facts=sc.formal.shared_context||[],ref=referenceSummary(sc,ui.history);$('reference-content').innerHTML=`${facts.map(f=>`<div class="reference-row"><strong>Context:</strong> ${escapeHtml(f.value||'')}</div>`).join('')}${ref.map(r=>`<div class="reference-row"><strong>${escapeHtml(r.label)}:</strong> ${escapeHtml(r.text)}</div>`).join('')}<details style="margin-top:12px"><summary class="fine">View complete canonical source JSON</summary><pre class="pre">${escapeHtml(JSON.stringify({tool:sc.tool,formal:sc.formal},null,2))}</pre></details>`;
 $('conversation').innerHTML=history.variants[cond].map((turn,index)=>`<div class="turn"><div class="num">${turn.index}</div><div class="bubble ${turn.role==='assistant'?'assistant':''} ${index===history.variants[cond].length-1?'dec':''}"><div class="bubble-head">${escapeHtml(turn.role)} · ${escapeHtml(turn.lang)}${index===history.variants[cond].length-1?' · DECISIVE TURN':''}</div><div dir="auto">${escapeHtml(turn.text)}</div></div></div>`).join('');
 const other=sc.histories[1-ui.history].variants[cond];$('compare-content').innerHTML=`<div class="fine" style="margin:10px 0">History ${ui.history===0?2:1} · ${cond}. Check that only the intended decisive meaning differs.</div>${other.map(turn=>`<div class="comp-bubble"><b>${turn.index} · ${escapeHtml(turn.role)}</b><div dir="auto">${escapeHtml(turn.text)}</div></div>`).join('')}`;
 $('compare-language-content').innerHTML=LANGS.map(condition=>`<div class="comp-bubble"><b>${condition}</b>${history.variants[condition].map(turn=>`<div style="margin-top:8px" dir="auto"><span class="small">${turn.index} · ${escapeHtml(turn.role)}</span> ${escapeHtml(turn.text)}</div>`).join('')}</div>`).join('');
}
function complete(key){return itemComplete(key)}
function updateGlobal(){
 const done=counts();$('total-count').textContent=`${done} / ${ITEMS.length} complete`;$('global-fill').style.width=`${done/ITEMS.length*100}%`;$('scene-done').textContent=SOURCE.reduce((count,scenario,index)=>count+(ITEMS.filter(item=>item.si===index).every(item=>complete(item.key))?1:0),0);const current=ui.answers[keyOf()];
 $('item-status').textContent=complete(keyOf())?'Reviewed ✓':current?'In progress':'Not reviewed';$('item-status').classList.toggle('empty',!complete(keyOf()));$('export-jsonl').disabled=done!==448||!ui.bindings;$('save-next').textContent=complete(keyOf())?'Saved · next →':'Save & next →';
}
function sceneLabel(sc){return sc.domain.replace(/_/g,' ')+' · '+sc.family.replace(/_/g,' ')}
function renderNav(){const filter=$('scene-filter').value.toLowerCase().trim();$('scenarios-nav').innerHTML=SOURCE.map((sc,si)=>{const count=ITEMS.filter(item=>item.si===si&&complete(item.key)).length;if(filter&&!(`${sc.id} ${sceneLabel(sc)}`.toLowerCase().includes(filter)))return '';return `<button class="scene ${ui.scenario===si?'active':''}" data-go-scene="${si}" title="${escapeHtml(sceneLabel(sc))}"><span class="scene-count">${String(si+1).padStart(2,'0')}</span><span class="scene-info"><span class="scene-name" style="display:block">${escapeHtml(sc.id)}</span><span class="scene-sub" style="display:block">${escapeHtml(sceneLabel(sc))}</span></span><span class="scene-badge">${count}/8</span></button>`}).join('')}
function renderAll(){renderNav();renderReading();renderForm();updateGlobal()}
function navigate(delta){const current=byKey.get(keyOf()),next=Math.max(0,Math.min(ITEMS.length-1,current+delta)),item=ITEMS[next];ui.scenario=item.si;ui.history=item.hi;ui.condition=item.ci;save();renderAll();$('reading').scrollIntoView({behavior:'instant',block:'start'})}
function jumpUnfinished(){const current=byKey.get(keyOf());for(let offset=1;offset<=ITEMS.length;offset++){const item=ITEMS[(current+offset)%ITEMS.length];if(!complete(item.key)){ui.scenario=item.si;ui.history=item.hi;ui.condition=item.ci;save();renderAll();return}}alert('All 448 variants are complete. You can export the final JSONL.')}
function keyForRerender(target){if(target.id)return target.id;if(target.dataset?.reportProperty!==undefined)return `report:${JSON.stringify([target.dataset.reportTrigger,target.dataset.reportIndex,target.dataset.reportProperty])}`;if(target.dataset?.reportAction==='add')return `report:${JSON.stringify([target.dataset.reportTrigger,Math.max(0,(answer().issue_reports[target.dataset.reportTrigger]||[]).length-1),'turn_index'])}`;for(const name of ['answer','reasonQuestion','supportTurn','requirementField','issueCode','otherIssue','checklist','reportTrigger','reportIndex','reportProperty'])if(target.dataset?.[name]!==undefined)return `${name}:${target.dataset[name]}`;return ''}
function restoreFocus(id){if(!id)return;let target=document.getElementById(id);if(!target){if(id.startsWith('report:')){const [trigger,index,property]=JSON.parse(id.slice(7));target=document.querySelector(`[data-report-trigger="${CSS.escape(trigger)}"][data-report-index="${CSS.escape(String(index))}"][data-report-property="${CSS.escape(property)}"]`)}else{const [key,value]=id.split(':');if(key&&value!==undefined)target=document.querySelector(`[data-${key.replace(/[A-Z]/g,m=>'-'+m.toLowerCase())}="${CSS.escape(value)}"]`)}}if(target)target.focus({preventScroll:true})}
function refreshForm(target){const focused=keyForRerender(target);renderForm();updateGlobal();renderNav();restoreFocus(focused)}
function updateGeneratedPreviews(a){for(const [id,value] of [['q3-rationale-preview',a.decisive_update_dependence_rationale],['q4-rationale-preview',a.whole_action_dependence_rationale]]){const node=$(id);if(node)node.textContent=value||'Select a compatible reason and supporting turn(s) to preview the rationale.'}const notes=$('notes-preview');if(notes){notes.hidden=!a.notes;const paragraph=notes.querySelector('p');if(paragraph)paragraph.textContent=a.notes}}
function reportFor(a,key,index){if(!Array.isArray(a.issue_reports[key]))a.issue_reports[key]=[];while(a.issue_reports[key].length<=index)a.issue_reports[key].push(emptyIssueReport());return a.issue_reports[key][index]}
function handleForm(event){
 const target=event.target,a=answer();let rerender=false;
 if(target.dataset.answer){a[target.dataset.answer]=target.value;rerender=true}
 else if(target.dataset.checklist){a.checklist[target.dataset.checklist]=target.value==='yes';rerender=true}
 else if(target.dataset.issueCode){const selected=new Set(a.issue_codes);target.checked?selected.add(target.dataset.issueCode):selected.delete(target.dataset.issueCode);a.issue_codes=ISSUE_CODES.map(([code])=>code).filter(code=>selected.has(code));rerender=true}
 else if(target.hasAttribute('data-other-issue')){a.other_issue=target.checked;rerender=true}
 else if(target.dataset.reasonQuestion){const selection=target.dataset.reasonQuestion==='q3'?a.q3_selection:a.q4_selection,values=new Set(selection.reasons);target.checked?values.add(target.value):values.delete(target.value);selection.reasons=[...values];rerender=true}
 else if(target.dataset.supportTurn){const selection=target.dataset.supportTurn==='q3'?a.q3_selection:a.q4_selection,value=Number(target.value),values=new Set(selection.supporting_turns);target.checked?values.add(value):values.delete(value);selection.supporting_turns=[...values].sort((x,y)=>x-y)}
 else if(target.dataset.requirementField){const selection=target.dataset.requirementField==='q3'?a.q3_selection:a.q4_selection,values=new Set(selection.fields);target.checked?values.add(target.value):values.delete(target.value);selection.fields=[...values]}
 else if(target.dataset.reasonExplanation){const selection=target.dataset.reasonExplanation==='q3'?a.q3_selection:a.q4_selection;selection.explanation=target.value}
 else if(target.dataset.reportTrigger){const record=reportFor(a,target.dataset.reportTrigger,Number(target.dataset.reportIndex));record[target.dataset.reportProperty]=target.dataset.reportProperty==='turn_index'?(target.value===''?'':Number(target.value)):target.type==='checkbox'?target.checked:target.value;if(['field','explanation_required'].includes(target.dataset.reportProperty))rerender=true}
 else return;
 syncDerived(a);save();if(rerender)refreshForm(target);else{updateGeneratedPreviews(a);updateGlobal();renderNav();if($('form-warning'))$('form-warning').textContent=''}
}
function handleReportAction(event){const button=event.target.closest('[data-report-action]');if(!button)return;const a=answer(),key=button.dataset.reportTrigger,index=Number(button.dataset.reportIndex);if(button.dataset.reportAction==='add')reportFor(a,key,(a.issue_reports[key]||[]).length);else if(button.dataset.reportAction==='remove'){a.issue_reports[key].splice(index,1);if(!a.issue_reports[key].length)delete a.issue_reports[key]}syncDerived(a);save();refreshForm(button)}
function checkpointData(){for(const [key,answer] of Object.entries(ui.answers))syncDerived(answer,key);return {format:'p2c-review-draft-3',reason_taxonomy_version:TAXONOMY.version,legacy_imported:ui.legacyNotice,slot:SLOT,source_fingerprint:SOURCE_FINGERPRINT,answers:ui.answers,position:[ui.scenario,ui.history,ui.condition]}}
function save(){try{localStorage.setItem(localKey,JSON.stringify(checkpointData()));$('binding-state').textContent='Autosaved in this browser · export checkpoints regularly';$('binding-state').classList.remove('danger')}catch(error){$('binding-state').textContent='Browser storage unavailable · use Save checkpoint regularly';$('binding-state').classList.add('danger')}}
function download(name,content,type='application/json'){const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),3000)}
function checkpoint(){download(`p2c-${SLOT}-checkpoint-v3.json`,JSON.stringify(checkpointData(),null,2)+'\n')}
function checkpointConfig(){return {slot:SLOT,source_fingerprint:SOURCE_FINGERPRINT,legacy_source_fingerprints:REVIEW_DATA.legacy_source_fingerprints||[],valid_item_ids:ITEMS.map(item=>item.key),valid_turns_by_item:Object.fromEntries(ITEMS.map(item=>[item.key,SOURCE[item.si].histories[item.hi].variants[LANGS[item.ci]].map(turn=>turn.index)])),checklist_keys:checklistKeys,reason_taxonomy_version:TAXONOMY.version,scenario_count:SOURCE.length}}
function restore(data){const restored=logic.restoreCheckpoint(data,checkpointConfig());ui.answers=restored.answers;ui.scenario=restored.position[0];ui.history=restored.position[1];ui.condition=restored.position[2];ui.legacyNotice=restored.legacyImported;save();renderAll()}
function exportComplete(){
 const done=counts();if(done!==448){alert(`Only ${done} of 448 variants are complete. Use Next unfinished to locate the remaining assessments.`);return}if(!ui.bindings||!ui.template){alert('The embedded source package has not passed hash verification.');return}
 const templateById=new Map(ui.template.map(row=>[row.example_id,row])),used=new Set(),lines=[];
 for(const item of ITEMS){const binding=ui.bindings.get(item.key),source=templateById.get(binding?.example_id);if(!source||used.has(binding.example_id)||source.example_sha256!==binding.example_sha256||source.canonical_scenario_sha256!==binding.canonical_scenario_sha256)throw Error('Binding or source hash mismatch during export.');used.add(binding.example_id);const a=syncDerived(ui.answers[item.key],item.key),row={...source,reviewer_id:SLOT};for(const field of KEY_FIELDS)row[field]=field==='checklist'?Object.fromEntries(CK.map(([key])=>[key,a.checklist[key]])):field==='issue_codes'?[...a.issue_codes]:a[field];lines.push(JSON.stringify(row))}
 if(lines.length!==448||used.size!==448)throw Error('The complete export has missing or duplicate rows.');download(`p2c-${SLOT}-completed.jsonl`,lines.join('\n')+'\n','application/x-ndjson;charset=utf-8');
}
function bindSource(){
 const packetByKey=new Map(),idHash=new Map();if(REVIEW_DATA.packets.length!==56)throw Error(`Expected 56 scenario packets; found ${REVIEW_DATA.packets.length}.`);
 for(const packet of REVIEW_DATA.packets){if(packet.reviewer_slot!==SLOT||!packet.canonical_scenario_sha256||!SOURCE.some(sc=>sc.id===packet.scenario_id)||packet.language_variants?.length!==8)throw Error('Packet reviewer slot, source, or variant count is invalid.');const scenario=SOURCE.find(sc=>sc.id===packet.scenario_id);
  for(const variant of packet.language_variants){const key=`${packet.scenario_id}|${variant.history_id}|${variant.condition}`;if(packetByKey.has(key)||!byKey.has(key))throw Error('A packet variant is duplicate or cannot be mapped: '+key);const shown=scenario.histories.find(history=>history.id===variant.history_id)?.variants?.[variant.condition],turns=variant.turns?.map(turn=>({index:turn.turn_index,role:turn.speaker,text:turn.segments.map(segment=>segment.text).join('').trim()}));if(!shown||turns.length!==shown.length||turns.some((turn,index)=>turn.index!==shown[index].index||turn.role!==shown[index].role||turn.text!==shown[index].text.trim()))throw Error('Displayed conversation differs from its source packet. Stop and contact the research owner.');packetByKey.set(key,{example_id:variant.derivative_id,example_sha256:variant.example_sha256,canonical_scenario_sha256:packet.canonical_scenario_sha256});if(idHash.has(variant.derivative_id))throw Error('Duplicate derivative ID across packets.');idHash.set(variant.derivative_id,{example_sha256:variant.example_sha256,canonical_scenario_sha256:packet.canonical_scenario_sha256})}
 }
 if(packetByKey.size!==448)throw Error(`Expected 448 source bindings, found ${packetByKey.size}.`);const templateById=new Map(ui.template.map(row=>[row.example_id,row]));if(templateById.size!==448||[...idHash].some(([id,hash])=>!templateById.has(id)||templateById.get(id).example_sha256!==hash.example_sha256||templateById.get(id).canonical_scenario_sha256!==hash.canonical_scenario_sha256))throw Error('Template IDs and hashes do not match the assigned packets.');ui.bindings=packetByKey;$('binding-state').textContent='Source package verified: 56 scenarios · 448 variants · original hashes aligned';$('binding-state').classList.remove('danger');updateGlobal();
}
function bindingFailure(error){$('binding-state').textContent='Cannot verify source package: '+error.message;$('binding-state').classList.add('danger');$('export-jsonl').disabled=true}
function exportGuidance(){const exportButton=$('export-jsonl');exportButton.disabled=counts()!==448||!ui.bindings}
$('hist-switcher').addEventListener('click',event=>{const button=event.target.closest('[data-history]');if(button){ui.history=Number(button.dataset.history);save();renderAll()}});
$('lang-switcher').addEventListener('click',event=>{const button=event.target.closest('[data-condition]');if(button){ui.condition=Number(button.dataset.condition);save();renderAll()}});
$('scenarios-nav').addEventListener('click',event=>{const button=event.target.closest('[data-go-scene]');if(button){ui.scenario=Number(button.dataset.goScene);ui.history=0;ui.condition=0;save();renderAll()}});
$('scene-filter').addEventListener('input',renderNav);
$('assessment-fields').addEventListener('input',handleForm);$('assessment-fields').addEventListener('change',handleForm);$('assessment-fields').addEventListener('click',handleReportAction);
$('save-next').addEventListener('click',()=>{const missing=problems(answer());if(missing.length){$('form-warning').textContent='Before marking this variant complete: '+missing.join(' · ');$('form-warning').scrollIntoView({behavior:'smooth',block:'center'});save();return}save();navigate(1)});
$('previous-item').addEventListener('click',()=>navigate(-1));$('jump-next').addEventListener('click',jumpUnfinished);$('guide-btn').addEventListener('click',()=>$('guide-modal').classList.remove('hide'));$('close-guide').addEventListener('click',()=>{$('guide-modal').classList.add('hide');try{localStorage.setItem(localKey+'-seen','1')}catch(error){}});
$('draft-btn').addEventListener('click',checkpoint);$('load-draft').addEventListener('click',()=>$('draft-file').click());$('draft-file').addEventListener('change',async event=>{const file=event.target.files?.[0];if(!file)return;try{restore(JSON.parse(await file.text()))}catch(error){alert('Checkpoint could not be restored: '+error.message+'. The original file remains unchanged.')}event.target.value=''});$('export-jsonl').addEventListener('click',exportComplete);
window.addEventListener('keydown',event=>{if(event.altKey&&event.key==='ArrowRight'){event.preventDefault();navigate(1)}if(event.altKey&&event.key==='ArrowLeft'){event.preventDefault();navigate(-1)}});
(function init(){
 try{
  let loaded=false;const raw=localStorage.getItem(localKey);if(raw){const saved=JSON.parse(raw);if(saved.format==='p2c-review-draft-3'&&saved.slot===SLOT&&saved.source_fingerprint===SOURCE_FINGERPRINT){restore(saved);loaded=true}}
  if(!loaded){for(const fingerprint of REVIEW_DATA.legacy_source_fingerprints||[]){const previousKey=`p2c-reviewer-workspace-${SLOT}-${fingerprint}`,previous=localStorage.getItem(previousKey);if(!previous)continue;const saved=JSON.parse(previous);if(['p2c-review-draft-1','p2c-review-draft-2','p2c-review-draft-3'].includes(saved.format)&&saved.slot===SLOT&&saved.source_fingerprint===fingerprint){restore(saved);loaded=true;break}}}
  if(localStorage.getItem(localKey+'-seen'))$('guide-modal').classList.add('hide');
 }catch(error){$('binding-state').textContent='Saved browser data needs review: '+error.message;$('binding-state').classList.add('danger')}
 try{bindSource()}catch(error){bindingFailure(error)}renderAll();
})();
