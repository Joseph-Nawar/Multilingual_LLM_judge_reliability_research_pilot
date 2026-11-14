# Bilingual Review Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate two offline, standalone, hash-bound P2C review workspaces from the research owner's supplied bilingual review studio and the existing private reviewer packages.

**Architecture:** A Python standard-library generator validates each review slot's packet/template inventory and embeds both into a slot-specific copy of the supplied HTML. The UI keeps independent variant answers, persists drafts under a slot/source fingerprint, and exports only a complete JSONL submission accepted by the existing P2C validator.

**Tech Stack:** Python 3.11+, standard-library HTML/JSON/hash tools, existing pytest suite, inline HTML/CSS/JavaScript from the supplied UI.

**Spec:** `docs/superpowers/specs/2026-11-14-bilingual-review-studio-design.md`

## Global Constraints

- Keep scenario content, reviewer packets, templates, and generated reviewer pages under ignored `.research-data/`.
- Preserve 56 scenarios, 448 variants per reviewer, original source hashes, and schema `p2b1-annotation-2`.
- Do not show predictions, oracle labels, or the other reviewer's responses.
- Do not auto-fill or copy substantive responses across variants.
- Keep the page offline with no external dependencies or network requests.
- Run `./.venv/bin/python -m pytest` after implementation changes.

## Review Focus

- Stale local drafts or checkpoints after packet revisions — synthetic test checks a changed source fingerprint is rejected.
- Slot/template mismatch — synthetic test verifies cross-slot packet or template data cannot bind.
- Duplicate, missing, or changed item hashes — synthetic test verifies the page builder and export gate reject them.
- Incomplete annotation or absent issue note — synthetic export is rejected by the existing `parse_submission_jsonl` contract.
- Embedded conversation/action drift — actual private generation reports counts and hash equality without printing content.

---

### Task 1: Generator validation and synthetic contract tests

**Files:**
- Create: `scripts/generate_p2c_reviewer_workspaces.py`
- Test: `tests/test_p2c_reviewer_studio.py`

**Interfaces:**
- `build_workspace_html(source_html: str, reviewer_slot: str, packets: list[dict], template_rows: list[dict]) -> str`
- `generate_workspaces(studio_html_path: Path, package_root: Path) -> dict[str, dict[str, object]]`

- [x] Write failing synthetic tests for 56 packets / 448 rows, slot isolation, source fingerprinting, stale source mismatch, and schema/hash mismatch.
- [x] Run focused tests and confirm they fail because the generator is absent.
- [x] Implement strict JSON parsing, per-slot inventory validation, exact packet/template matching, and generated HTML assembly.
- [x] Run focused tests and confirm they pass.

### Task 2: Reviewer UI binding and export behavior

**Files:**
- Modify: `scripts/generate_p2c_reviewer_workspaces.py`
- Test: `tests/test_p2c_reviewer_studio.py`

- [x] Add behavior tests for the embedded-template path, checkpoint fingerprint binding, and removal of cross-variant rationale-copy behavior.
- [x] Run focused tests and confirm the new assertions fail before the UI transformation.
- [x] Adapt the provided UI shell so packets/template bind automatically, stale checkpoints are rejected, and export includes each exact source row only after 448 complete assessments.
- [x] Keep `unclear`, independent rationales, all eight checklist answers, and required issue explanations.
- [x] Run the focused tests and the complete suite.

### Task 3: Generate and verify private reviewer workspaces

**Files:**
- Private output only: `.research-data/p2c-full/review-package/reviewer_slot_1/bilingual-review-studio.html`
- Private output only: `.research-data/p2c-full/review-package/reviewer_slot_2/bilingual-review-studio.html`
- Modify: `docs/research/full-study-execution.md` or a concise reviewer handoff document if needed.

- [x] Generate both files from the supplied Reviewer 2 HTML and current private P2C packet/template package.
- [x] Verify 56 scenarios and 448 unique variant/hash bindings per slot, exact packet-text mapping, the correct assigned slot, no reference-only or peer-response fields, and no network primitives.
- [x] Use synthetic completed rows only to verify final JSONL output against `parse_submission_jsonl`; never create reviewer answers in the real pages.
- [x] Confirm generated files remain ignored/untracked and document each private output path and how reviewers open, checkpoint, restore, and export.

### Task 4: Review and delivery

- [x] Run the full suite and `git diff --check`.
- [x] Inspect every staged path and verify no private data are tracked.
- [ ] Commit and push public-safe generator/tests/docs on a focused branch.
- [ ] Create and merge a normal PR into `p0-research-foundation` after checks and privacy review.
