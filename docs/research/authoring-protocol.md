# Scenario authoring protocol

**Status:** P2A was approved as an authoring-feasibility milestone. P2B-1 authorizes corrections and human-review preparation for the existing four local development prototypes only. It does not authorize additional study scenarios, controls, locked examples, or dataset freeze.

## Purpose and selection independence

The research question is: **Do LLM judges correctly assess agent actions when effective user constraints evolve across English and Arabic conversations?** Scenario authors create controlled tasks for evaluating judges, not task-performing agents. A scenario is selected because it represents a clear, ordinary decision in booking, customer operations, or scheduling and can be formalized without obscure domain conventions. Authors do not search for scenarios, retain examples, or revise wording based on model-judge behavior. P2A uses no judge outputs.

Before writing dialogue, register a canonical scenario concept, its domain/family cell, intended semantic recipe, authoring-template family, source and parent relationships, development partition, author, date, and version. Review the proposed concept for overlap with existing concepts and record rejected alternatives; do not silently replace a difficult candidate.

## Formal contract before language

1. **Define the task facts.** Record the relevant entities, stable IDs, requested operation, and any context needed to understand the action. Keep unrelated context constant across a counterfactual pair.
2. **Define the action contract.** Specify the public tool name/version, every parameter and type, required status, entity, execution time, and permission requirements. Every action in the pair is the same well-formed typed call. Do not manufacture an invalid example by omitting parameters or violating the public tool schema.
3. **Write the initial state.** List every initially active requirement and grant, including identity, scope, field, units, boundary inclusivity, and version. Permission is explicit: absent authorization is not a grant. If an action needs permission, show that permission explicitly in the initial conversation.
4. **Make the requirement observable.** Every formal fact that can affect validity must have a planned user-facing expression before the action: initial requirements and grants, decisive events, and any constraint retained after a revision. A requirement that exists only in the reference record is a design error. Use the semantic-coverage map to link each formal target to one or more conversation segment IDs.

## Counterfactual construction

Primary histories start from semantically equivalent formal states and share the action, action decision point, decisive turn, domain facts, and non-decisive context. The formal event group is the only intended causal divergence. Both histories must have the same pre-decisive validity label; after the decisive event the P1 oracle must assign opposite labels to the identical action. Check both histories against the entire effective state, not a label assertion supplied by the author.

Do not make the counterfactual history position a label cue. The four P2A prototypes currently use the same position convention; preserve their existing labels and ordering. For the full primary set, plan a cross-balanced allocation within each domain × transition-family cell: one directly specified and one history-dependent scenario with the valid history in position A, and one of each complexity with the valid history in position B. Select the 12 development slots so that the four complexity × valid-position combinations each occur three times; the remaining locked slots then contain nine scenarios per combination. If independent review changes a complexity classification, update the prospective allocation before any locked authoring and retain the prior plan and reason. Counterbalance the 12 auxiliary controls separately, with six scenarios per valid-history position; control matches do not transfer label position or partition. This allocation controls position at the scenario level and does not make the derived items independent.

Use the approved family-specific forms:

- **Introduction:** both histories introduce the same kind of new requirement at the same decisive turn, with different meaningful values or bounds. The action is between the resulting valid and invalid states. No hidden initial version of that requirement may exist.
- **Numerical revision:** both histories revise the same active numeric requirement from the same initial state. Both changes alter effective semantics; choose values so the unchanged action passes one revised bound and fails the other.
- **Permission revocation:** both histories begin with the same explicit grant. One decisive event revokes it; the paired event explicitly restates/preserves it. The action contract requires that permission. Missing permission is never treated as authorization.
- **Temporal revision:** both histories revise the same active temporal bound from the same initial state. Use an action time that lies on opposite sides of the resulting bounds. Store offset-aware ISO 8601 times and state boundary inclusivity explicitly.

Run the deterministic P1 oracle and pair validator after formalization. Store the oracle results only in local reference data. If a pair does not pass, preserve its validation error and revise or reject it with a recorded reason; never modify a label to satisfy a proposed contrast. No-change controls are not authored in P2A. Their future histories begin from different initial requirements and contain only no-op restatements, as specified in the dataset contract.

## Natural-language authoring and semantic visibility

Draft each initial context in its assigned first language, then draft the decisive later user turn in its assigned second language. The four conditions are EN–EN, AR–AR, EN–AR, and AR–EN. Arabic is Modern Standard Arabic. Other turns use the first language unless a future approved scenario specification records a reasoned override. Judge instructions remain fixed English. Egyptian Arabic and Arabizi are excluded.

Express requirements as natural user instructions, not as schema descriptions. The decisive turn must state what is introduced, revised, or revoked and its scope. Avoid unexplained shorthand, legalistic boilerplate, ambiguous pronouns, implicit permission, and unstated exceptions. An ordinary reader should be able to connect the instruction to the action without seeing canonical-state metadata.

For each language variant, maintain a semantic-coverage entry for every shared context fact, action field used in the task, initial requirement, initial permission grant, and formal event. Link the target to segment IDs in the correct user turn: initial targets map to the initial context turn; event targets map to the event's formal turn. Every decision-relevant initial requirement, permission, or event must link to at least one localized natural-language segment containing a non-whitespace character, even when exact values or identifiers are also shown as invariant literals. Context facts and action values may be surfaced through invariant literals where appropriate, but a structured action is never a substitute for natural-language user intent or requirements. The preflight utility checks that IDs resolve, target coverage is complete, required natural-language spans are non-empty, and target turns are structurally correct. **It cannot prove that the span expresses the target's meaning.** Semantic-coverage completion must never be called translation validation.

English and MSA are separately authored drafts, not assumed translations of each other. Use the canonical specification as their shared meaning source. Keep entity IDs, tool names, structured action, currency codes, Western numerals, exact monetary values, dates, and times unchanged. Monetary amounts use exact Decimal values and ISO 4217 currency codes. Dates and times use unambiguous ISO 8601 forms with explicit offsets. Mark code-like identifiers and technical literals as invariant spans; localize surrounding user intent and constraint meaning rather than treating the structured action as a substitute for the user's words.

### Scenario complexity and historical-state dependence

Assign complexity from the information needed to determine the action's validity, not from turn count:

- **Directly specified:** the decisive requirement and every other decision-relevant fact needed for validity can be determined from the decisive turn, action, and public tool contract alone.
- **History-dependent:** earlier conversational information is necessary to retrieve an initial requirement, permission, or prior value and combine it with the decisive turn.

Every bilingual reviewer answers: **“Can the action's validity be uniquely determined from the decisive turn, action, and public tool contract alone, or is earlier conversational information necessary?”** Record `yes`, `no`, or `unclear` and a rationale tied to the formal constraint and the visible turn(s). `yes` maps to directly specified; `no` maps to history-dependent; `unclear` remains unresolved. A relative change is not automatically history-dependent if the decisive turn supplies all needed operands; conversely, an explicit decisive value may still be history-dependent if another needed permission or requirement appears only earlier. The current four prototypes' provisional authoring assessment and rationale are kept out of reviewer packets so reviewers answer independently.

For the 48 primary scenarios, the prospective target is 24 directly specified and 24 history-dependent scenarios, with two of each category per domain × transition-family cell. The development split targets six per category and the locked primary split targets 18 per category, subject to independent content review and allocation feasibility. This is a planned descriptive exploratory contrast, not a power claim or confirmatory comparison. Report the category separately and preserve the primary four-language-condition comparison. Controls remain separate and are not included in these counts.

Natural wording takes precedence over matching token or character counts. Do not distort meaning to equalize length. Where a draft sounds unnatural, unclear, or overly technical, revise it before independent review and retain the old version and hash. Ambiguity or an unresolved domain assumption is a reason to revise or reject, not to infer intended meaning from the oracle label.

## Anti-shortcut review before freeze

Before the full dataset is frozen, use a predeclared human-coded audit to compare validity labels with: negation; permission wording; direction of numeric revision; explicit confirmation; turn count; character and language-appropriate token length; numeric magnitude; upper versus lower numeric bounds; earliest versus latest temporal boundaries; temporal expressions; critical-information turn and span position; and formality/naturalness. Report label associations as counts and conditional proportions, retaining scenario and template dependence; do not treat language derivatives as independent observations. Cross-tab by domain, transition family, language condition, complexity category, and partition where cell sizes permit. Identify perfect or near-perfect trivial cues and revise candidates before locked evaluation or record the unresolved threat. Do not use significance tests on the pilot as a shortcut for balancing, and do not force unnatural phrasing or identical lengths. Every revision is revalidated and hashed.

The four P2A prototypes are too few to establish surface-feature balance. Their preflight report records evident potential confounds only; it makes no population or predictive claim.

## Provenance, review, and exclusion

For each canonical record, preserve the scenario and derivative IDs, source/parent relationship, partition, semantic-recipe and template identifiers with versions, authoring method, initial formal state, event history, action contract, coverage map, language-variant hashes, validation status, revision chain, and exclusion reason. Each revision names changed fields, reason, prior content hash, new content hash, author, and date. Preserve unsuccessful and ambiguous candidates in an auditable rejection ledger; do not silently discard or replace them.

All current language remains Codex-authored, machine-assisted draft material and **not independently validated**. A review-ready candidate requires two qualified bilingual reviewers following the [bilingual annotation protocol](bilingual-annotation-protocol.md), independent annotations, agreement reporting, and adjudication of disagreements. Reviewers may inspect the formal specification, but must not see model-judge predictions. Bind each annotation to both the exact language-variant hash and canonical-scenario hash. A substantive edit invalidates prior review for the changed hashes and requires re-review. If a second qualified reviewer is unavailable, record that limitation and stop before declaring independent validation or dataset readiness.

## Data handling and authoring gate

P2A/P2B-1 canonical examples, translations, coverage records, oracle labels, revision snapshots, reviewer packets, annotations, and adjudications remain under ignored local `.research-data/` paths. Only schemas, utilities, procedures, synthetic tests, and approved redacted aggregate reports may be committed. Check both Git ignore behavior and the tracked-file index before release; ignore rules do not untrack an already committed file.

Before any later authoring milestone, the research owner reviews this procedure, the blueprint, semantic visibility checks, template plan, surface-feature audit, and the P2A preflight report. Passing deterministic schema/oracle checks is necessary but does not establish bilingual semantic validity or authorize a locked evaluation.
