"""Synthetic-only checks for the limited P3 infrastructure preparation slice."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from p3_synthetic_fixtures import (
    CONDITION_LANGUAGES,
    english_fixture_translation,
    fixture_input_manifest_sha256,
    synthetic_item,
)


def _runtime():
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline, TranslationOutput
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        DeterministicMockProvider,
        JudgeFacingInput,
        JudgeExecutor,
        ParseStatus,
        PromptSpec,
        ProviderCallError,
        ProviderIdentity,
        ProviderResponse,
        ResponseStatus,
        RetryPolicy,
        RunConfig,
        TranslationConfig,
        Verdict,
        parse_verdict_response,
    )

    return {**locals(), "DirectMultilingualBaseline": DirectMultilingualBaseline, "TranslationOutput": TranslationOutput}


def _prompt(runtime, version="synthetic-test-prompt-v1"):
    return runtime["PromptSpec"](
        version=version,
        instruction="SYNTHETIC TEST ONLY: return a JSON verdict for the fictional exhibit action.",
    )


def _config(runtime, baseline="direct_multilingual", **overrides):
    values = {
        "provider": runtime["ProviderIdentity"]("mock", "fixed-fixture-judge", "1"),
        "baseline": baseline,
        "prompt_bundle_version": "synthetic-test-prompt-v1",
        "input_manifest_sha256": fixture_input_manifest_sha256(),
        "code_revision": "synthetic-test-revision",
    }
    if baseline == "structured_decomposed":
        values["aggregation_version"] = "synthetic-aggregation-only-v1"
    values.update(overrides)
    return runtime["RunConfig"](**values)


def test_four_synthetic_language_conditions_map_initial_and_decisive_languages():
    assert CONDITION_LANGUAGES == {
        "EN-EN": ("en", "en"),
        "AR-AR": ("ar", "ar"),
        "EN-AR": ("en", "ar"),
        "AR-EN": ("ar", "en"),
    }
    for condition, expected in CONDITION_LANGUAGES.items():
        item = synthetic_item(condition)
        assert (item.conversation[0].language, item.conversation[1].language) == expected
        assert item.language_condition == condition


def test_request_is_an_allowlist_and_rejects_reference_fields_at_any_depth():
    runtime = _runtime()
    original = {
        "item_id": "synthetic-lunar-archive-en-en",
        "language_condition": "EN-EN",
        "action_turn_index": 2,
        "conversation": [
            {"turn_index": 0, "speaker": "user", "language": "en", "content": "Synthetic exhibit request."}
        ],
        "action": {"tool_name": "sequence_exhibit_cards", "order": ["A", "B"]},
        "public_tool_schema": {"tool_name": "sequence_exhibit_cards", "required": ["order"]},
    }
    item = runtime["JudgeFacingInput"].from_mapping(original)
    payload = json.loads(runtime["DirectMultilingualBaseline"](_prompt(runtime)).prepare(
        item, _config(runtime)
    ).requests[0].to_json())
    assert set(payload) == {
        "response_contract_version", "response_schema", "item_id", "instruction", "conversation", "action", "public_tool_schema"
    }
    assert "language_condition" not in payload
    assert "action_turn_index" not in payload
    assert "baseline" not in payload and "stage_id" not in payload and "prompt_version" not in payload

    for key in ("gold_label", "oracle_verdict", "effective_state", "canonical_state", "reference_label"):
        leaked = dict(original)
        leaked[key] = "forbidden"
        with pytest.raises(ValueError, match="reference-only|unknown field"):
            runtime["JudgeFacingInput"].from_mapping(leaked)
    leaked_nested = dict(original)
    leaked_nested["action"] = {"tool_name": "sequence_exhibit_cards", "gold_label": "valid"}
    with pytest.raises(ValueError, match="reference-only"):
        runtime["JudgeFacingInput"].from_mapping(leaked_nested)


def test_request_rejects_turns_at_or_after_action_instead_of_truncating():
    runtime = _runtime()
    item = synthetic_item()
    with pytest.raises(ValueError, match="before the action decision point"):
        runtime["JudgeFacingInput"].from_mapping(
            {
                "item_id": item.item_id,
                "language_condition": item.language_condition,
                "action_turn_index": 1,
                "conversation": [
                    {"turn_index": 0, "speaker": "user", "language": "en", "content": "Synthetic."},
                    {"turn_index": 1, "speaker": "user", "language": "en", "content": "Synthetic decisive turn."},
                ],
                "action": {"tool_name": "sequence_exhibit_cards"},
                "public_tool_schema": {"tool_name": "sequence_exhibit_cards"},
            }
        )


def test_binary_verdict_parser_keeps_valid_invalid_malformed_missing_and_refused_distinct():
    runtime = _runtime()
    parse = runtime["parse_verdict_response"]
    assert parse('{"verdict":"valid"}').verdict is runtime["Verdict"].VALID
    assert parse('{"verdict":"invalid"}').verdict is runtime["Verdict"].INVALID
    assert parse('{"verdict":"maybe"}').status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse('{"verdict":"valid","reason":"extra"}').status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse('{"verdict":"valid","verdict":"invalid"}').status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse("not JSON").status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse(None).status is runtime["ParseStatus"].MISSING
    assert parse('{"refusal":"I cannot assess this synthetic request."}').status is runtime["ParseStatus"].REFUSED
    assert parse("provider refusal text", provider_refused=True).status is runtime["ParseStatus"].REFUSED


def test_run_manifest_serialization_and_run_id_are_deterministic_and_credential_free():
    runtime = _runtime()
    config = _config(runtime)
    first = config.to_manifest_json()
    assert first == config.to_manifest_json()
    payload = json.loads(first)
    assert payload["run_id"].startswith("run-")
    assert payload["configuration_hash"] == config.config_hash
    assert payload["config"]["provider"] == {"provider_id": "mock", "model_id": "fixed-fixture-judge", "model_version": "1"}
    assert payload["config"]["retry_policy"]["version"] == "retry-policy-1"
    assert payload["config"]["aggregation_version"] == "single-binary-verdict-1"
    changed = replace(config, random_seed=17)
    assert changed.run_id != config.run_id
    with pytest.raises(ValueError, match="credential-shaped"):
        _config(runtime, decoding_parameters=(("api_key", "synthetic-secret"),))
    with pytest.raises(ValueError, match="unique"):
        _config(runtime, decoding_parameters=(("temperature", 0), ("temperature", 1)))


def test_direct_baseline_retains_raw_output_usage_timing_and_cost():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline

    item = synthetic_item("EN-AR")
    config = _config(runtime, decoding_parameters=(("max_tokens", 32), ("temperature", 0.0)))
    baseline = DirectMultilingualBaseline(_prompt(runtime))
    plan = baseline.prepare(item, config)
    provider = runtime["DeterministicMockProvider"](
        config.provider,
        [runtime["ProviderResponse"]('{"verdict":"valid"}', prompt_tokens=23, completion_tokens=4, cost_usd="0.0012")],
    )
    mismatched = runtime["DeterministicMockProvider"](
        runtime["ProviderIdentity"]("mock", "different-fixture-judge", "1"), []
    )
    with pytest.raises(ValueError, match="identity does not match"):
        runtime["JudgeExecutor"](config, mismatched)
    clock = iter((1_000_000_000, 1_004_000_000))
    result = runtime["JudgeExecutor"](config, provider, clock_ns=lambda: next(clock)).run(plan)
    assert result.final_result.verdict is runtime["Verdict"].VALID
    attempt = result.steps[0].attempts[0]
    assert attempt.raw_response == '{"verdict":"valid"}'
    assert (attempt.prompt_tokens, attempt.completion_tokens, attempt.cost_usd, attempt.latency_ms) == (23, 4, "0.0012", 4.0)
    assert provider.calls[0][1] == {"max_tokens": 32, "temperature": 0.0}
    step = result.to_record()["steps"][0]
    assert step["prompt_version"] == "synthetic-test-prompt-v1"
    assert set(json.loads(step["request_json"])) == {
        "response_contract_version", "response_schema", "item_id", "instruction", "conversation", "action", "public_tool_schema"
    }
    assert json.loads(result.to_json())["steps"][0]["attempts"][0]["raw_response"] == '{"verdict":"valid"}'


def test_translation_first_preserves_translator_provenance_and_same_action_tool_evidence():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import TranslationFirstBaseline

    class SyntheticFixtureTranslator:
        def __init__(self, identity):
            self.identity = identity

        def translate(self, item, config):
            assert not hasattr(item, "action")
            assert not hasattr(item, "public_tool_schema")
            assert not hasattr(item, "language_condition")
            from multilingual_judge_pilot.judge_baselines import TranslationOutput
            from p3_synthetic_fixtures import english_fixture_translation

            turns = tuple(replace(turn, language="en", content=english_fixture_translation(turn.content)) for turn in item.conversation)
            raw = json.dumps([turn.content for turn in turns], ensure_ascii=False)
            return TranslationOutput(turns, raw, latency_ms=2.0, prompt_tokens=16, completion_tokens=18, cost_usd="0.0004")

    judge_config = _config(runtime, baseline="translation_first", translation=runtime["TranslationConfig"](
        translator=runtime["ProviderIdentity"]("mock-translator", "fixture-translation", "1"),
        pivot_language="en",
        prompt_version="synthetic-translation-prompt-v1",
    ))
    translator = SyntheticFixtureTranslator(judge_config.translation.translator)
    baseline = TranslationFirstBaseline(_prompt(runtime), translator)
    mismatched_translator = SyntheticFixtureTranslator(
        runtime["ProviderIdentity"]("mock-translator", "different-fixture-translator", "1")
    )
    with pytest.raises(ValueError, match="translator identity does not match"):
        TranslationFirstBaseline(_prompt(runtime), mismatched_translator).prepare(
            synthetic_item("AR-EN"), judge_config
        )
    plan = baseline.prepare(synthetic_item("AR-EN"), judge_config)
    request = plan.requests[0]
    assert all(turn.language == "en" for turn in request.conversation)
    assert request.action == synthetic_item("AR-EN").action
    assert request.public_tool_schema == synthetic_item("AR-EN").public_tool_schema
    assert plan.translation_records[0].raw_output == json.dumps(
        [english_fixture_translation(synthetic_item("AR-EN").conversation[i].content) for i in range(2)], ensure_ascii=False
    )
    provider = runtime["DeterministicMockProvider"](judge_config.provider, [runtime["ProviderResponse"]('{"verdict":"invalid"}')])
    result = runtime["JudgeExecutor"](judge_config, provider).run(plan)
    assert result.final_result.verdict is runtime["Verdict"].INVALID
    assert result.translation_records[0].translator_model == "fixture-translation"


def test_structured_decomposition_uses_same_underlying_evidence_and_explicit_aggregation():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import (
        DecompositionSpec,
        DecompositionStage,
        StructuredDecomposedBaseline,
    )

    class SyntheticAggregator:
        version = "synthetic-aggregation-only-v1"

        def aggregate(self, results):
            return results[-1]

    config = _config(
        runtime,
        baseline="structured_decomposed",
        prompt_bundle_version="synthetic-decomposition-v1",
        aggregation_version="synthetic-aggregation-only-v1",
    )
    spec = DecompositionSpec(
        bundle_version="synthetic-decomposition-v1",
        stages=(
            DecompositionStage("synthetic-stage-a", _prompt(runtime, "synthetic-stage-a-v1")),
            DecompositionStage("synthetic-stage-b", _prompt(runtime, "synthetic-stage-b-v1")),
        ),
        aggregation=SyntheticAggregator(),
    )
    plan = StructuredDecomposedBaseline(spec).prepare(synthetic_item(), config)
    assert [request.stage_id for request in plan.requests] == ["synthetic-stage-a", "synthetic-stage-b"]
    assert plan.requests[0].conversation == plan.requests[1].conversation
    assert plan.requests[0].action == plan.requests[1].action
    assert plan.requests[0].public_tool_schema == plan.requests[1].public_tool_schema

    direct_config = _config(runtime)
    direct_request = runtime["DirectMultilingualBaseline"](_prompt(runtime)).prepare(synthetic_item(), direct_config).requests[0]
    assert plan.requests[0].conversation == direct_request.conversation
    assert plan.requests[0].action == direct_request.action
    assert plan.requests[0].public_tool_schema == direct_request.public_tool_schema

    provider = runtime["DeterministicMockProvider"](
        config.provider,
        [runtime["ProviderResponse"]('{"verdict":"invalid"}'), runtime["ProviderResponse"]('{"verdict":"valid"}')],
    )
    result = runtime["JudgeExecutor"](config, provider).run(plan)
    assert result.final_result.verdict is runtime["Verdict"].VALID
    assert result.aggregation_version == "synthetic-aggregation-only-v1"


def test_retry_accounting_retries_only_configured_provider_failures_and_keeps_every_attempt():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline

    config = _config(runtime, retry_policy=runtime["RetryPolicy"](max_attempts=3, retryable_error_codes=("temporary_unavailable",)))
    plan = DirectMultilingualBaseline(_prompt(runtime)).prepare(synthetic_item(), config)
    provider = runtime["DeterministicMockProvider"](
        config.provider,
        [
            runtime["ProviderCallError"]("temporary_unavailable"),
            runtime["ProviderCallError"]("temporary_unavailable"),
            runtime["ProviderResponse"]('{"verdict":"valid"}'),
        ],
    )
    result = runtime["JudgeExecutor"](config, provider).run(plan)
    assert len(provider.calls) == 3
    assert [attempt.failure_code for attempt in result.steps[0].attempts] == ["temporary_unavailable", "temporary_unavailable", None]
    assert result.final_result.verdict is runtime["Verdict"].VALID

    malformed_provider = runtime["DeterministicMockProvider"](
        config.provider,
        [runtime["ProviderResponse"]('{"verdict":"yes"}'), runtime["ProviderResponse"]('{"verdict":"valid"}')],
    )
    malformed = runtime["JudgeExecutor"](config, malformed_provider).run(plan)
    assert len(malformed_provider.calls) == 1
    assert malformed.final_result.status is runtime["ParseStatus"].INVALID_OUTPUT

    refused_provider = runtime["DeterministicMockProvider"](
        config.provider,
        [runtime["ProviderResponse"]("provider refusal", refused=True), runtime["ProviderResponse"]('{"verdict":"valid"}')],
    )
    refused = runtime["JudgeExecutor"](config, refused_provider).run(plan)
    assert len(refused_provider.calls) == 1
    assert refused.final_result.status is runtime["ParseStatus"].REFUSED
    assert refused.steps[0].attempts[0].provider_refused is True

    exhausted_provider = runtime["DeterministicMockProvider"](
        config.provider,
        [runtime["ProviderCallError"]("temporary_unavailable"), runtime["ProviderCallError"]("temporary_unavailable")],
    )
    exhausted_config = replace(config, retry_policy=runtime["RetryPolicy"](max_attempts=2, retryable_error_codes=("temporary_unavailable",)))
    exhausted = runtime["JudgeExecutor"](exhausted_config, exhausted_provider).run(plan)
    assert len(exhausted.steps[0].attempts) == 2
    assert exhausted.final_result.status is runtime["ParseStatus"].PROVIDER_FAILURE


def test_reference_scorer_is_separate_from_requests_and_preserves_unparsed_statuses():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline
    from multilingual_judge_pilot.reference_scoring import score_run

    config = _config(runtime)
    plan = DirectMultilingualBaseline(_prompt(runtime)).prepare(synthetic_item(), config)
    provider = runtime["DeterministicMockProvider"](config.provider, [runtime["ProviderResponse"]('{"verdict":"valid"}')])
    result = runtime["JudgeExecutor"](config, provider).run(plan)
    assert "reference" not in result.to_json().casefold()
    scored = score_run(result, {result.item_id: runtime["Verdict"].VALID})
    assert scored.is_correct is True
    assert scored.response_status is runtime["ParseStatus"].PARSED
    assert scored.execution_id == result.execution_id
    assert scored.configuration_hash == result.configuration_hash
    assert scored.terminal_stage == "judge"

    invalid_output_provider = runtime["DeterministicMockProvider"](config.provider, [runtime["ProviderResponse"]("bad output")])
    invalid_output = runtime["JudgeExecutor"](config, invalid_output_provider).run(plan)
    unscored = score_run(invalid_output, {invalid_output.item_id: runtime["Verdict"].VALID})
    assert unscored.is_correct is None
    assert unscored.response_status is runtime["ParseStatus"].INVALID_OUTPUT


def test_oracle_state_diagnostic_has_a_separate_type_and_cannot_enter_ordinary_runner():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline
    from multilingual_judge_pilot.oracle_diagnostic import OracleStateDiagnosticRequest, build_oracle_state_diagnostic

    item = synthetic_item()
    diagnostic = build_oracle_state_diagnostic(
        item,
        effective_state={"active_requirements": [{"kind": "display_order", "before": "amber-planet", "after": "teal-comet"}]},
        prompt=_prompt(runtime),
    )
    assert isinstance(diagnostic, OracleStateDiagnosticRequest)
    assert "gold_label" not in diagnostic.to_json()
    assert "oracle_verdict" not in diagnostic.to_json()
    assert "effective_state" in diagnostic.to_json()

    config = _config(runtime)
    plan = DirectMultilingualBaseline(_prompt(runtime)).prepare(item, config)
    provider = runtime["DeterministicMockProvider"](config.provider, [])
    with pytest.raises(TypeError, match="ordinary baseline plan"):
        runtime["JudgeExecutor"](config, provider).run(diagnostic)


def test_nonretryable_failure_is_counted_without_raw_exception_text_or_secret_leakage():
    runtime = _runtime()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline

    config = _config(runtime, retry_policy=runtime["RetryPolicy"](max_attempts=4, retryable_error_codes=("temporary_unavailable",)))
    plan = DirectMultilingualBaseline(_prompt(runtime)).prepare(synthetic_item(), config)
    provider = runtime["DeterministicMockProvider"](config.provider, [runtime["ProviderCallError"]("unauthorized")])
    result = runtime["JudgeExecutor"](config, provider).run(plan)
    assert len(provider.calls) == 1
    assert result.final_result.status is runtime["ParseStatus"].PROVIDER_FAILURE
    serialized = result.to_json()
    assert "unauthorized" in serialized
    assert "synthetic-secret" not in serialized
