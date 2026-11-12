# P3 Experimental Preparation Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` task-by-task. Keep tests and fixtures synthetic; do not inspect `.research-data/`.

**Goal:** Persist complete translation attempts in the accepted P3 mock infrastructure and deliver an evidence-backed methodology proposal for owner approval.

**Architecture:** Extend translation-first preparation with immutable per-attempt records, explicit retry/failure configuration, and an execution ID distinct from the deterministic configuration hash. Keep judge calls and reference scoring unchanged. Store model/method/budget recommendations and unapproved versioned configurations in public proposal documents.

**Tech Stack:** Python 3.11 standard library, pytest, Markdown/JSON; official provider documentation accessed read-only.

**Spec:** `docs/superpowers/specs/2026-11-03-p3-experimental-preparation-design.md`

## Global Constraints

- Synthetic English, MSA, and code-switched fixtures only; no study-example access.
- No live model or translator calls, paid APIs, dataset freeze, or P4/P5 activity.
- Ordinary judge requests remain reference-free and allowlisted.
- Model, prompt, translator, retry, and analysis choices are proposals until owner approval.
- Only verified public-safe files may be committed; private paths remain ignored and untracked.

## Review Focus

- Repeated executions with the same config need distinct IDs while preserving the same config hash; test repeated translation-first runs.
- Every failed attempt and retry decision must survive JSON serialization; test one retry then success and exhaustion.
- Failed or malformed translation must skip judge execution; test a provider call counter and distinct final status.
- Raw error text may contain secrets; serialize only a stable error category and explicitly supplied safe response metadata.
- Proposal token arithmetic must count the 288 Arabic-bearing locked items, three decomposed calls for each of the 384 locked items, one translation call per Arabic-bearing item, and retry overhead separately.

---

### Task 1: Translation attempt accounting

**Files:** Modify `multilingual_judge_pilot/judge_baselines.py`, `multilingual_judge_pilot/judge_inference.py`, and `multilingual_judge_pilot/reference_scoring.py` only if identifiers require schema propagation. Extend `tests/test_p3_judge_infrastructure.py`.

**Interfaces:** Translation config provides a separate retry policy and terminal failure policy. A translation-first plan carries an execution ID, all attempt records, and either a successful translation record plus judge request(s), or a terminal failure with no judge request. Run configuration hash stays deterministic; each actual execution and translation attempt has its own ID.

- [x] Add failing tests for attempt metadata, retry, exhaustion, malformed translation, skip-judge behavior, unique executions under identical configs, and separately serialized config hash.
- [x] Run the focused tests and confirm the expected failures.
- [x] Implement immutable UTC-timestamped attempt records, stable safe error categories, explicit retry decisions, and record/raise terminal failure policies without a translation fallback.
- [x] Run focused translation tests and the full suite.

### Task 2: Owner decision package

**Files:** Create `docs/research/proposals/2026-11-03-p3-experimental-methodology-proposal-v1.md` and `docs/research/proposals/p3-experimental-config-proposals-v1.json`.

**Interfaces:** The Markdown proposal documents evidence-backed candidates, baseline protocols, competence screening, and low/expected/high costs. The JSON file is versioned and marked `proposal`, with prompt/model/translator/aggregation choices explicitly unapproved.

- [x] Cite official current provider docs for availability, pinning, structured output, context, and prices; cite primary independent Arabic-language evidence for suitability.
- [x] Specify equivalent evidence for direct, translation-first, and three-criterion decomposed judging; define literal-preserving translation, parser and failure paths, call counts, and reproducibility fields.
- [x] Define separate English/MSA qualification material, thresholds, and reporting that do not rank on locked results.
- [x] Recompute item/call/token/cost arithmetic independently and state assumptions and exclusions.

### Task 3: Verification and commit

- [x] Run `python -m pytest`, compile checks, whitespace checks, and focused public-path/privacy scans.
- [x] Confirm no test or command accessed private examples and no network/API code or credentials were added.
- [x] Review staged paths and confirm only public-safe implementation, tests, proposal, roadmap, and decision files are staged.
