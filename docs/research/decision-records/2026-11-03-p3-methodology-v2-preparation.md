# P3 Methodology v2 Preparation Record

**Date:** 2026-11-03

**Status:** v2 proposal prepared and synthetic-only interfaces updated; owner approval of the methodology and full P3 remains outstanding.

**Decision owner:** Research owner.

## Authorized scope

The research owner directed preparation of a second, unapproved P3 methodology proposal with three provisional model candidates (GPT-6.1 Sol, Claude Sonnet 5.5, and Gemini 3.8 Flash), three mandatory proposed ordinary baselines (direct, translation-first, and single-call structured), a separate H2 diagnostic proposal, a candidate English/MSA screen, and a recalculated three-model budget. The owner also authorized the synthetic-only interface changes needed to represent the single-call structured baseline and active-state extraction request. The prior three-call decomposition interface is preserved as a possible secondary experiment.

This instruction is not authorization for live calls, paid inference, study-data access, model selection, dataset freeze, P4, or later work. All methods, settings, thresholds, prompts, and costs remain proposed.

## Evidence and decisions captured

- Official provider model, API, structured-output, pricing, reasoning, version, and data-handling documentation was checked on the date above and linked from the v2 proposal. Prices and terms must be checked again before a later authorization.
- The three API candidate IDs are `gpt-6.1-sol`, `claude-sonnet-5-5`, and `gemini-3.8-flash`. Provider configuration validation is specific to each candidate. In particular, Claude Sonnet 5.5 rejects `temperature`, `top_p`, and `top_k`; the provider settings are not treated as interchangeable.
- One-call structured judging receives the same original conversation, action, and public tool contract as direct judging. Its versioned output schema requires component assessments and a final binary verdict. Contradictory or malformed outputs remain invalid-output outcomes.
- Translation-first accounting retains every attempt. The proposed method calls for one hash-bound translation reused across model backbones where feasible, no hidden-state resolution, no reference-based repair, and no silent fallback after translation failure.
- State extraction uses only ordinary evidence. Oracle-state access is separately typed, withholds validity labels, and remains outside ordinary baseline scoring. Neither diagnostic is run.
- Budget arithmetic covers 3,456 ordinary calls across the three models, 144 competence-screen calls, 288 locked shared translations plus a separately marked optional 24-item translation-QC workload, technical retry stress, and optional H2 and three-call experiments. Gemini's published standard rate increase on 2027-01-01 is included. The budget is not spending authorization.

## Integrity and verification scope

Implementation and test fixtures are synthetic and independent of study data. No `.research-data/` files, locked examples, reference labels, or human-review materials were loaded or edited. No provider adapters, API credentials, live model calls, translator calls, or paid services were added or used. The proposed state-extraction request has no canonical state or validity label field; ordinary requests remain allowlisted and separate from the reference scorer.

Passing tests establishes only software-contract behavior. It does not establish model capabilities, prompt quality, translation fidelity, dataset validity, linguistic equivalence, or the scientific validity of proposed methods.

## Artifacts

- [P3 methodology proposal v2](../proposals/2026-11-03-p3-experimental-methodology-proposal-v2.md)
- [P3 configuration proposal v2](../proposals/p3-experimental-config-proposals-v2.json)
- `multilingual_judge_pilot/judge_inference.py`: versioned response contracts and strict structured parser.
- `multilingual_judge_pilot/judge_baselines.py`: one-call structured baseline; three-call interface retained.
- `multilingual_judge_pilot/provider_configuration.py`: proposed candidate-specific validation only; no adapters.
- `multilingual_judge_pilot/oracle_diagnostic.py`: separate state-extraction request plus existing oracle-state request.
- `tests/test_p3_methodology_v2.py`: independent synthetic contract, manifest, call-count, and budget checks.

## Remaining gates

Research-owner review is still required for model/service choice, availability and privacy terms, mandatory baselines, prompts/rubric, provider-native configurations, translation design and QA, structured aggregation, competence-screen threshold, optional diagnostics, retries, budget and spend. The independent P2C human validation and dataset-freeze gate remain separate. No live evaluation is authorized by this record.
