# Research protocol and hypotheses

**Status:** P0 specification amended after the 2026-10-29 research-owner audit; not frozen for execution.

**Study type:** controlled exploratory feasibility pilot.

**Primary object:** the LLM judge's binary action-validity classification.

## Research question

Do LLM-based evaluators become less reliable when agent-action validity depends on user constraints introduced, revised, or revoked across languages?

The pilot compares English and Arabic conditions with paired scenario content and counterfactual histories. It tests evaluator behavior, not the ability of an agent to complete a task.

## Provisional hypotheses

- **H1:** Language switching during a consequential constraint change introduces additional evaluation errors beyond individual-language difficulty.
- **H2:** Some evaluation errors arise from incorrectly reconstructing the effective task state.
- **H3:** Existing translation-first and structured/decomposed judging approaches leave a measurable unresolved weakness in this setting.

These statements are hypotheses, not findings. A null effect, a benefit from language switching, no detectable state-reconstruction contribution, or a strong baseline result are all valid outcomes. Language switching during a semantically unchanged restatement is measured in a separate exploratory control. Neither that small control nor a cross-language versus same-language contrast fully identifies the causal effect of consequential revision. H3 is especially provisional: the literature register documents nearby methods, but does not establish that any candidate baseline fails on this study's task.

## Proposed pilot design

### Primary consequential-change set

The primary set comprises 48 canonical scenarios across booking, customer operations, and scheduling. Each scenario has one consequential constraint-transition family: introduction, numerical revision, permission revocation, or temporal revision. Each has two counterfactual conversational histories that preserve the same action semantics while changing the effective constraint state so that the action is valid in one history and invalid in the other.

The primary set has 48 canonical scenarios, 96 counterfactual histories, and 384 derived evaluation items (48 × 2 × 4). It retains 12 development and 36 locked evaluation scenarios: 96 development items and 288 locked primary items. All histories and language variants of a canonical scenario stay in one partition.

### Separate no-change linguistic control

An exploratory control adds 12 canonical no-change scenarios, 24 histories, and 96 evaluation items (12 × 2 × 4). In each history, a later user turn restates or confirms an already active requirement without changing its effective meaning. The two histories in a control pair begin with different active values or permissions, and each later restatement repeats its own initial requirement; the unchanged action is therefore valid in one history and invalid in the other without any within-history constraint revision. For example, two histories can begin with different budget ceilings, repeat those same ceilings later, and retain one identical action that is valid under only one ceiling.

Where feasible, each control scenario is matched to a primary scenario on domain, constraint type, the pair of final effective states, action complexity, and turn structure. The relationship is recorded without merging the distinct canonical IDs. Control results remain auxiliary and are never included in the primary estimand. The current partition proposal keeps all 12 controls in a locked auxiliary set, matched only to locked primary scenarios; this proposal requires explicit P1 approval before construction. Under that proposal, the full plan has 60 canonical scenarios and 480 items: 12 development primary scenarios (96 items), 36 locked primary scenarios (288 items), and 12 locked controls (96 items). Each control language condition has 24 items, 12 valid and 12 invalid.

### Language conditions and controlled representations

The four conditions are EN–EN, AR–AR, EN–AR, and AR–EN. The initial context uses the first language; the decisive later turn (constraint change in the primary set, no-change restatement in the control) uses the second. All other turn-language assignments are fixed in the approved scenario specification. Arabic is Modern Standard Arabic (MSA); Egyptian Arabic and Arabizi are outside this pilot. The judge instruction is fixed in English and identical across all four conditions.

Tool names and the structured action representation remain unchanged across language conditions. Action semantics remain identical within counterfactual pairs. User-facing natural-language instructions that express a task or constraint are localized as natural language; they are not frozen in English merely because the structured action is invariant. Names, currencies, dates, times, and numeric values are controlled across variants. Dates and times must be unambiguous and include the applicable time zone. The dataset specification defines how invariant code-like strings are treated.

## Primary outcome and interpretation

The primary outcome is whether the judge's validity label matches the label produced by the canonical state and executable validity rule. The primary comparison reports correctness and class-specific performance separately for all four conditions: EN–EN, AR–AR, EN–AR, and AR–EN. The equally weighted cross-language versus same-language error contrast remains exploratory; a positive difference is directionally consistent with H1 but is not by itself evidence of a causal effect of consequential constraint revision.

Report all four conditions separately, alongside any clearly labeled exploratory cross-language and same-language summary. Do not infer a switching effect from a pooled score alone: English and Arabic difficulty, transition family, domain, and direction may differ. The primary locked set contains 36 canonical-scenario clusters; its 288 derived items are not 288 independent observations. The separate control contains 12 additional locked scenarios. Neither set supports confirmatory claims or invented power calculations.

## Ground truth and label isolation

The canonical task state and deterministic, executable validity rule are authoritative. The rule must resolve which constraints are active at the action time, including supersession, revocation, numerical bounds, and temporal conditions. For no-change controls, it must verify that the restatement leaves the effective state unchanged. LLM output is never a label source.

Ordinary judge inference and reference scoring use separated data-access paths. The ordinary judge receives the conversation and action needed for evaluation, but not gold labels, canonical effective states, oracle verdicts, or pairing keys. These materials are also excluded from development-time judge/model selection. The reference scorer consumes the response and opaque item ID through a separate path and cannot supply hidden references back to the judge. Any intervention that exposes canonical effective state is a separately named oracle diagnostic; it is not a fair deployable baseline and is excluded from ordinary-condition summaries.

## Design principles

- Preserve counterfactual pairing and equal valid/invalid counts in every language condition and partition.
- Keep the primary consequential-change set and no-change controls separately identified, scored, and reported.
- Change only the decisive state-changing content between a counterfactual pair where feasible; document other differences and review them for confounding.
- Keep source scenario, translations, and all derivatives traceable through stable identifiers.
- Track authoring templates and semantic recipes, detect near duplicates, and report genuinely distinct template counts; do not treat shared templates or derived items as additional independent scenarios.
- Have language variants validated independently for semantic equivalence, constraint scope, chronology, and label preservation.
- Run development-only basic English/MSA competence checks on separate screening material before judge selection; do not use locked examples, locked labels, or study gold labels for selection.
- Freeze prompts, dataset, model identity, decoding configuration, metrics, exclusions, and analysis before the locked evaluation.
- Do not select or alter examples after observing judge performance.
- Report uncertainty and practical size of effects. Statistical significance alone is not a go/no-go criterion.

## Scope limits

This pilot is a feasibility study over a small, controlled set of synthetic or authored scenarios, not a representative estimate of real-world judge reliability. The small no-change control cannot fully identify the causal effect of consequential revision. Shared authoring templates may induce dependence beyond canonical-scenario clustering. Exact baseline selection, translation/localization procedure, template-allocation feasibility, code-like literal policy, and H2 diagnostic protocol must be resolved at their roadmap gates. Negative or inconclusive results must be reported with the same care as positive results.

## Decisions for the P0 review gate

The 2026-10-29 review decisions and remaining uncertainties are recorded in [the P0 audit decision record](decision-records/2026-10-29-p0-research-audit.md). That record distinguishes approved scope from proposals that must be approved before P1, P3, or the locked evaluation. P0 approval does not authorize P1 or model inference.
