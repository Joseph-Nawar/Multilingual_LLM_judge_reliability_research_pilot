"""Synthetic-only contracts for the proposed P3 methodology v2."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from p3_synthetic_fixtures import fixture_input_manifest_sha256, synthetic_item


def _runtime():
    from multilingual_judge_pilot.judge_baselines import (
        StructuredSingleCallBaseline,
    )
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        ContractError,
        DeterministicMockProvider,
        JudgeExecutor,
        ParseStatus,
        PromptSpec,
        ProviderIdentity,
        ProviderResponse,
        RunConfig,
        BINARY_RESPONSE_CONTRACT,
        STRUCTURED_RESPONSE_CONTRACT,
        STRUCTURED_PARSER_VERSION,
        Verdict,
        parse_structured_verdict_response,
        response_schema,
    )
    from multilingual_judge_pilot.oracle_diagnostic import build_state_extraction_diagnostic

    return locals()


def _prompt(runtime):
    return runtime["PromptSpec"](
        "synthetic-structured-v1",
        "Synthetic fixture only. Assess the visible conversation and action.",
    )


def _config(runtime, provider=None, decoding=()):
    return runtime["RunConfig"](
        provider=provider or runtime["ProviderIdentity"]("mock", "fixture-judge", "1"),
        baseline="structured_single_call",
        prompt_bundle_version="synthetic-structured-v1",
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-test-revision",
        aggregation_version="single-structured-verdict-1",
        parser_version=runtime["STRUCTURED_PARSER_VERSION"],
        decoding_parameters=decoding,
    )


def _valid_structured(verdict="valid", *, tool="satisfied", assessment="satisfied"):
    return json.dumps(
        {
            "tool_contract": tool,
            "constraint_assessments": [
                {
                    "constraint_type": "permission",
                    "assessment": assessment,
                    "source_turn_indices": [0],
                }
            ],
            "verdict": verdict,
        }
    )


def test_single_call_structured_baseline_has_same_evidence_as_direct_and_one_call():
    runtime = _runtime()
    item = synthetic_item("EN-AR")
    prompt = _prompt(runtime)
    structured_config = _config(runtime)
    direct_config = replace(
        structured_config,
        baseline="direct_multilingual",
        aggregation_version="single-binary-verdict-1",
        prompt_bundle_version="synthetic-direct-v1",
        parser_version="p3-binary-json-verdict-1",
    )
    structured = runtime["StructuredSingleCallBaseline"](prompt).prepare(item, structured_config)
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline

    direct = DirectMultilingualBaseline(
        runtime["PromptSpec"]("synthetic-direct-v1", prompt.instruction)
    ).prepare(item, direct_config)
    structured_request = structured.requests[0]
    direct_request = direct.requests[0]
    assert len(structured.requests) == 1
    assert structured_request.conversation == direct_request.conversation
    assert structured_request.action == direct_request.action
    assert structured_request.public_tool_schema == direct_request.public_tool_schema
    assert structured_request.response_contract_version == "structured-validity-v1"
    assert direct_request.response_contract_version == "binary-verdict-v1"
    assert json.loads(structured_request.to_json())["conversation"][0]["turn_index"] == 0

    provider = runtime["DeterministicMockProvider"](
        structured_config.provider,
        [runtime["ProviderResponse"](_valid_structured("invalid", assessment="violated"))],
    )
    result = runtime["JudgeExecutor"](structured_config, provider).run(structured)
    assert result.final_result.verdict is runtime["Verdict"].INVALID
    assert result.final_result.structured_assessments[0].constraint_type == "permission"
    record = result.to_record()["steps"][0]
    assert record["response_contract_version"] == "structured-validity-v1"
    assert record["attempts"][0]["raw_response"] == _valid_structured("invalid", assessment="violated")
    assert len(provider.calls) == 1


def test_structured_parser_rejects_malformed_duplicate_out_of_range_and_contradictory_output():
    runtime = _runtime()
    parse = runtime["parse_structured_verdict_response"]
    assert parse(_valid_structured(), action_turn_index=2).verdict is runtime["Verdict"].VALID
    assert parse(_valid_structured("invalid", assessment="violated"), action_turn_index=2).verdict is runtime["Verdict"].INVALID
    assert parse(_valid_structured("valid", assessment="violated"), action_turn_index=2).status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse(_valid_structured("invalid"), action_turn_index=2).status is runtime["ParseStatus"].INVALID_OUTPUT
    uppercase_enum = _valid_structured().replace('"verdict": "valid"', '"verdict": "Valid"')
    assert parse(uppercase_enum, action_turn_index=2).status is runtime["ParseStatus"].INVALID_OUTPUT
    unordered_turns = _valid_structured().replace('[0]', '[1, 0]')
    assert parse(unordered_turns, action_turn_index=2).status is runtime["ParseStatus"].INVALID_OUTPUT
    out_of_range = _valid_structured().replace('"source_turn_indices": [0]', '"source_turn_indices": [1]')
    assert parse(out_of_range, action_turn_index=1).status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse(
        _valid_structured(), action_turn_index=2, observed_turn_indices=(1,)
    ).status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse('{"tool_contract":"satisfied","tool_contract":"violated"}', action_turn_index=2).status is runtime["ParseStatus"].INVALID_OUTPUT
    assert parse(None, action_turn_index=2).status is runtime["ParseStatus"].MISSING
    assert parse("{}", action_turn_index=2, provider_refused=True).status is runtime["ParseStatus"].REFUSED


def test_binary_and_structured_output_schemas_are_fixed_and_versioned():
    runtime = _runtime()
    binary = runtime["response_schema"](runtime["BINARY_RESPONSE_CONTRACT"])
    structured = runtime["response_schema"](runtime["STRUCTURED_RESPONSE_CONTRACT"])
    assert binary["required"] == ["verdict"]
    assert binary["additionalProperties"] is False
    assert structured["required"] == ["tool_contract", "constraint_assessments", "verdict"]
    assert structured["additionalProperties"] is False
    assessment = structured["properties"]["constraint_assessments"]["items"]
    assert assessment["required"] == ["constraint_type", "assessment", "source_turn_indices"]
    assert assessment["additionalProperties"] is False
    assert assessment["properties"]["source_turn_indices"]["minItems"] == 1


@pytest.mark.parametrize(
    "identity,decoding",
    [
        (
            ("openai", "gpt-6.1-sol", "stable-alias"),
            (("max_output_tokens", 1024), ("reasoning", {"effort": "low"}), ("store", False)),
        ),
        (
            ("anthropic", "claude-sonnet-5-5", "fixed-snapshot-alias"),
            (("max_tokens", 1024), ("output_config", {"effort": "low"})),
        ),
        (
            ("google", "gemini-3.8-flash", "stable-alias"),
            (("generation_config", {"max_output_tokens": 1024, "thinking_level": "low"}),),
        ),
    ],
)
def test_candidate_provider_specific_configuration_is_accepted(identity, decoding):
    runtime = _runtime()
    provider = runtime["ProviderIdentity"](*identity)
    config = _config(runtime, provider=provider, decoding=decoding)
    assert config.provider == provider


@pytest.mark.parametrize("unsupported", ["temperature", "top_p", "top_k"])
def test_claude_configuration_rejects_unsupported_sampling_parameters(unsupported):
    runtime = _runtime()
    provider = runtime["ProviderIdentity"]("anthropic", "claude-sonnet-5-5", "fixed-snapshot-alias")
    base = {"max_tokens": 1024, "output_config": {"effort": "low"}}
    base[unsupported] = 0
    with pytest.raises(runtime["ContractError"], match="unsupported|not accept"):
        _config(runtime, provider=provider, decoding=tuple(sorted(base.items())))


def test_candidate_provider_config_rejects_wrong_model_id_and_invalid_effort():
    runtime = _runtime()
    with pytest.raises(runtime["ContractError"], match="model ID"):
        _config(
            runtime,
            provider=runtime["ProviderIdentity"]("openai", "gpt-6.1-sol-not-real", "stable-alias"),
            decoding=(("max_output_tokens", 1024), ("reasoning", {"effort": "low"}), ("store", False)),
        )
    with pytest.raises(runtime["ContractError"], match="effort|thinking_level"):
        _config(
            runtime,
            provider=runtime["ProviderIdentity"]("google", "gemini-3.8-flash", "stable-alias"),
            decoding=(("generation_config", {"max_output_tokens": 1024, "thinking_level": "max"}),),
        )


def test_state_extraction_diagnostic_receives_evidence_but_no_reference_state_or_label():
    runtime = _runtime()
    item = synthetic_item("AR-EN")
    request = runtime["build_state_extraction_diagnostic"](
        item,
        prompt=runtime["PromptSpec"](
            "synthetic-state-extraction-v1", "Extract active constraints from the fictional fixture."
        ),
    )
    payload = json.loads(request.to_json())
    assert set(payload) == {
        "schema_version", "diagnostic_id", "item_id", "prompt_version", "instruction",
        "conversation", "action", "public_tool_schema", "response_schema",
    }
    assert "effective_state" not in payload
    assert "verdict" not in payload
    assert "oracle" not in json.dumps(payload).casefold()
    config = _config(runtime)
    provider = runtime["DeterministicMockProvider"](config.provider, [])
    with pytest.raises(TypeError, match="ordinary baseline plan"):
        runtime["JudgeExecutor"](config, provider).run(request)


def test_candidate_judge_configs_do_not_accept_cross_provider_settings():
    runtime = _runtime()
    provider = runtime["ProviderIdentity"]("anthropic", "claude-sonnet-5-5", "fixed-snapshot-alias")
    with pytest.raises(runtime["ContractError"]):
        _config(
            runtime,
            provider=provider,
            decoding=(("max_output_tokens", 1024), ("output_config", {"effort": "low"})),
        )


def test_v2_budget_call_counts_and_cost_arithmetic_match_the_proposal():
    proposal = json.loads(
        Path("docs/research/proposals/p3-experimental-config-proposals-v2.json").read_text(encoding="utf-8")
    )
    budget = proposal["budget_proposal"]
    counts = budget["call_counts_before_retries"]
    assert counts["per_backbone"]["ordinary_judging_total"] == 3 * 384
    assert counts["all_three_backbones"]["ordinary_judging_total"] == 3 * 1152
    assert counts["per_backbone"]["all_judge_calls"] == 1152 + 48
    assert counts["all_three_backbones"]["all_judge_calls"] == 3456 + 144
    assert counts["shared_translations"] == {
        "locked_arabic_bearing_inputs": 288,
        "independent_translation_quality_inputs_optional": 24,
        "total_assumed": 312,
    }
    assert counts["optional_all_backbones"] == {
        "state_extraction": 3 * 384,
        "oracle_state_intervention": 3 * 384,
        "three_call_decomposition_additional": 3 * 3 * 384,
    }

    rates = {
        "openai": (Decimal("2"), Decimal("10")),
        "anthropic": (Decimal("2"), Decimal("10")),
        "google": (Decimal("0.75"), Decimal("3.75")),
    }

    def charge(rate, token_pair, reasoning, number, factor):
        input_rate, output_rate = rate
        input_tokens, visible_output_tokens = map(Decimal, token_pair)
        billed_output = visible_output_tokens + Decimal(reasoning)
        return (input_tokens * input_rate + billed_output * output_rate) * Decimal(number) * Decimal(factor) / Decimal(1_000_000)

    for scenario, assumptions in budget["token_assumptions"].items():
        if scenario == "note":
            continue
        expected = budget["estimates_usd"]["current_intro_prices"][scenario]
        factor = Decimal(1) + Decimal(str(assumptions["retry_fraction"]))
        dt_tokens = assumptions["direct_translation_judge_input_output"]
        structured_tokens = assumptions["structured_judge_input_output"]
        screen_tokens = assumptions["competence_input_output"]
        reasoning = assumptions["reasoning_output_tokens"]
        per_model = {}
        for model in ("openai", "anthropic", "google"):
            per_model[model] = (
                charge(rates[model], dt_tokens, reasoning[model]["direct_translation"], 768, factor)
                + charge(rates[model], structured_tokens, reasoning[model]["structured"], 384, factor)
                + charge(rates[model], screen_tokens, reasoning[model]["screen"], 48, factor)
            )
        translation = charge(
            rates["google"],
            assumptions["translation_input_output"],
            reasoning["translator_google"],
            312,
            factor,
        )
        ordinary = sum(per_model.values()) + translation
        assert float(per_model["openai"]) == pytest.approx(expected["openai_ordinary_including_screen"], abs=0.0001)
        assert float(per_model["anthropic"]) == pytest.approx(expected["anthropic_ordinary_including_screen"], abs=0.0001)
        assert float(per_model["google"]) == pytest.approx(expected["google_ordinary_including_screen"], abs=0.0001)
        assert float(translation) == pytest.approx(expected["shared_translation"], abs=0.0001)
        assert float(ordinary) == pytest.approx(expected["ordinary_total"], abs=0.0001)

        h2_total = Decimal(0)
        decomposition_total = Decimal(0)
        extraction_tokens = assumptions["state_extraction_input_output"]
        oracle_tokens = assumptions["oracle_intervention_input_output"]
        criterion_tokens = assumptions["three_call_criterion_input_output"]
        for model in ("openai", "anthropic", "google"):
            h2_total += charge(
                rates[model], extraction_tokens, reasoning[model]["state_extraction"], 384, factor
            )
            h2_total += charge(
                rates[model], oracle_tokens, reasoning[model]["oracle_intervention"], 384, factor
            )
            decomposition_total += charge(
                rates[model], criterion_tokens, reasoning[model]["decomposition"], 1152, factor
            )
        assert float(h2_total) == pytest.approx(expected["optional_h2_all_models"], abs=0.0001)
        assert float(decomposition_total) == pytest.approx(expected["optional_three_call_all_models"], abs=0.0001)
        all_optional = ordinary + h2_total + decomposition_total
        assert float(all_optional) == pytest.approx(expected["all_optional_total"], abs=0.0001)

        future_google_rate = (Decimal("1.5"), Decimal("7.5"))
        future_google_ordinary = (
            charge(future_google_rate, dt_tokens, reasoning["google"]["direct_translation"], 768, factor)
            + charge(future_google_rate, structured_tokens, reasoning["google"]["structured"], 384, factor)
            + charge(future_google_rate, screen_tokens, reasoning["google"]["screen"], 48, factor)
        )
        future_translation = charge(
            future_google_rate,
            assumptions["translation_input_output"],
            reasoning["translator_google"],
            312,
            factor,
        )
        future_h2_google = (
            charge(future_google_rate, extraction_tokens, reasoning["google"]["state_extraction"], 384, factor)
            + charge(future_google_rate, oracle_tokens, reasoning["google"]["oracle_intervention"], 384, factor)
        )
        future_decomposition_google = charge(
            future_google_rate, criterion_tokens, reasoning["google"]["decomposition"], 1152, factor
        )
        future_ordinary = per_model["openai"] + per_model["anthropic"] + future_google_ordinary + future_translation
        future_all_optional = (
            future_ordinary
            + h2_total - charge(rates["google"], extraction_tokens, reasoning["google"]["state_extraction"], 384, factor)
            - charge(rates["google"], oracle_tokens, reasoning["google"]["oracle_intervention"], 384, factor)
            + future_h2_google
            + decomposition_total
            - charge(rates["google"], criterion_tokens, reasoning["google"]["decomposition"], 1152, factor)
            + future_decomposition_google
        )
        future_estimates = budget["estimates_usd"]["gemini_price_from_2027_01_01"]
        assert float(future_ordinary) == pytest.approx(future_estimates["ordinary_total"][scenario], abs=0.0001)
        assert float(future_all_optional) == pytest.approx(future_estimates["all_optional_total"][scenario], abs=0.0001)


def test_structured_run_configuration_serializes_reproducibly_without_credentials():
    runtime = _runtime()
    config = _config(runtime)
    first = config.to_manifest_json()
    assert first == config.to_manifest_json()
    manifest = json.loads(first)
    assert manifest["configuration_hash"] == config.config_hash
    assert manifest["config"]["parser_version"] == runtime["STRUCTURED_PARSER_VERSION"]
    assert "api_key" not in first.casefold()
    assert "synthetic-secret" not in first
