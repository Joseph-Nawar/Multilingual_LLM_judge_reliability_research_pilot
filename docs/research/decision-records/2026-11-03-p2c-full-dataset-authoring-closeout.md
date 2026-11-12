# P2C Full Dataset Authoring Closeout

**Date:** 2026-11-03
**Status:** Authoring and deterministic validation complete; dataset not frozen.
**Decision owner:** Research owner; this record reports implementation results and does not claim final scientific acceptance.

## Inventory and partition checks

The private authoring package contains 60 canonical scenarios: 48 primary scenarios (12 development and 36 locked primary) plus 12 locked auxiliary no-change controls. The package has 120 counterfactual histories and 480 history-language items. Each of the 12 primary domain × transition-family cells contains four primary scenarios: one development and three locked. Controls are separate from the primary dataset and occur four per domain.

All 60 counterfactual pairs use one structured action and have opposite deterministic validity labels. All 120 oracle records were checked. The 28 control restatement events left their effective states unchanged. Valid-history positions are balanced 6/6 in development, 18/18 in locked primary scenarios, and 6/6 in controls. Every history has all four language conditions; each condition has 120 items. Semantic-coverage maps structurally cover all 480 variants. These checks do not establish linguistic equivalence, naturalness, or human validation.

## Author-side complexity and content diversity

The new locked scenarios have provisional author-side decisive-update assessments, with rationales kept in the private package. The 12 preserved development scenarios were not reclassified, and the historical pilot disagreements remain unresolved. The proposed full-primary 24/24 complexity split is therefore not claimed; no examples were forced into categories to meet it. Whole-action dependence remains a separate assessment from understanding the decisive instruction.

The private package describes 22 authoring-template families across the 36 new locked primaries and 12 controls, and carries one semantic-recipe identifier per new scenario. Descriptions record the actual discourse mechanism and turn pattern; identifiers alone do not establish human-confirmed conceptual diversity. No template or recipe identifiers overlap between the new package and the existing development partition. Numeric and temporal polarity and direction allocations meet the blueprint's aggregate six/six and three/three targets.

Exact-duplicate and normalized-duplicate audits found no groups. Lexical screening flagged 24 candidate pairs: 12 overlap with declared control-to-primary matches and 12 additional candidates for contextual review. The automated audit does not adjudicate semantic duplication. The surface-feature audit identified one potential perfect association candidate for human review. No judge predictions were used to select or revise scenarios.

The 12 controls have 9 full matches and 3 partial matches to locked primaries; all 3 partial matches concern permission-scope comparisons, and none are unmatched. The control pair structure intentionally uses distinct initial states, followed by no-op restatements.

## Main-study quality-control package

The private package contains side-by-side English/MSA review materials, canonical state/event context, action and public-tool information, independent semantic and linguistic questions, separate decisive-update and whole-action questions with rationales, blank hash-bound annotations, and a disagreement tracker. Two reviewer slots cover 56 scenarios and 448 variants. The four pilot-reviewed scenarios (32 variants) are excluded from new review tasks; their original annotations and records were not rewritten or re-requested. The new review has not started and contains no fabricated responses.

The authored corpus, canonical states, oracle labels, review materials, manifests, and hashes remain under ignored `.research-data/`. Public documentation intentionally omits scenario content and reference labels.

## Remaining gate

Before dataset freeze, qualified bilingual reviewers must independently assess the new review scope, disagreements must be tracked and resolved under the review protocol, and the research owner must review the complexity shortfall, surface/duplicate/template findings, and proposed natural-language rendering conventions. Reviewers must determine whether wording revisions are needed and those revisions must receive new hashes and re-review. Partition integrity and label isolation must pass the later freeze review. No dataset freeze, model-judge inference, or paid API call occurred in this milestone.
