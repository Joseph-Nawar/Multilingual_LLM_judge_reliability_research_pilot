# P3 Experimental Preparation — Design

## Intent

Complete translation-first attempt accounting in the existing synthetic-only infrastructure, then prepare an evidence-backed, explicitly unapproved methodology and budget proposal for the research owner. The work must not use private study examples, make live calls, freeze data, or approve P3.

## Goals and boundaries

- Retain every translation attempt, including failures, with configuration/input hashes, independent execution and attempt IDs, UTC timestamps, latency, safe error category, raw output, usage, cost, and retry decision.
- Make translation retry and terminal-failure behavior explicit and versioned. A failed translation must never fall through to judging untranslated or partial content.
- Keep the accepted ordinary judge request allowlist, strict parser, baseline abstractions, scorer separation, and synthetic-only test boundary intact.
- Draft model, baseline, competence-screen, configuration, and budget options from the public protocol and evaluation plan. Mark every proposed choice unapproved.
- Use official current provider documentation for availability, versioning, structured output, context, and price; use primary external Arabic-language evidence where available.

## Approaches

1. **Add a live translator adapter and persist provider logs.** Rejected: no live calls are authorized, and provider choice is unresolved.
2. **Wrap the injected translator in a versioned synthetic execution policy and retain attempt records in the ordinary run result.** Chosen: this repairs the existing interface without selecting a provider or adding a service/database.
3. **Only document translation failures as a future limitation.** Rejected: the owner explicitly authorized closing the accounting gap now.

## Design

The translation-first plan owns a unique execution ID, separate from the stable run-configuration hash. Each translation invocation gets a unique attempt ID and a record bound to the translator identity, translation-config hash, opaque input ID, and canonical hash of the exact conversation sent to translation. Records include UTC start/end, measured latency, status, error category, raw response, token/cost metadata, retry-policy version, and whether another attempt was authorized. Exhausted failure returns a recorded item-level provider failure and skips judge execution; an explicit raise policy carries the records and never falls back to the source or partial translation.

The research-owner proposal remains a public Markdown decision package with source links, draft versioned baseline configurations compatible with the existing contracts, separate competence screening, and token-based cost scenarios. All method, model, translator, and retry choices remain proposals pending owner review.

## Non-goals

No study data access, live model/translator integration, API calls, locked selection, final prompt or model approval, dataset freeze, or P4/P5 work. The proposal does not claim faithful reproduction of a published baseline.
