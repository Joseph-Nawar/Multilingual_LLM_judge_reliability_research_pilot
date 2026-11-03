"""Provider-independent judge request, run, parsing, and attempt records.

This module contains no provider integrations and never imports the reference
oracle or private study data. Its only executable provider is an explicit
deterministic mock for tests and local interface development.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import math
import re
import time
from typing import Callable, Mapping, Protocol, Sequence


RUN_CONFIG_VERSION = "p3-run-config-1"
RUN_MANIFEST_VERSION = "p3-run-manifest-1"
JUDGE_REQUEST_VERSION = "p3-judge-request-1"
RUN_RESULT_VERSION = "p3-run-result-1"
PARSER_VERSION = "p3-binary-json-verdict-1"


class BaselineKind(str, Enum):
    DIRECT_MULTILINGUAL = "direct_multilingual"
    TRANSLATION_FIRST = "translation_first"
    STRUCTURED_DECOMPOSED = "structured_decomposed"


class Verdict(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class ParseStatus(str, Enum):
    PARSED = "parsed"
    INVALID_OUTPUT = "invalid_output"
    MISSING = "missing"
    REFUSED = "refused"
    PROVIDER_FAILURE = "provider_failure"


# Alias kept descriptive at call sites that deal with provider responses.
ResponseStatus = ParseStatus


REFERENCE_ONLY_FIELD_FRAGMENTS = (
    "oracle",
    "gold",
    "reference",
    "effectivestate",
    "canonicalstate",
    "pairid",
    "scenarioid",
    "historyid",
    "derivativeid",
    "partition",
    "templateid",
    "recipeid",
    "authorassessment",
    "authorsideclassification",
    "provenance",
    "decisiveevent",
)
SECRET_FIELD_FRAGMENTS = (
    "apikey",
    "secret",
    "password",
    "credential",
    "authorization",
    "accesstoken",
    "refreshtoken",
)

_CONDITIONS = {"EN-EN", "AR-AR", "EN-AR", "AR-EN"}
_LANGUAGES = {"en", "ar"}
_SPEAKERS = {"user", "assistant", "tool"}


class ContractError(ValueError):
    """A request or record violates the versioned infrastructure contract."""


class ProviderCallError(RuntimeError):
    """Safe provider failure category; exception text is never put in run logs."""

    def __init__(self, code: str):
        if not code or not re.fullmatch(r"[a-zA-Z0-9_.-]+", code):
            raise ValueError("provider failure code must be a short stable identifier")
        self.code = code
        super().__init__(code)


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).casefold())


def _check_forbidden_mapping_keys(value: object, *, reject_secrets: bool = False, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = _normalized_key(key)
            if any(fragment in normalized for fragment in REFERENCE_ONLY_FIELD_FRAGMENTS):
                raise ContractError(f"reference-only field is not allowed in ordinary inference data: {path}{key}")
            if reject_secrets and any(fragment in normalized for fragment in SECRET_FIELD_FRAGMENTS):
                raise ContractError(f"credential-shaped field is not allowed in run configuration: {path}{key}")
            _check_forbidden_mapping_keys(child, reject_secrets=reject_secrets, path=f"{path}{key}.")
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _check_forbidden_mapping_keys(child, reject_secrets=reject_secrets, path=f"{path}{index}.")


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ContractError("non-finite Decimal values cannot be serialized")
        return str(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ContractError("JSON object keys must be strings")
        return {key: _jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_jsonable(child) for child in value]
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ContractError("non-finite float values cannot be serialized")
        return value
    raise ContractError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Return stable UTF-8-friendly JSON, rejecting non-JSON values."""
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require_sha256(value: str, field_name: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ContractError(f"{field_name} must be a lowercase SHA-256 hex digest")


def validate_cost_usd(value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ContractError("cost_usd must be a decimal string")
    try:
        cost = Decimal(value)
    except InvalidOperation as exc:
        raise ContractError("cost_usd must be a decimal string") from exc
    if not cost.is_finite() or cost < 0:
        raise ContractError("cost_usd must be finite and non-negative")


def _validate_parameter_pairs(parameters: tuple[tuple[str, object], ...], name: str) -> None:
    if not isinstance(parameters, tuple):
        raise ContractError(f"{name} must be an immutable tuple of key/value pairs")
    keys = [key for key, _value in parameters]
    if any(not isinstance(key, str) or not key for key in keys):
        raise ContractError(f"{name} keys must be non-empty strings")
    if tuple(sorted(parameters)) != parameters:
        raise ContractError(f"{name} must be sorted by key")
    if len(set(keys)) != len(keys):
        raise ContractError(f"{name} keys must be unique")
    values = dict(parameters)
    _check_forbidden_mapping_keys(values, reject_secrets=True)
    canonical_json(values)


@dataclass(frozen=True)
class ConversationTurn:
    turn_index: int
    speaker: str
    language: str
    content: str

    def __post_init__(self) -> None:
        if type(self.turn_index) is not int or self.turn_index < 0:
            raise ContractError("turn_index must be a non-negative integer")
        if not isinstance(self.speaker, str) or self.speaker not in _SPEAKERS:
            raise ContractError("speaker must be user, assistant, or tool")
        if not isinstance(self.language, str) or self.language not in _LANGUAGES:
            raise ContractError("language must be en or ar")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ContractError("conversation turn content must be non-empty text")

    def to_record(self) -> dict[str, object]:
        return {
            "turn_index": self.turn_index,
            "speaker": self.speaker,
            "language": self.language,
            "content": self.content,
        }

    def to_public_record(self) -> dict[str, object]:
        return {"speaker": self.speaker, "content": self.content}


@dataclass(frozen=True)
class JudgeFacingInput:
    """Explicit allowlist of ordinary judge input; it has no label/state field."""

    item_id: str
    language_condition: str
    action_turn_index: int
    conversation: tuple[ConversationTurn, ...]
    action: Mapping[str, object]
    public_tool_schema: Mapping[str, object]
    _action_json: str = field(init=False, repr=False, compare=False)
    _tool_schema_json: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ContractError("opaque item_id must be non-empty text")
        if not isinstance(self.language_condition, str) or self.language_condition not in _CONDITIONS:
            raise ContractError("unsupported language condition")
        if type(self.action_turn_index) is not int or self.action_turn_index < 1:
            raise ContractError("action_turn_index must be a positive integer")
        if not isinstance(self.conversation, tuple) or not self.conversation:
            raise ContractError("ordinary judge input requires at least one conversation turn")
        if any(not isinstance(turn, ConversationTurn) for turn in self.conversation):
            raise ContractError("conversation must contain ConversationTurn records")
        indices = [turn.turn_index for turn in self.conversation]
        if len(indices) != len(set(indices)) or indices != sorted(indices):
            raise ContractError("conversation turns must have unique, increasing indices")
        if any(turn.turn_index >= self.action_turn_index for turn in self.conversation):
            raise ContractError("all judge conversation turns must be before the action decision point")
        if not isinstance(self.action, Mapping) or not isinstance(self.public_tool_schema, Mapping):
            raise ContractError("action and public_tool_schema must be JSON objects")
        if not self.action or not self.public_tool_schema:
            raise ContractError("action and public_tool_schema must not be empty")
        _check_forbidden_mapping_keys(self.action)
        _check_forbidden_mapping_keys(self.public_tool_schema)
        action_json = canonical_json(self.action)
        tool_schema_json = canonical_json(self.public_tool_schema)
        object.__setattr__(self, "_action_json", action_json)
        object.__setattr__(self, "_tool_schema_json", tool_schema_json)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "JudgeFacingInput":
        allowed = {
            "item_id", "language_condition", "action_turn_index", "conversation", "action", "public_tool_schema"
        }
        if not isinstance(value, Mapping):
            raise ContractError("judge-facing input must be an object")
        _check_forbidden_mapping_keys(value)
        unknown = set(value) - allowed
        missing = allowed - set(value)
        if unknown:
            raise ContractError(f"unknown judge-facing field(s): {', '.join(sorted(map(str, unknown)))}")
        if missing:
            raise ContractError(f"missing judge-facing field(s): {', '.join(sorted(missing))}")
        raw_turns = value["conversation"]
        if not isinstance(raw_turns, (tuple, list)):
            raise ContractError("conversation must be an array")
        turns = []
        for row in raw_turns:
            if not isinstance(row, Mapping):
                raise ContractError("conversation turn must be an object")
            _check_forbidden_mapping_keys(row)
            if set(row) != {"turn_index", "speaker", "language", "content"}:
                raise ContractError("conversation turn must contain exactly turn_index, speaker, language, and content")
            turns.append(ConversationTurn(**row))
        return cls(
            item_id=value["item_id"],
            language_condition=value["language_condition"],
            action_turn_index=value["action_turn_index"],
            conversation=tuple(turns),
            action=value["action"],
            public_tool_schema=value["public_tool_schema"],
        )

    def evidence_record(self) -> dict[str, object]:
        """Return a fresh copy of the checked allowlisted evidence snapshot."""
        return {
            "item_id": self.item_id,
            "conversation": [turn.to_public_record() for turn in self.conversation],
            "action": json.loads(self._action_json),
            "public_tool_schema": json.loads(self._tool_schema_json),
        }

    def action_record(self) -> dict[str, object]:
        return json.loads(self._action_json)

    def public_tool_schema_record(self) -> dict[str, object]:
        return json.loads(self._tool_schema_json)

    def with_conversation(self, turns: Sequence[ConversationTurn]) -> "JudgeFacingInput":
        return JudgeFacingInput(
            item_id=self.item_id,
            language_condition=self.language_condition,
            action_turn_index=self.action_turn_index,
            conversation=tuple(turns),
            action=self.action_record(),
            public_tool_schema=self.public_tool_schema_record(),
        )


@dataclass(frozen=True)
class PromptSpec:
    version: str
    instruction: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.instruction.strip():
            raise ContractError("prompt version and instruction must be non-empty")


@dataclass(frozen=True)
class JudgeRequest:
    request_id: str
    item_id: str
    baseline: str
    stage_id: str
    prompt_version: str
    action_turn_index: int = field(repr=False, compare=False)
    instruction: str
    conversation: tuple[ConversationTurn, ...]
    action: Mapping[str, object]
    public_tool_schema: Mapping[str, object]
    _action_json: str = field(init=False, repr=False, compare=False)
    _tool_schema_json: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.request_id or not self.item_id or not self.baseline or not self.stage_id or not self.prompt_version:
            raise ContractError("judge request identifiers and versions must be non-empty")
        if not self.instruction.strip():
            raise ContractError("judge request instruction must be non-empty")
        if type(self.action_turn_index) is not int or self.action_turn_index < 1:
            raise ContractError("judge request requires an action decision point")
        if not isinstance(self.conversation, tuple) or not self.conversation:
            raise ContractError("judge request requires conversation evidence")
        if any(not isinstance(turn, ConversationTurn) for turn in self.conversation):
            raise ContractError("judge request conversation must contain ConversationTurn records")
        indices = [turn.turn_index for turn in self.conversation]
        if len(indices) != len(set(indices)) or indices != sorted(indices):
            raise ContractError("judge request turns must be unique and chronological")
        if any(turn.turn_index >= self.action_turn_index for turn in self.conversation):
            raise ContractError("judge request turns must precede the action decision point")
        _check_forbidden_mapping_keys(self.action)
        _check_forbidden_mapping_keys(self.public_tool_schema)
        object.__setattr__(self, "_action_json", canonical_json(self.action))
        object.__setattr__(self, "_tool_schema_json", canonical_json(self.public_tool_schema))

    def to_record(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "instruction": self.instruction,
            "conversation": [turn.to_public_record() for turn in self.conversation],
            "action": json.loads(self._action_json),
            "public_tool_schema": json.loads(self._tool_schema_json),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_record())


def build_judge_request(
    item: JudgeFacingInput,
    *,
    run_id: str,
    baseline: BaselineKind | str,
    stage_id: str,
    prompt: PromptSpec,
) -> JudgeRequest:
    baseline_value = baseline.value if isinstance(baseline, BaselineKind) else baseline
    request_id = hashlib.sha256(f"{run_id}\0{item.item_id}\0{baseline_value}\0{stage_id}".encode("utf-8")).hexdigest()
    evidence = item.evidence_record()
    return JudgeRequest(
        request_id=request_id,
        item_id=item.item_id,
        baseline=baseline_value,
        stage_id=stage_id,
        prompt_version=prompt.version,
        action_turn_index=item.action_turn_index,
        instruction=prompt.instruction,
        conversation=item.conversation,
        action=evidence["action"],
        public_tool_schema=evidence["public_tool_schema"],
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


@dataclass(frozen=True)
class ParseResult:
    status: ParseStatus
    verdict: Verdict | None = None

    def __post_init__(self) -> None:
        if (self.status is ParseStatus.PARSED) != (self.verdict is not None):
            raise ContractError("only parsed responses may contain a binary verdict")

    def to_record(self) -> dict[str, object]:
        return {"status": self.status.value, "verdict": self.verdict.value if self.verdict else None}


def parse_verdict_response(raw_response: str | None, *, provider_refused: bool = False) -> ParseResult:
    """Parse only the strict binary JSON contract; never infer a verdict from prose."""
    if provider_refused:
        return ParseResult(ParseStatus.REFUSED)
    if raw_response is None:
        return ParseResult(ParseStatus.MISSING)
    try:
        parsed = json.loads(
            raw_response,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {value}")),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return ParseResult(ParseStatus.INVALID_OUTPUT)
    if isinstance(parsed, dict) and set(parsed) == {"refusal"} and isinstance(parsed["refusal"], str) and parsed["refusal"].strip():
        return ParseResult(ParseStatus.REFUSED)
    if not isinstance(parsed, dict) or set(parsed) != {"verdict"} or not isinstance(parsed["verdict"], str):
        return ParseResult(ParseStatus.INVALID_OUTPUT)
    try:
        verdict = Verdict(parsed["verdict"])
    except ValueError:
        return ParseResult(ParseStatus.INVALID_OUTPUT)
    return ParseResult(ParseStatus.PARSED, verdict)


@dataclass(frozen=True)
class ProviderIdentity:
    provider_id: str
    model_id: str
    model_version: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (self.provider_id, self.model_id, self.model_version)):
            raise ContractError("provider and model identity fields must be non-empty")

    def to_record(self) -> dict[str, str]:
        return {"provider_id": self.provider_id, "model_id": self.model_id, "model_version": self.model_version}


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    retryable_error_codes: tuple[str, ...] = ()
    version: str = "retry-policy-1"

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ContractError("max_attempts must be a positive integer")
        if len(self.retryable_error_codes) != len(set(self.retryable_error_codes)):
            raise ContractError("retryable error codes must be unique")
        if not self.version.strip():
            raise ContractError("retry policy version must be non-empty")

    def to_record(self) -> dict[str, object]:
        return {
            "version": self.version,
            "max_attempts": self.max_attempts,
            "retryable_error_codes": list(self.retryable_error_codes),
        }


@dataclass(frozen=True)
class TranslationConfig:
    translator: ProviderIdentity
    pivot_language: str
    prompt_version: str
    decoding_parameters: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    config_version: str = "translation-config-1"

    def __post_init__(self) -> None:
        if self.pivot_language not in _LANGUAGES or not self.prompt_version.strip():
            raise ContractError("translation pivot language and prompt version are required")
        if not self.config_version.strip():
            raise ContractError("translation config version must be non-empty")
        _validate_parameter_pairs(self.decoding_parameters, "translation decoding parameters")

    def to_record(self) -> dict[str, object]:
        return {
            "translator": self.translator.to_record(),
            "pivot_language": self.pivot_language,
            "prompt_version": self.prompt_version,
            "config_version": self.config_version,
            "decoding_parameters": dict(self.decoding_parameters),
        }


@dataclass(frozen=True)
class RunConfig:
    provider: ProviderIdentity
    baseline: str
    prompt_bundle_version: str
    input_manifest_sha256: str
    code_revision: str
    decoding_parameters: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    retry_policy: RetryPolicy = RetryPolicy()
    translation: TranslationConfig | None = None
    random_seed: int | str | None = None
    aggregation_version: str = "single-binary-verdict-1"
    config_version: str = RUN_CONFIG_VERSION
    parser_version: str = PARSER_VERSION

    def __post_init__(self) -> None:
        try:
            BaselineKind(self.baseline)
        except ValueError as exc:
            raise ContractError(f"unsupported baseline: {self.baseline}") from exc
        if not self.prompt_bundle_version.strip() or not self.code_revision.strip():
            raise ContractError("prompt bundle version and code revision are required")
        if not self.aggregation_version.strip():
            raise ContractError("aggregation version must be non-empty")
        _require_sha256(self.input_manifest_sha256, "input_manifest_sha256")
        if not self.config_version.strip() or not self.parser_version.strip():
            raise ContractError("run config and parser versions are required")
        _validate_parameter_pairs(self.decoding_parameters, "decoding parameters")
        if self.baseline == BaselineKind.TRANSLATION_FIRST.value and self.translation is None:
            raise ContractError("translation-first run configuration requires translation settings")
        if self.baseline != BaselineKind.TRANSLATION_FIRST.value and self.translation is not None:
            raise ContractError("translation settings are only valid for translation-first runs")
        if self.random_seed is not None and type(self.random_seed) not in {int, str}:
            raise ContractError("random seed must be an integer, string, or absent")

    def to_record(self) -> dict[str, object]:
        return {
            "config_version": self.config_version,
            "provider": self.provider.to_record(),
            "baseline": self.baseline,
            "prompt_bundle_version": self.prompt_bundle_version,
            "aggregation_version": self.aggregation_version,
            "translation": self.translation.to_record() if self.translation else None,
            "decoding_parameters": dict(self.decoding_parameters),
            "parser_version": self.parser_version,
            "retry_policy": self.retry_policy.to_record(),
            "random_seed": self.random_seed,
            "input_manifest_sha256": self.input_manifest_sha256,
            "code_revision": self.code_revision,
        }

    @property
    def run_id(self) -> str:
        digest = hashlib.sha256(canonical_json(self.to_record()).encode("utf-8")).hexdigest()
        return f"run-{digest}"

    def to_manifest_record(self) -> dict[str, object]:
        return {"manifest_version": RUN_MANIFEST_VERSION, "run_id": self.run_id, "config": self.to_record()}

    def to_manifest_json(self) -> str:
        return canonical_json(self.to_manifest_record())


@dataclass(frozen=True)
class ProviderResponse:
    raw_response: str | None
    refused: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: str | None = None

    def __post_init__(self) -> None:
        if type(self.refused) is not bool:
            raise ContractError("refused must be a boolean provider signal")
        if self.raw_response is not None and not isinstance(self.raw_response, str):
            raise ContractError("raw_response must be text or absent")
        for name, value in (("prompt_tokens", self.prompt_tokens), ("completion_tokens", self.completion_tokens)):
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"{name} must be a non-negative integer or absent")
        validate_cost_usd(self.cost_usd)


class JudgeProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def complete(self, request_json: str, decoding_parameters: Mapping[str, object]) -> ProviderResponse: ...


class DeterministicMockProvider:
    """Explicit local fake; it has no network behavior."""

    def __init__(self, identity: ProviderIdentity, responses: Sequence[ProviderResponse | ProviderCallError]):
        self._identity = identity
        self._responses = tuple(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._position = 0

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def complete(self, request_json: str, decoding_parameters: Mapping[str, object]) -> ProviderResponse:
        self.calls.append((request_json, dict(decoding_parameters)))
        if self._position >= len(self._responses):
            raise ProviderCallError("mock_response_exhausted")
        response = self._responses[self._position]
        self._position += 1
        if isinstance(response, ProviderCallError):
            raise response
        return response


@dataclass(frozen=True)
class AttemptRecord:
    attempt_number: int
    call_status: str
    raw_response: str | None
    parse_status: ParseStatus | None
    verdict: Verdict | None
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: str | None
    provider_refused: bool | None
    failure_code: str | None

    def to_record(self) -> dict[str, object]:
        return {
            "attempt_number": self.attempt_number,
            "call_status": self.call_status,
            "raw_response": self.raw_response,
            "parse_status": self.parse_status.value if self.parse_status else None,
            "verdict": self.verdict.value if self.verdict else None,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
            "provider_refused": self.provider_refused,
            "failure_code": self.failure_code,
        }


@dataclass(frozen=True)
class StepRunRecord:
    request_id: str
    stage_id: str
    prompt_version: str
    request_json: str
    attempts: tuple[AttemptRecord, ...]
    outcome: ParseResult

    def to_record(self) -> dict[str, object]:
        return {
            "request_schema_version": JUDGE_REQUEST_VERSION,
            "request_id": self.request_id,
            "stage_id": self.stage_id,
            "prompt_version": self.prompt_version,
            "request_json": self.request_json,
            "attempts": [attempt.to_record() for attempt in self.attempts],
            "outcome": self.outcome.to_record(),
        }


@dataclass(frozen=True)
class RunResult:
    run_id: str
    item_id: str
    baseline: str
    aggregation_version: str
    steps: tuple[StepRunRecord, ...]
    translation_records: tuple[object, ...]
    final_result: ParseResult

    def to_record(self) -> dict[str, object]:
        return {
            "result_version": RUN_RESULT_VERSION,
            "run_id": self.run_id,
            "item_id": self.item_id,
            "baseline": self.baseline,
            "aggregation_version": self.aggregation_version,
            "translation_records": [record.to_record() for record in self.translation_records],
            "steps": [step.to_record() for step in self.steps],
            "final_result": self.final_result.to_record(),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_record())


class JudgeExecutor:
    """Runs a prepared plan against an explicitly supplied provider implementation."""

    def __init__(
        self,
        config: RunConfig,
        provider: JudgeProvider,
        *,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
    ):
        if provider.identity != config.provider:
            raise ContractError("provider identity does not match the versioned run configuration")
        self.config = config
        self.provider = provider
        self.clock_ns = clock_ns

    def run(self, plan: _ExecutablePlan) -> RunResult:
        from .judge_baselines import BaselinePlan

        if not isinstance(plan, BaselinePlan):
            raise TypeError("ordinary baseline plan is required")
        if plan.baseline != self.config.baseline:
            raise ContractError("baseline plan does not match run configuration")
        if plan.aggregation_version != self.config.aggregation_version:
            raise ContractError("baseline aggregation does not match run configuration")
        if self.config.baseline == BaselineKind.TRANSLATION_FIRST.value and not plan.translation_records:
            raise ContractError("translation-first plan must retain translation provenance")
        if self.config.baseline != BaselineKind.TRANSLATION_FIRST.value and plan.translation_records:
            raise ContractError("translation provenance is only valid for translation-first plans")
        if not plan.requests:
            raise ContractError("baseline plan must contain at least one judge request")
        if any(request.baseline != self.config.baseline for request in plan.requests):
            raise ContractError("judge request baseline does not match run configuration")
        if any(request.item_id != plan.requests[0].item_id for request in plan.requests):
            raise ContractError("all steps in a baseline plan must refer to the same item")

        steps = tuple(self._run_request(request) for request in plan.requests)
        final = plan.aggregate(tuple(step.outcome for step in steps))
        if not isinstance(final, ParseResult):
            raise ContractError("baseline aggregation must return a ParseResult without coercion")
        return RunResult(
            run_id=self.config.run_id,
            item_id=plan.requests[0].item_id,
            baseline=self.config.baseline,
            aggregation_version=plan.aggregation_version,
            steps=steps,
            translation_records=plan.translation_records,
            final_result=final,
        )

    def _run_request(self, request: JudgeRequest) -> StepRunRecord:
        attempts: list[AttemptRecord] = []
        final_result = ParseResult(ParseStatus.PROVIDER_FAILURE)
        policy = self.config.retry_policy
        decoding = dict(self.config.decoding_parameters)
        request_json = request.to_json()
        for attempt_number in range(1, policy.max_attempts + 1):
            start = self.clock_ns()
            try:
                response = self.provider.complete(request_json, decoding)
            except Exception as exc:  # do not serialize arbitrary exception text, which may contain credentials
                end = self.clock_ns()
                code = exc.code if isinstance(exc, ProviderCallError) else type(exc).__name__
                attempts.append(
                    AttemptRecord(
                        attempt_number, "provider_failure", None, None, None,
                        max(0, end - start) / 1_000_000, None, None, None, None, code,
                    )
                )
                should_retry = (
                    isinstance(exc, ProviderCallError)
                    and code in policy.retryable_error_codes
                    and attempt_number < policy.max_attempts
                )
                if should_retry:
                    continue
                final_result = ParseResult(ParseStatus.PROVIDER_FAILURE)
                break

            end = self.clock_ns()
            final_result = parse_verdict_response(response.raw_response, provider_refused=response.refused)
            attempts.append(
                AttemptRecord(
                    attempt_number,
                    "response_received",
                    response.raw_response,
                    final_result.status,
                    final_result.verdict,
                    max(0, end - start) / 1_000_000,
                    response.prompt_tokens,
                    response.completion_tokens,
                    response.cost_usd,
                    response.refused,
                    None,
                )
            )
            # Parse failures and refusals are retained as outcomes; only configured provider errors retry.
            break
        return StepRunRecord(
            request.request_id,
            request.stage_id,
            request.prompt_version,
            request_json,
            tuple(attempts),
            final_result,
        )
