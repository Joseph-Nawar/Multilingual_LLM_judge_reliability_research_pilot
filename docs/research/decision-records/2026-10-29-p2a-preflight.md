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

## Independent P2A framework review and content-inspection gate

**Review date:** 2026-10-29

**Reviewed commit:** `2dc8a2d556541e8b88a765071bd1efd552e55631`

**Disposition:** The research owner accepted the P2A authoring protocol, prospective blueprint, bilingual annotation framework, and data-isolation architecture. P2A remains pending resolution of P2A-R1 and independent inspection of the four local prototype contents. P2B and all later milestones remain unauthorized.

### Finding P2A-R1 — Empty localized coverage spans

The previous validator accepted an initial-requirement, initial-permission, or event target when it linked to a localized segment whose text was empty or whitespace-only. The coverage check now requires at least one linked `LOCALIZED_NATURAL_LANGUAGE` segment whose text contains a non-whitespace character. A literal-only mapping and a literal plus empty localized segment are rejected; a substantive localized segment with an invariant technical literal is accepted. Empty spans remain allowed in the typed schema and unrelated synthetic infrastructure fixtures. This remains a structural check and makes no claim about translation fidelity or semantic equivalence.

### Private content-review gate

The four existing development prototypes are packaged for offline research-owner inspection under ignored `.research-data/p2a/owner-review/`. The bundle contains the formal specifications, both histories, all English/MSA variants, structured actions and public tool schemas, coverage maps, content hashes, readable conversation rendering, and a file-hash manifest. It excludes explicit validity labels, oracle verdicts/reason codes, judge predictions, model outputs, and credentials. Prototype content, formal states, actions, labels, and language text were not revised while preparing the bundle. The archive is not committed, pushed, or uploaded.

The local archive is `.research-data/p2a/owner-review/p2a-owner-review-bundle.zip` (24,703 bytes; SHA-256 `92d9cff3f2dbaa694711313a603579c2594c10c0acf4d2ce0cf7fd1b813d8318`). It contains four canonical-specification JSON files, four coverage JSON files, a readable Markdown rendering, current content hashes, a README, and a manifest with hashes for the other 11 files; the manifest does not hash itself. No reviewer identifiers or annotation records are included.

P2A cannot be called fully approved until the owner independently inspects this local bundle and records the content-review disposition. No human bilingual annotations or independent semantic validation are represented by this bundle. P2B remains unauthorized.

### Unresolved issues

Independent bilingual review of naturalness and meaning, possible additional draft corrections, template-family distinctness, full-study surface-feature balance, and feasibility of permission-scope control concepts remain open for their specified P2B/P2C gates. This correction does not authorize study controls, locked scenarios, dataset freezing, or inference.
