# P3 Feasibility Findings and Full-Study Authorization

**Date:** 2026-11-11

**Status:** Owner decision recorded; full locked execution authorized after existing bilingual validation and pre-inference freeze.

## Development feasibility findings

The 96-item four-language development experiment is retained as exploratory evidence. Direct judging scored 80/96, translation-first 67/96, and structured judging 55/96. Direct accuracy was 40/48 for same-language conditions and 40/48 for code-switched conditions; this pilot found no aggregate code-switching penalty. Errors were concentrated in numerical and temporal revisions. The post-hoc grouping by the language of the decisive turn is an exploratory hypothesis only.

The 12 canonical development scenarios, not the 96 derived language/history items, are the scenario-level units. These small results do not establish equivalence between language conditions, identify a causal mechanism, or establish general reliability. They are not grounds for changing prompts, settings, models, examples, or labels. The four-scenario P2B review remains closed and is not reopened.

## Approved full-study design

The research owner selected Gemma 4 12B as the sole judge for the full study and approved the three ordinary baselines:

1. Direct multilingual judging with Direct Prompt V2.
2. Translation-first judging with TranslateGemma V3 and Direct Prompt V2.
3. Single-call structured judging with Structured Prompt V2, structured-validity V2, and the existing strict parser/512-token output limit.

Use the existing zero-cost local Ollama setup. The previously approved model and prompt settings remain fixed; no post-pilot prompt, model, or parameter tuning is authorized. The full target is 288 locked primary items and 96 locked auxiliary controls. Controls remain separately identified and reported. No paid or remote API calls are permitted.

## Versioned translation time-equivalence correction

The owner authorized one general translation-validation correction for the previously observed false positive when a clock time such as `14:00` is rendered as `2:00 PM`. Translation literal-validation policy V4 accepts a 12-hour and 24-hour representation only when both parse to the same ordered local clock time. Any explicit date and numeric timezone context remains subject to the existing strict number and identifier checks; the rule does not convert across dates or time zones. Actual clock changes, missing clocks, or additional clocks remain failures. Other numbers, currency codes, identifiers, permission wording, and negation are not relaxed. The TranslateGemma model and prompt V3 are unchanged.

The previous V3 checker and all earlier raw translation responses and failure records remain preserved. Each new translation configuration binds the policy version into its configuration hash. Automated checks do not establish semantic preservation of permissions or negation; those remain part of independent bilingual review. No reference labels or canonical states are used to validate or repair translations.

## Existing validation and execution status

The commissioned two-reviewer package currently contains no submitted review exports and its quality-control status is `not_started`. The dataset is not frozen. No locked item was inferred on in this work.

The full-study authorization takes effect once the already-required bilingual validation is completed, substantive disagreements and uncertainty are documented, justified corrections (if any) are applied before freeze, and the hash-bound pre-inference freeze is prepared. No additional discretionary approval gate is required after those conditions are satisfied. Until then, no locked inference may run.

## Research-owner disposition

Proceed to the full study with Gemma 4 12B and the three approved baselines after the validation and freeze conditions above. Preserve the feasibility findings as exploratory. Keep all private study scenarios, labels, reviewer records, translations, and model outputs under ignored `.research-data/` paths. Do not modify labels from model results, rerun the development pilot, reopen P2B, use Qwen as another study judge, or make paid/remote calls.
