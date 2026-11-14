# P2C bilingual reviewer workspaces

The research-owner supplied review studio is the working interface for the two independent P2C reviewers. The generator embeds each reviewer's own current 56 scenario packets and 448 blank `p2b1-annotation-2` rows into a standalone offline HTML page. It validates the private package manifest and packet/template hashes before writing.

Generated files are private and ignored by Git:

- `.research-data/p2c-full/review-package/reviewer_slot_1/bilingual-review-studio.html`
- `.research-data/p2c-full/review-package/reviewer_slot_2/bilingual-review-studio.html`

## Regenerate after an approved source revision

Run from the repository root, using the current owner-supplied HTML shell:

```sh
./.venv/bin/python scripts/generate_p2c_reviewer_workspaces.py \
  --studio-html /path/to/bilingual-review-studio-reviewer-2.html
```

The command rejects changed source files that do not match the private package manifest. A regenerated workspace has a new source fingerprint when the shell, package, slot, packet, or template changes; drafts and checkpoint files from the earlier fingerprint will not load.

## Reviewer handoff

Give each reviewer only their assigned HTML file. They can open it directly in a current browser without installing software or loading packet/template files. The page displays one scenario at a time, with history and language-condition navigation, the same action for both histories, the public tool contract, the formal reference, and the English/MSA comparison views.

Review every displayed variant independently. Record semantic relation, linguistic quality, both dependence assessments with separate rationales, and all eight checklist answers. `Unclear` is available for either dependence judgment. Leave notes blank for clean items; explain any flagged problem briefly. The page never copies an answer or rationale to another variant.

Answers autosave in that browser. Reviewers should use **Save checkpoint** periodically and keep the downloaded JSON in a private location. To resume on another session, open the same assigned HTML and use **Restore checkpoint**. A checkpoint is rejected if its reviewer slot or source fingerprint differs. When the page reports all 448 variants complete, use **Export final JSONL** and return that file to the researcher through the established private channel. Do not share a checkpoint or export with the other reviewer.

The page does not create or infer human answers. Final exports remain subject to the existing strict P2C submission validator and adjudication workflow.
