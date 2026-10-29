# Evaluation and statistical-analysis plan

**Status:** P0 analysis proposal; freeze before any locked evaluation.

**Primary target:** validity classification by an LLM judge, not agent task completion.

## Conditions and baselines

The four mandatory language conditions are EN–EN, AR–AR, EN–AR, and AR–EN. Use the same canonical scenario, action, and counterfactual pairing across conditions. Ordinary judging receives the dialogue and action but no reference label, final canonical state, or oracle output.

Baseline candidates for later review and implementation:

1. **Direct multilingual judge:** the judge evaluates the original bilingual or monolingual history under a frozen instruction and validity rubric.
2. **Translation-first judge:** a frozen translation step renders the user history into a designated pivot language, then the judge applies the same validity rubric. The translator, translation prompt/model, handling of structured fields, and token/cost accounting must be specified before this becomes a baseline. The cited papers do not establish one canonical translation-first method for this task.
3. **Structured/decomposed judge:** a frozen criteria-based protocol asks for explicit criterion-level evidence or intermediate judgments before the final binary classification. Its criteria and aggregation rule must be fixed in advance. Published decomposition methods motivate this comparator but are not evidence that it will fail here.

Comparisons should use the same judge backbone/version and controlled decoding wherever feasible. Any exception, model change, or added call must be declared and justified before locked evaluation. The exact judge set and whether all three comparator conditions are feasible remain P0 review decisions.

### Oracle-state diagnostic

An optional separate diagnostic may supply the judge with the canonical effective state while still withholding the oracle validity label. This intervention can estimate how judgments change when state reconstruction is bypassed. It is not a fair deployable baseline, must not be pooled with ordinary conditions, and must be labeled as oracle-state access in every table and figure. It is intended to inform H2, not to establish practical judge performance.

## Outcomes

### Primary outcome

For each requested item, score exact correctness of the judge's binary valid/invalid classification against the deterministic reference label. Report accuracy separately for all four language conditions, with equal valid/invalid class balance. Also report the planned equally weighted cross-language versus same-language error-rate contrast from the protocol.

### Secondary outcomes

- sensitivity to invalid actions and specificity to valid actions (plus balanced accuracy);
- counterfactual pair consistency: whether the judge flips its verdict for the same action across the two histories as the oracle does;
- per-condition and per-transition-family/domain accuracy and error rates, treated as exploratory where cell counts are small;
- results by switch direction (EN–AR versus AR–EN), without assuming symmetry;
- parse failures, invalid output formats, refusals/abstentions, technical failures, and missing results;
- optional confidence/calibration metrics only if the output format and scoring rule are frozen before evaluation;
- token usage, latency, and inference cost when available, reported as operational outcomes rather than validity evidence.

Do not collapse the four language conditions into one headline score. Keep valid and invalid performance visible even though the planned construction is balanced.

## Dependence and uncertainty

The canonical scenario is the primary dependence and resampling unit. The 8 derived items from a scenario (2 histories × 4 language conditions) are repeated, paired observations, not independent samples. Paired condition contrasts should first be computed within each scenario, preserving both counterfactual histories, then summarized across scenarios.

Report scenario-clustered uncertainty intervals for condition estimates and paired contrasts. A proposed simple procedure is a bootstrap that resamples canonical scenario IDs and carries every paired history and language derivative with each sampled scenario. If adopted, fix the interval method, number of resamples, and random seed before locked evaluation. Do not bootstrap individual derived items as if independent. Report the number of scenario clusters and label the pilot's limited precision plainly.

No p-value threshold alone determines whether to continue. Report point estimates, uncertainty intervals, class-specific errors, missingness, baseline comparisons, and threats to validity. The 36 locked evaluation scenarios are a feasibility sample; absent a reviewed power/detectable-effect analysis, null estimates do not establish equivalence and positive estimates do not establish broad generality.

## H2 error mechanism diagnostic

H2 concerns a mechanism, not just a condition difference. A proposed follow-up is independent, blinded coding of judge errors into state reconstruction, rule application, language/semantic interpretation, output/format, or unresolved categories, using a prewritten coding guide and adjudication procedure. If judge rationales are used, treat them as observable explanations rather than faithful access to internal reasoning. Coders may consult canonical references only in this separate diagnostic process; the judge never receives them in ordinary conditions. The coding protocol and sampling rule require review before use.

## Invalid, missing, and failed outputs

Freeze the accepted output schema and all exclusions before the locked run. A returned abstention, malformed classification, or unparseable answer is not silently excluded; report it explicitly and count it as an incorrect classification for the primary intention-to-evaluate score unless a reviewed, pre-registered rule specifies otherwise. Record technical call failures as missing attempts, not as successful omissions. Report requested, completed, validly parsed, and scored counts for every condition; do not retry, replace, or drop failed items without an explicit frozen retry rule and a retained event log. Include a sensitivity analysis that distinguishes technical missingness from judge-produced invalid outputs.

## Freeze and run artifacts

Before locked evaluation, freeze and hash the dataset and partition manifest, prompts, model/provider identifiers and immutable versions, decoding settings, output parser, metrics, exclusions/retry policy, and analysis code/procedure. Assign an immutable run ID. Retain every raw judge response, request, failure, token count, timestamp, latency, and execution metadata. Development runs cannot be relabeled as locked evaluation. Any deviation is logged with time, reason, affected records, and impact; do not quietly patch the protocol after seeing results.

No model inference or analysis run occurs in P0. Any future paid inference requires explicit budget authorization.
