# P3 Experimental Methodology Proposal v1

**Status:** DRAFT FOR RESEARCH-OWNER DECISION — not an approved model, baseline, prompt, translation procedure, screening rule, or run plan.
**Evidence checked:** 2026-11-03. Recheck availability, versioning, pricing, and terms before any later purchase or freeze.

This proposal follows the research protocol, evaluation plan, and integrity requirements. It uses only public documentation and authored infrastructure; it does not inspect private examples or use study labels. The locked sample remains 288 primary items plus 96 separate auxiliary controls. No model call is authorized here.

## A. Model candidates

### Candidate comparison

The listed language evidence is a suitability signal for separate qualification, not a prediction of performance on this study. None of the cited Arabic evidence evaluates the exact current model on MSA action-validity judging.

| Candidate | Availability and pinning | Multilingual / Arabic evidence | Structured output, context, and integration | Standard API price and limitations |
|---|---|---|---|---|
| **OpenAI GPT-6.1 Sol** (`gpt-6.1-sol`) | Current API model, available through Responses and Chat Completions. The model page documents this exact ID but no dated snapshot for it; pin the ID and captured response metadata, and confirm lifecycle guarantees before freeze. | OpenAI describes its current model family as multilingual. An independent 2026 Arabic judge study found GPT-5.4 the most reliable of five judges on Egyptian and Iraqi sociolinguistic tasks; HELM Arabic Enterprise reports GPT-5.4 and older GPT-5.1 results. These are different model versions and dialect/enterprise tasks, not MSA judging. | Structured Outputs supported; 1,050,000 input context and 128,000 maximum output. Ordinary JSON judging can use the Responses API and official client SDK; no tools are needed. | **$2/M input, $10/M output.** Exact-current-version Arabic quality is unknown; its dated version-pinning option was not found in the reviewed model page. [Model details](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [API pricing](https://developers.openai.com/api/docs/pricing), [model catalog](https://developers.openai.com/api/docs/models), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs). |
| **Anthropic Claude Sonnet 5.5** (`claude-sonnet-5-5`) | Current Claude API model. Anthropic says this generation's dateless model ID pins one model snapshot; serving infrastructure may still change. | Anthropic describes all current models as multilingual. Its published Arabic result is for the older, now-deprecated Sonnet 4.5: Arabic was 97.2% of English performance on its translated MMLU test under extended thinking. That result is not a Sonnet 5.5 or MSA judge result. | JSON Schema structured output through the Messages API `output_config.format`; 1M context and 128K maximum output. Standard Messages API and SDK integration. It supports effort levels; `temperature`, `top_p`, and `top_k` are not accepted. | **$2/M input, $10/M output.** Current-version Arabic judging quality is unknown; structured JSON has documented schema limitations. [Model details and price](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [model-ID stability](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [effort settings](https://platform.claude.com/docs/en/build-with-claude/effort), [multilingual evidence](https://platform.claude.com/docs/en/build-with-claude/multilingual-support). |
| **Google Gemini 3.8 Flash** (`gemini-3.8-flash`) | Current stable Gemini API model ID. Google documents stable IDs as usually stable, not as an immutable dated snapshot. | Google model materials document broad multilingual coverage, but the reviewed 3.8 model card does not report MSA action-judging quality. Stanford HELM Arabic Enterprise includes an earlier Gemini 2.5 model, not 3.8. The 3.8 model card reports a small non-English safety regression versus 3.7; this is a safety measure, not task accuracy. | Structured outputs and Batch API supported; 1,048,576 input tokens and 65,536 output tokens. Official Google GenAI SDK with a response schema. | **$0.75/M input, $3.75/M output through 2026-12-31; $1.50/$7.50 from 2027-01-01.** Stable ID is not a dated snapshot; exact-version Arabic task quality is unknown. [Model details](https://aistudio.google.com/docs/models/gemini-3.8-flash), [official model card](https://deepmind.google/models/model-cards/gemini-3-8-flash/), [API pricing](https://aistudio.google.com/docs/pricing#gemini-3.8-flash). |

### Shortlist recommendation

Recommend **GPT-6.1 Sol and Claude Sonnet 5.5 as the minimal two-provider core set**, subject to the separate competence screen and owner approval. They provide two current multilingual APIs with structured-output support and comparable standard token prices. Keep Gemini 3.8 Flash as a cost-sensitive alternate; adding it would increase judge calls by 50% and gives the study a third provider. This recommendation follows public capability, reproducibility, and price documentation only. It does not choose a winner or use any locked-study performance.

The owner should resolve provider data-use/retention terms, exact model pin strategy, API access region, and the current availability of each ID before approving a run. Store provider request IDs and returned model/version metadata in private run records; never store credentials in manifests.

## B. Ordinary judging protocols

All three are draft proposals. Every judge stage receives the same evidence fields: opaque item ID, pre-action conversation with `turn_index < action_turn_index`, structured action, public tool schema, and the same fixed English instruction. No stage receives canonical state, oracle verdicts, gold labels, pairing keys, or author classifications. Keep primary and control reporting separate. Use the same judge backbone and its approved decoding settings across baselines where feasible.

### 1. Direct multilingual judging

- **Visible inputs:** original English, MSA, or mixed-language turns; action and public tool requirements.
- **Prompt outline:** identify the action decision point; decide whether this action is valid under the conversation and tool schema; do not assume later context; return only the strict binary object. The exact prompt remains unapproved.
- **Output / parser:** exactly `{"verdict":"valid"}` or `{"verdict":"invalid"}`. Accept no extra key, duplicate key, free text, or alternate spelling. Keep missing, refusal, malformed output, and provider failure distinct.
- **Decoding / failure:** propose the lowest effort setting approved as comparable after a separate development-only check; do not assume effort labels are comparable across providers. Use temperature zero only where supported (Claude Sonnet 5.5 rejects temperature/top-p/top-k), an output cap of 1,024 tokens, and a fixed seed where supported. The larger cap leaves room for model-native reasoning tokens while the requested visible response remains a one-field verdict. Record unsupported parameters instead of silently mapping them. Proposed retry: at most one additional attempt for explicitly allowlisted transient transport/rate-limit categories; never retry a refusal or judge-produced malformed response. Preserve each attempt.
- **Calls:** 1 judge call per item; 384 locked calls per backbone before retries.

### 2. Translation-first judging

- **Translation input:** one complete conversation per item, as turn-indexed `{speaker, turn_index, language, text}` records. The translator sees no action, tool schema, state, or label. Translate the 288 Arabic-bearing variants to English; pass through the 96 EN–EN variants without a translator call. The judge receives the resulting English conversation plus the exact same structured action, public schema, and instruction as the direct baseline.
- **Translation constraints:** do not add, infer, summarize, merge, split, reorder, or omit turns. Preserve speaker roles and chronology exactly. Keep names, IDs, code-like literals, numbers, units, dates, time zones, currencies, and quoted strings unchanged. Translate permission modality, negation, quantifiers, comparisons, scope, and constraint direction faithfully. Return the same count of turns and the same turn indexes/speakers; include protected literal spans for audit. Translation quality needs separate bilingual checks on non-study material before use.
- **Output / parser:** translation output must satisfy the structural turn contract before a judge call is built. The judge uses the same strict binary JSON contract as direct judging. A failed or structurally invalid translation is a translation-stage failure, not a judge verdict: retain all attempts, do not judge source/partial text, and report the item as missing unless a separately approved scoring rule says otherwise.
- **Decoding / failure:** version the translator, prompt, pivot, decoding, literal-preservation procedure, and retry/failure policy separately from the judge. Proposed maximum is two translator attempts total, with one retry only for listed transient technical categories. Invalid translation structure is not retried by default. On exhaustion, persist the failed attempts and skip judging; no fallback to direct judging.
- **Calls:** 1 judge call per item; 288 translation calls for Arabic-bearing variants and no translator call for EN–EN. Share the single approved translation output across judge backbones, and record translator cost separately.

### 3. Structured/decomposed judging

Use three criteria calls with the same backbone, settings, and complete evidence in each request:

1. **Public action/tool-contract conformance:** does the proposed structured action satisfy required fields, value types, and constraints in the public tool schema?
2. **Numerical and temporal requirements:** does the action satisfy every applicable amount, unit, date, time, and boundary requirement after considering later revisions?
3. **Permission and other explicit requirements:** does the action respect every applicable authorization, revocation, scope, and other task constraint after considering later instructions?

Each stage returns only `{"verdict":"valid"}` when its criterion passes or `{"verdict":"invalid"}` when it fails. Proposed deterministic aggregation is `valid` only when all three criteria parse as valid; `invalid` when all three parse and at least one criterion is invalid. If any stage is missing, refused, malformed, or technically failed, keep the aggregate unscored and preserve all stage records; do not coerce partial results. Each criterion must assess the complete visible history through the action point, including its chronology and relevant revisions. Stage prompts, criteria definitions, parsing, and aggregation need owner approval and must be versioned before a locked run. This is a proposed method, not a claimed reproduction of a published protocol.

- **Calls:** 3 judge calls per item; 1,152 calls per backbone before retries.
- **Shared controls:** same evidence, output shape, decoding, retry categories, and run ordering as the direct baseline. The planned differences are the three criterion-specific instructions and their predeclared aggregation.

### Run-order, parsing, and reporting proposal

Use the existing evaluation-plan proposal for a precomputed order from a 256-bit run seed and opaque item IDs, shared across baselines, with one item per isolated request context. Freeze and hash dataset, prompts, model/provider ID, native decoding fields, translation recipe, schemas, retry rules, parser, and analysis before locked inference. A configuration hash identifies the frozen settings; a fresh execution ID identifies each actual run; every attempt has its own ID. Preserve raw request/response, UTC timestamps, usage, cost, latency, refusal/parser/failure status, and provider request IDs. Keep model and translator token/cost totals separate. Report condition estimates separately, cluster uncertainty by canonical scenario, and report missing/invalid/refused results under the approved scoring rule.

## C. Separate English/MSA competence screen

Propose a small, independently authored screen of **24 English and 24 MSA items per candidate judge**. Each language form has 12 valid and 12 invalid actions, with simple comprehension and action checks spanning literal numbers/times, permission scope, and explicit instruction scope. MSA screen wording and labels must receive bilingual validation before screening. Screen items, canonical states, and labels remain in a separate development package and must not overlap with study scenarios or their wording.

Proposed qualification is at least **20/24 exact binary results in each language**, including at least **10/12 valid and 10/12 invalid** in each language. Treat this as pass/fail eligibility, not a ranking; report language-specific counts and uncertainty separately from benchmark performance. Freeze screen content, prompt, parser, threshold, and adjudication before calling candidate models. A pass does not validate code-switched competence or predict benchmark performance; no locked example, label, or oracle state may be used for qualification or selection.

## D. Draft locked-run budget

The estimates below use published standard API rates as of 2026-11-03, no caching/batch discounts, and a proposed fixed Gemini 3.8 Flash translator. The translator screen is 24 separately authored MSA snippets with independently validated English references; it is a translation-quality check, not a locked performance or model-selection set. Google's listed Gemini promotional price ends 2026-12-31, so reprice if execution occurs later. This is a planning estimate, not spend authorization. It does not use private conversation lengths or actual provider tokenizers.

### Workload and token assumptions

| Scenario | Judge tokens per call (input/output) | Translator tokens per item (input/output) | Separate screen tokens per call (input/output) | Retry stress assumption |
|---|---:|---:|---:|---:|
| Low | 800 / 100 | 600 / 120 | 600 / 50 | 0% extra attempts |
| Expected | 1,400 / 250 | 1,200 / 250 | 1,000 / 75 | 2% extra attempts |
| High | 2,500 / 500 | 2,500 / 500 | 1,500 / 100 | 10% extra attempts |

Token assumptions include fixed instructions and schemas. Charged output includes visible output and any provider-billed reasoning tokens. The retry percentages are transparent stress assumptions, not measured failure rates; each technical failure is assumed to receive at most one additional attempt. No retries are assumed for malformed/refused responses. The competence screen adds 48 calls per judge backbone; the separate translator screen adds 24 translation calls. Both use independently authored material.

| Workload | Calls before retries, per judge backbone |
|---|---:|
| Direct judging | 384 |
| Translation-first judge calls | 384 |
| Structured/decomposed judging | 1,152 (three criteria × 384 items) |
| **Judge calls total** | **1,920** |
| Shared translation-first translation | 288 Arabic-bearing locked items, plus 24 independent translator-screen calls |
| Judge competence screen | 48 per candidate model |

Per-backbone judge cost, including its 48-item competence screen, is estimated at:

| Candidate backbone | Low | Expected | High |
|---|---:|---:|---:|
| GPT-6.1 Sol | $5.07 | $10.31 | $19.39 |
| Claude Sonnet 5.5 | $5.07 | $10.31 | $19.39 |
| Gemini 3.8 Flash | $1.90 | $3.87 | $7.27 |

Shared Gemini translation costs for 288 Arabic-bearing locked items plus the 24-item translator screen are **$0.28 low / $0.57 expected / $1.17 high**. The resulting whole-study token-cost scenarios are:

| Model set | Low | Expected | High |
|---|---:|---:|---:|
| Recommended two-model core (GPT-6.1 Sol + Claude Sonnet 5.5) | **$10.43** | **$21.61** | **$43.95** |
| Core plus optional Gemini 3.8 Flash judge | **$12.33** | **$25.56** | **$51.95** |

These totals apply 0%/2%/10% extra-attempt factors to judge, translator, and screen calls. The optional three-model high scenario becomes approximately **$61.23** at Gemini's published 2027 standard rate. Actual private-item token counts, model-native reasoning-token billing, regional uplifts, taxes, batch eligibility, and future pricing can change the estimate. Recalculate from a separately approved public-safe token estimate and current provider rates before budget authorization.

## Owner decisions required before any live run

1. Approve the mandatory baseline set and whether to use the two-model core or add Gemini.
2. Approve exact model IDs and pinning/lifecycle plan after the independent screen.
3. Approve translator choice, pivot language, literal-handling and separate translation-quality check.
4. Approve the three decomposition criteria, exact prompts, schemas, and all-pass aggregation.
5. Approve provider-native decoding mappings, seed support, retryable categories, retry count, and terminal failure policy.
6. Approve screen material, bilingual QC, thresholds, and reporting.
7. Approve the final token/budget estimate, data handling terms, run ordering, scoring of failed items, and a separate inference budget.

Until those decisions and the outstanding independent dataset validation/freeze are complete, keep the proposal unapproved and do not run inference.

## Evidence notes

- Stanford [HELM Arabic Enterprise](https://crfm.stanford.edu/helm/arabic-enterprise/latest/) evaluates Arabic enterprise tasks and lists results for older model versions; it is background suitability evidence, not a locked-study selection metric.
- The 2026 [Arabic cultural and sociolinguistic judge study](https://arxiv.org/abs/2607.00139) uses Egyptian and Iraqi Arabic and human SME references. Its GPT-5.4 finding is not transferable to current GPT-6.1 Sol or MSA action-validity judging.
- Provider statements and version/price tables above are linked at the model rows and were checked on the stated date. External evidence can motivate a separate screen; it cannot establish this dataset’s linguistic or judging validity.
