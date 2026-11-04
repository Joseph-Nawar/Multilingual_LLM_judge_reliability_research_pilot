# P3 Local Inference Compatibility — Progress Report

**Status: adapter and synthetic-test preparation complete; model compatibility smoke not run.** This is a progress report for the research-owner gate, not model qualification or authorization for study inference. No study examples, locked labels, or private review materials were accessed.

## Environment verified

| Component | Observed value |
|---|---|
| macOS | 26.4 |
| Hardware | MacBook Air, identifier `Mac17,3`, Apple M5; 10 CPU cores (4 super, 6 efficiency), 8 GPU cores, Metal 4 |
| Unified memory | 16 GB |
| Ollama CLI and local API | `0.40.14` |
| Local listener | `127.0.0.1:11434`; `OLLAMA_HOST` unset; no proxy or remote endpoint used for inference |
| Free disk on repository volume | 105 GB |
| Baseline system memory | 70% free; swap 0 MB; no model loaded |
| Previously installed model | `qwen3:4b-instruct-2507-q4_K_M` (2.5 GB); not used for inference or as a candidate |

Apple identifies this MacBook Air generation as fanless. That makes sustained throughput and thermal checks important; model-weight size alone is not a viability test.

## Approved artifact downloads

Only the approved tags were requested from Ollama: `qwen3.5:9b-q4_K_M`, `gemma4:12b-it-qat`, and `translategemma:4b-it-q4_K_M`. At the last local check (2026-11-04, about 14:37 local time), none had completed, so none was installed, loaded, or run. Pull progress was approximately 82 MB / 921 MB for a Qwen layer (29 KB/s, estimated 8 h for that layer), 17 MB / 7.0 GB for a Gemma layer (3.9 KB/s, estimated more than 99 h), and 24 MB / 3.3 GB for a TranslateGemma layer (389 KB/s, estimated 2 h 20 min). Estimates are transfer-tool estimates for the current layer, not full-model download or runtime estimates. I stopped all three transfers after confirming the stalled progress. Partial Ollama cache blobs remain outside the repository and are resumable; the full local digest, exact size, template, and metadata-reported context/thinking support remain unverified until installation.

The Ollama library currently lists these tag-level reference values:

| Approved tag | Listed size | Listed context | Registry digest prefix |
|---|---:|---:|---|
| `qwen3.5:9b-q4_K_M` | 6.6 GB | 256K | `56671c2ab938` |
| `gemma4:12b-it-qat` | 7.2 GB | 256K | `38044be4f923` |
| `translategemma:4b-it-q4_K_M` | 3.3 GB | 128K | `c49d986b0764` |

These library values are not substitutes for the exact local digests and `ollama show` metadata that the smoke runner will record after the pulls complete.

## Implementation prepared

- `multilingual_judge_pilot/local_ollama.py` implements judge and translator adapters on the existing provider-independent interfaces. The endpoint validator accepts only literal HTTP loopback `127.0.0.1`, disables proxy use, rejects redirects, and allows only the needed local Ollama API paths. The model allowlist contains exactly the three approved tags; there is no remote fallback.
- The judge adapter sends the original conversation, action, and public tool contract, requests the versioned JSON Schema, and preserves raw output, refusal state, incomplete termination, token counts, prompt/generation/load/total timings, and zero local cost. The `think` control is sent only when `/api/show` reports the model capability.
- The translator receives transcript-only input, translates Arabic turns separately, and preserves speaker roles, chronology, and unchanged English turns. Deterministic literal shielding protects numbers, dates, currency codes, and technical identifiers. Refusals, incomplete outputs, and failed translations remain explicit records with raw responses and error categories.
- `translation_artifacts.py` provides hash-bound translation artifacts so the same translation can be reused across judge backbones. Reuse validates the source transcript and translation configuration; each judge run retains its own execution ID.
- `scripts/p3_local_compatibility_smoke.py` is bounded to four independently written synthetic cases in all four language conditions (16 items). When the approved models are installed it will run direct, translation-first, and single-call structured judging, share translation artifacts across the two judges, issue one 8K-context probe per judge, unload models between roles, and checkpoint synthetic records under ignored `.research-data/p3-local-smoke/` after each attempt.
- Resource capture includes runner RSS (a process-level lower-bound, not total unified-memory use), periodic system memory-free percentage, swap, thermal status, and `ollama ps` CPU/GPU placement. Per-baseline early/late token-rate summaries are recorded to help detect sustained slowdown. Measurements remain pending because no model call has occurred.

The four-condition synthetic fixtures exercise explicit permission revocation (with the prior grant), an amount revision, a relative-time revision, and a revision that depends on earlier context. They are not a competence screen or benchmark. Their Modern Standard Arabic wording is draft synthetic text, not human-validated language material. Synthetic expected properties are stored outside judge-facing requests and used only for diagnostic summaries.

## Verification completed so far

- `.venv/bin/python -m pytest -q`: **173 passed**.
- Targeted local-adapter and translation-artifact tests: **15 passed**.
- Python compilation and `git diff --check`: passed before this report was written.
- Automated checks cover loopback-only endpoint validation, strict request allowlists and reference-field rejection, fixed schema use, metadata-gated thinking controls, raw output/timing retention, malformed/missing/refused response distinction, retry attempt IDs, translation failure records, literal protection, translation artifact round-trip/reuse across judges, and four-language fixture mappings.
- No live model inference, paid call, study-data read, or change to study data has occurred.

## Workload and feasibility still pending

For two judge candidates, the approved ordinary workload is **2,304 judge calls**: 384 items × three ordinary baselines × two models. Translation-first covers 288 Arabic-bearing items. Because the locked conversations were not opened, the number of Arabic turns per item is unknown; the translation call count must be calculated after independent validation using the actual eligible-turn count, not assumed from these synthetic fixtures. A future 48-item-per-model competence screen would add 96 calls. A paired H2 state-extraction/oracle-state diagnostic would add up to 1,536 calls (two conditions × 384 items × two models). The optional three-call decomposition would add up to 2,304 calls if run for both models. These are call-count calculations only; no runtime projection is defensible until local throughput is measured.

After a successful smoke, use resumable batches of 32 items per model and baseline, checkpointing every item and unloading the model between judge backbones. On this fanless machine, pause between batches if memory pressure, swap use, or sustained throughput indicate thermal or memory stress. Keep translations in the shared hash-bound artifact store so a completed translation is not repeated in a later judge batch.

The following are specifically **not yet established**: local installation compatibility, full model digests and templates, Ollama JSON Schema behavior with each model, metadata-reported thinking support, 4K/8K model stability, GPU/CPU split, peak system memory and swap under load, actual tokens/s and latency, output validity, translation fidelity, meaning-changing translation errors, full-study runtime, and whether either judge candidate is practical on this machine. The model tags remain provisional and cannot be qualified or compared from the results of this preparation alone.

## Official references

- Ollama [Qwen 3.5 tags](https://ollama.com/library/qwen3.5/tags), [Gemma 4 tags](https://ollama.com/library/gemma4/tags), and [TranslateGemma tags](https://ollama.com/library/translategemma/tags).
- Ollama [chat API](https://docs.ollama.com/api/chat), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), and [TranslateGemma prompt guide](https://ollama.com/library/translategemma).
- Apple [MacBook Air technical specifications](https://support.apple.com/en-us/126320) and [M5 MacBook Air announcement](https://www.apple.com/newsroom/2026/03/apple-introduces-the-new-macbook-air-with-m5/).
