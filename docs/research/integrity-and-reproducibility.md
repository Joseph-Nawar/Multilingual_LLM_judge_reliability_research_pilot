# Research integrity and reproducibility

These requirements govern future dataset work and model evaluation. P0 creates no data and makes no model calls.

## Reference-label authority

- Canonical task state and the executable validity rule are the sole authority for reference labels.
- An LLM-generated answer, explanation, consensus, or majority vote is never ground truth.
- Ordinary judge prompts must not contain reference labels, final canonical states, or oracle outputs.
- Oracle-state access is a separate diagnostic intervention. Label it clearly, withhold the label where possible, and never present it as a fair deployable baseline.

## Dataset integrity

- Preserve counterfactual links and assign all derivatives of a canonical scenario to one partition.
- Enforce balanced valid and invalid labels within each language condition and partition.
- Maintain provenance for construction, translation, validation, oracle version, revisions, and exclusions.
- Independently validate each language variant for meaning, constraint scope, chronology, and label preservation.
- Record every ambiguous, unsuccessful, revised, or excluded candidate and its reason. Apply predeclared rules; do not discard cases silently or in response to model performance.
- Keep locked evaluation data and labels unavailable to development-time prompt selection and tuning.

## Frozen protocol and immutable runs

Before locked evaluation, version and hash the prompts, dataset files and split manifest, model identifiers, decoding configurations, output schema/parser, metrics, exclusion/retry rules, and analysis procedure. Record a unique immutable run ID and code revision. Preserve raw requests and responses, provider/API versions or local weight and quantization identifiers, token usage, timestamps, latency, errors, environment details, and all retries. A hash establishes identity, not correctness; pair it with provenance and independent review.

Failed or incomplete evaluations must remain visible. Never retry automatically or omit results without a predeclared rule. Report requested/completed/missing counts and any deviations by condition. A change after freeze creates a new version and run ID; retain prior artifacts and document why the change occurred.

## Statistical and reporting integrity

- Use canonical scenarios as the primary dependence unit; keep repeated counterfactual and language derivatives paired.
- Report all four language conditions separately, with class-specific outcomes and scenario-clustered uncertainty.
- Report invalid, malformed, refused, and missing outputs explicitly under the frozen scoring rule.
- Do not select, rewrite, or exclude evaluation items based on judge performance.
- Label pilot findings exploratory. Report null, mixed, adverse, and positive results; distinguish preplanned outcomes from exploratory analyses.
- Do not use statistical significance alone as a milestone or go/no-go rule.

## Model calls and cost

No model calls are permitted during P0. This repository setup grants no inference budget. Future paid inference requires explicit budget authorization before execution. A future runner must preserve the prompt, raw response, model version, token use, and execution metadata for every attempt, including failures.

## Independent review and decision ownership

Codex may draft specifications, implement approved tooling, and check artifacts, but is not the final authority on scientific correctness. Major methodological decisions—including operational language definitions, Arabic variety, counterfactual construction, baseline comparability, exclusion rules, and inferential procedures—require explicit research-owner review. Each milestone has an evidence-based review gate before the next begins.

Maintain a decision/deviation log with date, decision or deviation, rationale, reviewer, affected artifact/version, and consequences for validity or reproducibility. Record unresolved threats rather than implying that a checklist removes them.
