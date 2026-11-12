# P3 Experimental Methodology Proposal v2

**Status:** Draft for research-owner approval. Models, prompts, provider settings, translation procedure, screening thresholds, diagnostics, and costs are proposals, not a frozen protocol.

**Evidence checked:** 2026-11-03 using official provider documentation linked below. Recheck model IDs, structured-output behavior, pricing, service terms, data handling, and availability before any later approval or purchase.

**Subsequent accounting correction (2026-11-06):** The 288 Arabic-bearing variants below count items that require translation, not translator provider calls. The translator calls once per Arabic turn; calculate calls as the Arabic-turn total plus recorded retries. See the [P3 Local Method Stabilization proposal](2026-11-06-p3-local-method-stabilization-proposal.md). The earlier translation-call and price totals are superseded and must not be reused.

This revision follows the owner's direction to keep GPT-6.1 Sol, Claude Sonnet 5.5, and Gemini 3.8 Flash as provisional candidate backbones, and to use a single-call structured baseline as the primary structured alternative. It corrects the v1 three-call cost/method design. It does not access study data, authorize spend, authorize dataset freeze, or authorize inference.

## 1. Candidate models

All three are shortlist candidates, with no performance ranking. Public descriptions and nearby Arabic results indicate language capability but do not establish MSA validity-judging competence for the current versions. A separate small screen is proposed below; its threshold is not approved and must not use study examples or labels.

| Candidate and API ID | Version stability | Language evidence and limits | Structured output, context, and output | Standard API price checked 2026-11-03 |
|---|---|---|---|---|
| **OpenAI GPT-6.1 Sol** — `gpt-6.1-sol` | The current model page documents the ID but does not list a dated snapshot. Pin the exact ID, retain the returned model metadata, and recheck lifecycle/alias behavior before freeze. | OpenAI describes its current models as multilingual. A 2026 Arabic judge study reported results for GPT-5.4 on Egyptian and Iraqi tasks; that is a different model version and dialect context, not MSA action-validity judgment. | Responses API; JSON Schema structured output supported; 1,050,000-token context and 128,000-token maximum output. Reasoning effort supports low/medium/high/xhigh/max. | **$2/M input, $10/M output.** More than 272K input tokens incur long-context pricing. [Model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [models and multilingual support](https://developers.openai.com/api/docs/models), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [pricing](https://developers.openai.com/api/docs/pricing). |
| **Anthropic Claude Sonnet 5.5** — `claude-sonnet-5-5` | Anthropic documents the dateless generation 4.6+ ID as a fixed model snapshot; its current model page reports active availability and a retirement date no earlier than 2027-09-28. Record returned model metadata. | Anthropic reports general multilingual capability. Its Arabic relative-to-English result (97.2%) is for older Sonnet 4.5 on a zero-shot chain-of-thought task, not Sonnet 5.5 or action-validity judgment. | First-party Messages API; JSON Schema output through `output_config.format`; 1M context and 128K maximum output. Effort low/medium/high/xhigh/max. `temperature`, `top_p`, and `top_k` return an error. | **$2/M input, $10/M output.** [Model/version and pricing](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [version IDs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions), [multilingual support](https://platform.claude.com/docs/en/build-with-claude/multilingual-support), [structured output](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [effort](https://platform.claude.com/docs/en/build-with-claude/effort). |
| **Google Gemini 3.8 Flash** — `gemini-3.8-flash` | Google marks this model ID stable; stable IDs are not dated immutable snapshots. Record returned model metadata and recheck lifecycle before freeze. | The model card reports a multilingual safety evaluation, but not Arabic reasoning accuracy or MSA action-validity judging. No current-version task-specific result was identified. | Gemini API; structured outputs support a subset of JSON Schema; 1,048,576 input and 65,536 output tokens. Thinking level low/medium/high; minimal is unsupported. The 3.8 migration guide says to remove temperature, top_p, top_k, and candidate_count. | **$0.75/M input, $3.75/M output through 2026-12-31; $1.50/$7.50 from 2027-01-01.** [Model card/API ID and limits](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [model card](https://deepmind.google/models/model-cards/gemini-3-8-flash/), [migration and thinking levels](https://ai.google.dev/gemini-api/docs/latest-model), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [pricing](https://ai.google.dev/gemini-api/docs/pricing). |

Broader Arabic evidence includes [HELM Arabic Enterprise](https://crfm.stanford.edu/helm/arabic-enterprise/latest/) and the 2026 [Arabic cultural and sociolinguistic judge study](https://arxiv.org/abs/2607.00139). Those sources cover other model versions, tasks, and/or Arabic varieties. They motivate separate screening; they cannot rank these candidates for this benchmark.

### Proposed within-model comparison settings

Use one provider-native low-reasoning setting and one provider-native output cap across that model's three ordinary baselines and screening calls. Treat equal labels such as `low` as provider-specific categorical settings, not as equal compute or equivalent reasoning. Do not send unsupported sampling settings or pretend cross-provider parameters are identical.

| Provider | Draft provider-native configuration | Output schema transport |
|---|---|---|
| OpenAI | Responses API `reasoning.effort=low`, `max_output_tokens=2048`, `store=false`; omit temperature and seed. | Use the request's versioned JSON Schema in the Responses API structured-output format. |
| Anthropic | First-party Messages API `output_config.effort=low`, `max_tokens=2048`; omit `temperature`, `top_p`, and `top_k`. Adaptive thinking is model behavior; do not substitute a fixed thinking-token budget. | Use `output_config.format` with JSON Schema. The schema is provider-compiled; retain exact schema and parser versions. |
| Google | Paid Gemini API with `generation_config.thinking_level=low`, `max_output_tokens=2048`; omit temperature, top_p, top_k, candidate_count, and seed. | Use the model's structured JSON output with only schema constructs in Google's supported subset. |

These settings are draft API-native mappings, not shared raw parameter dictionaries. The implementation validates these candidate settings but has no provider adapter and sends no request. Output caps and reasoning spend must be revisited if synthetic-only testing or a separately approved development check shows truncation; no locked data may inform that choice.

Anthropic's [structured-output documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) warns that enum casing can vary even when a schema is provided. This proposal's strict parser will retain a case variant such as `Valid` as invalid output; it will not normalize it to `valid`. The structured schema uses only basic constructs documented by all three candidate APIs, and post-response parsing remains authoritative if a provider's constraint mode differs.

## 2. Ordinary baseline proposals

The mandatory proposed ordinary comparison is **three baselines × 384 locked items × three backbones = 3,456 judge calls before retries**. Each backbone sees the same item order and baseline-specific fixed evidence. Each ordinary request contains an opaque item ID, conversation turns strictly before the action decision point, the proposed structured action, and the public tool contract. No canonical state, oracle label, final validity label, pairing metadata, author classification, or reference-only field is available.

### Baseline A — Direct multilingual judging

- **One judge request per item.** Provide the original English, MSA, or code-switched conversation, action, and public tool contract.
- The prompt outline applies a fixed validity rubric: check tool-contract conformance and whether the action satisfies all applicable instructions at the action point; return the binary verdict only. Exact prompt text remains unapproved.
- Output is exactly `{"verdict":"valid"}` or `{"verdict":"invalid"}`. The parser rejects extra keys, duplicate keys, invalid casing/value, prose, and malformed JSON. Missing response, provider refusal, malformed output, and provider failure remain distinct.
- Proposed call count: **384 per backbone**. Retain each raw request, raw output, parser status, usage, cost, latency, timestamps, and retry attempt.

### Baseline B — Translation-first judging

- Translate the complete conversation to English wherever any turn is Arabic-bearing; leave all-English conversations untouched. The proposed locked translation workload is 288 Arabic-bearing items, with successful conversation artifacts hash-bound for reuse across all three judge backbones where feasible. Translation runs at Arabic-turn level; provider calls equal the eligible Arabic-turn count plus actual retries. Each model still receives one judge call for each of the 384 items.
- The translator receives only the turn-indexed conversation, with source language, speaker role, and chronology. It does not receive the action, tool contract, state, or label. It must preserve turn count/order and roles, numerical amounts and units, dates, times and time zones, currency codes, identifiers and code-like literals, negation, quantifiers, permission grants/revocations and scope, and relative references with their original intended meaning.
- Translation must not resolve an ambiguous or contextual reference from canonical state or hidden study metadata. It may translate the words and preserve the ambiguity. Do not silently correct mistranslations with a reference, label, or oracle. No judge sees canonical state.
- The same accepted, hash-bound translation output is reused by all backbones if the item/config hashes match. Retain all translation attempts, failures, costs, raw outputs, and retries. A terminal translation failure skips judging for that item and remains a translation-stage missing result; there is no silent direct-language fallback.
- Translation quality checks should use independent, non-study examples and a human-reviewed procedure before a later live run. The optional 24-item translation quality workload in the budget is a proposal, not a locked-data step.
- The translated judge request then carries the translated conversation, unchanged action, unchanged public tool contract, and the same validity rubric and strict binary parser as Baseline A.
- Proposed call count: **384 judge calls per backbone**. The 288 Arabic-bearing evaluation items are not a translator-call count; translation calls equal the sum of their Arabic turns plus actual retries. The optional 24 independent translation-QC items are also item counts, and their calls depend on Arabic-turn count.

### Baseline C — Single-call structured judging

- **One judge call per item.** Provide the same original conversation, action, and public tool contract that Baseline A receives. Do not hide evidence in staged requests.
- In one response, assess public tool-contract conformance and each relevant numerical, temporal, permission, or other explicit constraint; cite the supplied zero-based `turn_index` values; then return a binary validity verdict.
- Proposed strict object: `tool_contract` (`satisfied` or `violated`), `constraint_assessments` (array of `constraint_type`, `assessment` = `satisfied` / `violated` / `not_applicable`, and `source_turn_indices`), and `verdict` (`valid` or `invalid`). Reject missing/extra keys, duplicate keys, unknown values, duplicate assessment anchors, out-of-range turn references, and contradictions.
- Proposed deterministic aggregation: invalid if the tool contract or any applicable constraint is violated; valid if the tool contract is satisfied and no constraint is marked violated. A contradictory verdict is `invalid_output`, never silently repaired. A refusal, missing response, malformed output, and provider failure stay separate.
- Proposed call count: **384 per backbone**. This is the proposed primary structured/decomposed baseline. It is a proposed method, not a claim of faithful reproduction of published work.

### Optional secondary — Existing three-call decomposition

Preserve the current caller-defined three-stage interface, but keep it secondary and disabled as the primary structured condition. The proposal uses public tool/action conformance, numerical/temporal requirements, and permission/other explicit requirements, each with the full underlying evidence. It needs a preapproved all-three rule: valid if all parse valid, invalid if all parse and at least one is invalid, otherwise unscored. It adds **1,152 calls per backbone** for 384 items. No published-method reproduction claim is made without a separate method comparison.

## 3. Separate H2 diagnostic proposal

H2 concerns whether errors arise because the judge reconstructs the effective task state incorrectly. These diagnostics are not ordinary baselines and have not been run.

1. **Model-generated state extraction:** ask for active constraints, permission state, scope/value, and source turn indices using only the conversation, action, and public tool contract. Compare the visible extracted fields with canonical reference-state fields after inference using a separate scorer. The request path does not import reference state. Freeze the mapping, field normalization, missing/extra-field treatment, and scorer before any use. The result measures agreement of an observable extraction with the reference; it does not establish internal reasoning.
2. **Optional oracle-state intervention:** pair an ordinary direct item with a request containing the same transcript/action/tool evidence plus the effective state representation, while withholding every validity label and oracle outcome. Keep model, prompt except for a predeclared intervention instruction, output contract, and settings fixed. Compare paired correctness with and without state access and report this separately from ordinary accuracy. The intervention must not leak the final answer through a constructed state summary.

Each proposed diagnostic uses one call per locked item per backbone: **384 state-extraction plus 384 oracle-intervention calls per backbone**, or **2,304 calls across three backbones** before retries if both are approved. Extracted state fields and model explanations are observable outputs, not evidence of the model's hidden reasoning. Neither diagnostic is included in ordinary-baseline estimates.

## 4. Separate English/MSA competence screen

Retain the candidate framework pending approval: 24 independently authored English and 24 independently authored MSA items per model, balanced 12 valid / 12 invalid within each language. Screen material and labels must be disjoint from study text, scenarios, canonical state, reference labels, and translations, and must be bilingual-validated before any screen.

Proposed threshold: at least **20/24 overall in each language** and at least **10/12 in each validity class in each language**. That means 83.3% overall, at most four total errors, and at most two errors in either class; each one-item change is 4.17 percentage points overall and 8.33 points within a class. This is a small pass/fail eligibility check with coarse uncertainty, not a ranking or benchmark result. A pass does not establish code-switched competence. Threshold and use are provisional. Do not conduct this screen or select models from its outcomes before approval.

Call count: 48 per model, **144 total**. The cost proposal includes those calls. No study labels or state fields enter the screen.

## 5. Recalculated budget proposal

The estimates use current public standard token prices, no batch/caching discount, no regional uplift, and no private token counts. Work is proportional to the locked corpus and the screen:

| Workload | Calls before retries |
|---|---:|
| Direct judging | 384 per backbone |
| Translation-first judge calls | 384 per backbone |
| Single-call structured judging | 384 per backbone |
| **Ordinary judging** | **1,152 per backbone; 3,456 for three backbones** |
| Competence screen | 48 per backbone; **144 total** |
| Shared translation | 288 locked Arabic-bearing items, plus 24 optional independent translation-QC items; compute provider calls from Arabic turns plus retries |
| Optional H2, if both diagnostics run | 768 per backbone; 2,304 total |
| Optional three-call decomposition, in addition to Baseline C | 1,152 per backbone; 3,456 total |

### Token and retry assumptions

| Scenario | Direct/translation judge call: input / visible output | Structured call: input / visible output | Screen call: input / visible output | Translation: input / visible output | Retry stress |
|---|---:|---:|---:|---:|---:|
| Low | 900 / 75 | 1,200 / 220 | 700 / 80 | 700 / 140 | 0% extra attempts |
| Expected | 1,500 / 100 | 1,900 / 360 | 1,000 / 100 | 1,300 / 280 | 2% extra attempts |
| High | 2,600 / 150 | 3,300 / 600 | 1,600 / 160 | 2,600 / 600 | 10% extra attempts |

Reasoning-token output assumptions are provider-specific and add to visible output for costing. The low / expected / high reasoning tokens are:

| Provider | Direct / translation judge | Structured | Screen | State extraction | Oracle intervention | Three-call criterion | Translator (Gemini only) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OpenAI | 100 / 200 / 500 | 200 / 400 / 900 | 50 / 100 / 250 | 200 / 450 / 1,000 | 100 / 200 / 500 | 100 / 220 / 500 | — |
| Anthropic | 150 / 300 / 750 | 250 / 550 / 1,300 | 60 / 130 / 300 | 250 / 550 / 1,300 | 150 / 300 / 750 | 120 / 280 / 650 | — |
| Google | 100 / 240 / 600 | 180 / 450 / 1,100 | 50 / 120 / 300 | 180 / 450 / 1,100 | 100 / 240 / 600 | 100 / 220 / 600 | 50 / 120 / 300 |

Visible token assumptions are planning averages, not measurements or tokenizer outputs. Reasoning counts are illustrative stress assumptions. Gemini standard output pricing includes thinking tokens; all model outputs are priced as output tokens. The 0%/2%/10% retry factors assume at most one additional attempt for retryable technical errors; no retries are assumed for refusal or malformed output. Fractional retries represent expected/high workload estimates. Use actual returned usage in any future approved run. Every failed call remains recorded.

### Cost estimates

Estimated cost in USD, including 48 competence-screen calls per backbone and the 312 shared translation calls. The separate translation work is priced at Gemini 3.8 Flash standard rates. This table includes the optional 24 non-study translation-QC calls; without those calls, subtract approximately **$0.03 / $0.06 / $0.14** from low/expected/high current-price totals. These estimates are planning only.

| Cost component | Low | Expected | High |
|---|---:|---:|---:|
| GPT-6.1 Sol ordinary baselines + screen | $5.39 | $9.36 | $19.39 |
| Claude Sonnet 5.5 ordinary baselines + screen | $5.97 | $10.75 | $23.22 |
| Gemini 3.8 Flash ordinary baselines + screen | $1.99 | $3.71 | $7.92 |
| Shared translation | $0.39 | $0.79 | $1.83 |
| **Ordinary experiment + screen total, current intro prices** | **$13.74** | **$24.60** | **$52.36** |
| Optional H2 diagnostics, all three models | $10.52 | $19.73 | $41.87 |
| Optional three-call decomposition, all three models | $12.27 | $22.75 | $46.62 |
| **Total if all optional diagnostics also run, current intro prices** | **$36.53** | **$67.08** | **$140.84** |

Beginning 2027-01-01, Google's standard Gemini 3.8 Flash input/output rates double. At those prices, the ordinary totals become **$16.12 / $29.09 / $62.10** and totals including all optional diagnostics become **$42.39 / $78.09 / $164.56**. No later price is assumed. Check published prices again before an authorization request.

Not included: taxes, region-specific processing, paid storage/privacy add-ons, any price/model revision after the checked date, and human labor for bilingual or translation quality control. No spend is approved here.

## 6. Provider data handling

Use only a separately approved commercial paid API service and an approved account/workspace for any future unpublished research scenario. Confirm current terms, region, retention settings, account configuration, and institutional privacy requirements before transmission. Do not put credentials in source, manifests, or logs.

- **OpenAI API:** API input is not used for training by default unless the customer opts in. Standard abuse-monitoring logs may include prompts/responses and be retained up to 30 days. Responses API application state is retained for 30 days by default or when `store=true`; this proposal sets `store=false`. Zero Data Retention is an organization-level eligibility/configuration matter, not assumed here. [Data controls](https://developers.openai.com/api/docs/guides/your-data).
- **Anthropic API:** retained data is not used for training without express permission. Its current API documentation says prompt/output content is not retained by default except for designated Covered Models; verify Sonnet 5.5's live model/feature eligibility and use the first-party Messages API. ZDR requires organization-level enablement; structured output may retain only the schema cache for up to 24 hours when using that feature. Console/playground and consumer products are not substitutes for the commercial API. [Retention policy](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention).
- **Gemini API:** Paid Service requires using a Gemini API Cloud Project with active billing. Paid Service prompts/responses are not used to improve products, but Google logs them for a limited period for abuse-policy monitoring and may store them in any country. The free tier and Contributor tier permit product-improvement use; do not submit unpublished study material through those tiers absent explicit owner approval. “Paid” does not mean zero retention. [Pricing and tier terms](https://ai.google.dev/gemini-api/docs/pricing), [API terms](https://ai.google.dev/gemini-api/terms), [zero-retention controls](https://ai.google.dev/gemini-api/docs/zdr).

Third-party cloud resellers have separate processors, logs, and contracts. This proposal does not select a reseller, approve external transmission, or treat a provider's general training statement as a complete privacy review.

## 7. Synthetic infrastructure changes and evidence

The provider-independent infrastructure now carries the versioned `structured_single_call` baseline and its own strict `structured-validity-v1` JSON Schema/parser. It preserves the same visible evidence as direct judging, enforces consistency between component assessments and the binary verdict, and retains raw outputs and attempt records. Direct and translation-first keep the strict binary output contract. The existing three-call decomposition type remains available and unchanged as a secondary interface.

Candidate provider configuration validation uses separate allowlists for OpenAI, Anthropic, and Google, including Claude's rejected sampling parameters. No provider adapter or live call was added. A new state-extraction diagnostic request contains ordinary evidence only and no canonical state or label; the existing separately typed oracle-state request remains non-executable from the ordinary runner and excludes validity labels. No study data were loaded or modified.

Synthetic tests cover all four language-condition mappings; evidence parity and one-call behavior; schema and parser outcomes, including contradictory outputs; candidate provider settings and rejected parameters; state-diagnostic isolation; raw attempts; translation failure accounting; deterministic manifests; call counts; and independently recomputed budget arithmetic. These are software/interface checks. They do not establish prompt effectiveness, data validity, semantic equivalence, Arabic naturalness, model competence, or scientific correctness.

## 8. Decisions still required

Before live evaluation, the research owner must review the mandatory three-baseline set; confirm all three candidate models and exact provider/services; approve prompts and rubric; approve provider-native effort/output settings and privacy/retention conditions; approve translation model, procedure, independent quality control, and output reuse; approve the single-call structured aggregation/parser policy; decide whether the three-call secondary and H2 diagnostics are included; approve competence-screen material and thresholds; approve retry rules, run order, scoring treatment of missing/invalid/refused results, analysis, and the recalculated budget. A separate explicit authorization is required for spend and inference. Dataset validation and freeze are independent gates.

Until those reviews are complete, treat this document and [v2 configuration](p3-experimental-config-proposals-v2.json) as unapproved proposals. No model inference, paid API call, screening, H2 diagnostic, dataset freeze, P4, or later milestone is authorized by this package.
