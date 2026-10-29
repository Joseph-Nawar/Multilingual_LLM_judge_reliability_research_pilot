# Dataset and canonical-state specification

**Status:** conceptual P0 specification, amended after the 2026-10-29 research-owner audit. No dataset or generator is included.

**Authoritative label source:** canonical task state plus an executable validity rule, to be implemented and tested in P1.

## Study units and planned counts

- **Canonical scenario:** highest-level content and partition unit. It defines a domain, a requirement/state history, relevant entities, and one canonical action.
- **Counterfactual history:** one of two histories for a scenario. Both retain identical action semantics; their initial/effective states yield opposite validity labels.
- **Derived evaluation item:** one history rendered under one language condition and paired with the scenario's canonical action. A canonical scenario contributes 2 histories × 4 conditions = 8 items.

| Set | Canonical scenarios | Histories | Items | Partition plan |
| --- | ---: | ---: | ---: | --- |
| Primary consequential-change set | 48 | 96 | 384 | 12 development; 36 locked evaluation |
| Auxiliary no-change linguistic control | 12 | 24 | 96 | 12 locked auxiliary scenarios; none in development, pending P1 approval |
| **Total planned corpus** | **60** | **120** | **480** | **12 development primary; 48 locked total (36 primary + 12 control)** |

The primary design remains unchanged: 3 domains × 4 consequential transition families, 48 scenarios, and 384 items. It yields 96 development items and 288 locked primary items. Each scenario-condition pair has one valid and one invalid item. Each primary language condition has 96 items (48 valid, 48 invalid); the development partition has 24 per condition (12/12), and the locked primary partition has 72 (36/36).

The separate control adds 96 items. Each control language condition has 24 items (12 valid, 12 invalid). Under the current proposal, controls are locked and never used for development-time judge selection. Thus the combined locked evaluation inventory has 384 items (288 primary + 96 control), while the primary estimand continues to use only the 36 primary locked scenarios. The all-locked control allocation is a proposal that the research owner must approve in P1 before any control construction.

## Primary consequential-change scenarios

The primary set covers booking, customer operations, and scheduling and the four transition families: introduction, numerical revision, permission revocation, and temporal revision. It retains the proposed 4-scenarios-per-domain/family-cell allocation. The current primary partition proposal assigns one scenario per cell to development and three to locked evaluation. Every counterfactual history, language variant, action rendering, and other derivative follows its canonical scenario's partition.

## Auxiliary no-change linguistic controls

Each control history contains a later user turn that restates or confirms an already active requirement while leaving its effective meaning unchanged. For example, a booking history may begin with a maximum fare and later repeat that same maximum. The paired history begins with a different maximum and later repeats that different maximum. An identical action can then be valid under one initial requirement and invalid under the other. Opposite labels arise from the pair's different initial states; neither history contains an actual constraint revision. The oracle must verify state equality immediately before and after the restatement.

Where feasible, match each control scenario to a locked primary scenario on domain, constraint type, the pair of final effective states, action complexity, and turn structure. Give the two records distinct canonical IDs and link them with a match-set ID. Preserve all control histories and variants together in the locked auxiliary partition. Record failed matches and their reasons; do not weaken the matching record after observing judge results.

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

The rule must resolve active constraints, supersession, revocation, numerical bounds, and temporal conditions without an LLM. For each control restatement it must verify that the effective state is unchanged; for each counterfactual pair it must compute opposite labels for the same action. Booking and scheduling values must use unambiguous dates, times, and time zones. P1 will define the machine-readable schema and executable oracle; P0 defines their authority, not their implementation.

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

- canonical scenario ID, source scenario ID, derivative/parent IDs, history-pair ID, language-variant ID, and condition;
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
