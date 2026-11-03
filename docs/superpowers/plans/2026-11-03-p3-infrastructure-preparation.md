# P3 Infrastructure Preparation Implementation Plan

> **For agentic workers:** implement this plan in the current repository using a test-first workflow. Use the inline execution method; do not delegate. Keep all test inputs synthetic and do not inspect `.research-data/`.

## Goal

Implement the limited, owner-authorized P3 infrastructure slice described in `docs/superpowers/specs/2026-11-03-p3-infrastructure-preparation-design.md`. This does not authorize inference or the complete P3 milestone.

## Global constraints

- Python 3.11+; standard library at runtime; pytest for tests.
- Never read, load, copy, modify, or serialize private study examples or labels.
- No live model, translator, network, or paid API calls.
- Ordinary inference requests are allowlisted and reference-free; oracle diagnostics are separate.
- Do not finalize baseline prompts, backbone, translator, aggregation, analysis, or locked-run policy.
- Public changes only; check staged files before commit.

## File map

- `multilingual_judge_pilot/judge_inference.py`: request/config/result records, strict parser, mockable provider protocol, retry accounting, deterministic manifests and run IDs.
- `multilingual_judge_pilot/judge_baselines.py`: direct, translation-first, and configurable structured/decomposed preparation; mock-only collaborators for tests.
- `multilingual_judge_pilot/oracle_diagnostic.py`: explicitly separate diagnostic request and runner boundary.
- `tests/test_p3_judge_infrastructure.py`: independent synthetic fixtures and behavior/isolation/reproducibility tests.
- `docs/roadmap.md`, `README.md`, `AGENTS.md`, and a dated research decision record: accurately record limited authorization and remaining gates.

## Review focus

- A nested reference-only or unknown field must fail request construction; it must never be silently dropped.
- Turns at or after the action decision point must fail rather than be truncated.
- Missing, refused, malformed, valid, and invalid responses must remain distinguishable and raw output must be retained.
- Retry exhaustion must record every failed attempt; invalid/refused responses are not silently retried.
- Run IDs must be stable for identical configuration and change when any declared configuration field changes; credentials must be rejected.
- Baseline requests must expose equivalent action/tool evidence, while translation and decomposition provenance remain explicit and non-final.

## Tasks

### Task 1: Strict judge-facing and reproducibility records

Write failing tests first for four synthetic language-condition mappings, allowlist rejection, chronology rejection, strict verdict parsing, deterministic JSON/run ID, and credential rejection. Then implement typed immutable records and canonical serialization in `judge_inference.py`.

### Task 2: Mockable baseline and runner interfaces

Write failing tests first for direct evidence, translation-first flow with a fixture translator, configurable decomposition steps/aggregation, raw responses, token/latency/cost capture, provider failures, and explicit retry accounting. Then implement the provider protocol, deterministic mock provider, baseline preparation, and runner.

### Task 3: Oracle-diagnostic isolation

Write failing tests first showing ordinary requests/runner reject effective-state, oracle, and label fields, while the separate diagnostic constructor accepts synthetic state without any label field. Then implement the distinct diagnostic type/entry point and isolation checks.

### Task 4: Public authorization record and verification

Update the roadmap and concise repository guidance to record the tooling-only exception while preserving the complete P3, freeze, inference, budget, P4, and P5 gates. Run targeted tests and `python -m pytest`; inspect the final diff and staged paths; commit only the verified public-safe implementation and documentation.
