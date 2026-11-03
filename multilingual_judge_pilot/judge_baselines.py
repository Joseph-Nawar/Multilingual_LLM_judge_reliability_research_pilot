"""Preparation interfaces for candidate judge baselines; no final prompts ship here."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, Sequence

from .judge_inference import (
    BaselineKind,
    ContractError,
    ConversationTurn,
    JudgeFacingInput,
    JudgeRequest,
    ParseResult,
    PromptSpec,
    ProviderIdentity,
    RunConfig,
    TranslationConfig,
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
class TranslationOutput:
    translated_turns: tuple[ConversationTurn, ...]
    raw_output: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.raw_output, str) or not self.raw_output:
            raise ContractError("translation output must retain a non-empty raw response")
        if not isinstance(self.latency_ms, (int, float)) or self.latency_ms < 0:
            raise ContractError("translation latency must be non-negative")
        for name, value in (("prompt_tokens", self.prompt_tokens), ("completion_tokens", self.completion_tokens)):
            if value is not None and (type(value) is not int or value < 0):
                raise ContractError(f"{name} must be a non-negative integer or absent")
        validate_cost_usd(self.cost_usd)


class Translator(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def translate(self, item: JudgeFacingInput, config: TranslationConfig) -> TranslationOutput: ...


@dataclass(frozen=True)
class TranslationRecord:
    translator_provider: str
    translator_model: str
    translator_version: str
    prompt_version: str
    target_language: str
    source_conversation_sha256: str
    translated_conversation_sha256: str
    raw_output: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: str | None

    def to_record(self) -> dict[str, object]:
        return {
            "translator_provider": self.translator_provider,
            "translator_model": self.translator_model,
            "translator_version": self.translator_version,
            "prompt_version": self.prompt_version,
            "target_language": self.target_language,
            "source_conversation_sha256": self.source_conversation_sha256,
            "translated_conversation_sha256": self.translated_conversation_sha256,
            "raw_output": self.raw_output,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
        }


@dataclass(frozen=True)
class BaselinePlan:
    baseline: str
    requests: tuple[JudgeRequest, ...]
    aggregation: VerdictAggregator
    translation_records: tuple[TranslationRecord, ...] = ()

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
        return BaselinePlan(BaselineKind.DIRECT_MULTILINGUAL.value, (request,), SingleVerdictAggregator())


@dataclass(frozen=True)
class TranslationFirstBaseline:
    """Translate via an injected translator, then judge with the same provider identity."""

    prompt: PromptSpec
    translator: Translator

    def prepare(self, item: JudgeFacingInput, config: RunConfig) -> BaselinePlan:
        _validate_config(config, BaselineKind.TRANSLATION_FIRST, self.prompt.version, "single-binary-verdict-1")
        translation_config = config.translation
        if translation_config is None:
            raise ContractError("translation-first baseline requires a translation configuration")
        if self.translator.identity != translation_config.translator:
            raise ContractError("translator identity does not match the versioned translation configuration")
        translated = self.translator.translate(item, translation_config)
        if len(translated.translated_turns) != len(item.conversation):
            raise ContractError("translation must preserve the number of turns")
        for original, output in zip(item.conversation, translated.translated_turns, strict=True):
            if (original.turn_index, original.speaker) != (output.turn_index, output.speaker):
                raise ContractError("translation must preserve turn chronology and speaker roles")
            if output.language != translation_config.pivot_language:
                raise ContractError("translation output language does not match configured pivot")

        source_hash = sha256(canonical_json([turn.to_record() for turn in item.conversation]).encode("utf-8")).hexdigest()
        translated_hash = sha256(canonical_json([turn.to_record() for turn in translated.translated_turns]).encode("utf-8")).hexdigest()
        translation_record = TranslationRecord(
            translator_provider=translation_config.translator.provider_id,
            translator_model=translation_config.translator.model_id,
            translator_version=translation_config.translator.model_version,
            prompt_version=translation_config.prompt_version,
            target_language=translation_config.pivot_language,
            source_conversation_sha256=source_hash,
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
            (translation_record,),
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
        )
