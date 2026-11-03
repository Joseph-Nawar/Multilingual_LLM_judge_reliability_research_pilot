# P3 Infrastructure Preparation Authorization and Record

**Date:** 2026-11-03
**Status:** Limited infrastructure slice implemented under authorization; complete P3 milestone not approved.
**Decision owner:** Research owner, as stated in the P3 infrastructure-preparation authorization.

## Authorization

The research owner authorizes narrowly scoped P3 infrastructure development to proceed in parallel with independent P2C human validation. The implementation may provide provider-independent judge request/run records, strict response parsing, failure and retry accounting, deterministic mock interfaces for the three candidate baseline families, translation/decomposition interfaces, and a separate oracle-state diagnostic path. Tests must use independent synthetic fixtures only.

This is an exception to P3's normal sequencing requirement for tooling only. It does not approve the complete P3 milestone or its baseline set.

## Explicit exclusions

- No dataset freeze or inspection/loading of private locked study examples.
- No study-example inference, model selection from study labels, locked evaluation, or live translator calls.
- No paid API call or inference-budget authorization.
- No final research prompts, judge backbones, translator, translation policy, decomposition criteria, aggregation rules, or live retry policy.
- No P4 or P5 work.

## Integrity and acceptance

Canonical states, oracle verdicts, and gold labels remain reference-only. Ordinary judge requests use an explicit allowlist and cannot accept reference fields. The optional oracle-state diagnostic is a separate request/runner path and excludes reference labels. Raw outputs, parse status, attempts, usage, latency, and cost metadata are preserved in versioned records. No API credentials are stored in manifests or logs.

The public implementation and tests use only original synthetic English, Modern Standard Arabic, and code-switched examples. Passing structural tests demonstrates interface and isolation behavior only; it does not validate the study data, language quality, prompts, candidate baselines, or scientific claims.

## Implemented slice

- `multilingual_judge_pilot/judge_inference.py`: allowlisted ordinary requests, strict binary parser, explicit missing/refused/malformed/provider-failure outcomes, deterministic run manifest IDs, provider protocol, mock provider, and raw per-attempt timing/usage/cost records.
- `multilingual_judge_pilot/judge_baselines.py`: direct, translation-first, and caller-configured structured/decomposed request plans. Translation collaborator identity must match its versioned configuration. No final prompt, translator, decomposition, or aggregation procedure is selected.
- `multilingual_judge_pilot/oracle_diagnostic.py` and `reference_scoring.py`: separate diagnostic request and post-inference scorer; neither is imported by ordinary request construction.
- `tests/test_p3_judge_infrastructure.py` and `tests/p3_synthetic_fixtures.py`: synthetic-only tests for four language conditions, request isolation, baseline evidence parity, mock translation/decomposition, parsing, retries, run reproducibility, and scoring separation.

Malformed, missing, refused, and technical-failure outcomes remain distinct. The reference scorer reports correctness only for a parsed binary verdict; treatment of non-parsed outcomes in the eventual study score remains subject to the frozen analysis rule.

## Remaining gates

Two independent bilingual reviewers must validate the P2C review scope and material issues must be handled under the accepted QC process before dataset freeze. Full P3 still requires research-owner review of baseline fairness and scope, competence screening plan, exact prompts/models/translators/aggregation, development-only checks, and reproducibility artifacts. Separate explicit authorization is required before any study-example inference or paid call. P4/P5 remain unapproved.

The translation-first preparation path currently treats translation as a successful injected collaborator call: a translation exception aborts plan preparation without a persisted attempt record. Before any live translator use, the owner-approved execution design must add translation failure/retry records and decide its retry policy; the present no-call tooling slice does not exercise that path.
