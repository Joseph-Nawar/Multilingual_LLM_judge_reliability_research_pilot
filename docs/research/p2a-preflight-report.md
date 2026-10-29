# P2A/P2B-1 development-only preflight report

**Status:** Deterministic preflight complete; independent bilingual validation has not been performed.

## Scope and structure

- Four local, ignored primary development prototypes; no locked scenarios or auxiliary-control study examples.
- Four canonical scenarios × two histories × four language conditions per history = 32 history-language variants and 32 development-only items.
- Prototype domain-transition cells:
- `booking/introduction`
- `booking/numerical_revision`
- `customer_operations/permission_revocation`
- `scheduling/temporal_revision`
- Deterministic counterfactual validation passed for each pair. Reference validity labels and oracle outputs are omitted from this public report.
- Structural semantic-coverage map: 320 formal targets are linked to judge-visible spans in the expected user turns. Initial requirements, grants, and decisive events include localized natural-language spans; this link check does not verify meaning.

## Deterministic validation

- P1 typed schema, counterfactual oracle, language-condition coverage, and action chronology checks passed for all four records.
- Counterfactual pair-integrity checks passed for all four scenarios; pair-level verdicts are not reported.
- Exact duplicate groups: 0; normalized text duplicate groups: 0. Semantic near-duplicates were not machine-verified.
- Recorded template IDs: 4 distinct with 0 repeated assignments; recipe IDs: 4 distinct with 0 repeated assignments. IDs are provisional, semantic/template-family overlap has not been independently audited, and development-only data cannot establish cross-partition separation.

## Feasibility assessment

The preflight demonstrates that P1's bounded schema and oracle can support the formal structures, condition coverage, chronology, and provenance checks needed for these four development prototypes. It does not establish full-study authoring throughput, human-review capacity, naturalness, or semantic equivalence; these remain owner-review and later-milestone questions.

## P2B-1 draft-correction status

The four existing drafts were revised after independent content-audit findings. Wording was clarified, one public tool description was aligned with its intended operation, and relative numerical and temporal revision forms were adopted to exercise earlier-state reconstruction. Formal effective constraints and counterfactual oracle relationships were preserved. These changes remain unvalidated natural-language drafts; the provisional complexity assessment is not a human annotation.

## Human review status

All English and MSA conversations are Codex-authored, machine-assisted drafts marked **not independently validated**. Completed independent annotations: 0 of 64 expected; adjudications: 0. Two qualified bilingual reviewers must review every variant against the formal specification without access to judge predictions. Substantive corrections require re-review against new variant and canonical-scenario hashes. Reviewer slots and blank templates are preparation materials, not reviewer records.

## Remaining surface-feature risks

Four scenarios are insufficient to establish that labels are not predictable from surface features. Permission wording, numeric bound polarity and revision direction, values and action margins, earliest/latest temporal expressions, explicit confirmations, negation, length, turn count, magnitude, and critical-information position may correlate with validity by design. These properties require a pre-freeze, human-coded, label-association audit across the full planned dataset. Do not force unnatural wording or claim statistical balance from this preflight.

## Data handling

Canonical records, translations, coverage maps, reference labels, prior versions, review packets, blank annotation templates, annotations, and adjudications remain under ignored local `.research-data/` paths. No locked examples, auxiliary-control examples, judge predictions, or model outputs were created. Only this aggregate redacted report is public.
