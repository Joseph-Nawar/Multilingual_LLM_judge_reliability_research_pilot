# Dataset and canonical-state specification

**Status:** research specification amended after the 2026-10-29 research-owner audit. P1 schema and oracle infrastructure is implemented; no study dataset or generator is included.

**Authoritative label source:** canonical task state plus the deterministic validity rule in `multilingual_judge_pilot/oracle.py`; P1 implementation is pending independent owner review.

## Study units and planned counts

- **Canonical scenario:** highest-level content and partition unit. It defines a domain, a requirement/state history, relevant entities, and one canonical action.
- **Counterfactual history:** one of two histories for a scenario. Both retain identical action semantics; their initial/effective states yield opposite validity labels.
- **Derived evaluation item:** one history rendered under one language condition and paired with the scenario's canonical action. A canonical scenario contributes 2 histories × 4 conditions = 8 items.

| Set | Canonical scenarios | Histories | Items | Partition plan |
| --- | ---: | ---: | ---: | --- |
| Primary consequential-change set | 48 | 96 | 384 | 12 development; 36 locked evaluation |
| Auxiliary no-change linguistic control | 12 | 24 | 96 | 12 locked auxiliary scenarios; none in development; locked allocation approved for P1 infrastructure |
| **Total planned corpus** | **60** | **120** | **480** | **12 development primary; 48 locked total (36 primary + 12 control)** |

The primary design remains unchanged: 3 domains × 4 consequential transition families, 48 scenarios, and 384 items. It yields 96 development items and 288 locked primary items. Each scenario-condition pair has one valid and one invalid item. Each primary language condition has 96 items (48 valid, 48 invalid); the development partition has 24 per condition (12/12), and the locked primary partition has 72 (36/36).

The separate control adds 96 items. Each control language condition has 24 items (12 valid, 12 invalid). The research owner approved the all-locked auxiliary partition in the P1 authorization; controls remain unavailable for development-time judge selection. Thus the combined locked evaluation inventory has 384 items (288 primary + 96 control), while the primary estimand continues to use only the 36 primary locked scenarios. This authorization establishes a future partition target, not permission to construct the study controls during P1.

## Primary consequential-change scenarios

The primary set covers booking, customer operations, and scheduling and the four transition families: introduction, numerical revision, permission revocation, and temporal revision. It retains the proposed 4-scenarios-per-domain/family-cell allocation. The current primary partition proposal assigns one scenario per cell to development and three to locked evaluation. Every counterfactual history, language variant, action rendering, and other derivative follows its canonical scenario's partition.

## Auxiliary no-change linguistic controls

Each control history contains a later user turn that restates or confirms an already active requirement while leaving its effective meaning unchanged. For example, a booking history may begin with a maximum fare and later repeat that same maximum. The paired history begins with a different maximum and later repeats that different maximum. An identical action can then be valid under one initial requirement and invalid under the other. Opposite labels arise from the pair's different initial states; neither history contains an actual constraint revision. The oracle must verify state equality immediately before and after the restatement.

Where feasible, match each control scenario to a locked primary scenario on domain, constraint type, the pair of final effective states, action complexity, and turn structure. P1 match records preserve explicit dimensions and distinguish full, partial, and unmatched controls. Give the two records distinct canonical IDs and link them with a match-set ID. The research owner approved this locked-primary matching restriction. The P1 validator does not reassign either scenario or any derivative. Preserve all control histories and variants together in the locked auxiliary partition. Record failed matches and their reasons; do not weaken the matching record after observing judge results.

Control items must remain separately identifiable in storage, prompts/manifests, scoring, and reports. They support secondary exploratory comparisons of language switching under changed versus unchanged meaning. They do not enter the primary estimand, replace the four-condition primary comparison, or fully identify the causal effect of consequential revision.

## Canonical state and validity rule

Each canonical record should specify enough explicit information to derive the effective state at action time:

- domain objects and relevant attributes;
- initial request and initially active requirements;
- time-ordered events and their scope, including whether an event changes or merely restates a requirement;
- links to requirements superseded or revoked, if applicable;
- normalized state before and after each event and at the decision point;
- one canonical action and its parameters;
- a deterministic valid/invalid rule and reason code.

The rule must resolve active constraints, supersession, revocation, numerical bounds, and temporal conditions without an LLM. For each control restatement it must verify that the effective state is unchanged; for each counterfactual pair it must compute opposite labels for the same action. Booking and scheduling values must use unambiguous dates, times, and time zones. The P1 implementation contract below makes the bounded machine-readable semantics explicit; it defines no natural-language interpretation.

## P1 canonical schema and deterministic state contract

The implementation uses schema version `1.1`, typed standard-library records, and strict JSON encoding. Unknown fields, missing required fields, implicit type coercions, unsupported value types, non-finite numeric values, and timezone-naive datetimes are validation errors. Version 1.1 adds explicit decisive-turn/event-group metadata and required/optional tool-parameter declarations; version 1.0 records are rejected rather than auto-migrated because their causal and chronology links cannot be inferred safely. No study records exist to migrate. A parsed record must not be silently repaired. Canonical state, derived state, oracle output, and declared labels are reference-only. `RestateRequirement` and `RestatePermission` are explicit no-op events: each must exactly match an active formal requirement or permission grant.

Constraint events are ordered lexicographically by `(turn_index, event_index)`; this order must be unique and strictly increasing, and every event must precede the action decision point. Each history explicitly identifies its decisive conversation turn and the complete formal event group at that turn. The decisive turn must precede the action decision point; no later formal state events are permitted. Every event turn represented in a language variant must map to a user turn, and the language variant's decisive turn must match the formal event turn. Every conversation turn supplied to an ordinary judge, regardless of whether it is a user, assistant, or tool turn, must have `turn_index < action_turn_index`. A turn at the action index or later is invalid; validation and judge-facing serialization reject the record rather than truncating it. These checks establish chronology only; they do not verify that natural-language text expresses the formal event. That semantic correspondence remains subject to independent bilingual validation in P2.

A constraint introduction uses an identifier never used earlier in that history. A revision must target an active requirement and preserve its identifier, requirement type, scope, and action field; it advances the version and retains the prior version as superseded. It may not alter unrelated requirements. A restatement must exactly match the currently active formal requirement and leaves the state unchanged. Repeated introductions, revisions of inactive/unresolved requirements, duplicate/repeated revocations, contradictory restatements, and out-of-order events are errors.

Primary counterfactual histories must have semantically equivalent initial active states and the same action decision point and decisive turn. Semantic state comparisons ignore bookkeeping identifiers and versions, and include only active requirements and grants, not superseded history. Non-decisive formal events must be equivalent in order and active-state effect. Where same-condition language variants are present for both histories, their non-decisive turn structure and text spans must match exactly after ignoring segment IDs; this is a structural control, not proof of linguistic equivalence. The designated decisive event groups must target equivalent requirement/permission identities; each history's state immediately before the decisive turn must match, and the oracle validity labels at that point must agree. For introduction and numeric/temporal revision families, each decisive group must make a meaningful action-relevant semantic change. For permission revocation, one history revokes an initially active required permission and the other explicitly restates/preserves it. Final opposite labels must be explained by different active decision-relevant states; unrelated active-state differences are rejected. A version-only revision does not count as a semantic change. Auxiliary no-change controls remain separate: their opposite labels intentionally arise from different initial effective requirements, and each later restatement must leave active state unchanged.

Permission authorization is explicit and scoped. Absence of an active grant means `NOT_GRANTED`; it never means permission. A revocation removes the active grant. Authorization after revocation requires a later explicit grant. The canonical action contract lists each required permission and scope. An irreversible action must declare at least one required permission; an omitted requirement is ambiguous and rejected. A grant satisfies only the exact permission-and-scope key.

Numeric requirements use exact `Decimal` values. Each lower/upper numeric bound explicitly records inclusivity; equality passes an inclusive bound and fails an exclusive one. If a monetary requirement is used, both requirement and action value include the same uppercase ISO 4217 code. Runtime validation uses the fixed 178-code extract from the ISO 4217 Maintenance Agency's SIX List One XML published 2026-09-17; its source URL, source-file SHA-256, and exact supported codes are pinned in `multilingual_judge_pilot/iso4217_snapshot.py`. Runtime validation makes no network request and rejects codes absent from this snapshot. Binary floating-point values are not accepted.

Temporal requirements use optional lower and upper bounds, each with an explicit inclusive/exclusive flag. Date-time values must be ISO 8601 with a UTC offset (`Z` or signed offset); comparisons use the represented instant after UTC normalization. Naive local times, unresolved DST folds, invalid/empty intervals, and reversed bounds are rejected. The oracle uses the canonical action's explicit execution time and never reads the wall clock.

The engine preserves unrelated active requirements and evaluates all applicable requirements whose global or entity scope matches the action. A required action field that is missing or has an incompatible type is a validation error, not an inferred pass. Every oracle result retains the effective state, deterministic reason codes, ordered event audit, and a content digest.

## P1 language/action schema hooks

The typed schema supports EN–EN, AR–AR, EN–AR, and AR–EN conditions; Arabic is tagged specifically as Modern Standard Arabic. It records initial/decisive user-turn indices, per-turn language, explicit approved overrides for other turns with a reason, fixed English judge-instruction language, and ordered text spans marked as localized natural language or invariant technical literals. A separate pre-freeze validation hook requires all four conditions for each history. Across available variants of a history, the validator requires literal names, order, and text to match exactly. Tool schema and structured action are stored once per canonical scenario and cannot vary by language condition. Stable entity IDs, pinned ISO 4217 currency codes, exact monetary values, and offset-aware date-times are typed fields. These checks establish structure and representation only; they do not establish translation quality, semantic equivalence, bilingual validation, or a frozen dataset. P1 creates no study-language variants.

Each public tool parameter explicitly declares `required: true|false`. Every supplied action parameter must be declared and have the specified type; every required parameter must be present. For P1, an absent optional parameter means it is omitted and has no value; if an active requirement references a missing value, the oracle rejects the action as underspecified. The judge-facing public schema exposes the same parameter requirement flags enforced by the reference validator.

## Counterfactual pairing and language conditions

For primary pairs, hold the action, domain facts, and non-decisive context constant where feasible; vary the consequential state history so that the same action has opposite labels. For controls, hold the action and restatement operation constant while the pair begins with different active requirements; each restatement preserves its own initial meaning. Match turn count and comparable length/specificity where practical. Record any unavoidable label or difficulty cues.

| Condition | Initial context and earlier turns | Later decisive turn |
| --- | --- | --- |
| EN–EN | English | English |
| AR–AR | Arabic | Arabic |
| EN–AR | English | Arabic |
| AR–EN | Arabic | English |

The first language is used in the initial context; the second is used in the later consequential change (primary set) or no-change restatement (control). All other turn-language assignments must be fixed by the approved scenario specification before construction. Arabic is Modern Standard Arabic (MSA). Egyptian Arabic and Arabizi are outside the initial pilot. The judge instruction language is English and must be identical across the four conditions. The task's user-facing natural language is still localized; invariant judge instructions do not authorize leaving user requirements untranslated.

Tool names and the structured action representation remain unchanged across language conditions. The canonical action's semantics remain identical within each counterfactual pair. Keep entity identity, currency, calendar date, time, timezone, and numeric value controlled across language variants: use stable entity mappings, the same ISO 4217 currency and amount, unambiguous date/time with timezone, and identical normalized numeric values. Freeze any numeral-glyph and date-display convention before construction; do not silently convert units, currencies, or calendar values.

### Code-like technical strings in conversation text

Keep literal technical spans byte-identical across language variants when they are identifiers rather than prose, including tool/function names, API and field identifiers, account/record IDs, URLs, email addresses, and code snippets. Mark such spans as invariant literals in the authoring record. Translate/localize the surrounding natural-language instruction when it conveys user intent, a constraint, or a reason. Do not confuse invariant tool/action structure with natural-language content that belongs in the user's instruction. If a code-like token itself carries a user-facing constraint or status meaning, include a localized natural-language statement of that meaning as well, or exclude the case under a reviewed rule; do not assume an unchanged technical token is semantically transparent in Arabic.

## Provenance, templates, and leakage control

Every record and derivative must retain, at minimum:

- canonical scenario ID, source scenario ID, derivative/parent IDs, history-pair ID, language-variant ID, and condition; P1 provenance enumerates all history and language-variant derivative IDs;
- primary/control set membership, domain, transition or no-change family, match-set ID when applicable, and partition;
- authoring template ID and semantic-recipe ID, including version;
- construction/source method, oracle version, language/translation version, validation/adjudication status, revision history, and exclusion reason;
- invariant-literal spans and the controlled name, currency, date, time, timezone, and numeric mappings.

An authoring template records a reusable linguistic/structural frame; a semantic recipe records the constraint logic and action pattern. Before a dataset is frozen, define and run lexical and semantic near-duplicate checks, record their method/version and adjudication, and retain matches and exclusions. Inventory shared linguistic frames, constraint structures, values, and action patterns. Report the number of genuinely distinct authoring templates and semantic recipes, the number of scenarios per template/recipe, near-duplicate rates, and cross-partition reuse.

Where feasible, keep template families in one partition and preserve independent templates across development and locked evaluation. If a template must span partitions, document why, quantify the overlap, and treat it as a leakage threat in analysis. Scenario-level clustering remains the primary dependence unit, but it can underestimate uncertainty when scenarios share templates or recipes; report a template-aware sensitivity analysis where the number and distribution of templates permit it. Do not inflate the nominal independent sample size by counting histories, translations, or items as scenarios.

The 12 control scenarios are additional to the 48 primary scenarios. Their matching links and any shared templates/recipes must be considered in dependence and leakage accounting, while control results remain separate from primary results.

## Validation, competence checks, and exclusions

Each English/Arabic variant requires independent semantic validation by qualified bilingual reviewers. Check meaning, polarity, scope, chronology, referents, quantities, permission, temporal interpretation, invariant literals, and validity-label preservation. A back-translation is supplementary, not a substitute. Adjudicate ambiguity under a predeclared rule and retain unsuccessful or excluded candidates in an audit log; never silently discard or replace cases based on judge performance.

Before selecting judges for locked evaluation, run development-only basic English/MSA competence checks on separate screening material. Predefine the screen and qualification criteria; do not use locked examples or labels, study gold labels, canonical effective states, or oracle verdicts for judge selection. These checks are not part of the 480-item benchmark and do not establish task-judging reliability.

No examples, translations, or records are created during P0. If a later construction method uses a generative model, disclose its model, prompt, and role, then independently validate outputs; generated content never establishes its own reference label.

## Label isolation and access

Store gold labels, canonical effective states, and oracle verdicts in a reference layer separated from ordinary judge inputs. Ordinary inference receives only the approved conversation, action, fixed judge instruction, and an opaque item ID. Reference scoring runs through a separate access path after the response is retained; it cannot return hidden reference data to the judge. No gold labels, canonical effective states, or oracle verdicts may enter ordinary judge prompts or development-time judge/model selection. Oracle-state access is a separately named diagnostic condition and is not an ordinary baseline.
