# P3 Exploratory Competence-Screen Pilot

**Date:** 2026-11-11
**Status:** owner-authorized, single exploratory local pilot; not formal dataset validation or model qualification.

The research owner authorized one run of the existing 48-item English/MSA competence screen using the fixed Direct Prompt V2 configurations for Qwen3.5 9B and Gemma 4 12B. The run uses local Ollama only, temperature 0, seed 17, thinking disabled, 4,096-token context, a 96-token output limit, and the fixed technical retry policy. It uses no translation or structured-judging baseline.

The exploratory entry point is separate from the formal qualification runner. It requires the submitted 48-item pre-reveal reviewer assessment, preserves its actual incomplete status, and records each run as `PILOT_EXPLORATORY_UNVALIDATED`. It does not create reviewer answers or formal acceptance. The existing formal runner continues to require independent bilingual QC completion and explicit research-owner acceptance.

Judge requests contain only the allowlisted screen conversation, proposed action, public tool contract, fixed prompt, and binary response contract. The exploratory inference module does not import the screen reference key. Reference scoring occurs afterward through a separate function and preserves the reference labels as authored. All review exports, raw outputs, run manifests, scoring reports, and reconciliation records stay under ignored `.research-data/` paths.

The result is descriptive evidence for deciding whether further zero-cost research is worthwhile. It does not validate the full study, directly test code-switching, qualify either model, or authorize locked-study inference. Prompt, model, threshold, and label changes are outside this pilot.
