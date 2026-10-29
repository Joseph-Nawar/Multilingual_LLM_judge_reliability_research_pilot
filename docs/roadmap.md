# Milestone roadmap

Progress stops after each milestone until an evidence-based review accepts the current work and authorizes the next. The research-owner decision record is the authority for approved P0 choices and remaining questions. No milestone is authorized by Codex implementation alone.

## P0 — Research foundation and audit amendments (approved 2026-10-29)

**Deliverables:** repository guidance; protocol/hypotheses; primary and no-change control specification; language/action and code-like-string policy; evaluation/statistical plan; integrity and template-provenance requirements; prior-work register; research-owner audit record; this roadmap; minimal Python/pytest setup.

**Acceptance evidence:** primary design remains 48 scenarios, 96 histories, 384 items, with 12 development and 36 locked primary scenarios; separate no-change control is 12 scenarios and 96 items; all planned counts and splits are consistently documented; H1–H3 remain hypotheses; language, baseline, oracle, template, and data-access rules are explicit; audit decisions and deferrals have milestones; structural checks pass. No generator, dataset, inference runner, or model call exists.

**Gate:** P0 was approved, followed by P1 approval and a separate P2A authorization on 2026-10-29. P2A alone permits the authoring procedure and exactly four local development prototypes; it does not authorize locked examples, study controls, or model inference.

## P1 — Canonical schema, counterfactuals, deterministic oracle, integrity tests (approved)

**Deliverables:** versioned typed schema and strict JSON codec; scenario, history, language-derivative, match, template, recipe, and partition identifiers; deterministic constraint-state oracle; counterfactual, provenance, duplicate, partition, and rejection-ledger validators; allowlisted judge projection; synthetic deterministic tests only.

**Acceptance evidence:** primary target remains 48 scenarios/384 items with 12 development and 36 locked; the research owner has approved 12 additional controls/96 items, all locked auxiliary. Tests show no-change requirement and permission restatements leave effective state unchanged while paired initial states yield opposite oracle labels for the identical action. Primary transitions cover all four families, and adversarial pair tests reject unequal initial states, irrelevant family events, metadata-only revisions, pre-decisive label differences, and inconsistent action points. Decisive formal events, conversation turns, action chronology, and language-variant assignments are structurally linked; judge serialization rejects every turn at or after the action decision point, including user, assistant, and tool turns, without claiming to verify translation meaning. Public tool parameters declare required/optional status, which is enforced consistently for reference validation and judge-facing schemas; currency codes are checked against a pinned offline ISO 4217 snapshot. Language hooks map all four conditions and a pre-freeze validator rejects incomplete condition coverage. All derivatives stay with their canonical scenario and match/control links cannot reassign partitions. Template/recipe IDs, exact and normalized duplicate checks, distinct-template reports, and partition reuse are auditable; semantic equivalence is not inferred from text similarity. Invalid candidates retain source bytes, hashes, and rejection reasons in an audit outcome. Judge-facing serialization excludes reference-only fields. No study scenarios, translations, locked labels, or model calls are created.

**Gate:** The research owner approved P1 at commit `3139cebe6926edeca0997c965617c7a35c3e0d27`. That approval did not itself authorize later milestones; P2A was separately authorized.

## P2A — Authoring protocol and controlled preflight (authorized; review pending)

**Deliverables:** reproducible scenario-authoring procedure; balanced prospective 60-scenario blueprint; two-reviewer English/MSA annotation rubric and audit utilities; exactly four local primary development prototypes from four distinct domain/family cells (32 history-language variants); structural semantic-coverage links; redacted preflight report. Prototype text, language drafts, references, review packets, and annotations remain local under ignored `.research-data/` paths.

**Acceptance evidence:** only four development-only primary prototypes exist locally; all have the approved schema and oracle labels, two histories, four conditions, chronology, and complete formal-target coverage links; every requirement, permission, and event target maps to at least one non-whitespace localized natural-language span; all pairs have oracle-established opposite labels; duplicate/template checks and local data-isolation tests pass. Coverage links are explicitly not human semantic validation. Translation drafts remain unvalidated. No controls or locked scenarios are authored; no dataset is frozen; no inference occurs.

**Gate:** research owner independently reviews the authoring method, blueprint, four prototypes, coverage report, feasibility, and limitations. No P2B work follows automatically.

## P2B — Independent bilingual validation (not started; separate authorization required)

**Deliverables:** two independent qualified bilingual reviews of approved prototype drafts and later authorized study variants; hash-bound annotations; disagreement adjudication; retained corrections, exclusions, and revision history; semantic near-duplicate review and template-family audit.

**Acceptance evidence:** reviewers assess all decision-relevant meaning, initial requirements, decisive turns, actions, chronology, quantities, permissions, temporal expressions, and invariant literals without judge predictions or oracle verdicts. Agreement, missing reviews, disagreements, adjudications, and limitations are reported; substantive revisions receive full re-review. Codex-authored drafts are not human-approved by structural checks.

**Gate:** owner accepts reviewer qualifications, coverage, adjudication, and language/template findings before any dataset-freeze milestone.

## P2C — Dataset authoring, partition freeze, and release review (not started; separate authorization required)

**Deliverables:** complete 48-scenario primary set and separately identified 12-scenario auxiliary controls; frozen partitions, match/template/recipe inventories, provenance, exclusion ledger, hashes, and reviewed release package.

**Acceptance evidence:** 48 primary scenarios/384 items (12 development, 36 locked) and 12 controls/96 locked auxiliary items; 60 canonical scenarios/480 items total. All language variants are independently validated, counterfactual/oracle and control no-change invariants pass, all 12 primary cells retain four scenarios each with one development and three locked, and controls are matched only to locked primary scenarios where feasible. Report template reuse/leakage, near duplicates, anti-shortcut feature balance, unmatched controls, exclusions, and all deviations. No item is selected or changed in response to judge behavior; no confirmatory or power claim is made.

**Gate:** independent owner review accepts validation, partition integrity, provenance, label isolation, and public/private release handling before P3 uses any study items.

## P3 — Judge adapters, baseline approval, reproducibility, development-only checks

**Deliverables:** minimal judge interface/adapters; direct, translation-first, and structured/decomposed baseline procedures; translator and prompt manifests; reference-scoring separation; development-only English/MSA competence screen on separate material; development execution and analysis checks.

**Acceptance evidence:** research owner explicitly approves the mandatory baseline set before locked evaluation. Any omitted candidate has a cost/feasibility rationale recorded before locked evaluation and unblinding. Same-backbone comparisons are used where feasible; evidence access is equivalent; prompts, translation procedures, criteria, decoding, parsers, aggregation, failure/retry rules, and analysis are frozen. Translator and judge tokens/costs are separately accounted. No method is described as a faithful published reproduction without verification. Competence-screen material and thresholds are frozen, separate from benchmark examples, and use no locked examples/labels or study gold/state/oracle data for selection. Tests confirm inference/scoring separation and preserve failures and raw outputs.

**Gate:** research owner reviews baseline fairness and scope for H3, competence qualification, data isolation, cost estimates, and complete development artifacts. P4 additionally requires explicit budget authorization for paid inference.

## P4 — Authorized frozen pilot execution

**Deliverables:** immutable run manifests and complete execution records for the frozen primary evaluation and separately identified auxiliary controls.

**Acceptance evidence:** run contains the approved 288 locked primary items from 36 primary scenarios and 96 auxiliary control items from 12 locked control scenarios, with primary and control results reported separately. The 96 development primary items and separate competence screen are not relabeled as locked. Frozen prompts, data/template/match manifests, model/configuration hashes, budget authorization, and immutable run ID are recorded. Ordinary and oracle-diagnostic conditions are clearly separated. Every requested item has a success, parse, or failure record; raw responses, token/cost data by component, versions, and execution metadata are preserved. No label-driven selection, silent retry, or result-driven item change occurs.

**Gate:** independent review checks run completeness, missingness, deviations, prompt/data isolation, baseline coverage, and control separation before analysis.

## P5 — Statistical analysis, independent audit, go/no-go recommendation

**Deliverables:** four-condition primary analysis; separate control and baseline analyses; scenario- and template-dependence sensitivity; error/missingness breakdowns; independent audit; documented continuation recommendation.

**Acceptance evidence:** all four primary condition estimates are reported separately with class-specific performance and scenario-clustered uncertainty; the cross-language versus same-language contrast is labeled exploratory; control results remain secondary and do not substitute for the primary comparison or claim full causal identification. The nominal sample is stated as 48 primary scenarios and 12 auxiliary controls, not 480 independent items. Template counts, reuse, near-duplicates, and feasible template-aware sensitivity are reported. Invalid/missing outputs and all deviations remain visible. Results are explicitly exploratory, and no decision relies on significance alone.

**Gate:** research owner accepts the independent audit and records go/no-go reasoning. A go decision requires a separately reviewed next milestone and does not authorize additional inference by itself.
