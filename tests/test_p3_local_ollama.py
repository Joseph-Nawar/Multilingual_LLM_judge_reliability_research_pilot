"""Synthetic and mocked compatibility tests for the local Ollama adapters."""

from __future__ import annotations

import json
import pytest

from p3_synthetic_fixtures import CONDITION_LANGUAGES, fixture_input_manifest_sha256, synthetic_item


def _ollama_module():
    from multilingual_judge_pilot.local_ollama import (
        OLLAMA_DEFAULT_BASE_URL,
        OllamaLocalClient,
        OllamaLocalJudgeProvider,
        OllamaLocalTranslator,
        OllamaModelDescriptor,
    )

    return locals()


def _descriptor(module, model="qwen3.5:9b-q4_K_M", *, capabilities=("completion", "thinking")):
    return module["OllamaModelDescriptor"](
        model_tag=model,
        digest="sha256:" + "a" * 64,
        size_bytes=6_600_000_000,
        details={"format": "gguf", "family": "qwen3_5", "parameter_size": "9.0B", "quantization_level": "Q4_K_M", "context_length": 262144},
        capabilities=capabilities,
        template="{{ .System }}\n{{ .Prompt }}",
        parameters="num_ctx 4096",
    )


class _FakeClient:
    base_url = "http://127.0.0.1:11434"

    def __init__(self, descriptor, responses=()):
        self.descriptor = descriptor
        self.responses = list(responses)
        self.requests = []

    def discover_model(self, model_tag):
        assert model_tag == self.descriptor.model_tag
        return self.descriptor

    def chat(self, payload):
        self.requests.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_ollama_client_rejects_remote_and_non_loopback_endpoints():
    module = _ollama_module()
    with pytest.raises(ValueError, match="127.0.0.1"):
        module["OllamaLocalClient"]("https://example.invalid")
    with pytest.raises(ValueError, match="127.0.0.1"):
        module["OllamaLocalClient"]("http://localhost:11434")
    assert module["OLLAMA_DEFAULT_BASE_URL"] == "http://127.0.0.1:11434"


def test_ollama_judge_uses_schema_local_endpoint_and_preserves_response_metrics():
    module = _ollama_module()
    descriptor = _descriptor(module)
    client = _FakeClient(descriptor, [{
        "model": descriptor.model_tag,
        "message": {"role": "assistant", "content": '{"verdict":"valid"}'},
        "done": True,
        "prompt_eval_count": 39,
        "eval_count": 4,
        "prompt_eval_duration": 1_250_000_000,
        "eval_duration": 500_000_000,
        "load_duration": 2_000_000_000,
        "total_duration": 3_900_000_000,
    }])
    provider = module["OllamaLocalJudgeProvider"](client, descriptor.model_tag)
    request = {
        "response_contract_version": "binary-verdict-v1",
        "response_schema": __import__("multilingual_judge_pilot.judge_inference", fromlist=["response_schema"]).response_schema("binary-verdict-v1"),
        "item_id": "synthetic-item",
        "instruction": "Synthetic only: follow the validity rubric.",
        "conversation": [{"turn_index": 0, "speaker": "user", "content": "Synthetic request."}],
        "action": {"tool_name": "synthetic_tool", "value": "A"},
        "public_tool_schema": {"tool_name": "synthetic_tool", "required": ["value"]},
    }

    response = provider.complete(json.dumps(request), {"num_ctx": 4096, "num_predict": 48, "seed": 17, "temperature": 0.0, "think": False})

    payload = client.requests[0]
    assert payload["model"] == descriptor.model_tag
    assert payload["stream"] is False
    assert payload["format"] == request["response_schema"]
    assert payload["think"] is False
    assert payload["options"] == {"num_ctx": 4096, "num_predict": 48, "seed": 17, "temperature": 0.0}
    assert payload["messages"][0] == {"role": "system", "content": request["instruction"]}
    assert json.loads(payload["messages"][1]["content"]) == {
        key: request[key] for key in ("item_id", "conversation", "action", "public_tool_schema")
    }
    assert response.raw_response == '{"verdict":"valid"}'
    assert response.prompt_tokens == 39 and response.completion_tokens == 4
    assert response.prompt_eval_duration_ns == 1_250_000_000
    assert response.generation_duration_ns == 500_000_000
    assert response.load_duration_ns == 2_000_000_000
    assert response.total_duration_ns == 3_900_000_000
    assert provider.identity.model_version == descriptor.digest


def test_local_judge_rejects_reference_fields_unknown_fields_and_unsupported_thinking():
    module = _ollama_module()
    descriptor = _descriptor(module, capabilities=("completion",))
    client = _FakeClient(descriptor, [])
    provider = module["OllamaLocalJudgeProvider"](client, descriptor.model_tag)
    request = {
        "response_contract_version": "binary-verdict-v1",
        "response_schema": __import__("multilingual_judge_pilot.judge_inference", fromlist=["response_schema"]).response_schema("binary-verdict-v1"),
        "item_id": "synthetic-item",
        "instruction": "Synthetic instruction.",
        "conversation": [{"turn_index": 0, "speaker": "user", "content": "Synthetic."}],
        "action": {"tool_name": "synthetic_tool"},
        "public_tool_schema": {"tool_name": "synthetic_tool"},
        "effective_state": {"permission": "granted"},
    }
    with pytest.raises(ValueError, match="reference-only"):
        provider.complete(json.dumps(request), {"num_ctx": 4096, "num_predict": 32})
    request.pop("effective_state")
    with pytest.raises(ValueError, match="does not report thinking"):
        provider.complete(json.dumps(request), {"num_ctx": 4096, "num_predict": 32, "seed": 17, "temperature": 0.0, "think": False})
    assert client.requests == []


def test_translategemma_uses_official_prompt_format_and_preserves_roles_and_chronology():
    module = _ollama_module()
    descriptor = _descriptor(module, "translategemma:4b-it-q4_K_M", capabilities=("completion",))
    client = _FakeClient(descriptor, [
        {"message": {"content": "At the Synthetic Harbor, allow the observer to cancel order XJ-47."}, "done": True, "done_reason": "stop", "prompt_eval_count": 74, "eval_count": 14, "prompt_eval_duration": 900, "eval_duration": 500},
    ])
    translator = module["OllamaLocalTranslator"](client, descriptor.model_tag)
    item = synthetic_item("AR-EN")
    config_type = __import__("multilingual_judge_pilot.judge_inference", fromlist=["TranslationConfig", "ProviderIdentity", "TranslationFacingInput"])
    config = config_type.TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version="translategemma-ollama-official-prompt-literal-shield-v1",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 256), ("seed", 17), ("temperature", 0.0)),
    )

    translation_input = config_type.TranslationFacingInput.from_judge_input(item)
    assert not hasattr(translation_input, "action")
    assert not hasattr(translation_input, "public_tool_schema")
    output = translator.translate(translation_input, config)

    assert len(output.translated_turns) == len(item.conversation) == 2
    assert [(turn.turn_index, turn.speaker, turn.language) for turn in output.translated_turns] == [
        (turn.turn_index, turn.speaker, "en") for turn in item.conversation
    ]
    assert output.translated_turns[0].content.startswith("At the Synthetic Harbor")
    assert output.translated_turns[1].content == item.conversation[1].content
    assert len(client.requests) == 1
    user_prompt = client.requests[0]["messages"][0]["content"]
    assert user_prompt.startswith("You are a professional Arabic (ar) to English (en) translator.")
    assert "Produce only the English translation, without any additional explanations or commentary." in user_prompt
    assert "Please translate the following Arabic text into English:\n\n\n" in user_prompt
    assert item.conversation[0].content in user_prompt
    assert client.requests[0]["model"] == descriptor.model_tag


def test_local_translator_retains_failed_model_call_for_outer_failure_accounting():
    module = _ollama_module()
    descriptor = _descriptor(module, "translategemma:4b-it-q4_K_M", capabilities=("completion",))
    client = _FakeClient(descriptor, [RuntimeError("synthetic local connection failure")])
    translator = module["OllamaLocalTranslator"](client, descriptor.model_tag)
    from multilingual_judge_pilot.judge_inference import TranslationConfig, TranslationFacingInput

    config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version="translategemma-ollama-official-prompt-literal-shield-v1",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 256), ("seed", 17), ("temperature", 0.0)),
    )
    with pytest.raises(Exception, match="local_connection_failure") as caught:
        translator.translate(TranslationFacingInput.from_judge_input(synthetic_item("AR-EN")), config)
    records = getattr(caught.value, "provider_call_records", ())
    assert len(records) == 1
    assert records[0]["status"] == "failure"
    assert records[0]["error_category"] == "local_connection_failure"
    assert records[0]["raw_response"] is None
    assert records[0]["input_sha256"]


def test_local_translator_records_refusal_as_translation_failure():
    module = _ollama_module()
    descriptor = _descriptor(module, "translategemma:4b-it-q4_K_M", capabilities=("completion",))
    refusal = "Synthetic translator refusal."
    client = _FakeClient(descriptor, [{"message": {"content": "", "refusal": refusal}, "done": True}])
    translator = module["OllamaLocalTranslator"](client, descriptor.model_tag)
    from multilingual_judge_pilot.judge_inference import TranslationConfig, TranslationFacingInput

    config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version="translategemma-ollama-official-prompt-literal-shield-v1",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 256), ("seed", 17), ("temperature", 0.0)),
    )
    with pytest.raises(Exception, match="translation_refused") as caught:
        translator.translate(TranslationFacingInput.from_judge_input(synthetic_item("AR-EN")), config)
    record = caught.value.provider_call_records[0]
    assert record["status"] == "failure"
    assert record["error_category"] == "translation_refused"
    assert record["raw_response"] == refusal


def test_translategemma_literal_shield_preserves_numbers_dates_currency_and_ids():
    from multilingual_judge_pilot.local_ollama import _restore_literals, _shield_literals

    original = "للطلب MK-204، المبلغ 240 EGP، الموعد 10:30 UTC، والتاريخ 2031-05-12."
    protected, literals = _shield_literals(original)
    assert "MK-204" not in protected and "240" not in protected and "2031-05-12" not in protected
    assert len(literals) == 6
    assert _restore_literals(protected, literals) == original
    with pytest.raises(ValueError, match="protected_literal_mismatch"):
        _restore_literals(protected.replace(literals[0][0], "MISSING"), literals)


def test_translation_first_serializes_local_subattempts_and_judge_provider_timings():
    module = _ollama_module()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline, TranslationFirstBaseline
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        DeterministicMockProvider,
        JudgeExecutor,
        PromptSpec,
        ProviderIdentity,
        ProviderResponse,
        RetryPolicy,
        RunConfig,
        TranslationConfig,
        TranslationFailurePolicy,
    )

    translator_descriptor = _descriptor(module, "translategemma:4b-it-q4_K_M", capabilities=("completion",))
    failed_translator = module["OllamaLocalTranslator"](
        _FakeClient(translator_descriptor, [RuntimeError("synthetic connection issue")]),
        translator_descriptor.model_tag,
    )
    judge_identity = ProviderIdentity("mock", "synthetic-judge", "1")
    translation_config = TranslationConfig(
        translator=failed_translator.identity,
        pivot_language="en",
        prompt_version="translategemma-ollama-official-prompt-literal-shield-v1",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 256), ("seed", 17), ("temperature", 0.0)),
        retry_policy=RetryPolicy(max_attempts=1),
        failure_policy=TranslationFailurePolicy.RECORD_AND_SKIP_JUDGE,
    )
    config = RunConfig(
        provider=judge_identity,
        baseline=BaselineKind.TRANSLATION_FIRST.value,
        prompt_bundle_version="synthetic-test-prompt-v1",
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-only-test",
        translation=translation_config,
    )
    prompt = PromptSpec("synthetic-test-prompt-v1", "Synthetic only: assess the fictional action.")
    plan = TranslationFirstBaseline(prompt, failed_translator).prepare(synthetic_item("AR-EN"), config)
    result = JudgeExecutor(config, DeterministicMockProvider(judge_identity, [])).run(plan)
    nested = result.to_record()["translation_attempts"][0]["provider_call_records"]
    assert result.steps == ()
    assert nested[0]["status"] == "failure"
    assert nested[0]["attempt_number"] == 1
    assert nested[0]["translator"]["model_version"] == translator_descriptor.digest

    judge_descriptor = _descriptor(module)
    judge = module["OllamaLocalJudgeProvider"](
        _FakeClient(judge_descriptor, [{
            "message": {"content": '{"verdict":"valid"}'},
            "prompt_eval_count": 14,
            "eval_count": 4,
            "prompt_eval_duration": 700,
            "eval_duration": 300,
            "load_duration": 1100,
            "total_duration": 2300,
        }]),
        judge_descriptor.model_tag,
    )
    direct_config = RunConfig(
        provider=judge.identity,
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-only-test",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 64), ("seed", 17), ("temperature", 0.0), ("think", False)),
    )
    direct_plan = DirectMultilingualBaseline(prompt).prepare(synthetic_item("EN-AR"), direct_config)
    direct_result = JudgeExecutor(direct_config, judge).run(direct_plan)
    attempt = direct_result.to_record()["steps"][0]["attempts"][0]
    assert attempt["prompt_eval_duration_ns"] == 700
    assert attempt["generation_duration_ns"] == 300
    assert attempt["load_duration_ns"] == 1100
    assert attempt["total_duration_ns"] == 2300
    assert attempt["raw_response"] == '{"verdict":"valid"}'
    assert attempt["cost_usd"] == "0"


def test_local_judge_marks_output_limit_termination_as_invalid_and_retains_raw_text():
    module = _ollama_module()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        JudgeExecutor,
        PromptSpec,
        RunConfig,
    )

    descriptor = _descriptor(module)
    provider = module["OllamaLocalJudgeProvider"](_FakeClient(descriptor, [{
        "message": {"content": '{"verdict":"valid"}'},
        "done": True,
        "done_reason": "length",
        "prompt_eval_count": 12,
        "eval_count": 4,
        "prompt_eval_duration": 500,
        "eval_duration": 100,
    }]), descriptor.model_tag)
    prompt = PromptSpec("synthetic-local-incomplete-v1", "Synthetic only: check the fictional action.")
    config = RunConfig(
        provider=provider.identity,
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-only-test",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 4), ("seed", 17), ("temperature", 0.0), ("think", False)),
    )
    plan = DirectMultilingualBaseline(prompt).prepare(synthetic_item("EN-AR"), config)
    result = JudgeExecutor(config, provider).run(plan)
    attempt = result.to_record()["steps"][0]["attempts"][0]
    assert attempt["parse_status"] == "invalid_output"
    assert attempt["response_incomplete"] is True
    assert attempt["completion_reason"] == "length"
    assert attempt["raw_response"] == '{"verdict":"valid"}'


def test_local_judge_preserves_provider_refusal_as_distinct_status():
    module = _ollama_module()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        JudgeExecutor,
        ParseStatus,
        PromptSpec,
        RunConfig,
    )

    descriptor = _descriptor(module)
    provider = module["OllamaLocalJudgeProvider"](_FakeClient(descriptor, [{
        "message": {"role": "assistant", "content": "", "refusal": "Synthetic safety refusal."},
        "done": True,
        "done_reason": "stop",
    }]), descriptor.model_tag)
    prompt = PromptSpec("synthetic-local-refusal-v1", "Synthetic only: assess the fictional action.")
    config = RunConfig(
        provider=provider.identity,
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-only-test",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 64), ("seed", 17), ("temperature", 0.0), ("think", False)),
    )
    plan = DirectMultilingualBaseline(prompt).prepare(synthetic_item("EN-AR"), config)
    result = JudgeExecutor(config, provider).run(plan)
    attempt = result.to_record()["steps"][0]["attempts"][0]
    assert result.final_result.status is ParseStatus.REFUSED
    assert attempt["parse_status"] == "refused"
    assert attempt["provider_refused"] is True
    assert attempt["raw_response"] == "Synthetic safety refusal."


def test_local_ollama_provider_retry_preserves_failed_http_response_and_execution_ids():
    module = _ollama_module()
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        JudgeExecutor,
        PromptSpec,
        RetryPolicy,
        RunConfig,
        Verdict,
    )
    from multilingual_judge_pilot.local_ollama import OllamaLocalError

    descriptor = _descriptor(module)
    client = _FakeClient(descriptor, [
        OllamaLocalError("local_timeout", raw_response='{"error":"synthetic timeout"}'),
        {"message": {"content": '{"verdict":"valid"}'}, "done": True, "done_reason": "stop"},
    ])
    provider = module["OllamaLocalJudgeProvider"](client, descriptor.model_tag)
    prompt = PromptSpec("synthetic-local-retry-v1", "Synthetic only: assess this fictional action.")
    config = RunConfig(
        provider=provider.identity,
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-only-test",
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 64), ("seed", 17), ("temperature", 0.0), ("think", False)),
        retry_policy=RetryPolicy(max_attempts=2, retryable_error_codes=("local_timeout",)),
    )
    plan = DirectMultilingualBaseline(prompt).prepare(synthetic_item("EN-EN"), config)
    result = JudgeExecutor(config, provider).run(plan)
    attempts = result.to_record()["steps"][0]["attempts"]
    assert result.final_result.verdict is Verdict.VALID
    assert len(attempts) == 2
    assert attempts[0]["failure_code"] == "local_timeout"
    assert attempts[0]["raw_response"] == '{"error":"synthetic timeout"}'
    assert attempts[0]["attempt_id"] != attempts[1]["attempt_id"]


def test_local_identity_and_config_are_digest_bound_and_seeded():
    module = _ollama_module()
    descriptor = _descriptor(module)
    provider = module["OllamaLocalJudgeProvider"](_FakeClient(descriptor, []), descriptor.model_tag)
    assert provider.identity.provider_id == "ollama-local"
    assert provider.identity.model_version == descriptor.digest
    assert CONDITION_LANGUAGES["EN-AR"] == ("en", "ar")
    assert fixture_input_manifest_sha256()


def test_local_smoke_inventory_covers_four_conditions_without_synthetic_labels_in_requests():
    from p3_local_smoke_fixtures import CASES, CONDITION_LANGUAGES, local_smoke_items

    rows = local_smoke_items()
    assert len(rows) == 16
    assert {condition for _case, condition, _item in rows} == set(CONDITION_LANGUAGES)
    assert {case for case, _condition, _item in rows} == set(CASES)
    for _case, condition, item in rows:
        assert (item.conversation[0].language, item.conversation[1].language) == CONDITION_LANGUAGES[condition]
        assert condition.casefold() not in item.item_id.casefold()
        assert "expected_valid" not in item.evidence_record()
        assert "reference" not in json.dumps(item.evidence_record()).casefold()


def test_smoke_cleanup_only_stops_models_started_by_the_smoke(monkeypatch):
    from scripts import p3_local_compatibility_smoke as smoke

    calls = []
    monkeypatch.setattr(smoke, "_loaded_model_tags", lambda: ["unrelated-local-model", smoke.MODEL_TAGS[0]])
    monkeypatch.setattr(smoke, "_run_command", lambda args: calls.append(args) or "stopped")
    smoke._stop_any_loaded_models()
    assert calls == [["ollama", "stop", smoke.MODEL_TAGS[0]]]
