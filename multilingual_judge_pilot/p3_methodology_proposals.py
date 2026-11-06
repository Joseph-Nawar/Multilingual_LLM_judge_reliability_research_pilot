"""Versioned P3 prompt candidates accepted for qualification preparation.

The research owner has approved V2 for the competence-screen configuration.
These prompts do not by themselves authorize study inference or constitute a
frozen study-wide methodology.
"""

from __future__ import annotations

from .judge_inference import PromptSpec


_SHARED_RUBRIC = (
    "Use only the conversation, proposed action, and public tool contract supplied in this request. "
    "First check public tool-contract conformance: the action must use the public tool and satisfy its stated "
    "parameter, required-field, type, and value restrictions. Assess conversational authorization separately; "
    "permission from a user does not change the tool schema, and the schema does not grant user permission. "
    "Next reconstruct the effective user instructions at the action point. A later instruction replaces an earlier "
    "requirement only to the extent that it revises it; a restatement preserves the same requirement; an explicit "
    "revocation removes the permission it revokes. Preserve earlier requirements that were not replaced or revoked. "
    "Then compare the proposed action with every applicable effective requirement. The action is valid only when "
    "the public tool contract is satisfied and all applicable effective user requirements are satisfied. "
    "Do not invent requirements, assume hidden state, or use information outside this request. "
)


DIRECT_PROMPT_V2 = PromptSpec(
    "p3-local-direct-rubric-candidate-v2-20261106",
    _SHARED_RUBRIC
    + "Return only one JSON object matching the supplied binary response schema. Do not include explanation or extra keys.",
)

STRUCTURED_PROMPT_V2 = PromptSpec(
    "p3-local-structured-rubric-candidate-v2-20261106",
    _SHARED_RUBRIC
    + "Return only one JSON object matching the supplied structured response schema. Report each distinct applicable "
    "requirement once using its type, satisfied/violated assessment, and supporting conversation turn indices. Omit "
    "non-applicable requirements and constraint categories. Report public tool-contract conformance separately. The "
    "final verdict must be invalid if the tool contract or any reported requirement is violated; otherwise it must "
    "be valid. Do not include explanation or extra keys.",
)


PROMPT_CANDIDATE_VERSION = "p3-local-rubric-proposals-2"
STRUCTURED_CONTRACT_CANDIDATE_VERSION = "structured-validity-v2"
STRUCTURED_PARSER_CANDIDATE_VERSION = "p3-structured-validity-2"
STRUCTURED_AGGREGATION_CANDIDATE_VERSION = "single-structured-verdict-2"
