# P2C Full-Study Pipeline Design

## Intent

Add a private-data-aware command layer that turns the existing P2C reviewer packages and approved local inference components into a complete, auditable workflow. It must be usable when the two real reviewer exports arrive, while keeping locked inference impossible until human validation and freeze conditions pass.

## Goals and limits

- Reuse canonical schemas, annotation/adjudication validators, oracle, judge-facing projection, baseline executors, local Ollama adapters, translation artifacts, and scoring primitives.
- Preserve reviewer files immutably and reject incomplete, duplicate, stale, malformed, or wrong-slot annotations.
- Freeze exactly 288 locked primary and 96 locked control inputs, with development inputs kept separately.
- Keep labels, canonical state, pair identity, and analysis metadata out of the inference path.
- Execute only Gemma 4 12B locally for the three approved baselines; prepare TranslateGemma outputs in a separate stage.
- Retain raw attempts and allow safe resumption; ambiguous interrupted calls fail closed.
- Score immutable outputs with the approved scenario-clustered analysis and report technical/parser/translation failures separately.
- Test only independent synthetic fixtures and mocked providers. Do not run locked inference or edit the authored dataset.

## Approaches considered

1. **Thin integration modules over the current library (selected).** Adds P2C-specific ingestion, freeze, run, and analysis functions while calling existing validators, oracle, request projection, baseline, Ollama, and parser APIs. This keeps contracts consistent and minimizes duplicate research logic.
2. **One all-in-one study script.** Fewer files, but review/reference loading, inference, and scoring would share one module and make accidental reference leakage harder to audit.
3. **Replace the existing components with a new runner framework.** Rejected because it duplicates validated infrastructure and increases the risk of schema and scoring drift.

## Proposed structure

- `multilingual_judge_pilot/p2c_review.py`: private package inventory, strict JSONL ingestion, immutable submission records, reviewer agreement/disagreement summaries, and adjudication validation.
- `multilingual_judge_pilot/p2c_freeze.py`: full corpus validation, deterministic oracle rechecks, opaque ID assignment, randomized order, and separate reference/inference artifacts.
- `multilingual_judge_pilot/p2c_inference.py`: reference-free frozen-input loading, exact run configuration, translation preparation, baseline execution, raw attempt persistence, and safe resume.
- `multilingual_judge_pilot/p2c_analysis.py`: separate reference-side scoring, descriptive outcomes, paired contrasts, and scenario-clustered intervals.
- `scripts/p2c_full_study.py`: concise `status`, `ingest`, `disagreements`, `validate-adjudications`, `verify`, `freeze`, `translate`, `run`, and `analyze` commands.
- `tests/test_p2c_full_study.py`: synthetic-only tests for the complete gate, storage, isolation, retry/resume, and scoring path.
- `docs/research/full-study-execution.md`: operator commands, private path layout, gates, and recovery behavior.

## Operational choices

- The default dataset root is `.research-data/p2c-full`; execution state is in a separate ignored `.research-data/p2c-full-study` tree.
- `ingest` binds each import to the exact reviewer slot, source filename, byte hash, import time, and preserved raw bytes. A changed submission requires an explicit revision reason and never overwrites the prior file.
- Annotation hashes are checked against the current typed scenario and language variant. Both slots must independently provide exactly 448 valid rows. The current adjudication contract is used; unresolved, excluded, revised-without-fresh-review, or missing adjudications block freeze.
- Freeze uses a 256-bit recorded seed and the evaluation-plan SHA-256 ordering algorithm. Opaque UUIDs and analysis/reference maps are private reference-side artifacts. Judge inputs contain only the established `JudgeFacingInput` allowlist and are stored separately.
- Freeze requires the existing 60-scenario private dataset validator and recomputation of the deterministic oracle. Any negative semantic/language checklist, non-empty issue code, or non-clean linguistic/semantic category blocks freeze pending correction and fresh review. `unclear` dependence assessments are preserved as valid human judgments; they are never coerced.
- Translation preparation is a distinct TranslateGemma V3/V4 stage. Successful translations are stored as source/config hash-bound artifacts; translation failures remain recorded and block only the affected translation-first judge call. The judge stage never has access to reference keys.
- Each run has a frozen config hash, item hash, execution ID, exclusive lock, and atomic result/state records. Completed results are skipped; an in-progress item without a result is treated as ambiguous and requires manual reconciliation.
- Analysis reads stored result records and the separate private reference key. It never edits requests or outputs. Primary uncertainty resamples canonical scenario clusters with all paired derivatives intact; controls are summarized separately.

## Acceptance

The CLI must fail closed on missing reviewer exports, stale hashes, incomplete or duplicate rows, unresolved required adjudications, changed frozen inputs, model digest mismatch, missing translation artifacts, or ambiguous run state. Synthetic tests must demonstrate the full path with mock responses only. No study model call, paid/remote call, dataset mutation, or public private-data artifact is allowed in this milestone.
