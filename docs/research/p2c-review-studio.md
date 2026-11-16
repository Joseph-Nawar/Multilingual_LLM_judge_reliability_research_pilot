# P2C bilingual reviewer workspaces

The two standalone, offline reviewer pages embed separate reviewer-slot source packets and the matching blank 448-row `p2b1-annotation-2` template. The generator verifies the private manifest and packet/template hashes before writing. This structured-reason interface is a **prospective instrument improvement proposed for owner review**; it does not establish bilingual validation or change the dataset, hypotheses, model prompts, locked configuration, or inference gate. See [the proposal](proposals/2026-11-16-p2-structured-review-reasons.md) for the versioned taxonomy and rationale.

Generated pages remain private and ignored by Git:

- `.research-data/p2c-full/review-package/reviewer_slot_1/bilingual-review-studio.html`
- `.research-data/p2c-full/review-package/reviewer_slot_2/bilingual-review-studio.html`

## Regenerate after a source revision

Run from the repository root with the research-owner supplied HTML shell:

```sh
./.venv/bin/python scripts/generate_p2c_reviewer_workspaces.py \
  --studio-html /path/to/bilingual-review-studio-reviewer-2.html
```

The command rejects source files that do not match the current private package manifest. It rewrites each slot's existing page only after validating that slot's packets, all 448 template rows, and their hashes. Keep both outputs and all checkpoints in `.research-data/` or another private location; never stage or publish them.

## Independent review

Each reviewer independently assesses all 448 variants assigned to that reviewer. No variant is auto-approved or paired with another variant's answers. The workspace preserves the existing Yes/No/Unclear judgments, exact meanings, all eight checklist items, and the existing issue-code vocabulary. Q3 and Q4 remain separate and never infer one another's answers. The interface does not show judge predictions or oracle verdicts.

For Q3 and Q4, select a polarity, one or more compatible reasons, and at least one supporting turn. Select relevant requirement or field details where needed. “Multiple earlier turns needed” requires two turns; “Multiple earlier requirements needed” requires two requirement/field selections, which may point to one turn. The workspace generates the existing rationale strings from those explicit choices. A clean variant needs no notes. A semantic or linguistic defect, issue code, or failed checklist item opens a structured report for the relevant turn and field. Value discrepancies need expected and observed entries. Other, ambiguity, and complex or uncategorized problems need a specific explanation.

The page autosaves in that browser. Use **Save checkpoint** periodically and keep the downloaded JSON private. The private checkpoint records the original structured choices, issue evidence, generated strings, taxonomy version, reviewer slot, source fingerprint, and position. Final JSONL export includes only the existing `p2b1-annotation-2` fields and remains subject to the current strict submission validator and adjudication workflow.

## Checkpoint compatibility

- A current `p2c-review-draft-3` checkpoint restores in the same reviewer slot and reason-taxonomy version when its source fingerprint is current or is explicitly allowlisted by a previous workspace whose reviewer slot and complete item, variant, and canonical-scenario hash bindings match. This preserves already structured work across a UI-only regeneration with unchanged source hashes.
- A prior `p2c-review-draft-2` checkpoint with the same verified slot/source binding and taxonomy version is upgraded in memory. Existing structured selections and issue evidence are retained; reports from that format receive an unchecked additional-explanation choice because that control did not exist in that checkpoint version.
- A legacy `p2c-review-draft-1` checkpoint is offered for migration only when the previous generated workspace has the same reviewer slot and all item, variant, and canonical-scenario hashes match the current package. Existing judgments, checklist answers, issue codes, rationales, and notes are preserved. Old rationale and note text stays visibly marked as legacy evidence and is not converted into a selected reason or issue report. Reviewers must explicitly choose new Q3/Q4 reasons and provide any required structured issue evidence before an item can be complete.
- A different slot, changed source binding, or unrecognized checkpoint format is rejected with an explanation. The original checkpoint file is not modified and remains available for its matching workspace.

Never copy judgments between variants or reviewer slots. Automated checks of structure, hashes, or span coverage do not establish linguistic equivalence or human validation. The research dataset, reviewer source packets, annotations, and adjudication records remain unchanged by this proposed interface improvement.
