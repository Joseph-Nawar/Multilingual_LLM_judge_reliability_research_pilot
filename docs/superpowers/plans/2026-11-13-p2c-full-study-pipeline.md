# P2C Full-Study Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing P2C validation, freeze, local inference, and analysis components into a fail-closed CLI without using real review submissions or locked inference.

**Architecture:** Keep review/reference code, reference-free execution, and post-inference scoring in separate modules. Reuse current schemas, validators, oracle, baseline, adapter, artifact, and parser contracts; persist all operational data under ignored `.research-data/` paths.

**Tech Stack:** Python 3.12 in the repository environment, standard library, existing project modules, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-p2c-full-study-pipeline-design.md`

## Global Constraints

- Do not use, modify, stage, or publish real private examples or reviewer records in tests or commits.
- Do not run real locked inference, remote inference, paid calls, or new model experiments.
- Preserve the approved Gemma, Direct V2, Structured V2/schema V2, TranslateGemma V3, and literal policy V4 configurations.
- Fail closed on incomplete reviews, unresolved required issues, changed hashes, unknown model digests, and ambiguous attempts.
- Do not import reference data in the inference module.

## Review Focus

- Duplicate JSON object keys or JSONL rows: reject before import; Task 1.
- Wrong reviewer slot, stale variant hash, or partial export: reject and preserve source bytes; Task 1.
- A disagreement with missing/unresolved adjudication: freeze blocked; Task 2.
- Reference-only fields in frozen inference records or prompts: reject; Task 2 and Task 3.
- Interrupted or translation-failed execution: retain attempts and avoid duplicate calls; Task 3.

---

### Task 1: Review submission ingestion and adjudication records

**Files:**
- Create: `multilingual_judge_pilot/p2c_review.py`
- Create: `tests/test_p2c_full_study.py`
- Test: `tests/test_p2c_full_study.py`

**Interfaces:**
- Produces `load_review_inventory(dataset_root)`, `ingest_submission(slot, source, state_root, revision_reason=None)`, `load_current_submissions(state_root)`, `build_disagreement_report(submissions, expected_hashes)`, and `validate_current_adjudications(...)`.
- Uses `preflight.summarize_annotations` and `preflight.validate_adjudication_records` as the annotation/adjudication authority.

- [ ] Write failing synthetic tests for missing rows, duplicate IDs, duplicate JSON keys, wrong-slot IDs, stale hashes, preserved source bytes, and disagreement reporting.
- [ ] Run the focused test and confirm each missing behavior fails.
- [ ] Implement strict JSONL parsing and hash-bound immutable import records.
- [ ] Run focused tests; verify only synthetic data is used.

### Task 2: Pre-freeze validation and isolated freeze artifacts

**Files:**
- Create: `multilingual_judge_pilot/p2c_freeze.py`
- Modify: `tests/test_p2c_full_study.py`

**Interfaces:**
- Produces `verify_pre_freeze(...)` and `create_freeze(...)`.
- Uses canonical schema/integrity/oracle/serialization APIs and Task 1 adjudication validation.
- Writes judge-facing inputs and input manifest separately from reference key, opaque mapping, and analysis metadata.

- [ ] Add failing tests proving missing exports, unresolved disagreement, non-clean semantic/checklist values, corpus hash mismatch, and oracle mismatch block freeze.
- [ ] Add synthetic success test proving exact counts per supplied test inventory and no reference-only keys in inference records.
- [ ] Run the focused tests and verify failure before implementation.
- [ ] Implement corpus/hash/oracle verification, seed/order/UUID generation, artifact hashing, and fail-closed freeze storage.
- [ ] Run tests and verify frozen input and reference files remain separate.

### Task 3: Resumable local translation and judge execution

**Files:**
- Create: `multilingual_judge_pilot/p2c_inference.py`
- Modify: `multilingual_judge_pilot/local_ollama.py` only if explicit local model unloading is required to maintain one-loaded-model operation.
- Modify: `tests/test_p2c_full_study.py`

**Interfaces:**
- Produces `build_study_configs(...)`, `prepare_translations(...)`, and `run_frozen_baseline(...)`.
- Reads only frozen judge-facing inputs/configs and, for translation-first, hash-bound translation artifacts.
- Uses `JudgeExecutor`, the three accepted baseline implementations, local Ollama adapters, and strict existing parsers.

- [ ] Add failing tests for exact baseline/config construction, model digest mismatch, reference leakage, mocked translation use, attempt retention, completed-item resume, and ambiguous-state refusal.
- [ ] Verify failure before implementation.
- [ ] Implement translation stage and baseline runner with atomic per-item records and explicit local model switching.
- [ ] Run synthetic-only tests and confirm every provider request contains only approved evidence.

### Task 4: Immutable scoring and clustered analysis

**Files:**
- Create: `multilingual_judge_pilot/p2c_analysis.py`
- Modify: `tests/test_p2c_full_study.py`

**Interfaces:**
- Produces `analyze_frozen_runs(...)` over immutable stored result files and the separate reference key.
- Reports all four conditions, class recalls, pair consistency, baseline contrasts, domain/family summaries, controls, parse/translation/technical failures, and scenario-clustered bootstrap intervals.

- [ ] Add failing synthetic tests for denominator handling, pair consistency, paired contrasts, deterministic bootstrap, and controls being summarized separately.
- [ ] Verify failure before implementation.
- [ ] Implement deterministic scoring/report serialization without modifying result records.
- [ ] Run focused scoring tests.

### Task 5: CLI, operator documentation, and end-to-end verification

**Files:**
- Create: `scripts/p2c_full_study.py`
- Create: `docs/research/full-study-execution.md`
- Modify: `tests/test_p2c_full_study.py`

- [ ] Add CLI parser tests for `status`, `ingest`, `disagreements`, `validate-adjudications`, `verify`, `freeze`, `translate`, `run`, and `analyze`.
- [ ] Add a synthetic end-to-end test from two synthetic reviewer submissions through freeze, mocked runs, resume, and scoring.
- [ ] Run targeted tests and then the full `./.venv/bin/python -m pytest` suite.
- [ ] Inspect Git paths, ignored private outputs, CLI help, manuscript build-tool availability, staged diff, and `git diff --check`.
- [ ] Commit and push public-safe changes, create a PR, and merge normally only after tests and privacy review pass.
