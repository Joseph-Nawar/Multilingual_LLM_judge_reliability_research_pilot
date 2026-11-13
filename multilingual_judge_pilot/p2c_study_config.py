"""Fixed local P2C run configurations, without reference-side dependencies."""

from __future__ import annotations

from typing import Mapping

from .judge_inference import (
    BINARY_RESPONSE_CONTRACT,
    STRUCTURED_PARSER_VERSION_V2,
    STRUCTURED_RESPONSE_CONTRACT_V2,
    BaselineKind,
    ProviderIdentity,
    PromptSpec,
    RetryPolicy,
    RunConfig,
    TranslationConfig,
    canonical_json,
)
from .local_ollama import TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3
from .p3_methodology_proposals import DIRECT_PROMPT_V2, STRUCTURED_PROMPT_V2
from .qualification import sha256_text


JUDGE_MODEL_TAG = "gemma4:12b-it-qat"
JUDGE_MODEL_DIGEST = "sha256:38044be4f923e5a55264ed7df4eaac2676651a905f735197c504045140c02bd3"
TRANSLATOR_MODEL_TAG = "translategemma:4b-it-q4_K_M"
TRANSLATOR_MODEL_DIGEST = "sha256:eeb875b066dbbc91ad481f7423c61c23eccc5b96e85b50d6667753bdee726227"
STUDY_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    retryable_error_codes=("http_500", "http_502", "http_503", "http_504", "local_connection_error", "local_timeout"),
    version="p3-qualification-transient-retry-v1",
)


def build_run_configs(input_manifest: Mapping[str, object], code_revision: str) -> dict[str, tuple[RunConfig, PromptSpec]]:
    """Return runtime config/prompt pairs without importing reference-side modules."""
    manifest_hash = input_manifest.get("manifest_sha256")
    if not isinstance(manifest_hash, str) or len(manifest_hash) != 64:
        raise ValueError("inference configuration requires a valid frozen input manifest hash")
    judge = ProviderIdentity("ollama-local", JUDGE_MODEL_TAG, JUDGE_MODEL_DIGEST)
    translator = ProviderIdentity("ollama-local", TRANSLATOR_MODEL_TAG, TRANSLATOR_MODEL_DIGEST)
    base_decoding = tuple(sorted({"num_ctx": 4096, "seed": 17, "temperature": 0.0, "think": False}.items()))
    direct = RunConfig(
        provider=judge,
        baseline=BaselineKind.DIRECT_MULTILINGUAL.value,
        prompt_bundle_version=DIRECT_PROMPT_V2.version,
        input_manifest_sha256=manifest_hash,
        code_revision=code_revision,
        decoding_parameters=tuple(sorted((*base_decoding, ("num_predict", 96)))),
        retry_policy=STUDY_RETRY_POLICY,
        random_seed=17,
        response_contract_version=BINARY_RESPONSE_CONTRACT,
    )
    translation = TranslationConfig(
        translator=translator,
        pivot_language="en",
        prompt_version=TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3,
        decoding_parameters=tuple(sorted({"num_ctx": 4096, "num_predict": 128, "seed": 17, "temperature": 0.0}.items())),
        retry_policy=STUDY_RETRY_POLICY,
        literal_validation_policy_version="literal-preservation-time-equivalence-v4",
    )
    translation_first = RunConfig(
        provider=judge,
        baseline=BaselineKind.TRANSLATION_FIRST.value,
        prompt_bundle_version=DIRECT_PROMPT_V2.version,
        input_manifest_sha256=manifest_hash,
        code_revision=code_revision,
        decoding_parameters=tuple(sorted((*base_decoding, ("num_predict", 96)))),
        retry_policy=STUDY_RETRY_POLICY,
        translation=translation,
        random_seed=17,
        response_contract_version=BINARY_RESPONSE_CONTRACT,
    )
    structured = RunConfig(
        provider=judge,
        baseline=BaselineKind.STRUCTURED_SINGLE_CALL.value,
        prompt_bundle_version=STRUCTURED_PROMPT_V2.version,
        input_manifest_sha256=manifest_hash,
        code_revision=code_revision,
        decoding_parameters=tuple(sorted((*base_decoding, ("num_predict", 512)))),
        retry_policy=STUDY_RETRY_POLICY,
        random_seed=17,
        parser_version=STRUCTURED_PARSER_VERSION_V2,
        aggregation_version="single-structured-verdict-2",
        response_contract_version=STRUCTURED_RESPONSE_CONTRACT_V2,
    )
    return {
        "direct": (direct, DIRECT_PROMPT_V2),
        "translation_first": (translation_first, DIRECT_PROMPT_V2),
        "structured": (structured, STRUCTURED_PROMPT_V2),
    }


def build_study_configs(input_manifest: Mapping[str, object], code_revision: str) -> dict[str, dict[str, object]]:
    """Build the fixed, hash-bound local run configurations approved for the study."""
    entries = build_run_configs(input_manifest, code_revision)
    configs = {}
    for name, (config, prompt) in entries.items():
        record = config.to_record()
        record["configuration_hash"] = config.config_hash
        record["prompt_sha256"] = sha256_text(prompt.instruction)
        record["output_limit"] = dict(config.decoding_parameters)["num_predict"]
        configs[name] = record
    return configs


def verify_study_config_records(
    stored: Mapping[str, object], input_manifest: Mapping[str, object], code_revision: str
) -> bool:
    return dict(stored) == build_study_configs(input_manifest, code_revision)


def configuration_set_sha256(configurations: Mapping[str, object]) -> str:
    return sha256_text(canonical_json(configurations))
