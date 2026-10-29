# P2B-1 prototype content-audit decision record

**Review date:** 2026-10-29

**Approved P2A implementation:** `3a491a29c2ba0792a509f794a167854dc7aff2c3`

**Authorized scope:** P2A authoring feasibility is approved. P2B-1 only is authorized for corrections to the existing four local development prototypes and preparation for independent bilingual review. No later milestone is authorized here.

**Status:** Corrections and review materials are prepared for owner review. No independent bilingual annotations have been completed; the revised language remains unvalidated.

## Independent findings and dispositions

### P2A-R2 — Counterfactual history ordering

The audit found that all four existing prototype pairs use the same history-position convention. Their history ordering and oracle-established labels are preserved; no label was changed to improve balance. For the full primary design, the prospective blueprint crosses directly specified/history-dependent complexity with valid-history position A/B within each domain × transition-family cell. Development and locked slots have explicit balancing targets. Auxiliary controls are counterbalanced separately. Future judge-facing IDs are opaque UUIDv4 values with no encoded label, history, language, domain, family, partition, or template information. A reproducible hash-sort order policy is documented for later research-owner approval; it has not been implemented or frozen.

### P2A-R3 — Numerical, permission, and temporal surface shortcuts

The blueprint now targets upper and lower numeric bounds, earliest and latest temporal boundaries, and tightening/loosening revision directions. It requires pre-freeze reporting of label associations with negation, permission wording, confirmation, bound polarity and direction, magnitudes, temporal expressions, conversation length, and critical-information position. Balancing is required where semantically meaningful; unnatural wording is not an acceptable balancing method. The four existing examples do not establish full-study cue balance.

### P2A-R4 — Historical-state dependence

The protocol distinguishes **directly specified** cases from **history-dependent** cases by information required to determine the action's validity, not by turn count. Reviewers receive the explicit sufficiency question and must record a rationale. The prospective target is 24 scenarios per category in the primary set (six per category in development and 18 per category in locked primary), with two of each category per domain × transition-family cell. This is exploratory allocation guidance, not a power claim. Provisional authoring classifications and rationales are kept outside reviewer packets until independent answers are submitted.

## Prototype correction record

The originals and their exact file hashes were copied to ignored local `.research-data/p2b-1/originals/` before any edits. Each scenario has proposal and applied entries in the local revision ledger; the canonical P1 provenance also records a revision with the prior canonical content hash. Revised scenario and language-variant hashes are recorded locally. All changed language remains marked not validated and requires fresh independent human review.

| Prototype area | Correction | Formal state/action disposition |
| --- | --- | --- |
| Booking introduction | Revised English and MSA wording so non-refundable clearly describes the ticket. | Fare bounds, explicit purchase authorization, structured action, and pair labels unchanged. |
| Booking numerical revision | Adopted relative reductions of EGP 3,000 and EGP 2,000 from the shared EGP 9,000 initial maximum. Renamed the tool to `place_cancellable_hotel_hold` and aligned its description/context with a temporary cancellable hold requiring no payment. | Effective maxima remain EGP 6,000 and EGP 7,000; action fields and EGP 6,500 amount remain unchanged. Formal scenario tool name/schema description/version are aligned; constraint states and oracle labels are unchanged. |
| Customer operations permission revocation | Removed the broad profile-wide prohibition and made the two decisive turns a scoped contrast between withdrawal and continued authorization for the same email change. | Grant, revoke/restatement events, action, and pair labels unchanged. |
| Scheduling temporal revision | Replaced ISO-form conversation time expressions with ordinary English/MSA dates and clock expressions, explicitly naming Cairo time and UTC+02:00. Adopted relative shifts of two hours and one hour from the earlier latest-start limit. | Structured action remains ISO 8601 at 16:30 Cairo time; the inclusive 16:00/17:00 effective boundaries, dates, offsets, and oracle labels are unchanged. |

The relative numerical and temporal revisions are adopted for these development drafts. The decisive instruction does not repeat the final numeric/time boundary; the paired formal event still sets the approved effective bound. Independent reviewers must assess whether the natural-language arithmetic and reference are clear in both English and MSA.

## Human-review preparation and status

The existing reviewer-packet exporter now binds packets to both the canonical-scenario SHA-256 and each language-variant SHA-256. The local preparation includes two separate reviewer slots, 32 blank hash-bound annotations per slot, a briefing, an English/MSA side-by-side rendering, and a completeness report. The human historical-dependence field and rationale are required by the annotation validator. Reviewer-slot names are placeholders only.

Expected coverage is 32 derivatives × two reviewers = 64 independent annotations. Completed annotations: **0**. Missing annotations: **64**. Adjudications: **0**. No reviewer qualifications or identities have been recorded, and a second qualified bilingual human has not yet been confirmed. Codex is not a reviewer and no human annotations have been fabricated. The owner may serve as one reviewer; an independent second qualified bilingual reviewer remains necessary.

## Unresolved questions and limitations

- Independent reviewers must assess semantic equivalence, naturalness, scope, terminology, and chronology for every English/MSA variant, including the relative arithmetic and explicit timezone wording.
- The proposed complexity assessments may be revised by reviewers; they are not human labels and are hidden from the independent packet set.
- Four examples cannot establish that surface cues are balanced or that the prospective template allocation is feasible.
- The proposed UUIDv4 and hash-sort evaluation-order policy requires later owner approval before implementation.
- No locked examples, auxiliary-control examples, study dataset, model inference, or paid calls were created or authorized.

P2B-1 remains at the research-owner review gate. P2C, P3, P4, and P5 have not started.
