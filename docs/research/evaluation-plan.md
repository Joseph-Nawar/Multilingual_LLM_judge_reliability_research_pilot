# Evaluation and statistical-analysis plan

**Status:** The research owner authorized the full study on 2026-11-11 and approved the single state-access amendment on 2026-11-15 (registered in the [amendment decision record](decision-records/2026-11-16-paper2-state-access-amendment.md)). The dataset and run configurations are not frozen. Both commissioned independent bilingual submissions, substantive-issue resolution, deterministic revalidation, and the pre-inference freeze are still pending; no locked inference has occurred.

**Primary target:** validity classification by an LLM judge, not agent task completion.

## Primary conditions and outcomes

The primary consequential-change set retains 48 canonical scenarios, two opposite-label histories per scenario, and four language conditions: EN–EN, AR–AR, EN–AR, and AR–EN. The primary outcome is exact correctness of the judge's binary valid/invalid classification against the deterministic reference label.

The primary comparison is the four condition-specific accuracy and class-specific performance estimates, with scenario-clustered uncertainty. Keep all four conditions visible; do not reduce the primary comparison to a single pooled score. The equally weighted cross-language versus same-language error contrast is exploratory, as are directional or family/domain contrasts. It does not by itself identify the causal effect of consequential revision.

## Counterbalanced history positions and evaluation order

History-position balancing is complete for the authored package: valid history is in position A/B for 6/6 development primaries, 18/18 locked primaries, and 6/6 controls. The prospective 48-scenario blueprint also targeted a cross-balance of decisive-update dependence within each domain × transition-family cell, but the 24/24 split could not be supported without classifying the 12 preserved development scenarios or forcing assignments. The new locked examples carry provisional author-side assessments; the original annotations and pilot disagreements are unchanged. The shortfall is documented in private data, and no oracle-established label was changed to meet an allocation target.

The primary complexity allocation refers specifically to **decisive-update dependence**: whether the effective requirement communicated by the decisive turn can be determined without earlier context. The 24 directly interpretable / 24 history-dependent split remains a prospective descriptive target, not a quota that justifies unnatural or ambiguous examples. New locked items have provisional author-side assessments; the preserved 12 development scenarios do not have a full-primary classification under this package, so no full 24/24 result is claimed. Preserve `unclear` reviewer assessments. **Whole-action dependence**—whether all requirements needed to determine action validity are available from the decisive turn, action, and public tool contract—is a separate diagnostic assessment. Report the two categories separately and do not substitute one for the other or infer either from turn count, transition family, or oracle labels. This does not change the primary four-language-condition estimand or scenario counts.

At the separately reviewed freeze step, assign each item an opaque random UUIDv4 that does not encode validity, history position, language condition, domain, transition family, partition, scenario, or template/recipe. Keep its reference mapping outside the judge-access path. This is a design requirement only; P2B-1 creates no study item IDs.

Reproducible run order: after human validation and immediately before the pre-inference freeze, freeze and hash the complete item manifest; generate a 256-bit run seed; record the seed and an immutable order-algorithm version in the private run manifest; compute `SHA-256(seed_bytes || 0x00 || UTF8(item_id))` for each opaque ID; sort ascending by digest, breaking any tie by the opaque ID. Use the same precomputed order for all baseline methods in a paired run, invoke each item in an isolated context, and do not group by history, label, language condition, or scenario. Record the exact ordered opaque-ID list and its hash. The seed and item map remain reference-side metadata. No locked run order or manifest is frozen yet.

Each ordinary judge input must contain only conversation turns with `turn_index < action_turn_index`, regardless of speaker role, plus the canonical structured action, public tool/schema information, fixed English judge instructions, and an opaque item ID. The structural validator links formal event turns to user turns and rejects turns at or after the action decision point; it does not truncate invalid histories. It cannot establish whether English or MSA text faithfully expresses those formal events. The public tool schema's required-parameter flags must match the rules enforced when validating the canonical action.

The separate no-change control has 12 additional canonical scenarios and 96 items. It estimates language-condition behavior when a later turn restates an existing requirement without changing its effective meaning. Report its four condition estimates and any cross-language versus same-language error contrast separately as secondary exploratory results. A matched primary-versus-control contrast may be reported only as exploratory, with matched-set and template dependence retained. The small control does not fully identify a causal effect of constraint revision and never replaces the primary four-condition comparison.

## Approved ordinary-condition baselines

The research owner approved these three ordinary-condition baselines for the full study, using Gemma 4 12B as the judge:

1. **Direct multilingual judging:** judge the original English, Arabic, or mixed-language history using a frozen, fixed-language instruction and validity rubric.
2. **Translation-first judging:** translate the user history to a designated pivot language, then judge it with the frozen rubric.
3. **Structured/decomposed judging:** apply a frozen criteria-based protocol with specified criterion evidence and aggregation to the binary classification.

The approved baselines are direct multilingual judging with Direct Prompt V2; translation-first judging with the same judge prompt after TranslateGemma V3 contextual translation; and single-call structured judging with Structured Prompt V2 and structured-validity V2. Structured parsing remains strict with a 512-token output limit. Do not describe a baseline as a faithful reproduction of a published method unless its implementation has been checked against that method and the reproduction is documented. No baseline may be omitted or changed after locked results are inspected. Any method introduced after inspecting locked results is exploratory and cannot support an unqualified preplanned H3 claim.

The TranslateGemma V3 prompt and model remain unchanged. Translation literal-validation policy V4 accepts only equivalent 12/24-hour representations of the same local clock time; dates, numeric timezone offsets, identifiers, currency codes, and all other numbers remain subject to strict preservation checks. It does not convert times across dates or time zones. Historical V3 failure records are retained unchanged. Automated literal checks do not establish semantic preservation of permission or negation meaning; the commissioned bilingual review remains required before freeze.

For fairness:

- Use the same judge backbone, immutable version, and decoding settings across baselines where feasible. Predeclare and justify exceptions.
- Give ordinary baselines equivalent access to the underlying user evidence, structured action, and relevant public tool/schema evidence. Translation may change language form, not add canonical state, labels, or other evidence.
- Freeze each baseline prompt, criteria, translator/model, translation prompt, translation settings, field/literal handling, output parser, and aggregation procedure before locked evaluation.
- Track translator and judge token usage, calls, latency, and cost separately and report their combined baseline totals. Do not hide translation calls in judge costs.
- Keep ordinary baselines separate from the oracle-state diagnostic below.

The judge instruction is English and identical across the four language conditions. User-facing requirements remain localized. The judge instruction does not expose reference labels, canonical effective state, or oracle verdicts.

## Development-only language competence qualification

Before selecting judges for locked evaluation, run basic English and MSA competence checks using separate development screening material. Freeze the screen and qualification criteria before judging. Do not use locked examples or labels, study gold labels, canonical effective states, or oracle verdicts for judge selection. Competence qualification is not benchmark performance and must be reported separately. It cannot justify changing a locked example or selecting a judge based on locked results.

## Prespecified state-access diagnostic and H2

The owner-approved amendment adds one paired state-access diagnostic to the locked study, separate from all three ordinary baselines. It covers 36 locked primary scenarios (288 items) and 12 locked auxiliary no-change scenarios (96 items). Each of the 384 items receives one withheld-state request (`effective_state: null`) and one supplied-state request, for 768 additional local calls. The paired requests are identical except for the `effective_state` field.

Reuse the development-tested `paper2-h2-shared-state-information-v2-20261115` instruction, binary JSON schema and parser, pinned local `gemma4:12b-it-qat` identity/digest, decoding options, and one-call/no-retry policy exactly; do not tune them. The supplied-state projection exposes only active constraints and permissions. It excludes validity labels, oracle verdicts, reason codes, judge predictions, revoked grants, and superseded requirements. The development prompt/configuration is the source of the frozen experiment contract, not a source of examples or labels for model selection.

For each scenario, calculate mean item correctness difference (supplied minus withheld) over its eight items. The primary diagnostic estimate is the macro-average over the 36 primary scenarios. Report withheld/supplied accuracy, corrections and damages over the planned denominator, and supplementary correction/damage counts restricted to items parsed in both arms. Report the four language conditions and transition-family patterns. Use 10,000 scenario-cluster bootstrap resamples with replacement, retaining all items in each sampled scenario, and seed 17 for effects and intervals. Analyze auxiliary scenarios separately using the same method. The primary-versus-auxiliary effect difference is explicitly exploratory, with independent scenario resampling, 10,000 replicates, and seed 20261115. Do not use it as a confirmatory or equivalence test.

Report by arm and group all planned, attempted, completed, parsed, refused, invalid-output, technical-failure, ambiguous-interrupted, and unattempted counts. Keep every planned item in its arm denominator; non-parsed and absent outcomes count as incorrect for planned-denominator estimates, while the paired-parsed transition counts distinguish response changes from call failures. The diagnostic does not change the original primary outcomes or the three ordinary baseline comparisons. A supplied-state improvement is behavioral evidence about the intervention; it does not establish that hidden internal state reconstruction caused earlier errors or prove an internal reasoning process.

## Label isolation and data-access separation

Ordinary judge inference and reference scoring use separate data-access paths. Ordinary inference supplies only approved conversation/action content, fixed instructions, and an opaque item ID. The separately frozen supplied-state diagnostic may receive only the active-state projection in its designated arm; neither arm receives a gold label, oracle verdict, reason code, judge prediction, pairing key, or reference-only field. Its scorer joins retained outputs to the isolated reference key only after inference. No reference may flow back into either inference path or development-time judge/model selection.

The development-only H2 diagnostic remains restricted to eligible development data and separate outputs. In the locked study, the paired state-access experiment above is the authorized state-supplying diagnostic; it is not an ordinary baseline. Even development labels used to validate the data or scorer must remain out of judge selection and prompt/configuration tuning. Keep the control subset separately identified and do not use its locked items for development selection.

## Secondary outcomes

- sensitivity to invalid actions and specificity to valid actions, plus balanced accuracy;
- counterfactual pair consistency: whether the judge flips its verdict when the oracle label flips for the same action;
- per-condition and per-transition-family/domain accuracy and errors, exploratory where cell counts are small;
- switch direction (EN–AR versus AR–EN), without assuming symmetry;
- control-set estimates reported independently from primary estimates;
- state-access arm accuracy, correction/damage counts, language-condition results, transition-family patterns, and explicitly exploratory primary-versus-auxiliary contrast, kept separate from ordinary baseline comparisons;
- parse failures, invalid output formats, refusals/abstentions, technical failures, and missing results;
- optional confidence/calibration only if output format and scoring are frozen before evaluation;
- translator and judge token usage, latency, and inference cost, reported separately and combined.

## Dependence, uncertainty, and interpretation

The canonical scenario is the primary dependence and resampling unit. The eight primary derivatives per scenario (2 histories × 4 language conditions) are paired observations, not independent samples. The eight control derivatives are likewise paired. Compute paired contrasts within scenarios; for matched primary-control comparisons, preserve the match set as a dependent unit.

Authoring templates and semantic recipes can induce dependence across canonical scenarios. Report distinct template/recipe counts and their reuse distribution. Scenario-level clustering may underestimate uncertainty if many scenarios share a template. Where the number and distribution of templates permit, provide a template-clustered sensitivity analysis in addition to the scenario-clustered primary uncertainty; if too few independent templates exist, state that inference is limited rather than treating template variants as independent.

Report scenario-clustered uncertainty for all four primary condition estimates and paired contrasts. A proposed bootstrap resamples canonical scenario IDs with all derivatives intact; for matched auxiliary contrasts, resample matched sets. For the state-access diagnostic specifically, freeze a 10,000-replicate scenario bootstrap with replacement, all eight items per sampled scenario, and seed 17; independently resample primary and auxiliary scenario effects with seed 20261115 for the explicitly exploratory contrast. Freeze interval method, resample count, and seed before locked evaluation. Do not resample individual items as independent observations.

The primary locked set has 36 primary scenario clusters; the auxiliary control has only 12 more. The 384 locked items across both sets are not 384 independent observations. The full study remains exploratory and cannot support confirmatory or population-general claims. Do not invent a power calculation. Report effect estimates, uncertainty, missingness, baseline completeness, template dependence, and validity threats. Statistical significance alone is not a go/no-go criterion.

## Invalid, missing, and failed outputs

Freeze the accepted output schema and exclusions before the locked run. A returned abstention, malformed classification, or unparseable answer is reported and counted incorrect for the primary intention-to-evaluate score unless a reviewed, preregistered rule specifies otherwise. Record technical call failures as missing attempts. Report requested, completed, validly parsed, and scored counts for each baseline and condition. Do not retry, replace, or drop failed items without a frozen retry rule and retained event log. Distinguish technical missingness from judge-produced invalid outputs in sensitivity analyses. The state-access runner allows one attempt per arm/item; an interrupted `started` record remains ambiguous and is never resent automatically. Its full planned-request accounting includes completed, technical-failure, ambiguous, and unattempted outcomes.

## Freeze and run artifacts

Before locked evaluation, freeze and hash the primary and control datasets, partition and match manifests, template/recipe inventory, prompts, model/provider identifiers and immutable versions, decoding settings, translator and translation procedures, parser, metrics, exclusions/retry policy, and analysis procedure. The state-access freeze separately binds the shared diagnostic prompt/version, active-state projection, both arm requests for each item, model/configuration, randomized call order, and analysis definition; the private freeze manifest hashes these artifacts without exposing the reference key contents to the runner. Assign an immutable run ID. Retain raw judge and translation responses, requests, failures, token counts by component, timestamps, latency, and execution metadata. Development runs cannot be relabeled as locked evaluation. Log every deviation with date, reason, affected records, and impact; do not patch the protocol after inspecting locked results.

No model inference or analysis run occurs in P0. Any future paid inference requires explicit budget authorization.
