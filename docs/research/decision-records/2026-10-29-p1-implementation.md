# P1 implementation decision record

**Date:** 2026-10-29
**Approved base:** `e35a94584518692ee6cc664105fa20bc26770a19`
**Authorization:** The initial authorization approved P0 and P1 only. The later owner update below records P1 approval and separate authorization for P2A only.
**Status:** Historical P1 implementation decisions are retained below. The P1 branch passed independent research-owner review at commit `3139cebe6926edeca0997c965617c7a35c3e0d27`. P2A is authorized for a controlled authoring preflight with exactly four local development prototypes. P2B, P2C, and later milestones are not authorized by that decision.

## Resolved P0 gate and conflict

The P0 dataset specification described the 12-control all-locked partition as pending P1 owner approval. The P1 authorization now explicitly approves 12 locked auxiliary controls, alongside 12 development and 36 locked primary scenarios. This resolves that partition gate for P1 infrastructure; it does not authorize construction of study examples, translations, or a frozen dataset.

## Bounded P1 implementation decisions

1. **Versioned representation:** Use schema version `1.1`, Python standard-library dataclasses/enums, and strict JSON encoding. Reject unknown fields, missing required fields, implicit type coercion, non-finite numbers, and naive datetimes. Version 1.1 adds explicit decisive-turn/event-group metadata and required/optional tool parameters; version 1.0 records are rejected rather than auto-migrated because causal and chronology links cannot be inferred. No study records exist to migrate.
2. **Constraint event lifecycle:** Order events by `(turn_index, event_index)` and require strict order. An introduction uses a never-before-used constraint ID. A revision targets an active constraint and preserves its identity, type, scope, and action field; the old version is retained as superseded. Requirement and permission restatements must exactly equal the active formal requirement or permission grant and are no-ops. A mismatch is an explicit validation error. Unrelated active constraints remain unchanged. Repeated IDs, inactive targets, out-of-order events, contradictory restatements, and state-changing events in controls are rejected.
3. **Permission and irreversible actions:** Absence of an active grant means not authorized. Grants and revocations are explicit, scoped events; revocation removes the active grant, and only a later explicit grant restores it. Permission checks require an exact permission-and-scope match. An irreversible action must declare at least one required permission in its reference action contract; an undeclared or ungranted permission cannot be inferred from prose.
4. **Numeric and temporal comparisons:** Use `Decimal` for numeric values and explicit uppercase ISO 4217 codes for monetary constraints. Numeric boundary inclusivity is explicit; equality passes an inclusive bound and fails an exclusive one. Temporal boundaries are offset-aware ISO 8601 instants with explicit inclusivity; comparisons use UTC-normalized instants. Ambiguous local folds, naive times, and invalid or empty intervals are rejected. No oracle rule reads current time. Currency membership uses the fixed 178-code extract from SIX List One published 2026-09-17; the source URL and XML SHA-256 are pinned in `multilingual_judge_pilot/iso4217_snapshot.py`; validation is offline.

## P1 implementation decisions and recorded proposals

This section preserves the operational choices as first documented during implementation. Their later approval or deferral is recorded in the final research-owner review update below.

- **Action and language hooks:** Keep one typed structured action and public tool schema per canonical scenario. Every public parameter has an explicit required flag; all supplied values must be declared and correctly typed, and required values must be present. The judge-facing schema exposes those same flags. Store MSA as the Arabic language identifier, fix judge instructions to English, require initial and decisive turns to be user turns, and default other turns to the initial language unless an approved, reasoned override is recorded. Link each formal event turn and decisive-turn assignment to the conversation chronology; every conversation turn supplied to an ordinary judge must have an index strictly below the action decision point, regardless of role. Reject invalid records without truncating them. These are structural checks only and do not validate translations.
- **Pairs, partitions, and provenance:** Each scenario has exactly two histories, one canonical action, and oracle-computed opposite labels. Primary pairs share semantically equivalent initial active states, non-decisive events, decisive turn, and action decision point. A designated decisive event group must target matching formal constraint/permission identities, leave pre-decisive validity labels equal, and create the final action-relevant state difference that explains the label contrast; comparisons ignore IDs, versions, and superseded history. Numeric/temporal changes must alter active semantics; a permission pair revokes one initially granted required permission in one history and explicitly restates it in the preserving history. Controls retain their distinct initial-state design and no-op restatements. Use deterministic SHA-256 partition allocation with one development scenario per primary domain/family cell and all controls locked. Derivatives and parent/source relationships cannot cross partitions. Match records preserve dimensions and quality; the research owner approved limiting control matches to locked primary scenarios.
- **Duplicates, rejection records, and judge projection:** Detect exact scenario duplicates and NFC/casefold/whitespace-normalized conversation-text duplicates across different canonical scenarios. Report template/recipe counts and cross-partition reuse, but make no semantic-equivalence claim. Preserve malformed candidate bytes, source reference, hash, validator version, and rejection reason in a validation outcome; do not auto-repair or exclude. Ordinary judge serialization is an allowlisted record with an opaque ID, conversation, canonical action, and public tool schema only.

These bounded schema 1.1 implementation semantics do not claim natural-language equivalence or prescribe future scenario wording. They implement the P1 audit repairs under the existing experimental design; counts and hypotheses are unchanged. The repairs do not constitute final scientific approval. The research owner must review the implementation and evidence before P1 closeout; do not patch scenarios around the oracle.

## Independent P1 research-audit repair record

**Review date:** 2026-10-29
**Reviewed commit:** `ce96769dd00090c643efcf80827f017ad10e8832`
**Repair status:** Implemented on the authorized P1 branch; pending independent research-owner review. No hypothesis or planned count changed.

| Finding | Implemented correction | Owner disposition / remaining resolution milestone |
| --- | --- | --- |
| P1-R1: counterfactual causal integrity | Explicit decisive turn/event groups; equivalent initial active states and non-decisive transitions; shared action chronology; equal pre-transition labels; opposite final labels explained by changed active action-relevant state. Available same-condition non-decisive conversation spans must also match exactly across primary histories, ignoring segment IDs. Version-only changes are not semantic changes. Permission revocation is paired with explicit preservation. Auxiliary controls keep their distinct-initial-state design. | Accepted in the independent review of `a7a8ed56…`; retain for independent inspection at the final P1 gate. |
| P1-R2: conversational/formal chronology | Formal event turns, decisive turn, language variant turns, and action decision point are structurally linked. All turns supplied to the judge must precede the action point, regardless of role; the serializer rejects violations without truncation. The validator makes no translation-equivalence claim. | Structural repair accepted subject to the P1-R4 correction; independent bilingual semantic correspondence remains a P2 validation requirement. |
| P1-R3: tool parameter requirements | Public schema has typed `required` flags; supplied parameters must be declared and correctly typed, and required parameters must be present. Judge-facing schema serializes the same rules. | Accepted in the independent review of `a7a8ed56…`; actual scenario/tool contract remains subject to P2 authoring review. |
| Currency membership | Offline validator uses the 178 non-empty `Ccy` values extracted from SIX List One published 2026-09-17. Source SHA-256: `33139b438657d1cee116ba737807ea71d19d6de4b90f799a09c56f0cc6a1b0ff`. | Accepted in the independent review of `a7a8ed56…`; any update requires a reviewed schema/rules version change. |
| P1-R4: post-action assistant turns | Every conversation turn supplied to an ordinary judge must have an index strictly below the action decision point. Turns at or after it are rejected for every role by validation and judge serialization; no automatic truncation occurs. | Correction is implemented in this change and awaits final independent P1 research-owner review. |

Schema version 1.1 is intentionally incompatible with version 1.0 JSON because decisive-event and parameter-presence rules were previously unavailable. The parser rejects 1.0; no automated migration is provided, and no research dataset exists to migrate. Synthetic test fixtures were updated to 1.1.

## Final P1 research-owner review update

**Review date:** 2026-10-29

**Reviewed commit:** `a7a8ed56bb7b5c6f16ac76a5347ac8fd29bb8e2c`

The independent review accepted the substantive P1-R1 counterfactual-causality repair, P1-R3 required-parameter validation, the offline currency-membership repair, schema version 1.1, and its bounded numeric, temporal, and permission constraint types. The research owner also approved matching auxiliary controls only to locked primary scenarios. These decisions do not authorize scenario authoring or dataset freezing.

The review accepted the P1-R2 structural event/conversation chronology repair but identified the remaining P1-R4 omission: assistant turns at or after the action point were not rejected. This correction requires every supplied conversation turn, whether user, assistant, or tool, to have `turn_index < action_turn_index`. Equality and later indices are invalid. Structural validation and `build_judge_facing_item()` reject such records; they do not silently truncate them. Legitimate assistant and tool turns before the action remain permitted. The correction is recorded in this change and awaits the final independent P1 research-owner review.

Linguistic semantic validation, study-dataset authoring, and partition freezing are deferred to P2 and have not started. P2 must separately resolve approved scenario wording, independent bilingual validation/adjudication, template allocation and leakage reporting, and a reviewed immutable partition manifest. Structural chronology checks do not establish that natural-language turns express the associated formal event.

## Remaining uncertainties and resolution milestones

| Uncertainty | Current treatment | Required resolution |
| --- | --- | --- |
| Natural-language equivalence of restatements, revisions, labels, and invariant technical literals | P1 stores language/span hooks and checks turn structure and exact literal invariants; no study-language variants exist | Independent bilingual validation and adjudication in P2 |
| Semantic near-duplicates and template-family separability across the 12 development and 36 locked primary scenarios | P1 reports exact/normalized duplicates and template/recipe reuse only | Human review and feasible template allocation report in P2; disclose overlap and template sensitivity limits at P5 |
| Final partition seed and immutable manifest for real scenarios | Allocator behavior is deterministic given an explicit seed; no study seed or dataset is created in P1 | Research-owner review and frozen manifest before P2 release |
| Whether actual scenario needs fit the approved bounded numeric, temporal, and permission types and public tool contracts | Schema 1.1 rejects unsupported types and ambiguous missing values rather than interpreting prose or guessing | Review against approved scenario contracts before authoring in P2; any extension requires owner review and explicit schema/rules versioning |

The public repository contains no study scenarios, Arabic translations, locked labels, or experimental results. P1 synthetic fixtures are implementation tests only and must not be counted as pilot observations.

## P1 execution boundaries

- Use only in-memory or test-only synthetic fixtures authored independently of any proposed study scenario.
- Create no primary/control benchmark records, no English/Arabic study variants, and no translation data.
- The judge projection is an allowlisted type and serializer. Reference states, verdicts, reasons, pairing IDs, template/recipe metadata, and provenance stay outside that projection.
- No inference, model selection, paid call, or P2 validation/release is authorized.

## Evidence required at the P1 review gate

Review the schema/version contract, event semantics, oracle reason codes and boundary behavior, pair-integrity rules, deterministic partition manifest, provenance/duplicate reports, and judge/reference separation. P2 may begin only after the research owner accepts the implementation and separately authorizes the milestone.

The P1 verification suite covers all four consequential transition families, exact/inclusive/exclusive numeric boundaries, permission grant/revocation and absent authorization, temporal revision across UTC offsets, preservation of unrelated constraints, ordered events, exact no-change restatements, malicious state-changing controls, causal-pair confounds, chronology mismatches, public tool parameter requirements, pinned currency membership, opposite-label counterfactuals, incorrect declared labels, malformed records, partition allocation and derivative/source leakage, shared template reporting, invariant literal checks, normalized duplicate behavior, judge-projection isolation, and repeated deterministic outputs. All fixtures are synthetic and test-only.

## Final P1 approval and P2A authorization update

**Review date:** 2026-10-29

**Approved P1 commit:** `3139cebe6926edeca0997c965617c7a35c3e0d27`

**Owner disposition:** P1 passed independent research-owner review, including P1-R1 through P1-R4, the currency allowlist repair, schema 1.1, and the bounded constraint types. P2A is separately authorized; P2B, P2C, P3, P4, and P5 remain outside scope.

P2A may establish the authoring protocol, prospective full-study blueprint, bilingual review rubric/utilities, and exactly four local primary development prototypes from distinct domain-transition cells, with their 32 language-condition variants. These records and all translations, semantic-coverage maps, reference labels, packets, and reviewer materials remain under ignored `.research-data/`; only code, documentation, tests, and a redacted aggregate report may be public. No controls or locked scenarios may be authored, and no model calls or dataset freeze are authorized.

The P2A drafts are machine-assisted, not independently validated. The semantic-coverage checker proves only that formal targets are linked to spans in the structurally expected user turns. It does not establish that English or MSA text expresses the linked meaning. Two independent bilingual reviewers and adjudication remain required in P2B. Full dataset authoring, semantic near-duplicate adjudication, empirical template-family inventory, anti-shortcut audit, and partition freeze remain for P2C, subject to a separate authorization and review.
