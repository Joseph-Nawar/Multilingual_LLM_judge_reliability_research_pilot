"""Synthetic contracts for proposed local-method stabilization."""

from __future__ import annotations

import json

import pytest

from p3_synthetic_fixtures import fixture_input_manifest_sha256, synthetic_item


def _v2_contract():
    from multilingual_judge_pilot.judge_inference import (
        STRUCTURED_PARSER_VERSION_V2,
        STRUCTURED_RESPONSE_CONTRACT_V2,
        parse_structured_verdict_response,
        response_schema,
    )

    return STRUCTURED_PARSER_VERSION_V2, STRUCTURED_RESPONSE_CONTRACT_V2, parse_structured_verdict_response, response_schema


def test_structured_v2_schema_lists_only_applicable_requirements_and_rejects_not_applicable():
    parser_version, contract_version, parse, schema = _v2_contract()
    response_schema_v2 = schema(contract_version)
    assessment_schema = response_schema_v2["properties"]["constraint_assessments"]["items"]["properties"]["assessment"]
    assert assessment_schema["enum"] == ["satisfied", "violated"]
    assert response_schema_v2["properties"]["constraint_assessments"]["minItems"] == 0

    good = {
        "tool_contract": "satisfied",
        "constraint_assessments": [{
            "constraint_type": "permission",
            "assessment": "satisfied",
            "source_turn_indices": [0],
        }],
        "verdict": "valid",
    }
    assert parse(json.dumps(good), action_turn_index=2, contract_version=contract_version).verdict.value == "valid"
    good["constraint_assessments"][0]["assessment"] = "not_applicable"
    assert parse(json.dumps(good), action_turn_index=2, contract_version=contract_version).status.value == "invalid_output"
    empty = {"tool_contract": "satisfied", "constraint_assessments": [], "verdict": "valid"}
    assert parse(json.dumps(empty), action_turn_index=2, contract_version=contract_version).status.value == "parsed"
    assert parser_version == "p3-structured-validity-2"


def test_structured_v2_run_uses_same_evidence_and_versioned_parser():
    from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline, StructuredSingleCallBaseline
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        PromptSpec,
        ProviderIdentity,
        RunConfig,
        STRUCTURED_PARSER_VERSION_V2,
        STRUCTURED_RESPONSE_CONTRACT_V2,
    )

    item = synthetic_item("AR-EN")
    prompt = PromptSpec("candidate-prompt-v2", "Synthetic only: assess visible requirements and the action.")
    structured_config = RunConfig(
        provider=ProviderIdentity("mock", "synthetic-judge", "fixture"),
        baseline=BaselineKind.STRUCTURED_SINGLE_CALL.value,
        prompt_bundle_version=prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-test",
        aggregation_version="single-structured-verdict-2",
        parser_version=STRUCTURED_PARSER_VERSION_V2,
    )
    direct_prompt = PromptSpec("candidate-prompt-v2", prompt.instruction)
    direct_config = RunConfig(
        provider=structured_config.provider,
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=direct_prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-test",
    )
    structured = StructuredSingleCallBaseline(prompt).prepare(item, structured_config)
    direct = DirectMultilingualBaseline(direct_prompt).prepare(item, direct_config)
    a, b = structured.requests[0], direct.requests[0]
    assert a.conversation == b.conversation
    assert a.action == b.action
    assert a.public_tool_schema == b.public_tool_schema
    assert a.response_contract_version == STRUCTURED_RESPONSE_CONTRACT_V2


def test_post_inference_constraint_coverage_is_separate_and_matches_one_to_one():
    from multilingual_judge_pilot.judge_inference import (
        ConstraintAssessment,
        ParseResult,
        ParseStatus,
        Verdict,
    )
    from multilingual_judge_pilot.reference_scoring import score_constraint_coverage

    parsed = ParseResult(
        ParseStatus.PARSED,
        Verdict.INVALID,
        tool_contract="satisfied",
        structured_assessments=(
            ConstraintAssessment("numerical", "violated", (0, 1)),
            ConstraintAssessment("permission", "violated", (2,)),
            ConstraintAssessment("other", "satisfied", (1,)),
            ConstraintAssessment("numerical", "satisfied", (3,)),
        ),
    )
    score = score_constraint_coverage(
        parsed,
        (
            {"requirement_id": "number", "constraint_type": "numerical", "assessment": "violated", "source_turn_indices": [0]},
            {"requirement_id": "permission", "constraint_type": "permission", "assessment": "satisfied", "source_turn_indices": [2]},
            {"requirement_id": "time", "constraint_type": "temporal", "assessment": "satisfied", "source_turn_indices": [1]},
        ),
    )
    assert score.evidence_covered_requirement_ids == ("number", "permission", "time")
    assert score.evidence_omitted_requirement_ids == ()
    assert score.correct_constraint_type_requirement_ids == ("number", "permission")
    assert score.correct_assessment_requirement_ids == ("number", "time")
    assert score.exact_turn_match_requirement_ids == ("permission", "time")
    assert score.unmatched_prediction_indices == (3,)
    assert score.evidence_coverage_fraction == pytest.approx(1.0)
    assert score.constraint_type_accuracy_fraction == pytest.approx(2 / 3)
    assert score.assessment_accuracy_fraction == pytest.approx(2 / 3)
    assert score.exact_turn_match_fraction == pytest.approx(2 / 3)


def test_constraint_coverage_does_not_score_unparsed_outputs_as_omissions():
    from multilingual_judge_pilot.judge_inference import ParseResult, ParseStatus
    from multilingual_judge_pilot.reference_scoring import score_constraint_coverage

    score = score_constraint_coverage(
        ParseResult(ParseStatus.INVALID_OUTPUT),
        ({
            "requirement_id": "permission",
            "constraint_type": "permission",
            "assessment": "violated",
            "source_turn_indices": [0],
        },),
    )
    assert score.parsed is False
    assert score.evidence_covered_requirement_ids == ()
    assert score.evidence_omitted_requirement_ids == ()
    assert score.evidence_coverage_fraction is None
    assert score.assessment_accuracy_fraction is None


def test_v1_structured_schema_and_parser_remain_available():
    from multilingual_judge_pilot.judge_inference import (
        STRUCTURED_RESPONSE_CONTRACT,
        parse_structured_verdict_response,
        response_schema,
    )

    schema = response_schema(STRUCTURED_RESPONSE_CONTRACT)
    assert "not_applicable" in schema["properties"]["constraint_assessments"]["items"]["properties"]["assessment"]["enum"]
    legacy = json.dumps({
        "tool_contract": "satisfied",
        "constraint_assessments": [{
            "constraint_type": "temporal",
            "assessment": "not_applicable",
            "source_turn_indices": [0],
        }],
        "verdict": "valid",
    })
    assert parse_structured_verdict_response(legacy, action_turn_index=2).status.value == "parsed"


def test_candidate_prompts_share_rubric_and_distinguish_replacement_preservation_revocation():
    from multilingual_judge_pilot.p3_methodology_proposals import DIRECT_PROMPT_V2, STRUCTURED_PROMPT_V2

    for phrase in (
        "public tool-contract conformance",
        "permission from a user does not change the tool schema",
        "revises it",
        "restatement preserves",
        "explicit revocation removes",
        "Preserve earlier requirements",
        "all applicable effective user requirements",
    ):
        assert phrase in DIRECT_PROMPT_V2.instruction
        assert phrase in STRUCTURED_PROMPT_V2.instruction
    assert "reference" not in DIRECT_PROMPT_V2.instruction.casefold()
    assert "oracle" not in STRUCTURED_PROMPT_V2.instruction.casefold()


def test_v2_structured_execution_preserves_strict_result_and_raw_response():
    from multilingual_judge_pilot.judge_baselines import StructuredSingleCallBaseline
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        DeterministicMockProvider,
        JudgeExecutor,
        PromptSpec,
        ProviderIdentity,
        ProviderResponse,
        RunConfig,
        STRUCTURED_PARSER_VERSION_V2,
    )

    prompt = PromptSpec("candidate-structured-v2", "Synthetic-only contract test.")
    provider_id = ProviderIdentity("mock", "synthetic-judge", "fixture")
    raw = json.dumps({
        "tool_contract": "satisfied",
        "constraint_assessments": [{
            "constraint_type": "numerical",
            "assessment": "violated",
            "source_turn_indices": [0],
        }],
        "verdict": "invalid",
    })
    provider = DeterministicMockProvider(provider_id, [ProviderResponse(raw_response=raw, prompt_tokens=100, completion_tokens=22)])
    config = RunConfig(
        provider=provider_id,
        baseline=BaselineKind.STRUCTURED_SINGLE_CALL.value,
        prompt_bundle_version=prompt.version,
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-test",
        aggregation_version="single-structured-verdict-2",
        parser_version=STRUCTURED_PARSER_VERSION_V2,
    )
    plan = StructuredSingleCallBaseline(prompt).prepare(synthetic_item("EN-EN"), config)
    result = JudgeExecutor(config, provider).run(plan)
    assert result.final_result.verdict.value == "invalid"
    assert result.to_record()["steps"][0]["attempts"][0]["raw_response"] == raw
    assert result.to_record()["steps"][0]["response_contract_version"] == "structured-validity-v2"


def test_contextual_unshielded_translation_preserves_turns_and_checks_literals():
    from multilingual_judge_pilot.judge_inference import TranslationConfig, TranslationFacingInput
    from multilingual_judge_pilot.local_ollama import (
        OllamaLocalTranslator,
        TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION,
    )
    from multilingual_judge_pilot.judge_inference import ConversationTurn

    descriptor = {
        "model_tag": "translategemma:4b-it-q4_K_M",
        "digest": "a" * 64,
        "size_bytes": 1,
        "details": {"context_length": 4096},
        "capabilities": ("completion",),
        "template": "synthetic",
        "parameters": "synthetic",
    }

    class Client:
        base_url = "http://127.0.0.1:11434"

        def __init__(self, response):
            self.response = response
            self.requests = []

        def discover_model(self, _tag):
            from multilingual_judge_pilot.local_ollama import OllamaModelDescriptor

            return OllamaModelDescriptor(**descriptor)

        def chat(self, body):
            self.requests.append(body)
            return {
                "message": {"content": self.response},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 88,
                "eval_count": 20,
                "prompt_eval_duration": 100,
                "eval_duration": 80,
            }

    turns = (
        ConversationTurn(0, "user", "en", "Use the East Gate entrance at 09:30 UTC+03:00; booking HJ-77."),
        ConversationTurn(1, "user", "ar", "بدّل الموعد إلى الساعة ١٠:٣٠ بالتوقيت نفسه، مع إبقاء الحجز HJ-77."),
    )
    source = TranslationFacingInput("synthetic-context-1", turns)
    client = Client("Change the time to ١٠:٣٠ in the same time zone and keep booking HJ-77.")
    translator = OllamaLocalTranslator(client, "translategemma:4b-it-q4_K_M")
    config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version=TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION,
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 128), ("seed", 17), ("temperature", 0.0)),
    )
    output = translator.translate(source, config)
    prompt = client.requests[0]["messages"][0]["content"]
    assert "booking HJ-77" in prompt
    assert "preceding conversation context" in prompt.casefold()
    assert "ZXQKEEP" not in prompt
    assert output.translated_turns[0].content == turns[0].content
    assert [(t.turn_index, t.speaker, t.language) for t in output.translated_turns] == [(0, "user", "en"), (1, "user", "en")]
    call = output.provider_call_records[0]
    assert call["input_context_turn_indices"] == [0]
    assert call["literal_preservation_status"] == "passed"


def test_contextual_unshielded_translation_literal_mismatch_is_a_recorded_failure():
    from multilingual_judge_pilot.judge_inference import ConversationTurn, TranslationConfig, TranslationFacingInput
    from multilingual_judge_pilot.local_ollama import OllamaLocalTranslator, TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION
    from multilingual_judge_pilot.judge_baselines import TranslationCallError

    class Client:
        base_url = "http://127.0.0.1:11434"

        def discover_model(self, _tag):
            from multilingual_judge_pilot.local_ollama import OllamaModelDescriptor

            return OllamaModelDescriptor("translategemma:4b-it-q4_K_M", "b" * 64, 1, {"context_length": 4096}, ("completion",), "synthetic", "synthetic")

        def chat(self, _body):
            return {"message": {"content": "Keep booking HJ-78."}, "done": True, "done_reason": "stop"}

    turns = (ConversationTurn(0, "user", "ar", "أبقِ رقم الحجز HJ-77."),)
    source = TranslationFacingInput("synthetic-literal-failure", turns)
    translator = OllamaLocalTranslator(Client(), "translategemma:4b-it-q4_K_M")
    config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version=TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION,
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 128), ("seed", 17), ("temperature", 0.0)),
    )
    with pytest.raises(TranslationCallError, match="literal_preservation_failure") as exc:
        translator.translate(source, config)
    assert exc.value.provider_call_records[0]["status"] == "failure"
    assert exc.value.provider_call_records[0]["literal_preservation_status"] == "failed"


def test_v3_preservation_check_normalizes_digit_scripts_without_matching_prompt_text():
    from multilingual_judge_pilot.local_ollama import _literal_preservation_failures_v3

    source = "أخّر الموعد إلى ١٠:٣٠ يوم ٦ أكتوبر ٢٠٢٧، مع إبقاء المعرّف HJ-77 ورمز UTC+02:00."
    translated = "Move it to 10:30 on 6 October 2027, keeping ID HJ-77 and UTC+02:00."
    assert _literal_preservation_failures_v3(source, translated) == {
        "missing_numbers": [],
        "unexpected_numbers": [],
        "missing_identifiers": [],
        "unexpected_identifiers": [],
        "missing_currency_codes": [],
        "unexpected_currency_codes": [],
    }
    assert _literal_preservation_failures_v3("المبلغ ١٢٠ EUR", "The amount is 120 euros") == {
        "missing_numbers": [],
        "unexpected_numbers": [],
        "missing_identifiers": [],
        "unexpected_identifiers": [],
        "missing_currency_codes": ["EUR"],
        "unexpected_currency_codes": [],
    }


def test_v3_contextual_translation_uses_official_prompt_shape_and_preserves_roles():
    from multilingual_judge_pilot.judge_inference import ConversationTurn, TranslationConfig, TranslationFacingInput
    from multilingual_judge_pilot.local_ollama import OllamaLocalTranslator, TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3
    from multilingual_judge_pilot.local_ollama import OllamaModelDescriptor

    class Client:
        base_url = "http://127.0.0.1:11434"

        def __init__(self):
            self.requests = []

        def discover_model(self, _tag):
            return OllamaModelDescriptor("translategemma:4b-it-q4_K_M", "c" * 64, 1, {"context_length":4096}, ("completion",), "synthetic", "synthetic")

        def chat(self, body):
            self.requests.append(body)
            return {"message":{"content":"Move the appointment to 10:30 and keep identifier HJ-77."},"done":True,"done_reason":"stop","prompt_eval_count":160,"eval_count":16,"prompt_eval_duration":100,"eval_duration":100}

    source = TranslationFacingInput("synthetic-v3", (
        ConversationTurn(0,"user","en","The initial appointment is at 09:30 UTC+02:00."),
        ConversationTurn(1,"user","ar","أخّر الموعد إلى ١٠:٣٠ مع إبقاء المعرّف HJ-77."),
    ))
    client = Client()
    translator = OllamaLocalTranslator(client,"translategemma:4b-it-q4_K_M")
    config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version=TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3,
        decoding_parameters=(("num_ctx",4096),("num_predict",128),("seed",17),("temperature",0.0)),
    )
    result = translator.translate(source,config)
    prompt = client.requests[0]["messages"][0]["content"]
    assert prompt.startswith("You are a professional Arabic (ar) to English (en) translator.")
    assert "Preceding transcript for context only" in prompt
    assert "Please translate the following Arabic text into English:" in prompt
    assert "ZXQKEEP" not in prompt
    assert result.translated_turns[0].content == source.conversation[0].content
    assert [(x.speaker,x.turn_index,x.language) for x in result.translated_turns] == [("user",0,"en"),("user",1,"en")]
    assert result.provider_call_records[0]["literal_preservation_status"] == "passed"
