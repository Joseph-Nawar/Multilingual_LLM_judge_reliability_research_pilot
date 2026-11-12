# Milestone roadmap

Progress follows the research-owner decisions recorded below. The 2026-11-11 decision accepted the P3 local feasibility work and authorized the full study with Gemma 4 12B and three baselines. This authorization is sufficient to proceed after the existing independent bilingual validation and pre-inference freeze; it does not waive those requirements or authorize paid/remote calls.

## P0 — Research foundation and audit amendments (approved 2026-10-29)

**Deliverables:** repository guidance; protocol/hypotheses; primary and no-change control specification; language/action and code-like-string policy; evaluation/statistical plan; integrity and template-provenance requirements; prior-work register; research-owner audit record; this roadmap; minimal Python/pytest setup.

**Acceptance evidence:** primary design remains 48 scenarios, 96 histories, 384 items, with 12 development and 36 locked primary scenarios; separate no-change control is 12 scenarios and 96 items; all planned counts and splits are consistently documented; H1–H3 remain hypotheses; language, baseline, oracle, template, and data-access rules are explicit; audit decisions and deferrals have milestones; structural checks pass. No generator, dataset, inference runner, or model call exists.

**Gate:** P0 was approved, followed by P1 and P2A approval. The P2B feasibility pilot is concluded with limitations. A later owner decision authorized P2C full-dataset authoring and deterministic validation; this still does not authorize dataset freeze or model inference.

## P1 — Canonical schema, counterfactuals, deterministic oracle, integrity tests (approved)

**Deliverables:** versioned typed schema and strict JSON codec; scenario, history, language-derivative, match, template, recipe, and partition identifiers; deterministic constraint-state oracle; counterfactual, provenance, duplicate, partition, and rejection-ledger validators; allowlisted judge projection; synthetic deterministic tests only.

**Acceptance evidence:** primary target remains 48 scenarios/384 items with 12 development and 36 locked; the research owner has approved 12 additional controls/96 items, all locked auxiliary. Tests show no-change requirement and permission restatements leave effective state unchanged while paired initial states yield opposite oracle labels for the identical action. Primary transitions cover all four families, and adversarial pair tests reject unequal initial states, irrelevant family events, metadata-only revisions, pre-decisive label differences, and inconsistent action points. Decisive formal events, conversation turns, action chronology, and language-variant assignments are structurally linked; judge serialization rejects every turn at or after the action decision point, including user, assistant, and tool turns, without claiming to verify translation meaning. Public tool parameters declare required/optional status, which is enforced consistently for reference validation and judge-facing schemas; currency codes are checked against a pinned offline ISO 4217 snapshot. Language hooks map all four conditions and a pre-freeze validator rejects incomplete condition coverage. All derivatives stay with their canonical scenario and match/control links cannot reassign partitions. Template/recipe IDs, exact and normalized duplicate checks, distinct-template reports, and partition reuse are auditable; semantic equivalence is not inferred from text similarity. Invalid candidates retain source bytes, hashes, and rejection reasons in an audit outcome. Judge-facing serialization excludes reference-only fields. No study scenarios, translations, locked labels, or model calls are created.

**Gate:** The research owner approved P1 at commit `3139cebe6926edeca0997c965617c7a35c3e0d27`. That approval did not itself authorize later milestones; P2A was separately authorized.

## P2A — Authoring protocol and controlled preflight (approved 2026-10-29)

**Deliverables:** reproducible scenario-authoring procedure; balanced prospective 60-scenario blueprint; two-reviewer English/MSA annotation rubric and audit utilities; exactly four local primary development prototypes from four distinct domain/family cells (32 history-language variants); structural semantic-coverage links; redacted preflight report. Prototype text, language drafts, references, review packets, and annotations remain local under ignored `.research-data/` paths.

**Acceptance evidence:** only four development-only primary prototypes exist locally; all have the approved schema and oracle labels, two histories, four conditions, chronology, and complete formal-target coverage links; every requirement, permission, and event target maps to at least one non-whitespace localized natural-language span; all pairs have oracle-established opposite labels; duplicate/template checks and local data-isolation tests pass. Coverage links are explicitly not human semantic validation. Translation drafts remain unvalidated. No controls or locked scenarios are authored; no dataset is frozen; no inference occurs.

**Gate:** the research owner accepted the framework and approved P2A feasibility. The four language drafts still required content inspection and independent bilingual validation; P2A approval did not approve those translations as validated. P2B-1 has a separate, narrower authorization.

## P2B-1 — Prototype corrections and human-review preparation (completed)

**Scope:** correct the four existing development prototypes in response to the independent content audit; preserve originals and hashes; update the prospective blueprint and annotation rubric; prepare hash-bound packets, blank templates, briefing, side-by-side presentation, and a completeness report. All private records remain ignored local data. This submilestone creates no additional scenarios, controls, locked examples, or judge results.

**Acceptance evidence:** original bytes and hashes are preserved; each proposed change and rationale is in the revision ledger; revised formal records pass schema/oracle/counterfactual/chronology/coverage checks with all 32 language variants present; changed variants remain unvalidated. The blueprint addresses history-position counterbalancing, opaque IDs, reproducible order randomization, upper/lower and earliest/latest constraints, direction and surface-cue audit, and separate decisive-update versus whole-action dependence. Two reviewer slots have separate packets and versioned blank dual-hash annotation templates containing both questions and rationales; the completeness report states actual human coverage, including zero if no reviewer has submitted records. Adjudications bind both hashes, require resolution of disagreements on both dependence categories, and do not treat an unresolved disagreement as completed validation. Private-data isolation and redacted public reporting pass.

**Gate:** the research owner reviewed the corrected prototypes and materials. This stage did not itself complete semantic validation or authorize inference.

## P2B — Four-scenario feasibility pilot (concluded with documented limitations)

**Evidence:** two bilingual reviewers assessed all 32 English/MSA language variants across four development scenarios. Initial semantic and linguistic assessments were positive: all variants were marked semantically equivalent; 40/64 reviewer ratings were `natural` and 24/64 `acceptable_variation`; no issue codes or failed checklist items were reported. Initial categorical ratings agreed for all 32 paired variants. Follow-up dependence forms supplied complete responses and rationales, but reviewers disagreed on decisive-update dependence in four of eight history combinations and whole-action dependence in four of eight; two histories were disputed on both constructs. No adjudication was performed, and the research owner directed that no further pilot review or adjudication be requested. These findings support authoring feasibility only, not full-benchmark semantic validity or independently resolved dependence annotation.

**Lessons for future annotation:** keep the two dependence constructs distinct; state explicitly that `yes` means earlier conversation is unnecessary and `no` means it is necessary; ask reviewers to consider all requirements needed for the whole-action verdict, including earlier permissions; preserve `unclear`; and require construct-specific rationales. These clarifications do not rewrite prior human responses or convert disagreements into adjudicated labels.

**Disposition:** no more review of these four pilot scenarios is authorized. Dependence disagreements remain unresolved. Full-study bilingual validation of future dataset variants remains a distinct required gate before any dataset freeze or evaluation; the concluded pilot is not reopened to satisfy that gate.

## P2C-Development — Development-scenario authoring (completed)

**Completed deliverables:** the eight authorized development primary scenarios were authored in the eight uncovered domain × transition-family cells, with two formal histories and four language conditions per history. Combined with four existing pilot prototypes, the development set contains 12 primary scenarios and 96 derived items.

**Acceptance evidence for this authorized scope:** all 12 primary cells are represented once in development; every scenario has two histories, each with four conditions; the deterministic oracle establishes opposite labels for the same well-formed action; structural chronology and semantic-coverage checks pass; valid-history position is balanced 6/6 across the 12 scenarios; duplicate checks report exact/normalized results and template/recipe reuse; no development language draft is mislabeled as human validated. All new data remain local and ignored.

**Disposition:** the eight development scenarios completed the authorized development milestone. The original development records and all pilot evidence remain preserved.

## P2C-Full — Full dataset authoring and validation-package preparation (authoring complete)

**Completed deliverables:** 36 locked primary scenarios and 12 locked auxiliary no-change controls, combined with the 12 preserved development primaries. The private package contains 60 canonical scenarios, 120 counterfactual histories, and 480 language items; it includes formal-state-first specifications, action/tool contracts, four language conditions per history, semantic-coverage mappings, provisional author-side dependence assessments, provenance, template/recipe inventories, duplicate and surface-risk audits, partition/control-match manifests, exclusion/revision ledgers, hashes, and consolidated review materials.

**Deterministic evidence:** all 12 primary cells contain four scenarios (one development, three locked); all 60 counterfactual pairs have opposite deterministic labels for their shared action; all 28 control restatements preserve effective state; and all four language conditions cover every history. Valid-history positions are balanced 6/6 in development, 18/18 in locked primary scenarios, and 6/6 in controls. Control matching records 9 full and 3 partial permission-scope matches. No exact or normalized duplicate groups were found; lexical screening flagged 24 candidate pairs (12 declared control-match overlaps, 12 other candidates) and one potential surface-feature shortcut. Machine checks do not adjudicate semantic duplicates, linguistic equivalence, or naturalness. The target 24/24 complexity split is not claimed; the deviation is documented without forcing categories.

**Human review package:** two hash-bound reviewer slots cover 56 scenarios and 448 variants. The four scenarios and 32 variants already covered in the concluded P2B feasibility pilot are excluded from new review tasks; their annotations remain unchanged. No new reviewer responses have been submitted, and no new bilingual validation is claimed.

**Gate at P2C closeout:** at that milestone, the dataset was not frozen. Independent bilingual review, quality-control and disagreement resolution, human review of duplicate/surface/template findings, research-owner acceptance of documented deviations and rendering proposals, and a separate freeze authorization remained required before locked evaluation. No judge inference or paid API call occurred during authoring.

## P3 — Judge adapters, baseline approval, reproducibility, development-only checks

### Limited infrastructure-preparation exception (authorized 2026-11-03)

**Authorization:** the research owner separately authorized the implementation of minimal provider-independent interfaces for direct multilingual, translation-first, and structured/decomposed judging, reproducibility records, strict parsing/failure accounting, and reference-isolation checks. Development and tests must use independent synthetic English, MSA, and code-switched fixtures only. This infrastructure slice may proceed in parallel with the two-reviewer P2C validation.

**Scope limits:** deterministic mocks only; no private study examples may be loaded or inspected; no model or translator calls, paid API calls, judge selection from study data, prompt/backbone/translator/aggregation approval, locked evaluation, dataset freeze, or P4/P5 activity. The later 2026-11-03 authorization also permits closing translation-attempt accounting and preparing an evidence-backed experimental-methodology proposal. Proposed models, prompts, translation procedure, decomposition, retry policy, competence screen, and cost plan remain unapproved. This limited tooling/proposal work does not signify acceptance of the complete P3 milestone.

**Implementation record:** see [P3 infrastructure-preparation decision record](research/decision-records/2026-11-03-p3-infrastructure-preparation.md), [experimental methodology proposal](research/proposals/2026-11-03-p3-experimental-methodology-proposal-v1.md), and [versioned configuration proposals](research/proposals/p3-experimental-config-proposals-v1.json). Acceptance of the infrastructure slice and preparation package does not advance the roadmap gate for full P3.

### Commercial methodology v2 preparation (historical; superseded by the local-study decision of 2026-11-11)

The research owner directed a v2 proposal around GPT-6.1 Sol, Claude Sonnet 5.5, and Gemini 3.8 Flash; direct, translation-first, and one-call structured judging; separate H2 diagnostics; a candidate English/MSA competence screen; and a recalculated three-model budget. The owner also authorized synthetic-only changes for the one-call structured output/parser and state-extraction request contracts. The existing caller-configured three-call interface remains a possible secondary experiment.

At that preparation milestone, the v2 package and implementation were **not** a frozen methodology or full P3 approval. Those commercial-provider options were superseded by the owner's zero-cost local Gemma 4 design and full-study authorization recorded below. The historical proposal and its synthetic-only limits remain in the linked records.

See [methodology proposal v2](research/proposals/2026-11-03-p3-experimental-methodology-proposal-v2.md), [configuration proposal v2](research/proposals/p3-experimental-config-proposals-v2.json), and [v2 preparation record](research/decision-records/2026-11-03-p3-methodology-v2-preparation.md).

### Full P3 milestone (accepted for the local study design)

**Accepted deliverables:** local Gemma 4 12B selected as the primary judge; Direct Prompt V2, Structured Prompt V2/schema V2, and TranslateGemma V3 baselines accepted; the separate English/MSA competence screen and four-language development feasibility pilot completed. Pilot findings are exploratory and retained without prompt, model, threshold, or label changes. Translation literal-validation policy V4 permits only same-local-time 12/24-hour notation equivalence and is hash-bound separately from prompt V3.

**Status:** P3 methodology and local execution are accepted for the approved study. This does not imply that the study dataset is frozen or human-validated.

See the [full-study authorization and feasibility findings](research/decision-records/2026-11-11-p3-feasibility-go-full-study.md).

**Gate:** none remains for model or baseline selection. The existing dataset validation and pre-inference freeze requirements still apply. Paid and remote inference remain prohibited.

## P4 — Owner-authorized full locked execution after validation and freeze

**Authorization:** on 2026-11-11, the research owner authorized execution of the full locked study with local Gemma 4 12B once the existing two-reviewer bilingual validation is accepted and the pre-inference freeze is complete. No additional discretionary approval gate is required after those conditions are met. No paid or remote APIs are permitted.

**Deliverables:** immutable run manifests and complete execution records for the frozen primary evaluation and separately identified auxiliary controls.

**Acceptance evidence:** run contains the approved 288 locked primary items from 36 primary scenarios and 96 auxiliary control items from 12 locked control scenarios, with primary and control results reported separately. The 96 development primary items and separate competence screen are not relabeled as locked. Frozen prompts, data/template/match manifests, model/configuration hashes, zero-cost local execution authorization, and immutable run ID are recorded. Ordinary and oracle-diagnostic conditions are clearly separated. Every requested item has a success, parse, or failure record; raw responses, token/cost data by component, versions, and execution metadata are preserved. No label-driven selection, silent retry, or result-driven item change occurs.

**Current blocker:** the commissioned reviewer submissions are not present in the private package, so independent validation is incomplete. The dataset remains unfrozen. Do not begin locked inference until that existing validation is complete and the pre-inference freeze record binds the final data and configuration hashes.

**Post-run check:** review run completeness, missingness, deviations, prompt/data isolation, baseline coverage, and control separation before analysis.

## P5 — Statistical analysis, independent audit, go/no-go recommendation

**Deliverables:** four-condition primary analysis; separate control and baseline analyses; scenario- and template-dependence sensitivity; error/missingness breakdowns; independent audit; documented continuation recommendation.

**Acceptance evidence:** all four primary condition estimates are reported separately with class-specific performance and scenario-clustered uncertainty; the cross-language versus same-language contrast is labeled exploratory; control results remain secondary and do not substitute for the primary comparison or claim full causal identification. The nominal sample is stated as 48 primary scenarios and 12 auxiliary controls, not 480 independent items. Template counts, reuse, near-duplicates, and feasible template-aware sensitivity are reported. Invalid/missing outputs and all deviations remain visible. Results are explicitly exploratory, and no decision relies on significance alone.

**Gate:** research owner accepts the independent audit and records go/no-go reasoning. A go decision requires a separately reviewed next milestone and does not authorize additional inference by itself.
