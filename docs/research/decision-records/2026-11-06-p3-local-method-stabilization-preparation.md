# P3 Local Method Stabilization Preparation

**Date:** 2026-11-06

**Status:** Candidate methods and private competence-screen materials prepared for research-owner review; no qualification screen or study inference performed.

## Scope

This work followed the owner's authorization to stabilize local judging and translation methods before an independent English/MSA competence screen. It used the three already-installed local models and independent synthetic fixtures. It did not access locked evaluation items, change the dataset, run the competence screen, make remote or paid calls, or freeze the dataset.

## Prepared changes

- Added versioned candidate direct and single-call structured prompts that separate public tool conformance, effective conversational requirements, revision/preservation/revocation, and action validity.
- Added `structured-validity-v2`, which omits non-applicable requirements, reports applicable requirement assessments and evidence, and keeps tool conformance separate. V1 remains available. Added a post-inference coverage metric that does not repair outputs or verdicts.
- Retested the judges once with a predeclared 512-token structured-output limit. Generation-limit failures were absent in that retest; structural and verdict-consistency failures remained, so parser rules were not relaxed.
- Compared the preserved literal-shield translation procedure with one corrected contextual, unshielded TranslateGemma procedure. The corrected procedure retains prior turns only as language context, performs strict preservation checks, and records failures without reference-state repair.
- Prepared a private 48-item English/MSA competence-screen candidate and blank hash-bound bilingual quality-check package. The threshold remains at least 20/24 in each language and 10/12 in each validity class. No human review or screening result is claimed.
- Corrected planning documentation to distinguish 288 Arabic-bearing items from the number of Arabic-turn translation calls. Exact study calls remain unestimated until an authorized, validated manifest is available.

## Evidence and limits

The private synthetic-run package retains raw responses, attempt records, configuration and model digests, timing, parser status, and translation artifacts. A duplicate-listing defect in one preserved run record was handled only in analysis by deduplicating on execution ID; the original record was preserved and the runner corrected. A preceding run terminated during post-hoc scoring before it could persist its outputs; it is documented privately and is not treated as evidence.

The bounded synthetic results identify compatibility and consistency risks but do not establish model competence, bilingual quality, dataset validity, or benchmark performance. Translation checks are mechanical safeguards plus author-side inspection, not independent semantic validation. The private screen needs one focused independent bilingual quality check and research-owner acceptance before execution.

## Artifacts and remaining gate

- [Local method stabilization proposal](../proposals/2026-11-06-p3-local-method-stabilization-proposal.md)
- [Versioned P3 configuration proposal](../proposals/p3-experimental-config-proposals-v2.json)
- Private screen and run package: `.research-data/p3-local-method-stabilization/`

Research-owner review remains required for the candidate prompts and rubric, V2 schema/parser and coverage metric, V3 translation procedure and preservation policy, screen content and QC results, thresholds, and local execution settings. The independent screen must not run until those materials are accepted.
