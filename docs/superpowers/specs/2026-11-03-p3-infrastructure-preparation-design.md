# P3 Infrastructure Preparation — Design

## Intent

Implement a small, provider-independent foundation for future multilingual judge evaluation while independent P2C human validation proceeds. This is the research-owner-authorized P3 tooling exception, not approval of the full P3 milestone.

## Goals and constraints

- Accept only an explicit judge-facing allowlist: opaque item ID, pre-action conversation turns, action, public tool schema, and fixed instruction.
- Preserve each request, raw response, parsed response status, failure/retry attempt, timing, usage, and cost as versioned records.
- Provide direct, translation-first, and structured/decomposed baseline interfaces, exercised with deterministic mocks.
- Keep oracle-state diagnostics in a distinct request type and execution path.
- Use Python 3.11+ standard library only; use independent synthetic English, MSA, and mixed-language fixtures.
- Never load private study data, call a model, or send a network request.

## Approaches

1. **Add live provider adapters now.** Rejected because providers, prompts, backbones, budget, and inference are not authorized.
2. **Build one compact local package with provider and translator protocols plus deterministic mocks.** Chosen: it supports the requested interface and tests without choosing a vendor or finalizing a method.
3. **Build a service, database, or distributed runner.** Rejected as unnecessary for this infrastructure slice.

## Design

Use small standard-library modules for strict request/run records and execution, baseline preparation, and the separate oracle diagnostic. The ordinary request type has no reference-only fields, rejects unknown or forbidden fields, and serializes deterministically. A strict parser accepts only a JSON object containing the binary `verdict` value `valid` or `invalid`; missing, refused, malformed, and provider-failure outcomes remain distinct and retain raw data where available. Retry behavior is explicit in a versioned policy and every attempt is recorded.

Direct and translation-first adapters prepare one request each. Translation is behind a translator protocol and its provenance/output is recorded separately. Structured/decomposed preparation accepts explicit step and aggregation specifications; test examples are labeled mock-only and are not proposed as final research prompts or rules. Ordinary runs require only judge-facing input. Oracle-state diagnostics use a separate type and entry point and never accept reference labels.

Run configuration includes provider/model identity, prompt and parser versions, baseline, translation configuration when relevant, decoding parameters, retry policy, supported random seed, and input/code hashes. A deterministic canonical JSON representation produces a content-addressed run ID. Credential-shaped fields are rejected and no credential value is logged.

## Non-goals and later owner decisions

No dataset freeze, study-example inference, judge selection, competence screen, paid API call, final prompt, provider, translator, baseline aggregation rule, retry policy for a live study, or P4/P5 activity is included. Those choices remain subject to the existing research-owner gates. This implementation does not establish scientific validity or reproduce a published method.
