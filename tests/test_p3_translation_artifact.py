"""Synthetic-only tests for reusable, source/config hash-bound translations."""

from __future__ import annotations

from dataclasses import replace

import pytest

from p3_synthetic_fixtures import english_fixture_translation, fixture_input_manifest_sha256, synthetic_item


def test_translation_artifact_round_trip_reuse_and_mismatch_rejection():
    from multilingual_judge_pilot.judge_baselines import TranslationFirstBaseline, TranslationOutput
    from multilingual_judge_pilot.judge_inference import (
        BaselineKind,
        ContractError,
        ProviderIdentity,
        PromptSpec,
        RunConfig,
        TranslationConfig,
    )
    from multilingual_judge_pilot.translation_artifacts import TranslationArtifact

    item = synthetic_item("AR-EN")
    translator_identity = ProviderIdentity("mock-translator", "synthetic-only", "fixture-v1")
    translation = TranslationConfig(translator_identity, "en", "synthetic-translation-v1")
    config = RunConfig(
        provider=ProviderIdentity("mock-judge", "synthetic-judge", "fixture-v1"),
        baseline=BaselineKind.TRANSLATION_FIRST.value,
        prompt_bundle_version="synthetic-translation-judge-v1",
        input_manifest_sha256=fixture_input_manifest_sha256(),
        code_revision="synthetic-only-test",
        translation=translation,
    )
    prompt = PromptSpec("synthetic-translation-judge-v1", "Synthetic only: assess this fictional action.")

    class Translator:
        identity = translator_identity

        def translate(self, input_item, _config):
            turns = tuple(
                replace(turn, content=english_fixture_translation(turn.content), language="en")
                for turn in input_item.conversation
            )
            return TranslationOutput(turns, "synthetic translation output", 1.5)

    baseline = TranslationFirstBaseline(prompt, Translator())
    original_plan = baseline.prepare(item, config)
    artifact = TranslationArtifact.from_plan(item, config, original_plan)
    restored = TranslationArtifact.from_json(artifact.to_json())
    assert restored.artifact_sha256 == artifact.artifact_sha256
    assert restored.to_json() == artifact.to_json()

    class NeverCallTranslator:
        identity = translator_identity

        def translate(self, *_args):
            raise AssertionError("a verified artifact should be reused without another translation")

    second_judge_config = replace(
        config,
        provider=ProviderIdentity("mock-judge", "second-synthetic-judge", "fixture-v1"),
    )
    reused = TranslationFirstBaseline(prompt, NeverCallTranslator()).prepare(
        item, second_judge_config, translation_artifact=restored
    )
    assert reused.requests[0].conversation == original_plan.requests[0].conversation
    assert reused.requests[0].action == original_plan.requests[0].action
    assert reused.translation_records == original_plan.translation_records
    assert reused.translation_attempts == original_plan.translation_attempts
    assert reused.execution_id != original_plan.execution_id

    changed_item = replace(item, item_id="another-synthetic-item")
    with pytest.raises(ContractError, match="input identifier"):
        baseline.prepare(changed_item, config, translation_artifact=restored)
    changed_config = replace(second_judge_config, translation=replace(translation, prompt_version="different-prompt-v2"))
    with pytest.raises(ContractError, match="translation configuration"):
        TranslationFirstBaseline(prompt, NeverCallTranslator()).prepare(
            item, changed_config, translation_artifact=restored
        )

    payload = artifact.to_record()
    payload["translated_turns"][0]["content"] += " edited"
    with pytest.raises(ContractError, match="artifact hash"):
        TranslationArtifact.from_json(__import__("json").dumps(payload))
