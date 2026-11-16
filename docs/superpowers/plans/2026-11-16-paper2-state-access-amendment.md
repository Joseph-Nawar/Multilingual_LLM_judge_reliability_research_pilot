# Paper 2 State-Access Amendment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register and implement the owner-approved paired state-access diagnostic for the existing locked Paper 2 set without touching private study data or running locked inference.

**Architecture:** At dataset freeze, create a hash-bound, label-free state projection and two diagnostic requests per locked item in a separate namespace. A dedicated local runner preserves one attempt per arm/item and resumes only unstarted calls; a separate scorer performs paired scenario-level analysis after inference. Existing ordinary baseline prompts, runners, analysis, review packets, and annotations remain separate.

**Tech Stack:** Python 3.11+, standard library, existing local Ollama adapter, pytest.

**Spec:** [2026-11-16 owner-approved amendment](../../research/decision-records/2026-11-16-paper2-state-access-amendment.md).

## Global Constraints

- Keep all private inputs, projections, requests, outputs, and scores under ignored `.research-data/`.
- Do not modify scenarios, translations, annotations, reviewer packets, source hashes, oracle labels, or approved baseline prompts.
- Do not run locked inference or use model outputs for example selection or method tuning.
- Reuse the existing development diagnostic's exact instruction, response contract/parser, model identity, decoding options, and no-retry rule.
- Every model request must be reference-free; only the post-inference scorer may read reference verdicts.
- Run `python -m pytest` after foundation changes.

## Review Focus

- Canonical state records with unexpected fields must fail closed; only active constraints and permissions may enter the supplied arm.
- Withheld and supplied requests must differ only at `effective_state` and must bind the same item and frozen prompt/configuration.
- Missing or tampered freeze files, projections, requests, or run records must prevent execution or scoring.
- A saved terminal or interrupted-started attempt must never be called again during resume.
- Parse failures, technical failures, interrupted calls, and unattempted calls must remain in the planned denominators and failure report.

---

### Task 1: Freeze the shared diagnostic contract and build the state-access bundle

**Files:**
- Create: `multilingual_judge_pilot/paper2_state_access.py`
- Modify: `scripts/paper2_scientific_checkpoint.py`
- Modify: `multilingual_judge_pilot/p2c_freeze.py`
- Modify: `multilingual_judge_pilot/p2c_inference.py`
- Test: `tests/test_paper2_locked_state_access.py`

**Interfaces:**
- `project_effective_state(state: Mapping[str, object]) -> dict[str, object]`
- `build_locked_state_access_artifacts(items, reference_records, analysis_metadata, *, input_manifest_sha256, order_seed_hex) -> dict[str, bytes]`
- The existing development script continues exporting `evidence`, `safe_state`, and shared diagnostic constants from its module namespace.

- [ ] Write synthetic tests for strict active-state projection, label exclusion, A/B request equality except `effective_state`, and the exact locked inventory of 384 items/768 requests.
- [ ] Run the focused tests and confirm the intended missing-symbol or behavior failures.
- [ ] Implement the shared contract module and have the development script import its existing constants/helpers without changing values.
- [ ] Integrate the diagnostic bundle into new freeze manifests; keep ordinary run configurations unchanged and accept old freeze manifest version 1 in the ordinary loader.
- [ ] Run focused tests, then the existing full suite; commit `feat: freeze Paper 2 state-access diagnostic inputs`.

### Task 2: Add safe local execution and resume accounting

**Files:**
- Modify: `multilingual_judge_pilot/paper2_state_access.py`
- Create: `scripts/paper2_state_access.py`
- Test: `tests/test_paper2_locked_state_access.py`

**Interfaces:**
- `run_locked_state_access(freeze_root: str | Path, client: LocalClient) -> dict[str, object]`
- The CLI exposes `run --freeze-root PATH`; the production client is `OllamaLocalClient`.

- [ ] Add a fake-client test for request identity, raw-response preservation, terminal-result skipping, and one-call execution of missing requests.
- [ ] Add a test that a persisted `started` attempt is reported as ambiguous and never resent.
- [ ] Run those tests and confirm they fail before runner implementation.
- [ ] Implement local digest verification, one-attempt atomic result records, strict resume, and complete per-request attempt accounting.
- [ ] Run focused tests; commit `feat: add resumable state-access runner`.

### Task 3: Add separate deterministic paired analysis

**Files:**
- Modify: `multilingual_judge_pilot/paper2_state_access.py`
- Modify: `scripts/paper2_state_access.py`
- Test: `tests/test_paper2_locked_state_access.py`

**Interfaces:**
- `analyze_locked_state_access(freeze_root: str | Path, *, output_path: str | Path | None = None) -> dict[str, object]`
- The CLI exposes `analyze --freeze-root PATH` and writes private scored detail separately from aggregate results.

- [ ] Add synthetic tests for corrections, damages, four language conditions, transition-family grouping, paired scenario bootstrap determinism, primary-versus-auxiliary exploratory contrast, and all failure categories.
- [ ] Run focused tests and confirm the expected analysis behavior is missing.
- [ ] Implement the separate scorer and report while preserving existing baseline analysis code and result roots.
- [ ] Run focused tests, then the full suite; commit `feat: analyze paired state-access results`.

### Task 4: Register protocol, execution requirements, and manuscript methods

**Files:**
- Modify: `docs/research/protocol.md`
- Modify: `docs/research/evaluation-plan.md`
- Modify: `docs/research/full-study-execution.md`
- Modify: `manuscript/main.tex`
- Create: `docs/research/decision-records/2026-11-16-paper2-state-access-amendment.md`
- Create: `docs/superpowers/plans/2026-11-16-paper2-state-access-amendment.md`

- [ ] Confirm the experiment counts, paired estimand, uncertainty, failures, confounds, review gate, and interpretation match the approved decision record.
- [ ] Confirm the manuscript still marks locked results pending and states that no locked inference has occurred.
- [ ] Commit `docs: register Paper 2 state-access amendment`.

### Task 5: Verify package integrity and prepare the PR

**Files:**
- No private research files may be staged or changed.

- [ ] Run the full test suite with the repository Python 3.11+ environment.
- [ ] Recompute reviewer-package HTML, manifest, variant-hash, and scenario-hash fingerprints and compare them with the pre-change values.
- [ ] Inspect the complete diff and staged paths; confirm `.research-data/` and all private/reference/locked data are absent.
- [ ] Confirm no production runner or real model call was executed.
- [ ] Push the focused branch, create a normal PR to `p0-research-foundation`, and merge it with a normal merge commit after checks.
