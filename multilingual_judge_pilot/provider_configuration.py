"""Proposed, provider-specific inference settings for the v2 candidate shortlist.

This is validation metadata only. It does not send requests or implement provider
adapters. The allowlists intentionally reject unknown knobs until each is checked
against current official documentation and added with a versioned test.
"""

from __future__ import annotations

from collections.abc import Mapping
import re

from .judge_inference import ContractError, ProviderIdentity


_CANDIDATES = {
    "openai": {
        "model_id": "gpt-6.1-sol",
        "allowed": {"max_output_tokens", "reasoning", "store"},
        "required": {"max_output_tokens", "reasoning", "store"},
    },
    "anthropic": {
        "model_id": "claude-sonnet-5-5",
        "allowed": {"max_tokens", "output_config"},
        "required": {"max_tokens", "output_config"},
    },
    "google": {
        "model_id": "gemini-3.8-flash",
        "allowed": {"generation_config"},
        "required": {"generation_config"},
    },
}

_LOCAL_OLLAMA_MODELS = {
    "qwen3.5:9b-q4_K_M",
    "gemma4:12b-it-qat",
    "translategemma:4b-it-q4_K_M",
}


def _positive_integer(value: object, field_name: str) -> None:
    if type(value) is not int or value < 1:
        raise ContractError(f"{field_name} must be a positive integer")


def validate_provider_inference_configuration(
    identity: ProviderIdentity,
    decoding_parameters: tuple[tuple[str, object], ...],
) -> None:
    """Validate a shortlisted candidate against its own API parameter contract."""
    profile = _CANDIDATES.get(identity.provider_id)
    if profile is None:
        if identity.provider_id == "ollama-local":
            parameters = dict(decoding_parameters)
            if identity.model_id not in _LOCAL_OLLAMA_MODELS:
                raise ContractError("Ollama local model ID must be one of the three approved tagged models")
            if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", identity.model_version):
                raise ContractError("Ollama local model version must be its full SHA-256 digest")
            allowed = {"num_ctx", "num_predict", "seed", "temperature", "think"}
            unknown = set(parameters) - allowed
            if unknown:
                raise ContractError(f"unsupported Ollama decoding parameter(s): {', '.join(sorted(unknown))}")
            missing = {"num_ctx", "num_predict", "seed", "temperature"} - set(parameters)
            if missing:
                raise ContractError(f"missing Ollama decoding parameter(s): {', '.join(sorted(missing))}")
            _positive_integer(parameters["num_ctx"], "num_ctx")
            _positive_integer(parameters["num_predict"], "num_predict")
            if type(parameters["seed"]) is not int:
                raise ContractError("Ollama seed must be an integer")
            if type(parameters["temperature"]) not in {int, float} or not 0 <= parameters["temperature"] <= 2:
                raise ContractError("Ollama temperature must be between 0 and 2")
            if "think" in parameters and type(parameters["think"]) is not bool:
                raise ContractError("Ollama think must be an explicit boolean")
        return
    if identity.model_id != profile["model_id"]:
        raise ContractError(f"provider {identity.provider_id} model ID must be {profile['model_id']}")
    parameters = dict(decoding_parameters)
    unknown = set(parameters) - profile["allowed"]
    missing = profile["required"] - set(parameters)
    if unknown:
        if identity.provider_id == "anthropic" and unknown & {"temperature", "top_p", "top_k"}:
            raise ContractError("Claude Sonnet 5.5 does not accept temperature, top_p, or top_k")
        raise ContractError(f"unsupported {identity.provider_id} inference parameter(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ContractError(f"missing {identity.provider_id} inference parameter(s): {', '.join(sorted(missing))}")

    if identity.provider_id == "openai":
        _positive_integer(parameters["max_output_tokens"], "max_output_tokens")
        if parameters["store"] is not False:
            raise ContractError("OpenAI Responses API configuration must set store=false")
        reasoning = parameters["reasoning"]
        if (
            not isinstance(reasoning, Mapping)
            or set(reasoning) != {"effort"}
            or not isinstance(reasoning["effort"], str)
            or reasoning["effort"] not in {"low", "medium", "high", "xhigh", "max"}
        ):
            raise ContractError("OpenAI reasoning must specify one documented reasoning.effort level")
    elif identity.provider_id == "anthropic":
        _positive_integer(parameters["max_tokens"], "max_tokens")
        output_config = parameters["output_config"]
        if (
            not isinstance(output_config, Mapping)
            or set(output_config) != {"effort"}
            or not isinstance(output_config["effort"], str)
            or output_config["effort"] not in {"low", "medium", "high", "xhigh", "max"}
        ):
            raise ContractError("Anthropic output_config must specify one documented effort level")
    elif identity.provider_id == "google":
        generation = parameters["generation_config"]
        if not isinstance(generation, Mapping) or set(generation) != {"max_output_tokens", "thinking_level"}:
            raise ContractError("Google generation_config must contain max_output_tokens and thinking_level only")
        _positive_integer(generation["max_output_tokens"], "generation_config.max_output_tokens")
        if not isinstance(generation["thinking_level"], str) or generation["thinking_level"] not in {"low", "medium", "high"}:
            raise ContractError("Gemini 3.8 Flash thinking_level must be low, medium, or high")


def candidate_provider_configuration_profiles() -> dict[str, object]:
    """Return a detached, deterministic summary suitable for public documentation/tests."""
    return {
        "openai": {
            "model_id": "gpt-6.1-sol",
            "parameters": {"reasoning.effort": ["low", "medium", "high", "xhigh", "max"], "max_output_tokens": "positive integer", "store": False},
        },
        "anthropic": {
            "model_id": "claude-sonnet-5-5",
            "parameters": {"output_config.effort": ["low", "medium", "high", "xhigh", "max"], "max_tokens": "positive integer"},
            "rejected": ["temperature", "top_p", "top_k"],
        },
        "google": {
            "model_id": "gemini-3.8-flash",
            "parameters": {"generation_config.thinking_level": ["low", "medium", "high"], "generation_config.max_output_tokens": "positive integer"},
        },
    }
