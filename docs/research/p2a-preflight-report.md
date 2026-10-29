# P2A development-only preflight report

**Status:** Deterministic preflight complete; independent bilingual validation has not been performed.

## Scope and structure

- Four local, ignored primary development prototypes; no locked scenarios or auxiliary-control study examples.
- Four canonical scenarios × two histories × four language conditions per history = 32 history-language variants and 32 development-only items.
- Prototype domain-transition cells:
- `booking/introduction`
- `booking/numerical_revision`
- `customer_operations/permission_revocation`
- `scheduling/temporal_revision`
- Aggregate deterministic oracle labels: 16 valid and 16 invalid items. No per-scenario labels or reference records are included in this report.
- Structural semantic-coverage map: 320 formal targets are linked to judge-visible spans in the expected user turns. Initial requirements, grants, and decisive events include localized natural-language spans; this link check does not verify meaning.

## Deterministic validation

- P1 typed schema, counterfactual oracle, language-condition coverage, and action chronology checks passed for all four records.
- Each pair has the same structured action and oracle-established opposite labels.
- Exact duplicate groups: 0; normalized text duplicate groups: 0. Semantic near-duplicates were not machine-verified.
- Recorded template IDs: 4 distinct with 0 repeated assignments; recipe IDs: 4 distinct with 0 repeated assignments. IDs are provisional, semantic/template-family overlap has not been independently audited, and development-only data cannot establish cross-partition separation.

## Feasibility assessment

The preflight demonstrates that P1's bounded schema and oracle can support the formal structures, condition coverage, chronology, and provenance checks needed for these four development prototypes. It does not establish full-study authoring throughput, human-review capacity, naturalness, or semantic equivalence; those remain owner-review and P2B/P2C questions.

## Human review status

All English and MSA conversations are Codex-authored, machine-assisted drafts marked **not independently validated**. No bilingual reviewer annotations or adjudications exist. Two independent qualified bilingual reviewers must review every variant against the formal specification without access to judge predictions; substantive corrections require re-review and a new content hash.

A local editorial check identified and corrected one MSA wording issue in the booking numerical-revision draft (refundable versus cancellable wording and the duration phrase). The prior record and hashes are retained in the ignored revision history. This correction is still unvalidated by bilingual reviewers; whether other drafts need correction remains unknown until independent review.

## Remaining surface-feature risks

Four scenarios are insufficient to establish that labels are not predictable from surface features. The permission-revocation prototype necessarily contains explicit consent withdrawal on its invalid side; numeric and temporal boundary values also determine validity by design. Explicit confirmations, negation, event direction, length, turn count, magnitude, time expressions, and critical-information position require a pre-freeze, human-coded audit across the full planned dataset. Do not force unnatural wording or claim statistical balance from this preflight.

## Data handling

Canonical records, translations, coverage maps, reference labels, review packets, annotations, and adjudications remain under ignored local `.research-data/` paths. Only this aggregate redacted report is public.
