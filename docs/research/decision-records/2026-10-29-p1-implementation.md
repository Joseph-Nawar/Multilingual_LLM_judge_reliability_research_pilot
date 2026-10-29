# P1 implementation decision record

**Date:** 2026-10-29
**Approved base:** `e35a94584518692ee6cc664105fa20bc26770a19`
**Authorization:** The research owner independently reviewed and approved P0 and authorized P1 only. P2 and later milestones remain unauthorized.
**Status:** P1 implementation decisions below are proposals for independent research-owner review before any study dataset construction. P1 is authorized; P2 is not.

## Resolved P0 gate and conflict

The P0 dataset specification described the 12-control all-locked partition as pending P1 owner approval. The P1 authorization now explicitly approves 12 locked auxiliary controls, alongside 12 development and 36 locked primary scenarios. This resolves that partition gate for P1 infrastructure; it does not authorize construction of study examples, translations, or a frozen dataset.

## Bounded P1 implementation decisions

1. **Versioned representation:** Use schema version `1.0`, Python standard-library dataclasses/enums, and strict JSON encoding. Reject unknown fields, missing required fields, implicit type coercion, non-finite numbers, and naive datetimes. No general-purpose policy engine or external runtime dependency is introduced.
2. **Constraint event lifecycle:** Order events by `(turn_index, event_index)` and require strict order. An introduction uses a never-before-used constraint ID. A revision targets an active constraint and preserves its identity, type, scope, and action field; the old version is retained as superseded. Requirement and permission restatements must exactly equal the active formal requirement or permission grant and are no-ops. A mismatch is an explicit validation error. Unrelated active constraints remain unchanged. Repeated IDs, inactive targets, out-of-order events, contradictory restatements, and state-changing events in controls are rejected.
3. **Permission and irreversible actions:** Absence of an active grant means not authorized. Grants and revocations are explicit, scoped events; revocation removes the active grant, and only a later explicit grant restores it. Permission checks require an exact permission-and-scope match. An irreversible action must declare at least one required permission in its reference action contract; an undeclared or ungranted permission cannot be inferred from prose.
4. **Numeric and temporal comparisons:** Use `Decimal` for numeric values and uppercase three-letter ISO-shaped currency codes for monetary constraints. Numeric boundary inclusivity is explicit per boundary; equality passes an inclusive boundary and fails an exclusive one. Temporal boundaries are offset-aware ISO 8601 instants with explicit inclusivity; comparisons use the represented instant, not the local wall-clock spelling. Ambiguous local folds, naive times, and invalid or empty intervals are rejected. No oracle rule reads current time. The implementation checks currency-code shape but not membership in the official ISO list; this limitation must be resolved before study construction.

## Additional P1 operational proposals

- **Action and language hooks:** Keep one typed structured action and public tool schema on each canonical scenario. Validate supplied action fields against public tool parameter names/types. Store MSA as the Arabic language identifier, fix the judge-instruction language to English, require the initial and decisive turns to be user turns, and default other turns to the initial language unless an approved, reasoned override is recorded. Provide a pre-freeze validator requiring all four conditions per history. Require invariant literal names/order/text to match exactly across existing variants. These are structural checks only; they do not validate translations.
- **Pairs, partitions, and provenance:** Each canonical scenario has exactly two histories, a shared pair ID, one identical action, and opposite labels computed by the oracle. Primary pairs need different final effective-state digests and an event of their assigned family. Controls contain only later requirement/permission restatements, unchanged per-event state digests, and different initial states. Use a deterministic SHA-256 partition allocation with one development scenario per primary domain/family cell and all controls locked. Derivatives and parent/source scenario links cannot cross partitions. Match records preserve matching dimensions and quality; the current implementation requires any matched control to link to a locked primary, which remains a proposal for owner review.
- **Duplicates, rejection records, and judge projection:** Detect exact scenario duplicates and NFC/casefold/whitespace-normalized conversation-text duplicates across different canonical scenarios. Report template/recipe counts and cross-partition reuse, but make no semantic-equivalence claim. Preserve malformed candidate bytes, source reference, hash, validator version, and rejection reason in a validation outcome; do not auto-repair or exclude. Ordinary judge serialization is an allowlisted record with an opaque ID, conversation, canonical action, and public tool schema only.

These are bounded implementation semantics for the P1 oracle, not claims about natural-language equivalence or the intended wording of future scenarios. If the research owner rejects a decision, revise the P1 implementation before P2; do not patch examples around the oracle.

## Remaining uncertainties and resolution milestones

| Uncertainty | Current treatment | Required resolution |
| --- | --- | --- |
| Whether matching controls only to locked primary scenarios is preferable to recording broader auxiliary matches | Validator currently enforces locked-primary match targets so a locked control match is usable in the locked primary/control comparison; this is stricter than the explicit partition non-reassignment rule | Research-owner decision at the P1 review gate, before P2 construction |
| Official ISO 4217 membership and versioning | P1 validates uppercase three-letter shape only; it does not claim registry membership | Select an authoritative registry/version and add a deterministic check before P2 dataset construction |
| Whether the bounded numeric, temporal, and permission requirement types cover all intended cases in the three domains | P1 rejects unsupported requirement types rather than interpreting prose or guessing | Review the formal scenario contract at the P1 gate; resolve any missing type before P2 |
| Natural-language equivalence of restatements, revisions, labels, and invariant technical literals | P1 stores language/span hooks and checks exact literal invariants; no research-language variants exist | Independent bilingual validation and adjudication in P2 |
| Semantic near-duplicates and template-family separability across the 12 development and 36 locked primary scenarios | P1 reports exact/normalized duplicates and template/recipe reuse only | Human review and feasible template allocation report in P2; disclose overlap and template sensitivity limits at P5 |
| Final partition seed and immutable manifest for real scenarios | Allocator behavior is deterministic given an explicit seed; no study seed or dataset is created in P1 | Research-owner review and frozen manifest before P2 release |
| Whether schema version `1.0` and action/tool field mapping need changes for actual scenario content | Typed fixtures cover only synthetic numeric, temporal, and permission cases | Review schema against the approved formal scenario contract at the P1 gate before study records are authored |

The public repository contains no study scenarios, Arabic translations, locked labels, or experimental results. P1 synthetic fixtures are implementation tests only and must not be counted as pilot observations.

## P1 execution boundaries

- Use only in-memory or test-only synthetic fixtures authored independently of any proposed study scenario.
- Create no primary/control benchmark records, no English/Arabic study variants, and no translation data.
- The judge projection is an allowlisted type and serializer. Reference states, verdicts, reasons, pairing IDs, template/recipe metadata, and provenance stay outside that projection.
- No inference, model selection, paid call, or P2 validation/release is authorized.

## Evidence required at the P1 review gate

Review the schema/version contract, event semantics, oracle reason codes and boundary behavior, pair-integrity rules, deterministic partition manifest, provenance/duplicate reports, and judge/reference separation. P2 may begin only after the research owner accepts the implementation and separately authorizes the milestone.

The P1 verification suite covers introduction, numeric revision and exact/exclusive boundaries, permission grant/revocation and absent authorization, temporal revision across UTC offsets, preservation of unrelated constraints, ordered events, exact no-change restatements, malicious state-changing controls, opposite-label counterfactuals, incorrect declared labels, malformed records, partition allocation and derivative/source leakage, shared template reporting, invariant literal checks, normalized duplicate behavior, judge-projection isolation, and repeated deterministic outputs. All fixtures are synthetic and test-only.
