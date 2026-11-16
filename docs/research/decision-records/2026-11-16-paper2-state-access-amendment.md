# Paper 2 state-access design amendment

**Date:** 2026-11-16. **Decision:** GO with the single state-access amendment approved by the research owner. This registers the decision following the 2026-11-15 scientific investment record. It does not change the original scenarios, language variants, actions, oracle labels, reviewer packets, or approved ordinary-baseline prompts.

This is the final scientific investment decision before human validation. It does not reopen the concluded P2B feasibility pilot, commission another feasibility study, or require another discretionary go/no-go decision. The next major milestone is completion of independent bilingual review and dataset freeze.

## Implementation approach

Keep the diagnostic in the ordinary baseline runner was considered and rejected because it would mix a non-deployable state intervention into baseline outputs. Building the state projection at call time was also rejected because the projection and randomization would not be frozen with the study inputs. The selected approach stores a hash-bound, label-free state projection and paired requests in a separate diagnostic namespace at dataset freeze, executes them through a dedicated local runner, and analyzes them separately from the ordinary baselines.

## Prespecified experiment

Run one paired state-access diagnostic on the existing locked set after independent review, documented resolution of substantive issues, deterministic revalidation, and the hash-bound pre-inference freeze:

- **Primary:** all 36 locked primary scenarios and their 288 items.
- **Auxiliary:** all 12 locked auxiliary no-change scenarios and their 96 items.
- **Arms:** one request per item with `effective_state: null` (withheld) and one request with the canonical active state supplied. The two requests share the conversation, action, public tool contract, instruction, output schema, model, decoding, and parser; only `effective_state` differs.
- **Workload:** 384 paired items × two arms = **768 additional local calls**. This is a separate diagnostic, not a fourth ordinary baseline.

Reuse the instruction, binary JSON output contract and parser, pinned `gemma4:12b-it-qat` digest, decoding options, and no-retry policy from `paper2-h2-shared-state-information-v2-20261115` without tuning. The supplied-state projection contains only active numerical/temporal constraints and active permissions in the development diagnostic's state representation. It excludes validity labels, oracle verdicts, reason codes, judge predictions, revoked permissions, and superseded constraints. The ordinary three-baseline prompts and their comparisons remain unchanged.

Before any locked inference, the freeze must bind the projection, both arms' requests, prompt, response contract, model/configuration, randomization, and analysis definition by hash. Execution and outputs use a dedicated state-access path. Every planned arm/item is accounted for once; interrupted started calls are retained as ambiguous and are not automatically resent. Raw requests, responses, technical failures, and parser outcomes are preserved. Reference labels are read only by the separate post-inference scorer.

## Prespecified analysis

The existing primary outcome remains four-condition validity accuracy for each ordinary baseline. Report the state-access comparison separately, with no pooling into ordinary-baseline estimates.

For each scenario, calculate the mean paired correctness difference (`supplied - withheld`) over its eight language/history items. Report the macro-average over the 36 primary scenarios as the primary diagnostic contrast, along with withheld/supplied accuracy, planned-denominator correction/damage counts, correction/damage counts restricted to items parsed in both arms, and scenario-clustered percentile-bootstrap 95% intervals. Use 10,000 scenario resamples with replacement and seed 17, retaining all eight items in each sampled scenario; calculate percentile indices as `floor((n - 1) * p)`. Report condition-specific results for EN–EN, AR–AR, EN–AR, and AR–EN, and transition-family patterns. Keep the 12 auxiliary scenarios separate and use the same scenario-level summaries. The primary-versus-auxiliary contrast in paired effects is explicitly exploratory; independently resample primary and auxiliary scenario clusters for 10,000 replicates with seed 20261115 and make no significance or equivalence claim.

All 384 planned items remain in each arm's denominator. Report parsed responses, refusals, malformed/unparseable outputs, technical failures, ambiguous interrupted calls, and unattempted calls by arm and analysis group. Non-parsed and missing results count as incorrect for the planned-denominator accuracy and paired-difference summaries; failure types remain visible.

## Interpretation and remaining limitations

Supplying a structured state changes more than access to information: it changes request length, representation, salience, and disclosure of the active constraints and permissions. A behavioral improvement supports sensitivity to this intervention in this task. It does not prove that hidden internal state reconstruction caused earlier errors or establish an internal reasoning mechanism. The diagnostic is not a deployable baseline and cannot establish ordinary judge performance.

## Human-validation gate

The 56 existing scenarios and their current source hashes remain authoritative. The two already commissioned bilingual reviewers must independently validate all 448 assigned variants each using the existing interactive HTML packages and current `p2b1-annotation-2` ingestion contract. No state-access annotations or new reviewer tasks are added. Reviews, resolution, verification, and dataset freeze remain prerequisites to every locked inference call. This amendment does not claim that review or adjudication has occurred.
