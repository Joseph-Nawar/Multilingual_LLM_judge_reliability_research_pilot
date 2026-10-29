# Milestone roadmap

Progress stops after P0 until an evidence-based review accepts the current milestone. A review gate requires a named research owner to inspect the evidence, record decisions and unresolved issues, and authorize the next milestone. Completion of a gate is not inferred from Codex implementation alone.

## P0 — Research foundation (current)

**Deliverables:** project instructions, README, protocol/hypotheses, dataset and state specification, evaluation/statistical plan, integrity/reproducibility requirements, prior-work register, roadmap, minimal Python/pytest setup.

**Acceptance evidence:** every P0 requirement is documented; literature verification status and blockers are explicit; project-layout checks pass; Git records the foundation on a dedicated branch. No generator, dataset, judge runner, or model call exists.

**Gate:** research owner reviews hypotheses, the proposed primary contrast, condition semantics, baseline candidates, and open design questions. Record approval or requested revisions before P1.

## P1 — Canonical schema, counterfactuals, deterministic oracle, integrity tests

**Deliverables:** versioned canonical record schema; scenario-level partition manifest; paired-history construction rules; deterministic validity oracle; provenance and exclusion ledger; tests for state transitions, counterfactual labels, class balance, and leakage.

**Acceptance evidence:** deterministic tests cover every transition family and relevant boundary case; oracle outputs reproduce from canonical states; each counterfactual pair yields opposite labels for the same action; all derivatives remain in one split; balance and provenance checks pass; ambiguous candidates are retained in the audit trail.

**Gate:** research owner reviews schema, oracle semantics, split plan, synthetic-data limitations, and test evidence before bilingual annotation begins.

## P2 — Independent bilingual validation and frozen dataset release

**Deliverables:** independently validated English/Arabic variants, adjudication records, frozen dataset and label files, documented dataset version and hashes.

**Acceptance evidence:** qualified bilingual reviewers independently verify every retained item against a frozen checklist; disagreements and exclusions are adjudicated under a recorded rule; label balance, pair integrity, partition integrity, and language semantics pass reproducible checks; release manifest includes provenance and hashes.

**Gate:** independent review accepts validation coverage, adjudication, label isolation, and dataset limitations before any judge adapter or prompt tuning uses the data.

## P3 — Judge adapters, baselines, reproducibility, development-only tests

**Deliverables:** minimal judge interface/adapters; direct, translation-first, and structured/decomposed baseline protocols; raw-response-preserving run format; development-only execution and analysis checks.

**Acceptance evidence:** prompts, translators, model identifiers, decoding, parsers, failure/retry rules, metrics, and analysis are versioned; deterministic tests cover input/output handling, hashes, run identifiers, error retention, and metric calculations; only development data is used; no locked labels leak into prompts or selection.

**Gate:** research owner reviews baseline fairness, implementation fidelity, cost estimates, data isolation, and complete development-run artifacts. P4 also requires separate explicit budget authorization for any paid inference.

## P4 — Authorized frozen pilot execution

**Deliverables:** immutable run manifest and complete execution records for the authorized frozen evaluation.

**Acceptance evidence:** frozen prompt/data/model/configuration hashes and immutable run ID are recorded; authorization and cost cap are documented; every requested item has a success, parse, or failure record; raw responses, token use, versions, and execution metadata are preserved; deviations and retries follow the frozen policy; no evaluation item is modified or selected by observed performance.

**Gate:** an independent reviewer checks run completeness, deviations, missingness, protocol adherence, and data-label isolation before analysis is interpreted.

## P5 — Statistical analysis, independent audit, go/no-go recommendation

**Deliverables:** scenario-clustered analysis, condition-level results, error and missingness breakdowns, independent audit, limitations, and a documented continuation recommendation.

**Acceptance evidence:** all four language conditions are reported separately; paired scenario-level contrasts and clustered uncertainty estimates are reproducible; invalid/missing outputs and all deviations are visible; exploratory and preplanned analyses are distinguished; conclusions reflect uncertainty and do not rely on significance alone; an independent audit checks calculations and supports the recommendation.

**Gate:** research owner accepts the audit and records go/no-go reasoning. A go decision authorizes a new reviewed milestone; it does not automatically enlarge the benchmark or authorize additional inference.
