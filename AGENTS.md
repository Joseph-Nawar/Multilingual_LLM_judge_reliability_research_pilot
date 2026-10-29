# Research repository instructions

- Treat `docs/research/` as the authority for the study protocol, dataset, analysis, and integrity requirements. Keep implementation guidance here concise.
- This is an exploratory study of LLM judges. Canonical task states and executable validity rules define reference labels; model judgments never do.
- P1 and P2A authoring feasibility have passed independent research-owner review. P2B-1 is authorized only to correct the same four local development prototypes and prepare their human review. Keep prototypes, prior versions, translations, coverage maps, reviewer packets, blank annotation templates, annotations, and reference records under ignored `.research-data/`; never stage or publish them. Do not author additional scenarios, locked examples, or auxiliary controls.
- Do not begin P2B validation beyond this preparation, P2C, P3, P4, or P5; do not generate the complete study dataset, call models, or spend inference budget without separate explicit authorization. P2B-1 does not authorize human-validation claims, dataset freezing, or model inference.
- Record methodological choices as proposals until reviewed by the research owner. Codex implements and documents decisions; it is not the final authority on scientific correctness.
- Prefer Python's standard library. Keep dependencies small, preserve raw evaluation records in future runners, and document deviations and exclusions.
- Use Python 3.11 or newer and pytest for deterministic checks. Run `python -m pytest` after changes that affect the project foundation.
- Keep canonical reference data and future judge-facing material on separate access paths. Machine checks of span coverage do not establish linguistic equivalence; do not mark Codex-authored language drafts as human validated.
- Before committing, inspect staged paths and verify no `.research-data/`, private, locked, reference, or unapproved study data are tracked.
