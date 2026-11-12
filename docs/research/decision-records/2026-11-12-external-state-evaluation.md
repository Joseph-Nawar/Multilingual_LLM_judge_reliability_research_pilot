# External Dialogue-State Evaluation — Method Record

## Scope

This record documents a narrowly scoped external state-reconstruction evaluation intended to inform, but not resolve, H2. It does not modify the original study dataset, its labels, or the completed H2 development records.

## Versioned extraction contract

`multilingual_judge_pilot.external_state_contract.STATE_EXTRACTION_SCHEMA_V2` separates numerical constraints, temporal constraints, and active permissions. The matching normalizer validates finite decimal values, timezone-aware ISO-8601 temporal bounds, scoped permissions, and duplicate entries. The schema and normalizer reject representations they cannot consistently interpret. Tests use synthetic structures and publicly documented formats.

The original H2 run is preserved as recorded. V2 is a general contract repair and is not a retrospective correction of that run or a means of changing its reference labels.

## External benchmark handling

The Multi3WOZ source release, selected dialogue checkpoints, scorer-only annotations, model responses, and result tables are retained under ignored `.research-data/` paths. Inference inputs and reference annotations use separate files and code paths. Only the preselected conversation prefix and public slot inventory reach the local state-extraction runner.

The benchmark's English and Arabic data are paired by released dialogue/checkpoint structure, not treated as literal translations. Exact slot/value normalization does not perform translation, transliteration, or fuzzy semantic matching. No external benchmark result is used to claim code-switching effects or internal-reasoning faithfulness.

The repository's software license is not treated as a license for the dataset. The archived data are not redistributed by this project.

## Interpretation boundary

External dialogue-state extraction is distinct from action-validity classification. State-extraction performance can show whether a judge can produce an observable state representation under a separately specified task; it cannot, by itself, establish that state reconstruction caused an action-validity error. A causal H2 claim still requires a separate, controlled intervention that does not expose the validity label.

The inspected τ²-Bench-Verified annotations support trajectory-level expected-action and environment outcomes. They do not provide a defensible reference label for every individual action's validity, so no individual-action adaptation or inference is included here.

## Private record

The frozen selection, inference configuration, raw attempts, scorer, and aggregate analysis remain in `.research-data/external-multi3woz-20261112/`. They are not part of the public repository history.
