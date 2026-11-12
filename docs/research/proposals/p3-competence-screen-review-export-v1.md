# P3 Competence-Screen Reviewer Export Schema V1

**Status:** implementation contract for the one-time private screen quality check.

The offline reviewer page exports one JSON object. The export is bound to the input-manifest SHA-256 and contains 48 item rows, each with the item ID, canonical judge-input SHA-256, and reviewer responses. It also contains a private proficiency/experience/independence/conflict/prior-exposure declaration and whether independent judgments were locked before reference labels were revealed.

Each item response records:

- naturalness;
- conversation interpretation;
- action/tool semantics;
- independent valid/invalid/unclear judgment;
- numerical, temporal, and permission consistency;
- ambiguity or missing information;
- context distinctness;
- post-reveal reference-label assessment;
- optional issue note.

Allowed assessment values are defined in the private page schema `p3-screen-review-export-1`. Notes remain optional for clean items and are required when a response flags an issue or uncertainty. Draft exports may be incomplete; no unanswered field is treated as approval. Import checks the version, all 48 item IDs, item hashes, manifest hash, response field names, and allowed values. A completed export must include the reviewer declaration, all pre-reveal assessments, and a post-reveal label assessment for every item.

The export contains no model output, other-reviewer response, study example, or study reference data. Reviewer declarations and completed exports remain private under `.research-data/`.
