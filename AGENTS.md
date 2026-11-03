# Research repository instructions

- Treat `docs/research/` as the authority for the study protocol, dataset, analysis, and integrity requirements. Keep implementation guidance here concise.
- This is an exploratory study of LLM judges. Canonical task states and executable validity rules define reference labels; model judgments never do.
- P1 and P2A authoring feasibility have passed independent research-owner review. The four-scenario P2B feasibility pilot is concluded with documented limitations; no additional pilot review or adjudication is authorized. P2C authoring is authorized only for the eight remaining development primary scenarios. Keep all prototypes, new development scenarios, translations, coverage maps, annotations, prior versions, reviewer records, and reference data under ignored `.research-data/`; never stage or publish them.
- Do not author locked primary scenarios or auxiliary controls, freeze the dataset, or begin P3, P4, or P5. Do not call models or spend inference budget without separate explicit authorization. Structural/oracle checks do not establish bilingual semantic validation; pilot dependence disagreements remain unresolved and must not be presented as adjudicated or independently validated labels.
- Record methodological choices as proposals until reviewed by the research owner. Codex implements and documents decisions; it is not the final authority on scientific correctness.
- Prefer Python's standard library. Keep dependencies small, preserve raw evaluation records in future runners, and document deviations and exclusions.
- Use Python 3.11 or newer and pytest for deterministic checks. Run `python -m pytest` after changes that affect the project foundation.
- Keep canonical reference data and future judge-facing material on separate access paths. Machine checks of span coverage do not establish linguistic equivalence; do not mark Codex-authored language drafts as human validated.
- Before committing, inspect staged paths and verify no `.research-data/`, private, locked, reference, or unapproved study data are tracked.
