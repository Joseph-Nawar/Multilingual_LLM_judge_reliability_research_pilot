# P3 Experimental Methodology v2 — Design

## Intent

Prepare a research-owner decision package for three provisional judge backbones and three mandatory ordinary baselines, and make the existing synthetic infrastructure represent the proposed one-call structured baseline. Keep the three-call decomposition available as an optional secondary method. Add an isolated state-reconstruction diagnostic request contract without connecting it to ordinary scoring or a live runner.

## Goals

- Use exact provider IDs and provider-specific, documented request settings for GPT-6.1 Sol, Claude Sonnet 5.5, and Gemini 3.8 Flash.
- Give direct, translation-first, and one-call structured baselines equivalent conversation/action/public-schema evidence and one call per item each.
- Require a structured assessment record plus binary verdict for the one-call structured baseline; reject malformed or internally contradictory output.
- Preserve the existing three-call decomposition as a separate secondary option.
- Define model-generated active-state extraction and a separate optional oracle-state intervention for H2, with reference comparison only after inference in a separate scorer.
- Recalculate three-model budget with provider-specific visible and reasoning-token assumptions, translation, retries, optional diagnostics, and optional three-call decomposition.
- Document provider data use and retention; prohibit free/contributor tiers for unpublished scenarios unless the research owner explicitly approves their data terms.

## Boundaries

- No private study example, label, or canonical state may be loaded or inspected.
- No live model/translator call, paid API call, model selection, dataset freeze, P4, or later milestone.
- All concrete prompts, thresholds, provider choice, data terms, cost estimates, and methods remain proposals until explicit research-owner approval.
- No provider SDKs or live adapters are added.

## Approaches

1. **Overload the binary parser with structured output.** Rejected: it would blur two distinct response contracts and make ordinary verdict parsing less auditable.
2. **Add a versioned output-contract discriminator to judge requests and dispatch to a strict structured parser.** Chosen: existing direct and translation requests keep their binary contract; the new baseline carries its own schema version, parser, and one-call result while using the same run/execution/attempt envelope.
3. **Build provider adapters now.** Rejected: the owner authorized method preparation and synthetic interfaces only; provider access and data terms are unresolved.

## Design details

### Ordinary baselines

- Direct and translation-first retain the strict binary JSON contract.
- The primary structured baseline makes one request containing the complete visible history, proposed action, public tool schema, and fixed English rubric. Its strict JSON object contains `tool_contract`, a list of `constraint_assessments` (`numerical`, `temporal`, `permission`, `other`; each `satisfied`, `violated`, or `not_applicable`; source turn indices), and `verdict` (`valid` or `invalid`). A tool-contract violation or any violated assessment requires `invalid`; an all-satisfied/non-applicable result with a satisfied tool contract requires `valid`. Missing, unknown, duplicated, out-of-range, or contradictory data is invalid output, never coerced.
- Request metadata identifies the response-contract version; raw response remains in the existing attempt record. Direct/translation output schemas and the existing three-call stage interface remain separate.
- Provider configuration is validated against allowlisted provider-specific settings. Comparison holds the selected model ID/version, endpoint, effort, output cap, parser, retries, and run order constant across that model's baselines. Categorical effort settings are not assumed equivalent between providers.

### H2 diagnostics

- State extraction is a distinct diagnostic request built from ordinary evidence only. It asks for model-observable active-constraint slots with turn evidence; it does not receive reference state. A post-inference reference scorer compares the structured extraction against canonical fields in a separate access path and reports field-level matches, omissions, and additions. Results measure extracted-state agreement, not hidden reasoning.
- The oracle-state intervention is separately typed and may add only effective state, never a validity label. Pair it with the same model's ordinary direct result for a scenario/item-level correctness contrast. It is excluded from ordinary-baseline accuracy.
- Neither diagnostic is run in this milestone.

### Privacy and cost

Use paid commercial API services only for any future transmission of unpublished scenarios, with the exact project/workspace retention settings approved first. No free Google Gemini API tier, contributor tier, consumer interface, or unapproved training/data-sharing arrangement is permitted. Even paid API terms that disallow model training may allow bounded abuse-monitoring retention; document it rather than describing a provider as zero-retention unless the organization-level control is enabled and verified.

Budget scenarios use provider-specific input, visible-output, and reasoning-token assumptions at standard public rates. The assumptions are planning stress cases, not token measurements or failure-rate estimates. Cost covers three backbones, 1,152 ordinary judge calls per model, 48 screening calls per model, 312 shared translation calls, retry stress, optional H2 calls, and optional three-call decomposition. No spend is approved.

## Non-goals

No prompt freeze, dataset or provider selection from study outcomes, bilingual screening run, translation-quality run, H2 execution, oracle diagnostic, live integration, external data upload, dataset freeze, or claim of published-method reproduction.
