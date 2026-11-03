"""Separate, opt-in request shape for an oracle-state diagnostic.

Ordinary baseline plans and the ordinary executor do not accept this type.
No diagnostic provider or live execution is implemented in this slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Mapping

from .judge_inference import (
    ContractError,
    JudgeFacingInput,
    PromptSpec,
    canonical_json,
)


_LABEL_FRAGMENTS = ("oraclelabel", "oracleverdict", "goldlabel", "referencelabel", "referenceverdict", "validityverdict")
_STATE_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "active_constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "constraint_type": {
                        "type": "string",
                        "enum": ["numerical", "temporal", "permission", "other"],
                    },
                    "constraint_summary": {"type": "string"},
                    "source_turn_indices": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                },
                "required": ["constraint_type", "constraint_summary", "source_turn_indices"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["active_constraints"],
    "additionalProperties": False,
}


def _reject_labels(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = "".join(character for character in str(key).casefold() if character.isalnum())
            if any(fragment in normalized for fragment in _LABEL_FRAGMENTS):
                raise ContractError(f"reference label is not allowed in oracle diagnostic state: {key}")
            _reject_labels(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            _reject_labels(child)


@dataclass(frozen=True)
class OracleStateDiagnosticRequest:
    diagnostic_id: str
    item_id: str
    prompt_version: str
    instruction: str
    conversation: tuple[dict[str, object], ...]
    action: Mapping[str, object]
    public_tool_schema: Mapping[str, object]
    effective_state_json: str = field(repr=False)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "p3-oracle-state-diagnostic-1",
            "diagnostic_id": self.diagnostic_id,
            "item_id": self.item_id,
            "prompt_version": self.prompt_version,
            "instruction": self.instruction,
            "conversation": list(self.conversation),
            "action": self.action,
            "public_tool_schema": self.public_tool_schema,
            "effective_state": json.loads(self.effective_state_json),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_record())


@dataclass(frozen=True)
class StateExtractionDiagnosticRequest:
    """Model-observable state extraction request; contains no reference state."""

    diagnostic_id: str
    item_id: str
    prompt_version: str
    instruction: str
    conversation: tuple[dict[str, object], ...]
    action: Mapping[str, object]
    public_tool_schema: Mapping[str, object]

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "p3-state-extraction-diagnostic-1",
            "diagnostic_id": self.diagnostic_id,
            "item_id": self.item_id,
            "prompt_version": self.prompt_version,
            "instruction": self.instruction,
            "conversation": list(self.conversation),
            "action": self.action,
            "public_tool_schema": self.public_tool_schema,
            "response_schema": json.loads(canonical_json(_STATE_EXTRACTION_SCHEMA)),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_record())


def build_state_extraction_diagnostic(
    item: JudgeFacingInput,
    *,
    prompt: PromptSpec,
) -> StateExtractionDiagnosticRequest:
    """Build a diagnostic that asks the model to extract, not receive, active state."""
    evidence = item.evidence_record()
    return StateExtractionDiagnosticRequest(
        diagnostic_id=f"state-extraction-{item.item_id}-{prompt.version}",
        item_id=item.item_id,
        prompt_version=prompt.version,
        instruction=prompt.instruction,
        conversation=tuple(evidence["conversation"]),
        action=evidence["action"],
        public_tool_schema=evidence["public_tool_schema"],
    )


def build_oracle_state_diagnostic(
    item: JudgeFacingInput,
    *,
    effective_state: Mapping[str, object],
    prompt: PromptSpec,
) -> OracleStateDiagnosticRequest:
    """Build an explicitly non-ordinary diagnostic request without reference labels."""
    if not isinstance(effective_state, Mapping):
        raise ContractError("diagnostic effective_state must be a structured object")
    _reject_labels(effective_state)
    evidence = item.evidence_record()
    return OracleStateDiagnosticRequest(
        diagnostic_id=f"diagnostic-{item.item_id}-{prompt.version}",
        item_id=item.item_id,
        prompt_version=prompt.version,
        instruction=prompt.instruction,
        conversation=tuple(evidence["conversation"]),
        action=evidence["action"],
        public_tool_schema=evidence["public_tool_schema"],
        effective_state_json=canonical_json(effective_state),
    )
