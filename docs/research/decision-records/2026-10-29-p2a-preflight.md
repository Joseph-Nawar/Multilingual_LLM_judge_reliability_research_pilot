# P2A authoring preflight decision record

**Date:** 2026-10-29

**Approved P1 base:** `3139cebe6926edeca0997c965617c7a35c3e0d27`

**Owner authorization:** P1 passed independent review. P2A only is authorized.

**Status:** P2A artifacts are prepared for independent owner review; no P2B or later milestone has started.

## Scope decisions

- Preserve the approved 48 primary scenarios/384 items and 12 locked auxiliary controls/96 items: 60 scenarios/480 items total. P2A authors only four primary development prototypes and their 32 history-language variants. No control or locked study examples are authored.
- Use four distinct development domain-transition cells: booking/introduction, booking/numerical revision, customer operations/permission revocation, and scheduling/temporal revision. The other eight development slots and all locked slots remain prospective blueprint entries.
- Keep all prototype records, language variants, semantic-coverage maps, reference labels, reviewer packets, annotations, revision history, and adjudications under ignored `.research-data/`. Commit only code, procedures, tests, and the redacted aggregate report.
- Treat the preflight as deterministic schema, oracle, chronology, language-condition, span-link, duplicate, and isolation checking. Span links do not establish semantic equivalence.
- Require two independent qualified bilingual reviewers for eventual English/MSA validation. No human annotations or adjudications have been completed; Codex-authored drafts remain unvalidated.
- Do not run judge inference, select examples based on judge behavior, freeze the dataset, or begin P2B/P2C/P3/P4/P5.

## Local draft correction

A machine-assisted editorial check found an MSA wording problem in one booking numerical-revision draft: the Arabic distinguished cancellation from refund incorrectly and used an awkward duration phrase. The local ignored record was corrected, with the prior bytes preserved under `.research-data/p2a/revisions/`, hashes stored in `.research-data/p2a/revision-log.jsonl`, and a typed revision entry added to scenario provenance. No formal constraint, action, oracle result, or label changed. The revised language remains unvalidated pending independent review; other drafts may also require correction.

## Remaining uncertainties and resolution milestones

| Uncertainty | Current treatment | Resolution milestone |
| --- | --- | --- |
| Whether each English/MSA span faithfully expresses its formal target and is natural | Four drafts have structural span mappings only; no bilingual review is claimed | P2B: two independent reviewers, disagreement adjudication, and re-review after edits |
| Whether proposed permission-scope control concepts can be represented as no-op restatements without extending P1 semantics | Blueprint marks these control families conditional; unmatched controls are allowed and must be reported | P2C: validate feasibility against the approved schema; seek explicit owner review before any schema change |
| Whether the planned template families are genuinely distinct and separable across partitions | IDs and names are provisional; four prototype IDs do not prove template independence | P2C: human template-family inventory, overlap report, and feasible allocation; sensitivity limitations at P5 |
| Whether label-related surface cues remain imbalanced in the full set | Preflight lists plausible cues but four prototypes cannot establish balance | P2C: predeclared human-coded feature audit before partition freeze |
| Final study partitions, hashes, matching, and release handling | No study manifest or frozen dataset exists | P2C: explicit owner review and approval before freeze/release |

This record preserves the P0/P1 rationale. It authorizes a small authoring-method preflight only and does not claim that the prototypes are scientifically or linguistically validated.
