# P3 Competence-Screen Qualification Preparation

**Date:** 2026-11-06
**Status:** Qualification configuration fixed for the existing private screen; model runs remain gated on independent bilingual quality control and research-owner acceptance.

## Approved configuration

The research owner approved Direct Judging Prompt V2 for this qualification screen. Qwen3.5 9B (`qwen3.5:9b-q4_K_M`, `sha256:ddea16afe16ac5cd402c56ed3e7dcc0d9b250ff355e8913b3957f8ae80e4ed8b`) and Gemma 4 12B (`gemma4:12b-it-qat`, `sha256:38044be4f923e5a55264ed7df4eaac2676651a905f735197c504045140c02bd3`) use the same English prompt, evidence fields, and output contract.

The fixed contract is `binary-verdict-v1`, parsed by `p3-binary-json-verdict-1`. Decoding is temperature 0, seed 17, thinking disabled, 4,096-token context, and a 96-token generation limit. Translation is disabled. A single technical retry is allowed only for the predeclared local connection, timeout, and HTTP 500/502/503/504 categories. Refusals, malformed outputs, and incomplete model outputs are retained and are not retried.

The configuration files are generated from the final runner revision and the private screen input manifest. Each file carries its complete configuration hash. The fixed screening rule remains 20/24 correct per language and at least 10/12 correct in each validity class per language. Invalid or unparseable model outputs count incorrect. Any unresolved technical missingness blocks a pass and is reported separately.

## Screen validation and review gate

The existing private screen package was checked against its recorded source hashes, inventory, chronology, action/tool schemas, and deterministic label derivation. The detailed structural report and reference key remain private. These structural checks do not establish semantic correctness or bilingual naturalness; those checks remain with the independent reviewer.

The authorized offline overlap audit compared the private screen against the authored study package without inference or exposure to model execution paths. It found no replacement-level content overlap. Broad competency topics are shared by design. Detailed match records and metrics remain in the ignored private audit report; the reviewer will independently assess context distinctness and label correctness.

The private standalone reviewer package records one independent judgment per item before revealing the reference labels. It includes no study examples, study identifiers, author provisional complexity annotations, or model outputs. No reviewer response has been created. The runner refuses to start until a complete reviewer export and research-owner acceptance are recorded against the exact input-manifest and configuration hashes.

## Execution and scoring separation

The runner reads only the hash-bound judge-facing screen items. It does not import or read the reference key. It verifies the local Ollama model digest, requires one model loaded at a time, retains raw provider requests and responses, and writes resumable per-item records under `.research-data/`. Completed items are skipped on resume; an interrupted item without a retained result requires manual reconciliation and is never silently repeated.

Reference scoring is a separate command and code module. It reports per-language and per-validity-class accuracy, confusion matrices, invalid/unparseable outputs, technical missingness, and retry counts. A technical failure after the fixed retry is not called a model-produced error, but it prevents qualification. The 48-item screen has not been run.

## Boundaries

This preparation does not qualify either model, authorize study inference, freeze the dataset, or approve the provisional TranslateGemma V3 method for study use. No paid or remote inference is enabled.
