# Research integrity and reproducibility

These requirements govern future dataset work and model evaluation. P0 creates no data and makes no model calls.

## Reference authority and separated access

- Canonical task states and executable validity rules are the sole authority for reference labels. LLM output, rationales, consensus, or majority vote never define ground truth.
- Store gold labels, canonical effective states, and oracle verdicts in a reference layer separated from ordinary judge inputs.
- Ordinary inference receives only the approved conversation, action, fixed judge instruction, and opaque item ID. Reference scoring receives the retained response and ID through a separate access path after inference; it cannot return hidden reference data to the judge.
- Gold labels, canonical states, and oracle verdicts must not enter ordinary judge prompts or development-time judge/model selection. Offline reference scoring for data/oracle QA does not authorize label-driven judge or prompt selection.
- Oracle-state access is a separately named diagnostic intervention. It withholds the validity label, is excluded from ordinary-baseline summaries, and is never presented as a fair deployable baseline.

## Dataset and counterfactual integrity

- Preserve the 48-scenario primary consequential-change set (384 items; 12 development and 36 locked scenarios) separately from the 12-scenario no-change control (96 additional items). The control contains later restatements that leave effective meaning unchanged; its paired opposite labels arise from different initial active requirements, not an actual revision within either history.
- Keep primary and control counts, labels, scoring, and results distinct. Under the current proposal, controls are all locked auxiliary scenarios; the research owner must approve that partition before P1 construction.
- Preserve counterfactual links and assign every history, language variant, and derivative of a canonical scenario to one partition. Keep matched primary-control scenarios linked but separately identified.
- Balance valid and invalid items within each condition and approved partition. Record domain, condition, set, match, and partition in the manifest.
- Validate all four language conditions (EN–EN, AR–AR, EN–AR, AR–EN) independently for semantic equivalence, constraint scope, chronology, action meaning, and label preservation. Apply the approved MSA and invariant-literal policy.
- Run development-only basic English/MSA competence checks on separate screening material before judge selection. Predefine the materials and criteria; do not use locked examples or labels or study gold labels, canonical states, or oracle verdicts for selection.

## Provenance, templates, duplicates, and partitions

Every record and derivative must retain canonical/source/parent/derivative IDs; counterfactual, language, and match-set IDs; primary/control designation; domain, condition, and split; authoring-template ID; semantic-recipe ID and version; construction and translation method/version; oracle and validation status; invariant-literal spans; revisions; and exclusion reasons.

Before a dataset is frozen, run and document lexical and semantic near-duplicate detection, including method/version and adjudication. Inventory shared linguistic frames, constraint structures, values, and action patterns. Report how many genuinely distinct authoring templates and semantic recipes exist, their reuse distribution, near-duplicate rates, and template/recipe overlap across partitions. Where feasible, keep template families within one partition and preserve independent templates between development and locked evaluation. Record unavoidable cross-partition reuse as a leakage threat.

Canonical scenarios remain the main dependence unit, but scenario-level clustering can underestimate uncertainty when records share a template or semantic recipe. Preserve template identifiers for a template-aware sensitivity analysis when the number and distribution allow it. Do not inflate sample size using histories, translations, items, or template variants.

Preserve unsuccessful, ambiguous, revised, and excluded candidates with reasons. Apply exclusions before observing judge results; never silently discard or replace examples in response to performance.

## Baselines and protocol freeze

Direct multilingual, translation-first, and structured/decomposed judging are candidate mandatory ordinary-condition baselines. The research owner must approve which are mandatory before the locked evaluation. Document any cost/feasibility omission before locked evaluation and unblinding. Any method introduced after inspecting locked results is exploratory and cannot support an unqualified preplanned H3 claim.

Use the same judge backbone/version and controlled settings across baselines where feasible, provide equivalent access to underlying evidence, and freeze prompts, translator, translation procedures, criteria, aggregation, parsers, and exceptions before locked evaluation. Keep translator and judge tokens/costs separate and report both. Do not claim a published method was faithfully reproduced until its implementation has been checked and documented.

Before locked evaluation, version and hash the primary/control datasets, partition/match manifest, template inventory, prompts, models, decoding settings, translation procedures, output schema/parser, metrics, exclusion/retry rules, and analysis. Assign an immutable run ID and code revision. Preserve raw translation and judge requests/responses, model/provider versions, token use by component, timestamps, latency, failures, and deviations.

## Failures, analysis, and reporting

- Failed or incomplete evaluations remain visible. Never retry automatically or omit results without a predeclared rule. Report requested/completed/missing counts and deviations by condition and baseline.
- Use canonical scenarios as the primary dependence unit; keep counterfactual and language derivatives paired. Keep matched control comparisons linked and separately reported.
- Report all four primary language conditions separately. The cross-language versus same-language error contrast is exploratory. Control-set comparisons are secondary exploratory analyses and do not replace the primary comparison or fully identify a causal effect of revision.
- Report scenario-clustered uncertainty and template-aware sensitivity where feasible. Do not treat item count as independent sample size or invent power calculations.
- Model explanations are not ground truth about internal reasoning. H2 requires controlled diagnostic evidence; rationale coding alone is insufficient.
- Report invalid, malformed, refused, and missing results under the frozen scoring rule. Distinguish planned from exploratory analyses and report null, mixed, adverse, and positive results.
- Do not select, rewrite, or exclude locked examples based on judge performance. Statistical significance alone is not a go/no-go criterion.

## Model calls and cost

No model calls are permitted during P0. This repository grants no inference budget. Future paid inference requires explicit budget authorization. A future runner must preserve the prompt, raw response, model version, token use, and execution metadata for every attempt, including failures. Language-competence screening is a separate development-only qualification procedure, not a locked evaluation or task-accuracy result.

## Independent review and decision ownership

Codex may draft specifications, implement approved tooling, and check artifacts, but is not the final authority on scientific correctness. Major methodological decisions require explicit research-owner review. Maintain a dated decision/deviation record with the decision, approved status, rationale, reviewer, affected artifact/version, remaining uncertainty, resolution milestone, and consequences for validity or reproducibility. Each milestone requires an evidence-based review gate before the next begins.
