# Research repository instructions

- Treat `docs/research/` as the authority for the study protocol, dataset, analysis, and integrity requirements. Keep implementation guidance here concise.
- This is an exploratory study of LLM judges. Canonical task states and executable validity rules define reference labels; model judgments never do.
- Do not generate the study dataset, call models, or spend inference budget unless a later milestone and explicit authorization allow it. P1 is authorized; limit P1 fixtures to synthetic test data and stop before P2 pending an evidence-based review gate.
- Record methodological choices as proposals until reviewed by the research owner. Codex implements and documents decisions; it is not the final authority on scientific correctness.
- Prefer Python's standard library. Keep dependencies small, preserve raw evaluation records in future runners, and document deviations and exclusions.
- Use Python 3.11 or newer and pytest for deterministic checks. Run `python -m pytest` after changes that affect the project foundation.
