# Multi3WOZ External State-Extraction Audit

**Date:** 2026-11-12

**Status:** Offline audit complete; exploratory evidence only. This record does not qualify the model, establish H2, or change the main-study protocol.

## Source and evaluated unit

The audit used the official Multi3WOZ repository at pinned revision [`c65e80fe120704125255de5cf582a51ebaa285cd`](https://github.com/cambridgeltl/multi3woz/tree/c65e80fe120704125255de5cf582a51ebaa285cd) and the 2023 dataset paper ([Hu et al., TACL](https://aclanthology.org/2023.tacl-1.79/)). The selected set contains 100 paired English/Arabic dialogue checkpoints from the released evaluation split: 200 language items in total. The dialogue IDs and role/turn structures align, but the conversations are culturally adapted and are not literal translations.

Each retained request ends at a selected user turn, and its reference state comes from the following system row's metadata. All 200 prefixes and reference boundaries match the pinned source. The official legacy loader serializes each paired system response before its user turn, including the response following the current user. The retained experiment therefore evaluates chronological user-prefix state extraction; it is not an exact reproduction of that loader's input protocol.

The legacy evaluator describes 30 slots across hotel, train, restaurant, attraction, and taxi. The original prompt exposed 37 slots, including seven bus/hospital fields. No gold active fields were outside the official five-domain scope. Arabic output contained 42 raw out-of-scope fields, 41 of which remained after the canonical parser; English output contained none. These outputs are excluded from official-scope rescoring, but their fields were visible to the model.

## Results and scoring checks

The saved original results were reproduced exactly and left unchanged:

- Original 37-slot active slot/value micro F1: 44.7% English, 15.0% Arabic.
- Exact state: 0/100 in each language.
- Strictly parsed outputs: 97/100 in each language.
- English had three invalid outputs. Arabic had one invalid output and two technical HTTP failures.

For a sensitivity comparison, the unchanged reference key and canonical parser outputs were rescored over the official 30-slot inventory. All failures remain in the 100-item denominator and count as incorrect.

| Language | Slot accuracy | Per-item macro F1 | Micro active slot/value F1 | Exact state |
|---|---:|---:|---:|---:|
| English | 76.73% | 44.77% | 44.71% | 0/100 |
| Arabic | 70.87% | 16.14% | 15.49% | 0/100 |

The pinned source normalizer changes punctuation, spelling, and some entity forms. Symmetric source normalization raises micro F1 to 45.67% English and 15.63% Arabic; exact-state accuracy remains zero. One source/reference time value differs only by zero-padding (`9:15`/`09:15`). The legacy converter also emits four literal booking `none` sentinels per language as active values, while the sparse task-state contract treats them as absent. Active slot keys align after this absent-value handling; the references were not changed.

A deterministic sample of 20 bilingual checkpoint pairs, four per official changed-slot domain, was selected by source-ID hash without using model output. All 40 inspected items had at least one state mismatch. Recurrent patterns included omitted earlier constraints, wrong or missing revised values, time-field confusion, and cross-domain or placeholder predictions. This sample is descriptive and is not an independent 40-dialogue estimate.

## Interpretation

The audit shows weak observable state extraction for this Gemma 4 12B procedure, with a large English/Arabic score difference on culturally adapted data. It cannot isolate language as the cause, establish an internal reasoning mechanism, or explain action-validity errors. It does not measure code-switching. It therefore does not establish H2 and should remain a separate exploratory appendix/diagnostic rather than being pooled with action-validity accuracy.

The original external result is usable as evidence about this specific user-prefix extraction procedure, with its prompt-scope and input-serialization differences stated. The official-scope and normalization results are sensitivities, not replacements for the original score. No new inference was run for this audit; API expenditure was $0.

## Main-study status

The two commissioned reviewer slots remain `not_started`; each has 448 missing annotations and the shared tracker has zero received annotations. The only files in the slots are blank templates. Dataset validation and freeze remain outstanding, and no locked inference was run. The next action is to obtain the two completed independent reviewer exports from the existing slots, reconcile them, and complete the already authorized pre-freeze validation.
