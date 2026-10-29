# Evaluation and statistical-analysis plan

**Status:** P0 analysis specification amended after the 2026-10-29 research-owner audit; freeze before any locked evaluation.

**Primary target:** validity classification by an LLM judge, not agent task completion.

## Primary conditions and outcomes

The primary consequential-change set retains 48 canonical scenarios, two opposite-label histories per scenario, and four language conditions: EN–EN, AR–AR, EN–AR, and AR–EN. The primary outcome is exact correctness of the judge's binary valid/invalid classification against the deterministic reference label.

The primary comparison is the four condition-specific accuracy and class-specific performance estimates, with scenario-clustered uncertainty. Keep all four conditions visible; do not reduce the primary comparison to a single pooled score. The equally weighted cross-language versus same-language error contrast is exploratory, as are directional or family/domain contrasts. It does not by itself identify the causal effect of consequential revision.

The separate no-change control has 12 additional canonical scenarios and 96 items. It estimates language-condition behavior when a later turn restates an existing requirement without changing its effective meaning. Report its four condition estimates and any cross-language versus same-language error contrast separately as secondary exploratory results. A matched primary-versus-control contrast may be reported only as exploratory, with matched-set and template dependence retained. The small control does not fully identify a causal effect of constraint revision and never replaces the primary four-condition comparison.

## Candidate mandatory ordinary-condition baselines

These are candidate mandatory ordinary-condition baselines. Before the locked evaluation is frozen, the research owner must explicitly approve which of them are mandatory:

1. **Direct multilingual judging:** judge the original English, Arabic, or mixed-language history using a frozen, fixed-language instruction and validity rubric.
2. **Translation-first judging:** translate the user history to a designated pivot language, then judge it with the frozen rubric.
3. **Structured/decomposed judging:** apply a frozen criteria-based protocol with specified criterion evidence and aggregation to the binary classification.

If any candidate is omitted for cost or feasibility, document the reason and owner approval before locked evaluation and before unblinding. Record the resulting limit on H3's scope. Any method added after inspecting locked results is exploratory and must not support an unqualified preplanned H3 claim. Do not describe a baseline as a faithful reproduction of a published method unless its implementation has been checked against that method and the reproduction is documented.

For fairness:

- Use the same judge backbone, immutable version, and decoding settings across baselines where feasible. Predeclare and justify exceptions.
- Give ordinary baselines equivalent access to the underlying user evidence, structured action, and relevant public tool/schema evidence. Translation may change language form, not add canonical state, labels, or other evidence.
- Freeze each baseline prompt, criteria, translator/model, translation prompt, translation settings, field/literal handling, output parser, and aggregation procedure before locked evaluation.
- Track translator and judge token usage, calls, latency, and cost separately and report their combined baseline totals. Do not hide translation calls in judge costs.
- Keep ordinary baselines separate from the oracle-state diagnostic below.

The judge instruction is English and identical across the four language conditions. User-facing requirements remain localized. The judge instruction does not expose reference labels, canonical effective state, or oracle verdicts.

## Development-only language competence qualification

Before selecting judges for locked evaluation, run basic English and MSA competence checks using separate development screening material. Freeze the screen and qualification criteria before judging. Do not use locked examples or labels, study gold labels, canonical effective states, or oracle verdicts for judge selection. Competence qualification is not benchmark performance and must be reported separately. It cannot justify changing a locked example or selecting a judge based on locked results.

## Oracle-state diagnostic and H2

An optional oracle-state diagnostic supplies the judge with a canonical effective-state representation while withholding gold labels and oracle validity verdicts. Pair it with ordinary judging on the same items; keep backbone, evidence, action, instructions, and decoding fixed, changing only the approved state-access field. Analyze it separately. It is not a deployable baseline, must never be pooled with ordinary conditions, and cannot establish ordinary judge performance.

H2 requires controlled diagnostic evidence that state access changes classification or a separately measured state reconstruction aligns with the canonical reference. Generated explanations are observable outputs, not ground truth about internal reasoning. Rationales alone, retrospective interpretation, or an error narrative cannot establish H2. Any explicit state-output diagnostic and its scoring/adjudication procedure must be frozen before use and kept distinct from the primary judgment prompt where feasible.

## Label isolation and data-access separation

Ordinary judge inference and reference scoring use separate data-access paths. The inference path supplies only approved conversation/action content, fixed instructions, and an opaque item ID. The reference scorer receives the retained response and ID separately and has access to labels and canonical states. It cannot return these references to the judge. No gold label, canonical effective state, or oracle verdict may enter ordinary judge prompts or development-time judge/model selection.

Any exception that deliberately supplies state is an oracle diagnostic, not an ordinary baseline. Even development labels used to validate the data or scorer must remain out of judge selection and prompt/configuration tuning. Keep the control subset separately identified and do not use its locked items for development selection.

## Secondary outcomes

- sensitivity to invalid actions and specificity to valid actions, plus balanced accuracy;
- counterfactual pair consistency: whether the judge flips its verdict when the oracle label flips for the same action;
- per-condition and per-transition-family/domain accuracy and errors, exploratory where cell counts are small;
- switch direction (EN–AR versus AR–EN), without assuming symmetry;
- control-set estimates reported independently from primary estimates;
- parse failures, invalid output formats, refusals/abstentions, technical failures, and missing results;
- optional confidence/calibration only if output format and scoring are frozen before evaluation;
- translator and judge token usage, latency, and inference cost, reported separately and combined.

## Dependence, uncertainty, and interpretation

The canonical scenario is the primary dependence and resampling unit. The eight primary derivatives per scenario (2 histories × 4 language conditions) are paired observations, not independent samples. The eight control derivatives are likewise paired. Compute paired contrasts within scenarios; for matched primary-control comparisons, preserve the match set as a dependent unit.

Authoring templates and semantic recipes can induce dependence across canonical scenarios. Report distinct template/recipe counts and their reuse distribution. Scenario-level clustering may underestimate uncertainty if many scenarios share a template. Where the number and distribution of templates permit, provide a template-clustered sensitivity analysis in addition to the scenario-clustered primary uncertainty; if too few independent templates exist, state that inference is limited rather than treating template variants as independent.

Report scenario-clustered uncertainty for all four primary condition estimates and paired contrasts. A proposed bootstrap resamples canonical scenario IDs with all derivatives intact; for matched auxiliary contrasts, resample matched sets. Freeze interval method, resample count, and seed before locked evaluation. Do not resample individual items as independent observations.

The primary locked set has 36 primary scenario clusters; the auxiliary control has only 12 more. The 384 locked items across both sets are not 384 independent observations. This is an exploratory feasibility pilot; do not invent a power calculation or describe it as confirmatory. Report effect estimates, uncertainty, missingness, baseline completeness, template dependence, and validity threats. Statistical significance alone is not a go/no-go criterion.

## Invalid, missing, and failed outputs

Freeze the accepted output schema and exclusions before the locked run. A returned abstention, malformed classification, or unparseable answer is reported and counted incorrect for the primary intention-to-evaluate score unless a reviewed, preregistered rule specifies otherwise. Record technical call failures as missing attempts. Report requested, completed, validly parsed, and scored counts for each baseline and condition. Do not retry, replace, or drop failed items without a frozen retry rule and retained event log. Distinguish technical missingness from judge-produced invalid outputs in sensitivity analyses.

## Freeze and run artifacts

Before locked evaluation, freeze and hash the primary and control datasets, partition and match manifests, template/recipe inventory, prompts, model/provider identifiers and immutable versions, decoding settings, translator and translation procedures, parser, metrics, exclusions/retry policy, and analysis procedure. Assign an immutable run ID. Retain raw judge and translation responses, requests, failures, token counts by component, timestamps, latency, and execution metadata. Development runs cannot be relabeled as locked evaluation. Log every deviation with date, reason, affected records, and impact; do not patch the protocol after inspecting locked results.

No model inference or analysis run occurs in P0. Any future paid inference requires explicit budget authorization.
