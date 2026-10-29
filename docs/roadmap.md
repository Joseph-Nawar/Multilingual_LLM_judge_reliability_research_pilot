# Milestone roadmap

Progress stops after each milestone until an evidence-based review accepts the current work and authorizes the next. The research-owner decision record is the authority for approved P0 choices and remaining questions. No milestone is authorized by Codex implementation alone.

## P0 — Research foundation and audit amendments (current)

**Deliverables:** repository guidance; protocol/hypotheses; primary and no-change control specification; language/action and code-like-string policy; evaluation/statistical plan; integrity and template-provenance requirements; prior-work register; research-owner audit record; this roadmap; minimal Python/pytest setup.

**Acceptance evidence:** primary design remains 48 scenarios, 96 histories, 384 items, with 12 development and 36 locked primary scenarios; separate no-change control is 12 scenarios and 96 items; all planned counts and splits are consistently documented; H1–H3 remain hypotheses; language, baseline, oracle, template, and data-access rules are explicit; audit decisions and deferrals have milestones; structural checks pass. No generator, dataset, inference runner, or model call exists.

**Gate:** P0 is ready for research-owner review. P1 may begin only after required P1 uncertainties are resolved and the owner records authorization. This amendment task does not begin P1.

## P1 — Canonical schema, counterfactuals, deterministic oracle, integrity tests

**Deliverables:** versioned schemas for primary and control records; scenario, history, derivative, match, template, recipe, and partition identifiers; counterfactual-construction rules; deterministic validity oracle; provenance, near-duplicate, and exclusion procedures; tests for state transitions, no-change semantics, labels, balance, and leakage.

**Acceptance evidence:** primary target is 48 scenarios/384 items with 12 development and 36 locked; control target is 12 scenarios/96 additional items, with the proposed all-locked allocation explicitly approved before construction. Tests show each no-change turn leaves effective state unchanged while paired initial states yield opposite labels for the identical action. Primary transitions cover all four families. All derivatives stay with their canonical scenario and match/control links are preserved. Template/recipe IDs, near-duplicate method, distinct-template counts, and partition reuse are auditable. No ambiguous candidate is silently discarded.

**Gate:** research owner reviews schemas, oracle semantics, control matching and partitioning, template allocation/leakage, data-access separation, and test evidence before bilingual validation begins.

## P2 — Independent bilingual validation and frozen dataset release

**Deliverables:** independently validated MSA/English variants for primary and control sets; adjudication records; near-duplicate review; frozen datasets, partition/match/template manifests, and hashes.

**Acceptance evidence:** 48 primary canonical scenarios/384 items and 12 controls/96 additional items are separately accounted for; every control restatement is verified as semantically unchanged; every counterfactual pair retains opposite labels; qualified bilingual reviewers independently check meaning, action, chronology, values, and invariant literals; unresolved disagreements follow a recorded rule. Distinct template and recipe counts, near-duplicates, shared structures, and cross-partition overlap are reported. Where feasible, independent templates remain separated across development and locked evaluation. Reference data-access boundaries and label isolation pass reproducible checks.

**Gate:** independent review accepts validation coverage, adjudication, template/leakage accounting, label isolation, and limitations before P3 uses any study items.

## P3 — Judge adapters, baseline approval, reproducibility, development-only checks

**Deliverables:** minimal judge interface/adapters; direct, translation-first, and structured/decomposed baseline procedures; translator and prompt manifests; reference-scoring separation; development-only English/MSA competence screen on separate material; development execution and analysis checks.

**Acceptance evidence:** research owner explicitly approves the mandatory baseline set before locked evaluation. Any omitted candidate has a cost/feasibility rationale recorded before locked evaluation and unblinding. Same-backbone comparisons are used where feasible; evidence access is equivalent; prompts, translation procedures, criteria, decoding, parsers, aggregation, failure/retry rules, and analysis are frozen. Translator and judge tokens/costs are separately accounted. No method is described as a faithful published reproduction without verification. Competence-screen material and thresholds are frozen, separate from benchmark examples, and use no locked examples/labels or study gold/state/oracle data for selection. Tests confirm inference/scoring separation and preserve failures and raw outputs.

**Gate:** research owner reviews baseline fairness and scope for H3, competence qualification, data isolation, cost estimates, and complete development artifacts. P4 additionally requires explicit budget authorization for paid inference.

## P4 — Authorized frozen pilot execution

**Deliverables:** immutable run manifests and complete execution records for the frozen primary evaluation and separately identified auxiliary controls.

**Acceptance evidence:** run contains the approved 288 locked primary items from 36 primary scenarios and, if the P1-approved partition remains all-locked, 96 auxiliary control items from 12 control scenarios. The 96 development primary items and separate competence screen are not relabeled as locked. Frozen prompts, data/template/match manifests, model/configuration hashes, budget authorization, and immutable run ID are recorded. Ordinary and oracle-diagnostic conditions are clearly separated. Every requested item has a success, parse, or failure record; raw responses, token/cost data by component, versions, and execution metadata are preserved. No label-driven selection, silent retry, or result-driven item change occurs.

**Gate:** independent review checks run completeness, missingness, deviations, prompt/data isolation, baseline coverage, and control separation before analysis.

## P5 — Statistical analysis, independent audit, go/no-go recommendation

**Deliverables:** four-condition primary analysis; separate control and baseline analyses; scenario- and template-dependence sensitivity; error/missingness breakdowns; independent audit; documented continuation recommendation.

**Acceptance evidence:** all four primary condition estimates are reported separately with class-specific performance and scenario-clustered uncertainty; the cross-language versus same-language contrast is labeled exploratory; control results remain secondary and do not substitute for the primary comparison or claim full causal identification. The nominal sample is stated as 48 primary scenarios and 12 auxiliary controls, not 480 independent items. Template counts, reuse, near-duplicates, and feasible template-aware sensitivity are reported. Invalid/missing outputs and all deviations remain visible. Results are explicitly exploratory, and no decision relies on significance alone.

**Gate:** research owner accepts the independent audit and records go/no-go reasoning. A go decision requires a separately reviewed next milestone and does not authorize additional inference by itself.
