# P2C Full Dataset Authoring Authorization

**Date:** 2026-11-03
**Status:** Accepted for dataset authoring and deterministic validation only.
**Decision owner:** Research owner, as stated in the authorization for this task.

## Authorization

The P2B four-scenario feasibility pilot is concluded. Its original annotations, follow-up records, unresolved dependence disagreements, and prior versions remain preserved. No additional pilot review or adjudication is authorized.

The research owner authorizes construction of the remaining planned dataset:

- 36 locked primary scenarios: three scenarios in each of the 12 domain × transition-family cells.
- 12 locked auxiliary no-change control scenarios.
- Together with the 12 existing development primary scenarios, the planned inventory is 60 canonical scenarios, 120 counterfactual histories, and 480 history-language items.

This authorization covers authoring and deterministic validation. It does not freeze or release the dataset, authorize model inference or paid API calls, or start P3, P4, or P5.

## Integrity conditions

- Existing development scenarios and all original pilot-review evidence are preserved; human annotations are not rewritten.
- Canonical formal states and deterministic executable rules remain the sole reference-label authority.
- Locked scenarios, controls, language drafts, labels, coverage maps, annotations, review packets, hashes, and other study data remain under ignored `.research-data/` paths.
- Ordinary judge-facing material must use an explicit allowlist and exclude canonical states, reference labels, oracle results, pair links, author-side dependence assessments, and internal provenance.
- Newly authored English/MSA variants remain machine-assisted and unvalidated until two qualified reviewers independently assess them, hash-bound disagreements are resolved, and required corrections are re-reviewed. The four scenarios covered by the completed P2B pilot retain their existing evidence and are excluded from new review tasks; no pilot annotations are requested or rewritten.
- Structural and oracle checks do not establish bilingual semantic equivalence, linguistic naturalness, or independent validation.
- Decisive-update dependence and whole-action dependence remain separate constructs. New author-side assessments are provisional, rationale-backed, and may remain `unclear`; no pilot disagreement is reinterpreted or adjudicated.
- The prospective 24/24 complexity target is evaluated and any unsupported allocation is reported. Examples are not distorted to manufacture a split.
- Template descriptions, reuse, lexical and semantic near-duplicate candidates, history-position balance, surface cues, control matches, deviations, exclusions, and hashes are reported privately.

## Remaining gate

The authored package is not frozen or ready for judge inference. Independent bilingual review, quality-control outcomes, resolution of material disagreements, owner review of deviations and feasibility findings, reviewed partition/run materials, and a later explicit authorization remain necessary before downstream evaluation or freeze.

## Provenance

This record documents the research-owner authorization supplied with the P2C full-dataset authoring task. It does not claim that authored examples have been human-reviewed or that the dataset has been scientifically approved.
