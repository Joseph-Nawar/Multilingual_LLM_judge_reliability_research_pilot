# Research protocol and hypotheses

**Status:** P0 proposal for independent methodological review; not frozen for execution.

**Study type:** controlled exploratory feasibility pilot.

**Primary object:** the LLM judge's binary action-validity classification.

## Research question

Do LLM-based evaluators become less reliable when agent-action validity depends on user constraints introduced, revised, or revoked across languages?

The pilot compares English and Arabic conditions with paired scenario content and counterfactual histories. It tests evaluator behavior, not the ability of an agent to complete a task.

## Provisional hypotheses

- **H1:** Language switching during constraint revision introduces additional evaluation errors beyond individual-language difficulty.
- **H2:** Some evaluation errors arise from incorrectly reconstructing the effective task state.
- **H3:** Translation-first and structured-judging approaches leave a measurable unresolved weakness in this setting.

These statements are hypotheses, not findings. A null effect, a benefit from language switching, no detectable state-reconstruction contribution, or a strong baseline result are all valid outcomes. H3 is especially provisional: the literature register documents nearby methods, but does not establish that either approach fails on this study's task.

## Proposed pilot design

The pilot comprises 48 canonical scenarios across booking, customer operations, and scheduling. Each scenario has one constraint-transition family: introduction, numerical revision, permission revocation, or temporal revision. Each has two counterfactual conversational histories that preserve the same agent action while changing the effective constraint state so that the action is valid in one history and invalid in the other.

Each history is rendered under four ordered language conditions: EN–EN, AR–AR, EN–AR, and AR–EN. For an initial operationalization, the first language denotes the initial task/constraint context; the second denotes the later turn that introduces or changes the decisive constraint. Turns before that state-changing turn use the first language. Exact language assignment for all other turns, Arabic variety, and the action representation remain design decisions for the P0 review gate (see the dataset specification).

This yields 48 × 2 × 4 = 384 derived items: 96 items per language condition, with 48 valid and 48 invalid in each condition. The proposed partition is 12 development scenarios and 36 locked evaluation scenarios. Every history, language rendering, and other derivative of a canonical scenario remains in that scenario's single partition.

The language-neutral action representation should be identical within a scenario's counterfactual pair and across its language conditions. This is a proposed control to isolate language effects in the dialogue; whether a structured action object is the right representation requires review before dataset construction.

## Primary estimand and interpretation

The primary outcome is whether the judge's validity label matches the label produced by the canonical state and executable validity rule. The primary planned contrast for H1 is the equally weighted difference in classification error between the two cross-language conditions (EN–AR and AR–EN, averaged) and the two same-language conditions (EN–EN and AR–AR, averaged). A positive difference is directionally consistent with H1 but is not by itself evidence of a general causal language-switching effect.

Report all four conditions separately, alongside their equally weighted cross-language and same-language summaries. Do not infer a switching effect from a pooled score alone: English and Arabic difficulty, transition family, domain, and direction may differ. The locked set contains 36 independent canonical-scenario clusters; 288 derived items in that partition are not 288 independent observations. Treat this as an exploratory pilot with limited precision, not as a confirmatory test.

## Ground truth and label isolation

The canonical task state and deterministic, executable validity rule are authoritative. The rule must resolve which constraints are active at the action time, including supersession, revocation, numerical bounds, and temporal conditions. LLM output is never a label source.

In ordinary judge conditions, provide the conversation and action needed for evaluation, but withhold the reference label, canonical final state, and oracle output. Any intervention that exposes the canonical effective state is a separately named diagnostic condition. It is not a fair deployable baseline and must not be included in ordinary-condition accuracy summaries.

## Design principles

- Preserve counterfactual pairing and equal valid/invalid counts in every language condition and partition.
- Change only the decisive state-changing content between a counterfactual pair where feasible; document other differences and review them for confounding.
- Keep source scenario, translations, and all derivatives traceable through stable identifiers.
- Have language variants validated independently for semantic equivalence, constraint scope, chronology, and label preservation.
- Freeze prompts, dataset, model identity, decoding configuration, metrics, exclusions, and analysis before the locked evaluation.
- Do not select or alter examples after observing judge performance.
- Report uncertainty and practical size of effects. Statistical significance alone is not a go/no-go criterion.

## Scope limits

This pilot is a feasibility study over a small, controlled set of synthetic or authored scenarios, not a representative estimate of real-world judge reliability. Arabic variety, translation/localization conventions, judge-language instructions, the exact baseline implementations, and error-attribution procedures remain unresolved and must be reviewed before the relevant milestone. Negative or inconclusive results must be reported with the same care as positive results.

## Decisions for the P0 review gate

The research owner should explicitly review and resolve, or assign a later resolution gate for:

1. Whether the language-condition mapping above correctly operationalizes a language switch, including the language of intermediate turns and the agent action.
2. Arabic variety and conventions for numerals, dates, times, and terminology.
3. Whether a structured action object is the right control for holding agent-action semantics constant.
4. The 4-scenarios-per-domain/family-cell proposal and 1-development/3-evaluation split within each cell.
5. Feasible, fair definitions for the direct, translation-first, structured-judging, and oracle-state conditions, including same-model controls.
6. A valid and reliable H2 error-attribution procedure and the role of judge rationales.
7. The clustered interval procedure and any detectable-effect/power analysis warranted by 36 locked scenario clusters.

Unresolved items must remain visible in the decision log and be closed before the milestone that depends on them; they are not settled merely by appearing in this draft.
