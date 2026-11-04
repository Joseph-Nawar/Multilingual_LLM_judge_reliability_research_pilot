"""Preparation interfaces for candidate judge baselines; no final prompts ship here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import re
import time
from typing import Callable, Protocol, Sequence
from uuid import uuid4

from .judge_inference import (
    BaselineKind,
    ContractError,
    ConversationTurn,
    JudgeFacingInput,
    JudgeRequest,
    ParseResult,
    ParseStatus,
    PromptSpec,
    ProviderCallError,
    ProviderIdentity,
    RunConfig,
    TranslationConfig,
    TranslationFacingInput,
    TranslationFailurePolicy,
    STRUCTURED_PARSER_VERSION,
    STRUCTURED_RESPONSE_CONTRACT,
    validate_cost_usd,
    build_judge_request,
    canonical_json,
)


class VerdictAggregator(Protocol):
    version: str

    def aggregate(self, results: tuple[ParseResult, ...]) -> ParseResult: ...


@dataclass(frozen=True)
class SingleVerdictAggregator:
    """Identity aggregation used when a baseline produces one binary response."""

    version: str = "single-binary-verdict-1"

    def aggregate(self, results: tuple[ParseResult, ...]) -> ParseResult:
        if len(results) != 1:
            raise ContractError("single-verdict aggregation requires exactly one response")
        return results[0]


@dataclass(frozen=True)
class StructuredSingleVerdictAggregator:
    """Identity aggregation for the parser-validated one-call structured result."""

    version: str = "single-structured-verdict-1"

    def aggregate(self, results: tuple[ParseResult, ...]) -> ParseResult:
        if len(results) != 1:
            raise ContractError("single-call structured aggregation requires exactly one response")
        return results[0]


@dataclass(frozen=True)
class TranslationOutput:
    translated_turns: tuple[ConversationTurn, ...]
    raw_output: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: str | None = None
    provider_call_records: tuple[dict[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.raw_output, str) or not self.raw_output:
            raise ContractError("translation output must retain a non-empty raw response")
        if not isinstance(self.latency_ms, (int, float)) or self.latency_ms < 0:
            raise ContractError("translation latency must be non-negative")
        for name, value in (("prompt_tokens", self.prompt_tokens), ("completion_tokens", self.completion_tokens)):
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"{name} must be a non-negative integer or absent")
        validate_cost_usd(self.cost_usd)
        if not isinstance(self.provider_call_records, tuple) or any(not isinstance(row, dict) for row in self.provider_call_records):
            raise ContractError("provider_call_records must be a tuple of serializable call records")
        canonical_json(self.provider_call_records)


class TranslationCallError(RuntimeError):
    """Safe, structured translation failure with optional provider response metadata."""

    def __init__(
        self,
        category: str,
        *,
        raw_response: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost_usd: str | None = None,
        provider_call_records: tuple[dict[str, object], ...] = (),
        message: str | None = None,
    ) -> None:
        if not isinstance(category, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", category):
            raise ContractError("translation error category must be a short stable identifier")
        if raw_response is not None and not isinstance(raw_response, str):
            raise ContractError("translation raw response must be text or absent")
        for name, value in (("prompt_tokens", prompt_tokens), ("completion_tokens", completion_tokens)):
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"{name} must be a non-negative integer or absent")
        validate_cost_usd(cost_usd)
        if not isinstance(provider_call_records, tuple) or any(not isinstance(row, dict) for row in provider_call_records):
            raise ContractError("provider_call_records must be a tuple of serializable call records")
        canonical_json(provider_call_records)
        self.category = category
        self.raw_response = raw_response
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cost_usd = cost_usd
        self.provider_call_records = provider_call_records
        # Provider detail can include credentials; keep only the stable category in the exception text.
        super().__init__(category)


class Translator(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def translate(self, item: TranslationFacingInput, config: TranslationConfig) -> TranslationOutput: ...


@dataclass(frozen=True)
class TranslationRecord:
    execution_id: str
    translation_config_hash: str
    input_id: str
    translator_provider: str
    translator_model: str
    translator_version: str
    prompt_version: str
    target_language: str
    source_conversation_sha256: str
    input_sha256: str
    translated_conversation_sha256: str
    raw_output: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: str | None

    def to_record(self) -> dict[str, object]:
        return {
            "record_version": "translation-summary-2",
            "execution_id": self.execution_id,
            "translation_config_hash": self.translation_config_hash,
            "input_id": self.input_id,
            "translator_provider": self.translator_provider,
            "translator_model": self.translator_model,
            "translator_version": self.translator_version,
            "prompt_version": self.prompt_version,
            "target_language": self.target_language,
            "source_conversation_sha256": self.source_conversation_sha256,
            "input_sha256": self.input_sha256,
            "translated_conversation_sha256": self.translated_conversation_sha256,
            "raw_output": self.raw_output,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
        }


@dataclass(frozen=True)
class TranslationAttemptRecord:
    execution_id: str
    attempt_id: str
    configuration_hash: str
    translation_config_hash: str
    translation_config_version: str
    translation_prompt_version: str
    input_id: str
    input_sha256: str
    translator_provider: str
    translator_model: str
    translator_version: str
    attempt_number: int
    max_attempts: int
    retry_policy_version: str
    failure_policy: str
    started_at_utc: str
    completed_at_utc: str
    status: str
    error_category: str | None
    retry_decision: str
    raw_response: str | None
    translated_conversation_sha256: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: str | None
    latency_ms: float
    provider_call_records: tuple[dict[str, object], ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "record_version": "translation-attempt-2",
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "configuration_hash": self.configuration_hash,
            "translation_config_hash": self.translation_config_hash,
            "translation_config_version": self.translation_config_version,
            "translation_prompt_version": self.translation_prompt_version,
            "input_id": self.input_id,
            "input_sha256": self.input_sha256,
            "translator": {
                "provider_id": self.translator_provider,
                "model_id": self.translator_model,
                "model_version": self.translator_version,
            },
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts,
            "retry_policy_version": self.retry_policy_version,
            "failure_policy": self.failure_policy,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "status": self.status,
            "error_category": self.error_category,
            "retry_decision": self.retry_decision,
            "raw_response": self.raw_response,
            "translated_conversation_sha256": self.translated_conversation_sha256,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "provider_call_records": list(self.provider_call_records),
        }


class TranslationExecutionError(RuntimeError):
    """Explicit raise policy carrying every attempted translation as serializable data."""

    def __init__(
        self,
        *,
        execution_id: str,
        configuration_hash: str,
        attempts: tuple[TranslationAttemptRecord, ...],
    ) -> None:
        self.execution_id = execution_id
        self.configuration_hash = configuration_hash
        self.attempts = attempts
        super().__init__("translation failed; inspect the attached attempt records")

    def to_record(self) -> dict[str, object]:
        return {
            "failure_record_version": "translation-execution-failure-1",
            "execution_id": self.execution_id,
            "configuration_hash": self.configuration_hash,
            "translation_attempts": [attempt.to_record() for attempt in self.attempts],
        }


@dataclass(frozen=True)
class BaselinePlan:
    baseline: str
    requests: tuple[JudgeRequest, ...]
    aggregation: VerdictAggregator
    item_id: str | None = None
    execution_id: str = field(default_factory=lambda: uuid4().hex)
    translation_records: tuple[TranslationRecord, ...] = ()
    translation_attempts: tuple[TranslationAttemptRecord, ...] = ()
    preprocessing_result: ParseResult | None = None

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ContractError("baseline execution ID must be non-empty")
        if self.item_id is None and self.requests:
            object.__setattr__(self, "item_id", self.requests[0].item_id)
        if not self.item_id:
            raise ContractError("baseline plan requires an item ID")
        if any(request.item_id != self.item_id for request in self.requests):
            raise ContractError("baseline plan requests must refer to its item ID")
        if self.preprocessing_result is not None:
            if self.requests or self.preprocessing_result.status is not ParseStatus.PROVIDER_FAILURE:
                raise ContractError("failed preprocessing must skip judge requests and be recorded as provider failure")
            if not self.translation_attempts:
                raise ContractError("failed preprocessing must retain translation attempts")

    @property
    def aggregation_version(self) -> str:
        return self.aggregation.version

    def aggregate(self, results: tuple[ParseResult, ...]) -> ParseResult:
        return self.aggregation.aggregate(results)


def _validate_config(
    config: RunConfig,
    baseline: BaselineKind,
    prompt_bundle_version: str,
    aggregation_version: str,
) -> None:
    if config.baseline != baseline.value:
        raise ContractError(f"run configuration baseline must be {baseline.value}")
    if config.prompt_bundle_version != prompt_bundle_version:
        raise ContractError("run configuration prompt bundle version does not match baseline plan")
    if config.aggregation_version != aggregation_version:
        raise ContractError("run configuration aggregation version does not match baseline plan")


@dataclass(frozen=True)
class DirectMultilingualBaseline:
    """Use original user-language turns with the caller-supplied prompt version."""

    prompt: PromptSpec

    def prepare(self, item: JudgeFacingInput, config: RunConfig) -> BaselinePlan:
        _validate_config(config, BaselineKind.DIRECT_MULTILINGUAL, self.prompt.version, "single-binary-verdict-1")
        request = build_judge_request(
            item,
            run_id=config.run_id,
            baseline=BaselineKind.DIRECT_MULTILINGUAL,
            stage_id="direct_verdict",
            prompt=self.prompt,
        )
        return BaselinePlan(
            BaselineKind.DIRECT_MULTILINGUAL.value,
            (request,),
            SingleVerdictAggregator(),
            item_id=item.item_id,
        )


@dataclass(frozen=True)
class TranslationFirstBaseline:
    """Translate via an injected translator, then judge with the same provider identity."""

    prompt: PromptSpec
    translator: Translator
    clock_ns: Callable[[], int] = field(default=time.perf_counter_ns, repr=False, compare=False)
    utc_now: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc), repr=False, compare=False)
    execution_id_factory: Callable[[], str] = field(default=lambda: uuid4().hex, repr=False, compare=False)

    def prepare(self, item: JudgeFacingInput, config: RunConfig, *, translation_artifact=None) -> BaselinePlan:
        _validate_config(config, BaselineKind.TRANSLATION_FIRST, self.prompt.version, "single-binary-verdict-1")
        translation_config = config.translation
        if translation_config is None:
            raise ContractError("translation-first baseline requires a translation configuration")
        if self.translator.identity != translation_config.translator:
            raise ContractError("translator identity does not match the versioned translation configuration")
        execution_id = self.execution_id_factory()
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ContractError("translation execution ID factory must return non-empty text")
        if translation_artifact is not None:
            from .translation_artifacts import TranslationArtifact

            if not isinstance(translation_artifact, TranslationArtifact):
                raise ContractError("translation_artifact must be a versioned TranslationArtifact")
            translation_artifact.validate_for(item, config)
            translated_item = item.with_conversation(translation_artifact.translated_turns)
            request = build_judge_request(
                translated_item,
                run_id=config.run_id,
                baseline=BaselineKind.TRANSLATION_FIRST,
                stage_id="translated_verdict",
                prompt=self.prompt,
            )
            return BaselinePlan(
                BaselineKind.TRANSLATION_FIRST.value,
                (request,),
                SingleVerdictAggregator(),
                item_id=item.item_id,
                execution_id=execution_id,
                translation_records=translation_artifact.translation_records,
                translation_attempts=translation_artifact.translation_attempts,
            )
        source_turns = [turn.to_record() for turn in item.conversation]
        source_hash = sha256(canonical_json(source_turns).encode("utf-8")).hexdigest()
        attempts: list[TranslationAttemptRecord] = []
        translated: TranslationOutput | None = None
        retry_policy = translation_config.retry_policy

        for attempt_number in range(1, retry_policy.max_attempts + 1):
            started_at = self._timestamp_utc(self.utc_now())
            started_ns = self.clock_ns()
            output: TranslationOutput | None = None
            try:
                output = self.translator.translate(TranslationFacingInput.from_judge_input(item), translation_config)
                self._validate_translation_output(item, output, translation_config)
            except Exception as exc:  # exception messages may contain provider credentials
                completed_ns = self.clock_ns()
                completed_at = self._timestamp_utc(self.utc_now())
                category = self._translation_error_category(exc)
                can_retry = category in retry_policy.retryable_error_codes and attempt_number < retry_policy.max_attempts
                raw_response = getattr(exc, "raw_response", None)
                prompt_tokens = getattr(exc, "prompt_tokens", None)
                completion_tokens = getattr(exc, "completion_tokens", None)
                cost_usd = getattr(exc, "cost_usd", None)
                provider_call_records = getattr(exc, "provider_call_records", ())
                if output is not None:
                    raw_response = raw_response if raw_response is not None else output.raw_output
                    prompt_tokens = prompt_tokens if prompt_tokens is not None else output.prompt_tokens
                    completion_tokens = completion_tokens if completion_tokens is not None else output.completion_tokens
                    cost_usd = cost_usd if cost_usd is not None else output.cost_usd
                attempts.append(
                    self._attempt_record(
                        execution_id=execution_id,
                        config=config,
                        translation_config=translation_config,
                        item=item,
                        source_hash=source_hash,
                        attempt_number=attempt_number,
                        started_at=started_at,
                        completed_at=completed_at,
                        latency_ms=max(0, completed_ns - started_ns) / 1_000_000,
                        status="failure",
                        error_category=category,
                        retry_decision="retry" if can_retry else "stop",
                        raw_response=raw_response,
                        translated_hash=None,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost_usd=cost_usd,
                        provider_call_records=provider_call_records,
                    )
                )
                if can_retry:
                    continue
                return self._translation_failure_plan(item, config, execution_id, tuple(attempts))

            completed_ns = self.clock_ns()
            completed_at = self._timestamp_utc(self.utc_now())
            translated = output
            translated_hash = sha256(
                canonical_json([turn.to_record() for turn in output.translated_turns]).encode("utf-8")
            ).hexdigest()
            attempts.append(
                self._attempt_record(
                    execution_id=execution_id,
                    config=config,
                    translation_config=translation_config,
                    item=item,
                    source_hash=source_hash,
                    attempt_number=attempt_number,
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=max(0, completed_ns - started_ns) / 1_000_000,
                    status="success",
                    error_category=None,
                    retry_decision="stop",
                    raw_response=output.raw_output,
                    translated_hash=translated_hash,
                    prompt_tokens=output.prompt_tokens,
                    completion_tokens=output.completion_tokens,
                    cost_usd=output.cost_usd,
                    provider_call_records=output.provider_call_records,
                )
            )
            break

        if translated is None:
            raise ContractError("translation retry loop completed without a result or failure record")

        translated_hash = sha256(canonical_json([turn.to_record() for turn in translated.translated_turns]).encode("utf-8")).hexdigest()
        translation_record = TranslationRecord(
            execution_id=execution_id,
            translation_config_hash=translation_config.config_hash,
            input_id=item.item_id,
            translator_provider=translation_config.translator.provider_id,
            translator_model=translation_config.translator.model_id,
            translator_version=translation_config.translator.model_version,
            prompt_version=translation_config.prompt_version,
            target_language=translation_config.pivot_language,
            source_conversation_sha256=source_hash,
            input_sha256=source_hash,
            translated_conversation_sha256=translated_hash,
            raw_output=translated.raw_output,
            latency_ms=translated.latency_ms,
            prompt_tokens=translated.prompt_tokens,
            completion_tokens=translated.completion_tokens,
            cost_usd=translated.cost_usd,
        )
        translated_item = item.with_conversation(translated.translated_turns)
        request = build_judge_request(
            translated_item,
            run_id=config.run_id,
            baseline=BaselineKind.TRANSLATION_FIRST,
            stage_id="translated_verdict",
            prompt=self.prompt,
        )
        return BaselinePlan(
            BaselineKind.TRANSLATION_FIRST.value,
            (request,),
            SingleVerdictAggregator(),
            item_id=item.item_id,
            execution_id=execution_id,
            translation_records=(translation_record,),
            translation_attempts=tuple(attempts),
        )

    @staticmethod
    def _timestamp_utc(value: datetime) -> str:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ContractError("translation timestamps must be timezone-aware datetimes")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _translation_error_category(exc: Exception) -> str:
        if isinstance(exc, TranslationCallError):
            return exc.category
        if isinstance(exc, ProviderCallError):
            return exc.code
        if isinstance(exc, ContractError):
            return "invalid_translation_output"
        return type(exc).__name__

    @staticmethod
    def _validate_translation_output(
        item: JudgeFacingInput,
        translated: TranslationOutput,
        config: TranslationConfig,
    ) -> None:
        if not isinstance(translated, TranslationOutput):
            raise ContractError("translator must return a TranslationOutput")
        if len(translated.translated_turns) != len(item.conversation):
            raise ContractError("translation must preserve the number of turns")
        for original, output in zip(item.conversation, translated.translated_turns, strict=True):
            if (original.turn_index, original.speaker) != (output.turn_index, output.speaker):
                raise ContractError("translation must preserve turn chronology and speaker roles")
            if output.language != config.pivot_language:
                raise ContractError("translation output language does not match configured pivot")

    def _attempt_record(
        self,
        *,
        execution_id: str,
        config: RunConfig,
        translation_config: TranslationConfig,
        item: JudgeFacingInput,
        source_hash: str,
        attempt_number: int,
        started_at: str,
        completed_at: str,
        latency_ms: float,
        status: str,
        error_category: str | None,
        retry_decision: str,
        raw_response: str | None,
        translated_hash: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        cost_usd: str | None,
        provider_call_records: tuple[dict[str, object], ...] = (),
    ) -> TranslationAttemptRecord:
        return TranslationAttemptRecord(
            execution_id=execution_id,
            attempt_id=f"{execution_id}:translation:{attempt_number}",
            configuration_hash=config.config_hash,
            translation_config_hash=translation_config.config_hash,
            translation_config_version=translation_config.config_version,
            translation_prompt_version=translation_config.prompt_version,
            input_id=item.item_id,
            input_sha256=source_hash,
            translator_provider=translation_config.translator.provider_id,
            translator_model=translation_config.translator.model_id,
            translator_version=translation_config.translator.model_version,
            attempt_number=attempt_number,
            max_attempts=translation_config.retry_policy.max_attempts,
            retry_policy_version=translation_config.retry_policy.version,
            failure_policy=translation_config.failure_policy.value,
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            status=status,
            error_category=error_category,
            retry_decision=retry_decision,
            raw_response=raw_response,
            translated_conversation_sha256=translated_hash,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            provider_call_records=provider_call_records,
        )

    def _translation_failure_plan(
        self,
        item: JudgeFacingInput,
        config: RunConfig,
        execution_id: str,
        attempts: tuple[TranslationAttemptRecord, ...],
    ) -> BaselinePlan:
        if config.translation is None:
            raise ContractError("translation-first baseline requires a translation configuration")
        if config.translation.failure_policy is TranslationFailurePolicy.RAISE_WITH_ATTEMPTS:
            raise TranslationExecutionError(
                execution_id=execution_id,
                configuration_hash=config.config_hash,
                attempts=attempts,
            )
        return BaselinePlan(
            BaselineKind.TRANSLATION_FIRST.value,
            (),
            SingleVerdictAggregator(),
            item_id=item.item_id,
            execution_id=execution_id,
            translation_attempts=attempts,
            preprocessing_result=ParseResult(ParseStatus.PROVIDER_FAILURE),
        )


@dataclass(frozen=True)
class DecompositionStage:
    stage_id: str
    prompt: PromptSpec

    def __post_init__(self) -> None:
        if not self.stage_id.strip():
            raise ContractError("decomposition stage_id must be non-empty")


@dataclass(frozen=True)
class DecompositionSpec:
    """Caller-supplied steps and aggregation; no research procedure is preselected."""

    bundle_version: str
    stages: tuple[DecompositionStage, ...]
    aggregation: VerdictAggregator

    def __post_init__(self) -> None:
        if not self.bundle_version.strip() or not self.stages:
            raise ContractError("decomposition bundle requires a version and at least one stage")
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ContractError("decomposition stage IDs must be unique")


@dataclass(frozen=True)
class StructuredDecomposedBaseline:
    """Prepares caller-defined decomposition requests and aggregation."""

    spec: DecompositionSpec

    def prepare(self, item: JudgeFacingInput, config: RunConfig) -> BaselinePlan:
        _validate_config(
            config,
            BaselineKind.STRUCTURED_DECOMPOSED,
            self.spec.bundle_version,
            self.spec.aggregation.version,
        )
        requests = tuple(
            build_judge_request(
                item,
                run_id=config.run_id,
                baseline=BaselineKind.STRUCTURED_DECOMPOSED,
                stage_id=stage.stage_id,
                prompt=stage.prompt,
            )
            for stage in self.spec.stages
        )
        return BaselinePlan(
            BaselineKind.STRUCTURED_DECOMPOSED.value,
            requests,
            self.spec.aggregation,
            item_id=item.item_id,
        )


@dataclass(frozen=True)
class StructuredSingleCallBaseline:
    """Proposed one-call evidence decomposition with a strict structured verdict."""

    prompt: PromptSpec

    def prepare(self, item: JudgeFacingInput, config: RunConfig) -> BaselinePlan:
        _validate_config(
            config,
            BaselineKind.STRUCTURED_SINGLE_CALL,
            self.prompt.version,
            "single-structured-verdict-1",
        )
        if config.parser_version != STRUCTURED_PARSER_VERSION:
            raise ContractError("single-call structured baseline requires its versioned parser")
        request = build_judge_request(
            item,
            run_id=config.run_id,
            baseline=BaselineKind.STRUCTURED_SINGLE_CALL,
            stage_id="structured_validity",
            prompt=self.prompt,
            response_contract_version=STRUCTURED_RESPONSE_CONTRACT,
        )
        return BaselinePlan(
            BaselineKind.STRUCTURED_SINGLE_CALL.value,
            (request,),
            StructuredSingleVerdictAggregator(),
            item_id=item.item_id,
        )
