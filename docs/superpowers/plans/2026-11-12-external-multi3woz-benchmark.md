# External Multi3WOZ H2 Benchmark — Execution Plan

## Boundaries

- Use only the official Multi3WOZ English and Arabic evaluation split and a frozen subset of at most 100 aligned dialogue checkpoints.
- Keep downloaded data, selected checkpoints, gold states, prompts bound to private records, raw model outputs, and scores under ignored `.research-data/` paths.
- Use the locally installed Gemma 4 12B digest only. No paid or remote inference, no locked study examples, no tuning against evaluation results.
- Preserve the concluded H2 development result and its limitations; version any extraction contract repair separately.
- Do not assign τ²-Bench action-validity labels without an existing defensible per-action reference.

## Steps

1. Pin and download the official source revision/data archive; verify hashes, license statements, annotation format, official test/evaluation split, and English–Arabic alignment keys.
2. Audit eligible checkpoints, define a deterministic selection procedure, freeze selected judge inputs and scorer-only references in a hash-bound private manifest before inference.
3. Add a versioned H2 state-extraction schema/normalizer pair with regression fixtures for numeric, temporal, and permission representations; retain the original H2 result unchanged.
4. Validate source annotations and normalization on public benchmark examples; verify local Gemma digest, request isolation, and run configuration.
5. Run the frozen subset sequentially through local Ollama; preserve raw outputs, parser outcomes, timings, and hashes; score separately against gold states.
6. Analyze per-language state metrics, update-related errors, aligned EN/AR comparisons, and normalization/format failures; assess τ²-Bench without inventing action labels.
7. Run targeted tests and full repository tests; inspect staged paths; commit and push public-safe code/documentation only.

## Completion evidence

- Source commit and archive checksum, source license/annotation citation, split/checkpoint inventory, and selection-manifest hash.
- Versioned schema/normalizer tests and verified inference/scorer separation.
- Private raw inference and score package with checksums and no reference leakage into requests.
- Clearly separated state-extraction findings, H2 interpretation, and τ²-Bench feasibility conclusion.
