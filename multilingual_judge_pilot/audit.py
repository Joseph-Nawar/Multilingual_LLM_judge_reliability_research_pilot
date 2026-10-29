"""Auditable validation outcomes; rejected candidates are never silently dropped."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib

from .schema import CanonicalScenario, SCHEMA_VERSION, SchemaValidationError
from .serialization import scenario_from_json


class ValidationDisposition(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ValidationLedgerEntry:
    candidate_id: str
    source_reference: str
    payload_sha256: str
    validator_version: str
    disposition: ValidationDisposition
    error_codes: tuple[str, ...]
    message: str
    recorded_by: str


@dataclass(frozen=True)
class ValidationOutcome:
    scenario: CanonicalScenario | None
    ledger_entry: ValidationLedgerEntry
    raw_candidate_json: str


def audit_scenario_json(
    raw_json: str,
    *,
    candidate_id: str,
    source_reference: str,
    recorded_by: str,
) -> ValidationOutcome:
    """Validate a candidate and always return a ledger row tied to its exact source bytes."""
    for name, value in (("candidate_id", candidate_id), ("source_reference", source_reference), ("recorded_by", recorded_by)):
        if not isinstance(value, str) or not value.strip():
            raise SchemaValidationError(f"{name} must be a non-empty string")
    if not isinstance(raw_json, str):
        raise SchemaValidationError("raw candidate must be text")
    payload_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    try:
        scenario = scenario_from_json(raw_json)
    except SchemaValidationError as error:
        entry = ValidationLedgerEntry(
            candidate_id=candidate_id,
            source_reference=source_reference,
            payload_sha256=payload_hash,
            validator_version=SCHEMA_VERSION,
            disposition=ValidationDisposition.REJECTED,
            error_codes=(type(error).__name__,),
            message=str(error),
            recorded_by=recorded_by,
        )
        return ValidationOutcome(None, entry, raw_json)
    entry = ValidationLedgerEntry(
        candidate_id=candidate_id,
        source_reference=source_reference,
        payload_sha256=payload_hash,
        validator_version=SCHEMA_VERSION,
        disposition=ValidationDisposition.ACCEPTED,
        error_codes=(),
        message="canonical scenario passed deterministic schema and pair validation",
        recorded_by=recorded_by,
    )
    return ValidationOutcome(scenario, entry, raw_json)
