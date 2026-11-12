"""Deterministic, hash-bound artifacts for reusing one translation across judges."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping

from .judge_inference import ContractError, ConversationTurn, RunConfig, canonical_json
from .judge_baselines import BaselinePlan, TranslationAttemptRecord, TranslationRecord


TRANSLATION_ARTIFACT_VERSION = "p3-translation-artifact-1"


def conversation_sha256(item) -> str:
    turns = [turn.to_record() for turn in item.conversation]
    return hashlib.sha256(canonical_json(turns).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TranslationArtifact:
    input_id: str
    source_conversation_sha256: str
    translation_config_hash: str
    translated_turns: tuple[ConversationTurn, ...]
    translation_records: tuple[TranslationRecord, ...]
    translation_attempts: tuple[TranslationAttemptRecord, ...]

    def __post_init__(self) -> None:
        if not self.input_id.strip():
            raise ContractError("translation artifact input ID must be non-empty")
        for name, value in (
            ("source_conversation_sha256", self.source_conversation_sha256),
            ("translation_config_hash", self.translation_config_hash),
        ):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ContractError(f"translation artifact {name} must be a SHA-256 hash")
        if not self.translated_turns or any(not isinstance(turn, ConversationTurn) for turn in self.translated_turns):
            raise ContractError("translation artifact requires a translated conversation")
        if not self.translation_records or not self.translation_attempts:
            raise ContractError("translation artifact requires successful translation provenance")
        if any(record.input_id != self.input_id for record in self.translation_records):
            raise ContractError("translation artifact records must refer to its input ID")
        if any(record.translation_config_hash != self.translation_config_hash for record in self.translation_records):
            raise ContractError("translation artifact records must refer to its translation configuration")
        if any(
            record.source_conversation_sha256 != self.source_conversation_sha256
            or record.input_sha256 != self.source_conversation_sha256
            for record in self.translation_records
        ):
            raise ContractError("translation artifact source hash does not match its provenance")
        if any(
            attempt.input_id != self.input_id
            or attempt.input_sha256 != self.source_conversation_sha256
            or attempt.translation_config_hash != self.translation_config_hash
            for attempt in self.translation_attempts
        ):
            raise ContractError("translation artifact attempts do not match its input and configuration hashes")
        if not any(attempt.status == "success" for attempt in self.translation_attempts):
            raise ContractError("failed translation attempts cannot form a reusable artifact")
        translated_hash = hashlib.sha256(
            canonical_json([turn.to_record() for turn in self.translated_turns]).encode("utf-8")
        ).hexdigest()
        if any(record.translated_conversation_sha256 != translated_hash for record in self.translation_records):
            raise ContractError("translation artifact conversation hash does not match its provenance")

    @classmethod
    def from_plan(cls, item, config: RunConfig, plan: BaselinePlan) -> "TranslationArtifact":
        if config.translation is None or plan.baseline != "translation_first":
            raise ContractError("translation artifact requires a successful translation-first plan")
        if plan.item_id != item.item_id or len(plan.requests) != 1 or not plan.translation_records or not plan.translation_attempts:
            raise ContractError("translation plan is incomplete or belongs to another input")
        if plan.preprocessing_result is not None:
            raise ContractError("failed translation plans cannot be saved as reusable artifacts")
        return cls(
            input_id=item.item_id,
            source_conversation_sha256=conversation_sha256(item),
            translation_config_hash=config.translation.config_hash,
            translated_turns=plan.requests[0].conversation,
            translation_records=plan.translation_records,
            translation_attempts=plan.translation_attempts,
        )

    def validate_for(self, item, config: RunConfig) -> None:
        if config.translation is None:
            raise ContractError("translation artifact requires a translation configuration")
        if item.item_id != self.input_id:
            raise ContractError("translation artifact input identifier does not match")
        if conversation_sha256(item) != self.source_conversation_sha256:
            raise ContractError("translation artifact input hash does not match the source conversation")
        if config.translation.config_hash != self.translation_config_hash:
            raise ContractError("translation artifact translation configuration does not match")
        if len(item.conversation) != len(self.translated_turns):
            raise ContractError("translation artifact must preserve turn count")
        for source, target in zip(item.conversation, self.translated_turns, strict=True):
            if (source.turn_index, source.speaker) != (target.turn_index, target.speaker):
                raise ContractError("translation artifact must preserve roles and chronology")
            if target.language != config.translation.pivot_language:
                raise ContractError("translation artifact language does not match configured pivot")

    def _body_record(self) -> dict[str, object]:
        return {
            "artifact_version": TRANSLATION_ARTIFACT_VERSION,
            "input_id": self.input_id,
            "source_conversation_sha256": self.source_conversation_sha256,
            "translation_config_hash": self.translation_config_hash,
            "translated_conversation_sha256": hashlib.sha256(
                canonical_json([turn.to_record() for turn in self.translated_turns]).encode("utf-8")
            ).hexdigest(),
            "translated_turns": [turn.to_record() for turn in self.translated_turns],
            "translation_records": [record.to_record() for record in self.translation_records],
            "translation_attempts": [attempt.to_record() for attempt in self.translation_attempts],
        }

    @property
    def artifact_sha256(self) -> str:
        return hashlib.sha256(canonical_json(self._body_record()).encode("utf-8")).hexdigest()

    def to_record(self) -> dict[str, object]:
        return {**self._body_record(), "artifact_sha256": self.artifact_sha256}

    def to_json(self) -> str:
        return canonical_json(self.to_record())

    @classmethod
    def from_json(cls, serialized: str) -> "TranslationArtifact":
        try:
            payload = json.loads(serialized)
        except (json.JSONDecodeError, TypeError):
            raise ContractError("translation artifact must be valid JSON") from None
        expected = {
            "artifact_version", "input_id", "source_conversation_sha256", "translation_config_hash",
            "translated_conversation_sha256", "translated_turns", "translation_records", "translation_attempts", "artifact_sha256",
        }
        if not isinstance(payload, dict) or set(payload) != expected or payload["artifact_version"] != TRANSLATION_ARTIFACT_VERSION:
            raise ContractError("translation artifact schema or version is invalid")
        expected_hash = payload.get("artifact_sha256")
        body = {key: value for key, value in payload.items() if key != "artifact_sha256"}
        actual_hash = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
        if expected_hash != actual_hash:
            raise ContractError("translation artifact hash does not match its contents")
        try:
            turns = tuple(ConversationTurn(**row) for row in payload["translated_turns"])
            records = tuple(_translation_record_from_record(row) for row in payload["translation_records"])
            attempts = tuple(_translation_attempt_from_record(row) for row in payload["translation_attempts"])
            artifact = cls(
                input_id=payload["input_id"],
                source_conversation_sha256=payload["source_conversation_sha256"],
                translation_config_hash=payload["translation_config_hash"],
                translated_turns=turns,
                translation_records=records,
                translation_attempts=attempts,
            )
        except (TypeError, KeyError, ValueError) as exc:
            raise ContractError("translation artifact contains invalid records") from exc
        if payload["translated_conversation_sha256"] != artifact._body_record()["translated_conversation_sha256"]:
            raise ContractError("translation artifact translated-conversation hash is invalid")
        return artifact


def _translation_record_from_record(row: Mapping[str, object]) -> TranslationRecord:
    keys = (
        "execution_id", "translation_config_hash", "input_id", "translator_provider", "translator_model",
        "translator_version", "prompt_version", "target_language", "source_conversation_sha256", "input_sha256",
        "translated_conversation_sha256", "raw_output", "latency_ms", "prompt_tokens", "completion_tokens", "cost_usd",
    )
    return TranslationRecord(**{key: row[key] for key in keys})  # type: ignore[arg-type]


def _translation_attempt_from_record(row: Mapping[str, object]) -> TranslationAttemptRecord:
    translator = row["translator"]
    if not isinstance(translator, dict):
        raise ContractError("translation artifact translator identity is invalid")
    values = {
        "execution_id": row["execution_id"],
        "attempt_id": row["attempt_id"],
        "configuration_hash": row["configuration_hash"],
        "translation_config_hash": row["translation_config_hash"],
        "translation_config_version": row["translation_config_version"],
        "translation_prompt_version": row["translation_prompt_version"],
        "input_id": row["input_id"],
        "input_sha256": row["input_sha256"],
        "translator_provider": translator["provider_id"],
        "translator_model": translator["model_id"],
        "translator_version": translator["model_version"],
        "attempt_number": row["attempt_number"],
        "max_attempts": row["max_attempts"],
        "retry_policy_version": row["retry_policy_version"],
        "failure_policy": row["failure_policy"],
        "started_at_utc": row["started_at_utc"],
        "completed_at_utc": row["completed_at_utc"],
        "status": row["status"],
        "error_category": row["error_category"],
        "retry_decision": row["retry_decision"],
        "raw_response": row["raw_response"],
        "translated_conversation_sha256": row["translated_conversation_sha256"],
        "prompt_tokens": row["prompt_tokens"],
        "completion_tokens": row["completion_tokens"],
        "cost_usd": row["cost_usd"],
        "latency_ms": row["latency_ms"],
        "provider_call_records": tuple(row.get("provider_call_records", [])),
    }
    return TranslationAttemptRecord(**values)  # type: ignore[arg-type]
