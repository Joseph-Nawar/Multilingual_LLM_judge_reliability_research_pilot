# Prospective P2 bilingual review-instrument improvement: structured reasons

**Status:** Proposed instrument improvement for owner review before full annotation. This records an interface and annotation-efficiency proposal; it does not change the research dataset, hypotheses, locked configuration, model prompts, oracle labels, action contracts, or the meanings and polarity of existing answers. It does not establish that any language variant has been human validated.

**Taxonomy version:** `paper2-structured-reasons-v1`.

## Purpose

Replace repetitive required prose for Q3 and Q4 with human-selected reason categories and optional supporting-turn/field selections. The offline form deterministically renders those selections into the existing required rationale strings. Keep Q3 (decisive-update dependence) and Q4 (whole-action dependence) independently answered and independently explained.

## Q3 decisive-update dependence reasons

The existing `yes`, `no`, and `unclear` values and their protocol meanings are unchanged. The interface requires at least one reason that is compatible with the selected answer, with no preselection:

| Answer | Available reason categories |
| --- | --- |
| `yes` | Explicit numeric requirement; Explicit temporal requirement; Explicit permission state; Complete restatement; Other / not covered |
| `no` | Earlier numeric value needed; Earlier temporal value needed; Earlier permission state needed; Earlier referent or scope needed; Multiple earlier turns needed; Other / not covered |
| `unclear` | Ambiguous or conflicting interpretation; Other / not covered |

Multiple compatible reasons may be selected. Selecting “Other / not covered” or “Ambiguous or conflicting interpretation” requires a brief explanation. A selected reason must identify at least one supporting conversation turn and may include the relevant requirement type or field. Because a `no` answer means earlier context is needed, it must cite at least one turn before the decisive update. “Multiple earlier turns needed” requires at least two turns before the decisive update.

## Q4 whole-action dependence reasons

Q4 retains its existing `yes`, `no`, and `unclear` meanings and is never populated from Q3. The interface requires at least one compatible reason, with no preselection:

| Answer | Available reason categories |
| --- | --- |
| `yes` | The decisive instruction alone establishes invalidity; All relevant requirements are available; Other / not covered |
| `no` | Earlier numerical constraint needed; Earlier temporal constraint needed; Earlier permission information needed; Earlier unrelated requirements needed; Multiple earlier requirements needed; Other / not covered |
| `unclear` | Ambiguous or conflicting information; Other / not covered |

Multiple compatible reasons may be selected. Selecting “Other / not covered” or “Ambiguous or conflicting information” requires a brief explanation. Reviewers can identify supporting turns and relevant requirements or fields independently of Q3. Because a `no` answer means earlier conversation is necessary, it must cite at least one turn before the decisive update. “Multiple earlier requirements needed” requires at least two selected requirement/field values; both may be supported by the same earlier turn.

For each rationale, the form deterministically includes the selected reason labels, selected supporting turn indices, selected requirement/field, and any required explanation. The rationale is generated from the reviewer's explicit selections and contains no model-generated judgment or generic placeholder.

## Defect evidence and notes

Clean variants need no notes. A semantic or linguistic defect, an issue code, or a failed checklist item opens a structured issue report. Each report identifies the selected problem category and requests the relevant turn and affected field or requirement. Expected and observed meanings/values are requested for value or meaning discrepancies. “Other / not covered” and novel or complex issues require a brief explanation. The interface generates a substantive, newline-separated `notes` value from these selections and does not accept a generic note as a substitute for issue evidence.

The existing issue-code vocabulary and all eight independent checklist answers are preserved. Generic placeholders such as “wrong” or “problem” are rejected for issue fields and expected/observed evidence. The final `notes` and rationale strings continue to satisfy the unchanged `p2b1-annotation-2` JSONL contract.

## Checkpoints and compatibility

Structured selections, the taxonomy version, generated rationale strings, and issue-report evidence are stored in a private checkpoint bound to reviewer slot and source fingerprint. The final JSONL export contains only the existing schema fields.

An earlier `p2c-review-draft-1` checkpoint may be imported only when the previous generated workspace records the same reviewer slot and exactly matching item, variant, and canonical-scenario hashes. Existing judgments, checklist values, issue codes, and text are carried forward as legacy material, but no reason is inferred or preselected. The reviewer must make the new reason selections and complete any newly required issue evidence. A checkpoint from a different source fingerprint is rejected with an explicit explanation; the file remains untouched for recovery in its original workspace. No import copies data between variants or reviewer slots.

## Integrity constraints

- Each reviewer independently assesses every assigned one of 448 variants.
- No paired variant is auto-approved and no judgment is copied between variants.
- Q3 and Q4 remain separate; no answer or reason is inferred from the other.
- No model-judge prediction, oracle verdict, or other-reviewer response is shown.
- All eight checklist answers remain independent and required.
- Existing source and scenario SHA-256 values remain unchanged.
- Automated structural checks do not establish bilingual semantic validation.
- This proposal does not authorize inference or change the pre-inference validation and freeze gate.
