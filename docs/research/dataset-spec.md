# Dataset and canonical-state specification

**Status:** conceptual P0 specification. No dataset or generator is included.

**Authoritative label source:** canonical task state plus an executable validity rule, to be implemented and tested in P1.

## Study units and planned size

- **Canonical scenario:** the highest-level sampling and partition unit. It defines a domain, one transition family, relevant entities, an initial task state, a constraint-event history, and one canonical agent action.
- **Counterfactual history:** one of two minimally different histories for the scenario. Both retain the same action semantics; their effective task states yield opposite validity labels.
- **Derived evaluation item:** one counterfactual history rendered under one language condition and paired with the same scenario's canonical action. Each scenario contributes 2 histories × 4 conditions = 8 items.

The planned 48 scenarios yield 96 histories and 384 derived items. The two histories yield one valid and one invalid item for every scenario-condition combination. This gives 96 items (48 valid, 48 invalid) per language condition. The 12-scenario development partition contains 24 items per condition (12/12 valid/invalid); the 36-scenario locked evaluation partition contains 72 (36/36). These are design targets, not generated or validated records.

## Coverage and partition proposal

The design has 3 domains × 4 transition families = 12 domain-family cells. A balanced allocation of four canonical scenarios per cell would yield 48 total. A proposed stratified split assigns one scenario per cell to development and the remaining three to locked evaluation (12/36 overall). This is a transparent allocation proposal; review the cell balance and its implications for precision before P1. Use a recorded, reproducible allocation procedure if scenario selection is randomized.

The canonical scenario ID determines the partition. No alternate history, language variant, rewritten action, judge prompt example, or other derivative may cross partitions. Development material may support prompt and runner debugging; locked examples and labels remain inaccessible to model/prompt selection until the frozen evaluation plan is approved.

## Canonical state and validity rule

Each canonical scenario should specify enough explicit information to derive the effective state at the time of action:

- domain objects and their relevant attributes;
- the initial request and initially active constraints;
- time-ordered constraint events, including introduction, revision, revocation, or temporal change;
- the scope of each event and which earlier constraint it supersedes, if any;
- a normalized state snapshot at the decision point;
- a single canonical agent action and its relevant parameters;
- a deterministic rule that returns valid or invalid, with a reason code.

The validity rule must distinguish the current active constraint from superseded or revoked constraints. Booking and scheduling cases should use explicit dates, times, and time zones so the oracle's temporal result is unambiguous. Any derived state or verdict must be reproducible from the canonical record and rule, without an LLM.

P1 will define the machine-readable schema, rule semantics, and unit tests. P0 does not prescribe implementation details beyond this authority hierarchy.

## Counterfactual construction

For a given scenario, the action, domain facts, and non-decisive context should be held constant across the paired histories. The decisive constraint history differs so that the exact same action is valid under one effective state and invalid under the other. The pair should be matched in turn count and comparable in length and specificity where possible. Record any unavoidable differences that could reveal the label or change difficulty.

Pair identifiers must link the two histories and their derivatives. The oracle must independently compute both labels from the respective canonical states. A judge must not see the pairing key, counterpart, or reference labels during ordinary evaluation.

## Language conditions

Proposed operational mapping:

| Condition | Initial context and earlier turns | Decisive constraint event |
| --- | --- | --- |
| EN–EN | English | English |
| AR–AR | Arabic | Arabic |
| EN–AR | English | Arabic |
| AR–EN | Arabic | English |

This maps the first slot to the initial task/constraint context and the second slot to the turn that introduces or changes the constraint relevant to the action. All other turn-language assignments must be specified before generation; no incidental code-switching should be introduced unless it is an explicit, separately controlled factor. The identical structured action representation is a proposed control across variants.

Modern Standard Arabic is a candidate for the Arabic condition, not a settled choice. Arabic variety, orthography, numerals, date/time notation, names, locale assumptions, and how to preserve natural conversational phrasing require bilingual research-owner review before P1. Transliteration or normalization must not erase the linguistic feature being studied.

## Provenance, validation, and exclusions

Every record and derivative must carry stable provenance, including canonical ID, parent/variant IDs, domain, transition family, partition, construction method and version, source/authoring provenance, oracle version, language/translator version, validation status, and any revision or exclusion reason. Preserve unsuccessful, ambiguous, and excluded attempts in an audit log; never silently discard them or replace difficult cases after viewing judge results.

Each language variant requires independent semantic validation by qualified bilingual reviewers. Review should check that the constraint's meaning, polarity, numerical value, permission scope, chronology, referents, and relation to the action are preserved, and that the counterfactual pair still has opposite oracle labels. A back-translation may be supplementary but cannot substitute for independent semantic review. Disagreement or ambiguity must trigger documented adjudication or exclusion under a predeclared rule.

No actual examples, translations, or records are created during P0. LLM judgments must never validate or define the reference label. If a future construction method uses a generative model, disclose the model, prompt, and role, then validate independently; generated text alone does not establish semantic correctness.

## Label isolation and access

Reference labels, final canonical states, and oracle outputs are held in a restricted reference layer. Ordinary judge inputs contain no direct label, oracle verdict, or canonical final-state answer. Development labels may be used only within the documented development workflow. Locked evaluation labels and outputs should remain separated until the frozen run is complete. An oracle-state intervention is stored and analyzed under a distinct condition.
