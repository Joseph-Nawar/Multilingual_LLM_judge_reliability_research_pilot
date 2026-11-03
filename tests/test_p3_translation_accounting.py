"""Synthetic-only translation execution and retry accounting checks."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from p3_synthetic_fixtures import english_fixture_translation, fixture_input_manifest_sha256, synthetic_item
from multilingual_judge_pilot.judge_baselines import (
    TranslationCallError,
    TranslationExecutionError,
    TranslationFirstBaseline,
    TranslationOutput,
)
from multilingual_judge_pilot.judge_inference import (
    DeterministicMockProvider,
    JudgeExecutor,
    ParseStatus,
    PromptSpec,
    ProviderIdentity,
    ProviderResponse,
    RetryPolicy,
    RunConfig,
    TranslationConfig,
    TranslationFailurePolicy,
)


def _config(*, retry_policy=None, failure_policy=TranslationFailurePolicy.RECORD_AND_SKIP_JUDGE):
    return RunConfig(
        provider=ProviderIdentity("mock", "translation-accounting-judge", "1"),
        baseline="translation_first",
        prompt_bundle_version="synthetic-translation-accounting-prompt-v1",
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-translation-accounting-test",
        translation=TranslationConfig(
            translator=ProviderIdentity("mock-translator", "translation-accounting-fixture", "1"),
            pivot_language="en",
            prompt_version="synthetic-translation-prompt-v1",
            retry_policy=retry_policy or RetryPolicy(),
            failure_policy=failure_policy,
        ),
    )


def _successful_translation(item):
    turns = tuple(
        replace(turn, language="en", content=english_fixture_translation(turn.content))
        for turn in item.conversation
    )
    raw = json.dumps([turn.content for turn in turns], ensure_ascii=False)
    return TranslationOutput(
        turns,
        raw,
        latency_ms=7.0,
        prompt_tokens=21,
        completion_tokens=25,
        cost_usd="0.0007",
    )


class _ScriptedTranslator:
    def __init__(self, identity, outcomes):
        self.identity = identity
        self.outcomes = list(outcomes)
        self.calls = 0

    def translate(self, item, config):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome(item) if callable(outcome) else outcome


def test_translation_retries_retain_failed_and_successful_attempt_records():
    config = _config(
        retry_policy=RetryPolicy(max_attempts=2, retryable_error_codes=("temporary_unavailable",))
    )
    item = synthetic_item("AR-EN")
    translator = _ScriptedTranslator(
        config.translation.translator,
        [
            TranslationCallError(
                "temporary_unavailable",
                raw_response='{"error":"temporary"}',
                prompt_tokens=11,
                completion_tokens=2,
                cost_usd="0.0001",
                message="provider detail must not be logged",
            ),
            _successful_translation,
        ],
    )
    utc_times = iter(
        (
            datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 3, 12, 0, 0, 250000, tzinfo=timezone.utc),
            datetime(2026, 11, 3, 12, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 11, 3, 12, 0, 1, 500000, tzinfo=timezone.utc),
        )
    )
    ticks = iter((1_000_000, 3_500_000, 4_000_000, 7_000_000))
    baseline = TranslationFirstBaseline(
        PromptSpec("synthetic-translation-accounting-prompt-v1", "SYNTHETIC ONLY"),
        translator,
        clock_ns=lambda: next(ticks),
        utc_now=lambda: next(utc_times),
        execution_id_factory=lambda: "synthetic-execution-001",
    )

    plan = baseline.prepare(item, config)
    provider = DeterministicMockProvider(
        config.provider,
        [ProviderResponse('{"verdict":"valid"}', prompt_tokens=31, completion_tokens=4)],
    )
    result = JudgeExecutor(config, provider).run(plan)

    attempts = result.translation_attempts
    assert translator.calls == 2
    assert [attempt.status for attempt in attempts] == ["failure", "success"]
    assert [attempt.error_category for attempt in attempts] == ["temporary_unavailable", None]
    assert [attempt.retry_decision for attempt in attempts] == ["retry", "stop"]
    assert attempts[0].raw_response == '{"error":"temporary"}'
    assert (attempts[0].prompt_tokens, attempts[0].completion_tokens, attempts[0].cost_usd) == (11, 2, "0.0001")
    assert (attempts[0].started_at_utc, attempts[0].completed_at_utc, attempts[0].latency_ms) == (
        "2026-11-03T12:00:00Z",
        "2026-11-03T12:00:00.250000Z",
        2.5,
    )
    assert attempts[1].translated_conversation_sha256
    assert attempts[0].translator_model == "translation-accounting-fixture"
    assert attempts[0].translation_prompt_version == "synthetic-translation-prompt-v1"
    assert attempts[0].input_id == item.item_id
    assert len(attempts[0].input_sha256) == 64
    assert [attempt.attempt_id for attempt in attempts] == [
        "synthetic-execution-001:translation:1",
        "synthetic-execution-001:translation:2",
    ]
    assert result.final_result.status is ParseStatus.PARSED
    assert result.terminal_stage == "judge"
    assert len(provider.calls) == 1

    serialized = json.loads(result.to_json())
    assert serialized["configuration_hash"] == config.config_hash
    assert serialized["run_id"] == config.run_id
    assert serialized["execution_id"] == "synthetic-execution-001"
    assert len(serialized["translation_attempts"]) == 2
    assert serialized["steps"][0]["attempts"][0]["execution_id"] == "synthetic-execution-001"
    assert serialized["steps"][0]["attempts"][0]["attempt_id"] == result.steps[0].attempts[0].attempt_id
    assert "provider detail must not be logged" not in result.to_json()


def test_exhausted_translation_failure_is_recorded_and_skips_judge_call():
    config = _config(
        retry_policy=RetryPolicy(max_attempts=2, retryable_error_codes=("temporary_unavailable",))
    )
    item = synthetic_item("AR-AR")
    translator = _ScriptedTranslator(
        config.translation.translator,
        [
            TranslationCallError("temporary_unavailable", raw_response="first failure"),
            TranslationCallError("temporary_unavailable", raw_response="second failure"),
        ],
    )
    plan = TranslationFirstBaseline(
        PromptSpec("synthetic-translation-accounting-prompt-v1", "SYNTHETIC ONLY"),
        translator,
        execution_id_factory=lambda: "synthetic-execution-failed",
    ).prepare(item, config)
    provider = DeterministicMockProvider(config.provider, [ProviderResponse('{"verdict":"valid"}')])

    result = JudgeExecutor(config, provider).run(plan)

    assert result.final_result.status is ParseStatus.PROVIDER_FAILURE
    assert result.terminal_stage == "translation"
    assert result.steps == ()
    assert len(result.translation_attempts) == 2
    assert [attempt.retry_decision for attempt in result.translation_attempts] == ["retry", "stop"]
    assert [attempt.raw_response for attempt in result.translation_attempts] == ["first failure", "second failure"]
    assert provider.calls == []
    assert len(json.loads(result.to_json())["translation_attempts"]) == 2


def test_non_retryable_translation_error_stops_after_one_recorded_attempt():
    config = _config(retry_policy=RetryPolicy(max_attempts=4, retryable_error_codes=("temporary_unavailable",)))
    translator = _ScriptedTranslator(
        config.translation.translator,
        [TranslationCallError("invalid_credentials", message="synthetic secret"), _successful_translation],
    )
    plan = TranslationFirstBaseline(
        PromptSpec("synthetic-translation-accounting-prompt-v1", "SYNTHETIC ONLY"),
        translator,
    ).prepare(synthetic_item("EN-AR"), config)

    assert translator.calls == 1
    assert len(plan.translation_attempts) == 1
    assert plan.translation_attempts[0].error_category == "invalid_credentials"
    assert plan.translation_attempts[0].retry_decision == "stop"
    assert "synthetic secret" not in json.dumps(plan.translation_attempts[0].to_record())


def test_raise_failure_policy_carries_serializable_translation_attempts():
    config = _config(
        failure_policy=TranslationFailurePolicy.RAISE_WITH_ATTEMPTS,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    translator = _ScriptedTranslator(
        config.translation.translator,
        [TranslationCallError("service_unavailable", raw_response="synthetic provider output")],
    )

    with pytest.raises(TranslationExecutionError) as raised:
        TranslationFirstBaseline(
            PromptSpec("synthetic-translation-accounting-prompt-v1", "SYNTHETIC ONLY"),
            translator,
            execution_id_factory=lambda: "synthetic-execution-raised",
        ).prepare(synthetic_item("AR-EN"), config)

    record = raised.value.to_record()
    assert record["execution_id"] == "synthetic-execution-raised"
    assert record["configuration_hash"] == config.config_hash
    assert record["translation_attempts"][0]["raw_response"] == "synthetic provider output"
    assert record["translation_attempts"][0]["retry_decision"] == "stop"


def test_malformed_translation_is_distinct_and_does_not_reach_judge():
    config = _config()
    item = synthetic_item("AR-EN")

    def malformed(item):
        translated = tuple(
            replace(turn, turn_index=turn.turn_index + 10, language="en", content="synthetic changed order")
            for turn in item.conversation
        )
        return TranslationOutput(translated, "synthetic malformed translation response", latency_ms=1.0)

    translator = _ScriptedTranslator(config.translation.translator, [malformed])
    plan = TranslationFirstBaseline(
        PromptSpec("synthetic-translation-accounting-prompt-v1", "SYNTHETIC ONLY"), translator
    ).prepare(item, config)
    provider = DeterministicMockProvider(config.provider, [ProviderResponse('{"verdict":"invalid"}')])

    result = JudgeExecutor(config, provider).run(plan)

    assert result.final_result.status is ParseStatus.PROVIDER_FAILURE
    assert result.terminal_stage == "translation"
    assert result.translation_attempts[0].status == "failure"
    assert result.translation_attempts[0].error_category == "invalid_translation_output"
    assert result.translation_attempts[0].raw_response == "synthetic malformed translation response"
    assert provider.calls == []


def test_identical_configuration_hashes_keep_individual_translation_executions_distinct():
    config = _config()
    item = synthetic_item("EN-AR")
    translator = _ScriptedTranslator(
        config.translation.translator,
        [_successful_translation, _successful_translation],
    )
    ids = iter(("synthetic-execution-a", "synthetic-execution-b"))
    baseline = TranslationFirstBaseline(
        PromptSpec("synthetic-translation-accounting-prompt-v1", "SYNTHETIC ONLY"),
        translator,
        execution_id_factory=lambda: next(ids),
    )

    first_plan = baseline.prepare(item, config)
    second_plan = baseline.prepare(item, config)
    first_provider = DeterministicMockProvider(config.provider, [ProviderResponse('{"verdict":"valid"}')])
    second_provider = DeterministicMockProvider(config.provider, [ProviderResponse('{"verdict":"valid"}')])
    first_run = JudgeExecutor(config, first_provider).run(first_plan)
    second_run = JudgeExecutor(config, second_provider).run(second_plan)

    assert first_run.configuration_hash == second_run.configuration_hash == config.config_hash
    assert first_run.run_id == second_run.run_id == config.run_id
    assert first_run.execution_id != second_run.execution_id
    assert first_run.translation_attempts[0].attempt_id != second_run.translation_attempts[0].attempt_id
    assert first_run.steps[0].attempts[0].attempt_id != second_run.steps[0].attempts[0].attempt_id
    assert first_run.steps[0].attempts[0].execution_id == first_run.execution_id
    assert first_run.translation_attempts[0].input_sha256 == second_run.translation_attempts[0].input_sha256
