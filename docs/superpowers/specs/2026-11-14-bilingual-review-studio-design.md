# Bilingual reviewer studio design

## Intent

Replace the read-only P2C bilingual side-by-side viewer as the reviewers' primary work page. Deliver one standalone offline HTML workspace for each reviewer slot, with that slot's current 56 scenario packets and 448 blank hash-bound annotation rows embedded.

## Goals and boundaries

- Preserve the 56-scenario / 448-variant review scope, source hashes, assigned reviewer slots, and `p2b1-annotation-2` contract.
- Keep the supplied Reviewer 2 studio's visual layout and interaction model: scenario navigation, history and language tabs, formal specification, action/tool card, bilingual comparisons, assessment fields, progress, and instructions.
- Require independent answers and rationales for each variant. Do not copy substantive assessments or rationales across variants.
- Bind autosaved drafts, exported checkpoints, and restored checkpoints to the reviewer slot and a fingerprint of the exact embedded source package.
- Export exactly 448 complete, hash-bound JSONL rows only when all required fields and issue explanations are present.
- Keep generated pages and all scenario/reviewer content under ignored `.research-data/`; publish only generator code, synthetic tests, and concise documentation.

No human annotations are created or inferred. No model predictions, oracle verdicts, or other-reviewer responses are included. The task does not change the research protocol or source scenarios.

## Approaches considered

1. Edit two HTML files by hand. This risks slot drift and makes template/hash updates hard to reproduce.
2. Generate both pages from the provided Reviewer 2 HTML shell and the existing private reviewer packets/templates. **Selected:** it preserves the owner's UI while applying the same validation and binding rules to both slots.
3. Rebuild a new reviewer application. Rejected because it discards the approved starting point and adds unnecessary review infrastructure.

## Architecture

`scripts/generate_p2c_reviewer_workspaces.py` reads the supplied HTML shell and the existing private P2C packet/template directories. It verifies all packet, item, reviewer-slot, schema, package-manifest, and source-hash mappings before embedding them. It then writes slot-specific standalone HTML to each existing private reviewer directory. The page computes draft-storage keys from an exact source fingerprint, restores only matching and well-formed drafts/checkpoints, and permits final export only after all 448 rows are complete and their IDs and source hashes still match. Synthetic completed exports are validated with the existing `parse_submission_jsonl` contract. The generator never reads reference keys or judge outputs.

## Validation

Unit tests use only synthetic packets/templates and synthetic completed annotations. They verify slot isolation, embedded source binding, stale-checkpoint rejection, absence of cross-variant copying, final-export completeness/hash integrity, and compatibility with the existing validator. A final local generation check compares every actual packet conversation and source hash with its rendered source and template; generated pages remain ignored and untracked.
