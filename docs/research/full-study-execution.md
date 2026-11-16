# P2C full-study execution CLI

`scripts/p2c_full_study.py` connects the accepted reviewer-ingestion, pre-freeze, frozen-input, local inference, and scoring components. Run it from the repository root. Private inputs and outputs default to ignored `.research-data/p2c-full/` paths.

The CLI never fills reviewer fields. Each reviewer export must be a complete 448-row JSONL file using the IDs, hashes, slot identity, and annotation contract from that reviewer’s existing package. Preserve the export source bytes; importing a revised export requires a short revision reason. Adjudication JSONL is imported separately and must bind each disagreement to the same variant and canonical-scenario hashes.

The standalone offline reviewer workspaces and concise handoff instructions are documented in [P2C bilingual reviewer workspaces](p2c-review-studio.md). The generated reviewer pages remain private under `.research-data/`.

## Commands

```sh
./.venv/bin/python scripts/p2c_full_study.py status
./.venv/bin/python scripts/p2c_full_study.py ingest reviewer_slot_1 /path/to/reviewer-1.jsonl
./.venv/bin/python scripts/p2c_full_study.py ingest reviewer_slot_2 /path/to/reviewer-2.jsonl
./.venv/bin/python scripts/p2c_full_study.py disagreements
./.venv/bin/python scripts/p2c_full_study.py ingest-adjudications /path/to/adjudications.jsonl
./.venv/bin/python scripts/p2c_full_study.py validate-adjudications
./.venv/bin/python scripts/p2c_full_study.py verify
./.venv/bin/python scripts/p2c_full_study.py freeze
```

`verify` is read-only. `freeze` reruns the source-package, annotation, adjudication, corpus, language-coverage, and deterministic-oracle checks and fails closed unless both independent reviewer submissions are complete and all mandatory content issues and disagreements are resolved. The generated freeze separates opaque inference JSONL from reference verdicts and analysis metadata. It binds the accepted local model digests, prompts, parser, retry settings, run configurations, source hashes, and randomized item order. It also writes a separate `diagnostics/state-access/` bundle containing the active-state projection, both label-free arm requests for each locked item, and a plan binding the diagnostic prompt, response contract, model/configuration, randomization, and analysis definition. Every added file is hashed in the private freeze manifest. These generated artifacts remain under ignored `.research-data/`.

If adjudication requires a content revision, the freeze remains blocked. Preserve the imported reviewer and adjudication archives, apply the authorized change through the existing private P2C authoring source, and run its `build` and `validate` commands. The existing revision ledger records changed artifact versions and hashes, and the builder refreshes the review package hashes. Both reviewers must then submit complete exports against the refreshed 448-item inventory; import them with `ingest ... --revision-reason ...`, and ingest the adjudications for that current review version. The old exports and adjudications remain in the immutable private archive. The freeze gate does not treat an old adjudication as validation of revised content.

Only after a valid freeze exists, run the translation stage once and each fixed baseline:

```sh
./.venv/bin/python scripts/p2c_full_study.py translate --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
./.venv/bin/python scripts/p2c_full_study.py run direct --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
./.venv/bin/python scripts/p2c_full_study.py run translation_first --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
./.venv/bin/python scripts/p2c_full_study.py run structured --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
./.venv/bin/python scripts/p2c_full_study.py analyze --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
```

The separate state-access diagnostic is run and analyzed only after the same human-review, issue-resolution, verification, and freeze gates:

```sh
./.venv/bin/python scripts/paper2_state_access.py run --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
./.venv/bin/python scripts/paper2_state_access.py analyze --freeze-root .research-data/p2c-full/freezes/FREEZE_ID
```

It adds 768 local calls: two paired conditions for each of the 288 primary and 96 auxiliary locked items. The run command uses the exact development-tested shared prompt, schema/parser, local Gemma model digest, decoding options, and one-attempt/no-retry policy frozen in the diagnostic plan. Resume reuses terminal attempts and never resends an ambiguous interrupted `started` call. Raw requests, responses, and failures stay in the diagnostic result path. The analysis command reads the separately hashed reference key only after inference, writes per-item scored detail in a distinct reference-analysis path, and writes a deterministic aggregate report with planned-denominator, parsed-pair, language-condition, transition-family, uncertainty, and failure-accounting results. The primary-versus-auxiliary state-access contrast is exploratory and remains separate from the three baseline comparisons.

Inference uses only the frozen projection and the loopback Ollama adapters. Translation artifacts and every attempt are hash-bound; failures are retained and exclude only the corresponding translation-first judge call. Each baseline keeps immutable per-item raw requests, raw responses, parser outcomes, timings, token usage, and a result-hash manifest. An interrupted item with an in-progress marker but no saved result is ambiguous and will not be resent automatically; inspect the retained local record before deciding how to proceed.

The ordinary analysis command reads the separate reference key only after inference. It reports all four language conditions, class recall, confusion matrices, opposite-history consistency, paired baseline contrasts, scenario-clustered bootstrap intervals, domain/family breakdowns, auxiliary controls, and parser/translation failures. The state-access analysis has its own report and result path. Unparsed and technically missing outputs remain in the complete planned-item denominator. Neither analysis edits raw run records.

All commands that create private records enforce `.research-data/` output paths. The documented runner commands are operator instructions only; they do not mean the freeze or model runs have occurred.
