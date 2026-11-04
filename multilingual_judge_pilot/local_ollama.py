"""Strict local-only adapters for the approved Ollama model artifacts.

The module deliberately has no remote-provider fallback. It talks only to the
literal loopback address and accepts the three exact provisional model tags.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import time
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from .judge_inference import (
    ContractError,
    TranslationFacingInput,
    ProviderCallError,
    ProviderIdentity,
    ProviderResponse,
    TranslationConfig,
    canonical_json,
    response_schema,
    _check_forbidden_mapping_keys,
)
from .judge_baselines import TranslationCallError, TranslationOutput


OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
APPROVED_OLLAMA_TAGS = frozenset(
    {
        "qwen3.5:9b-q4_K_M",
        "gemma4:12b-it-qat",
        "translategemma:4b-it-q4_K_M",
    }
)
DIAGNOSTIC_OLLAMA_TAGS = frozenset({"qwen3:4b-instruct-2507-q4_K_M"})
TRANSLATEGEMMA_PROMPT_VERSION = "translategemma-ollama-official-prompt-literal-shield-v1"


class OllamaLocalError(ProviderCallError):
    """Ollama HTTP/transport failure with safe category and optional raw body."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


@dataclass(frozen=True)
class OllamaModelDescriptor:
    model_tag: str
    digest: str
    size_bytes: int
    details: Mapping[str, object]
    capabilities: tuple[str, ...]
    template: str
    parameters: str
    diagnostic_only: bool = False

    def __post_init__(self) -> None:
        if type(self.diagnostic_only) is not bool:
            raise ContractError("diagnostic_only must be a boolean")
        _approved_model_tag(self.model_tag, diagnostic_only=self.diagnostic_only)
        digest = self.digest.removeprefix("sha256:")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ContractError("Ollama model digest must be a full SHA-256 hex digest")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ContractError("Ollama model size must be a positive integer")
        if not isinstance(self.details, Mapping):
            raise ContractError("Ollama model details must be an object")
        if not isinstance(self.capabilities, tuple) or any(not isinstance(value, str) for value in self.capabilities):
            raise ContractError("Ollama model capabilities must be a tuple of strings")
        if not isinstance(self.template, str) or not isinstance(self.parameters, str):
            raise ContractError("Ollama model template and parameters must be strings")
        object.__setattr__(self, "digest", f"sha256:{digest}")

    @property
    def context_length(self) -> int | None:
        value = self.details.get("context_length")
        return value if type(value) is int and value > 0 else None

    @property
    def quantization(self) -> str | None:
        value = self.details.get("quantization_level")
        return value if isinstance(value, str) else None

    def to_record(self) -> dict[str, object]:
        return {
            "record_version": "ollama-model-descriptor-1",
            "model_tag": self.model_tag,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "quantization": self.quantization,
            "details": dict(self.details),
            "capabilities": list(self.capabilities),
            "context_length": self.context_length,
            "template": self.template,
            "parameters": self.parameters,
            "diagnostic_only": self.diagnostic_only,
        }


class OllamaLocalClient:
    """Small stdlib HTTP client locked to the local Ollama listener."""

    def __init__(self, base_url: str = OLLAMA_DEFAULT_BASE_URL, *, timeout_seconds: float = 600.0):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ContractError("Ollama endpoint must be an HTTP URL on 127.0.0.1 with an explicit port")
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ContractError("Ollama request timeout must be positive")
        self.base_url = f"http://127.0.0.1:{parsed.port}"
        self.timeout_seconds = float(timeout_seconds)
        # Ignore proxy environment variables and reject redirects so calls never leave loopback.
        self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def _json_request(self, method: str, path: str, payload: Mapping[str, object] | None = None) -> dict[str, object]:
        if path not in {"/api/version", "/api/tags", "/api/show", "/api/chat"}:
            raise ContractError("unsupported Ollama local API path")
        data = None if payload is None else canonical_json(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            raise OllamaLocalError(f"http_{exc.code}", raw_response=raw_body or None) from None
        except URLError:
            raise OllamaLocalError("local_connection_error") from None
        except TimeoutError:
            raise OllamaLocalError("local_timeout") from None
        try:
            parsed = json.loads(raw_body)
        except (json.JSONDecodeError, TypeError):
            raise OllamaLocalError("invalid_local_api_json", raw_response=raw_body or None) from None
        if not isinstance(parsed, dict):
            raise OllamaLocalError("invalid_local_api_response", raw_response=raw_body or None)
        if isinstance(parsed.get("error"), str):
            raise OllamaLocalError("ollama_api_error", raw_response=raw_body)
        return parsed

    def get_version(self) -> dict[str, object]:
        return self._json_request("GET", "/api/version")

    def discover_model(self, model_tag: str, *, diagnostic_only: bool = False) -> OllamaModelDescriptor:
        _approved_model_tag(model_tag, diagnostic_only=diagnostic_only)
        tags = self._json_request("GET", "/api/tags")
        models = tags.get("models")
        if not isinstance(models, list):
            raise OllamaLocalError("invalid_model_inventory")
        entry = next((row for row in models if isinstance(row, dict) and row.get("name") == model_tag), None)
        if entry is None:
            raise OllamaLocalError("approved_model_not_installed")
        shown = self._json_request("POST", "/api/show", {"model": model_tag, "verbose": True})
        details = shown.get("details") if isinstance(shown.get("details"), dict) else entry.get("details", {})
        details = dict(details) if isinstance(details, dict) else {}
        model_info = shown.get("model_info")
        if isinstance(model_info, dict) and "context_length" not in details:
            contexts = [value for key, value in model_info.items() if key.endswith(".context_length") and type(value) is int]
            if contexts:
                details["context_length"] = max(contexts)
        capabilities = shown.get("capabilities", entry.get("capabilities", []))
        if not isinstance(capabilities, list):
            capabilities = entry.get("capabilities", [])
        digest = entry.get("digest")
        if not isinstance(digest, str):
            raise OllamaLocalError("model_digest_missing")
        size = entry.get("size")
        if type(size) is not int:
            raise OllamaLocalError("model_size_missing")
        return OllamaModelDescriptor(
            model_tag=model_tag,
            digest=digest,
            size_bytes=size,
            details=details,
            capabilities=tuple(capabilities),
            template=shown.get("template", "") if isinstance(shown.get("template", ""), str) else "",
            parameters=shown.get("parameters", "") if isinstance(shown.get("parameters", ""), str) else "",
            diagnostic_only=diagnostic_only,
        )

    def chat(self, payload: Mapping[str, object]) -> dict[str, object]:
        return self._json_request("POST", "/api/chat", payload)


def _approved_model_tag(tag: str, *, diagnostic_only: bool = False) -> None:
    if type(diagnostic_only) is not bool:
        raise ContractError("diagnostic_only must be a boolean")
    if diagnostic_only:
        if tag not in DIAGNOSTIC_OLLAMA_TAGS:
            raise ContractError("diagnostic-only mode accepts only the specifically authorized diagnostic model")
    elif tag not in APPROVED_OLLAMA_TAGS:
        raise ContractError("model tag is not on the approved local shortlist")


def _request_options(parameters: Mapping[str, object], descriptor: OllamaModelDescriptor) -> tuple[dict[str, object], bool | None]:
    expected = {"num_ctx", "num_predict", "seed", "temperature"}
    allowed = expected | {"think"}
    if set(parameters) - allowed or not expected <= set(parameters):
        raise ContractError("Ollama decoding parameters must set num_ctx, num_predict, seed, and temperature")
    context = parameters["num_ctx"]
    output_limit = parameters["num_predict"]
    seed = parameters["seed"]
    temperature = parameters["temperature"]
    if type(context) is not int or context < 1 or type(output_limit) is not int or output_limit < 1:
        raise ContractError("Ollama context and generation limits must be positive integers")
    if descriptor.context_length is not None and context > descriptor.context_length:
        raise ContractError("requested context exceeds the installed model's reported context length")
    if type(seed) is not int or type(temperature) not in {int, float} or not 0 <= temperature <= 2:
        raise ContractError("invalid Ollama seed or temperature")
    options = {
        "num_ctx": context,
        "num_predict": output_limit,
        "seed": seed,
        "temperature": temperature,
    }
    think = parameters.get("think")
    if think is not None:
        if type(think) is not bool:
            raise ContractError("Ollama think must be a boolean")
        if "thinking" not in descriptor.capabilities:
            raise ContractError("think configuration was supplied but /api/show does not report thinking capability")
    return options, think


class OllamaLocalJudgeProvider:
    """Provider-independent judge protocol backed only by a local Ollama model."""

    def __init__(self, client: OllamaLocalClient, model_tag: str, *, diagnostic_only: bool = False):
        _approved_model_tag(model_tag, diagnostic_only=diagnostic_only)
        if not isinstance(getattr(client, "base_url", None), str) or not client.base_url.startswith("http://127.0.0.1:"):
            raise ContractError("local judge client must use the loopback Ollama endpoint")
        self.client = client
        self.descriptor = client.discover_model(model_tag, diagnostic_only=diagnostic_only)
        provider_id = "ollama-local-diagnostic" if diagnostic_only else "ollama-local"
        self._identity = ProviderIdentity(provider_id, model_tag, self.descriptor.digest)

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def complete(self, request_json: str, decoding_parameters: Mapping[str, object]) -> ProviderResponse:
        try:
            request = json.loads(request_json)
        except (json.JSONDecodeError, TypeError):
            raise ContractError("local judge request must be valid JSON") from None
        if isinstance(request, dict):
            _check_forbidden_mapping_keys(request)
        expected = {
            "response_contract_version", "response_schema", "item_id", "instruction", "conversation", "action", "public_tool_schema"
        }
        if not isinstance(request, dict) or set(request) != expected:
            raise ContractError("local judge request contains missing or unknown fields")
        contract = request["response_contract_version"]
        canonical_schema = response_schema(contract)
        if request["response_schema"] != canonical_schema:
            raise ContractError("local judge request schema does not match its versioned output contract")
        if not isinstance(request["instruction"], str) or not isinstance(request["conversation"], list):
            raise ContractError("local judge request instruction or conversation is malformed")
        options, think = _request_options(decoding_parameters, self.descriptor)
        evidence = {
            "item_id": request["item_id"],
            "conversation": request["conversation"],
            "action": request["action"],
            "public_tool_schema": request["public_tool_schema"],
        }
        payload: dict[str, object] = {
            "model": self.descriptor.model_tag,
            "messages": [
                {"role": "system", "content": request["instruction"]},
                {"role": "user", "content": canonical_json(evidence)},
            ],
            "format": canonical_schema,
            "options": options,
            "stream": False,
        }
        if think is not None:
            payload["think"] = think
        result = self.client.chat(payload)
        message = result.get("message")
        if not isinstance(message, dict):
            raise OllamaLocalError("local_chat_message_missing")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise OllamaLocalError("local_chat_content_invalid")
        refusal = message.get("refusal")
        provider_refused = isinstance(refusal, str) and bool(refusal.strip())
        return ProviderResponse(
            raw_response=content if isinstance(content, str) and content else refusal if provider_refused else content,
            refused=provider_refused,
            prompt_tokens=_optional_nonnegative_int(result.get("prompt_eval_count")),
            completion_tokens=_optional_nonnegative_int(result.get("eval_count")),
            cost_usd="0",
            prompt_eval_duration_ns=_optional_nonnegative_int(result.get("prompt_eval_duration")),
            generation_duration_ns=_optional_nonnegative_int(result.get("eval_duration")),
            load_duration_ns=_optional_nonnegative_int(result.get("load_duration")),
            total_duration_ns=_optional_nonnegative_int(result.get("total_duration")),
            completion_reason=result.get("done_reason") if isinstance(result.get("done_reason"), str) else None,
            response_incomplete=(
                result.get("done") is not True
                or result.get("done_reason") in {"length", "max_tokens"}
            ),
        )


def _optional_nonnegative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


_LITERAL_PATTERN = re.compile(
    r"(?<![\w])(?:[A-Za-z][A-Za-z0-9]*(?:[._/:+-][A-Za-z0-9]+)+|[A-Z]{3}|[+-]?\d+(?:[-.,:/+]\d+)*)(?![\w])"
)


def _shield_literals(text: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    found: list[tuple[str, str]] = []

    def replace_literal(match: re.Match[str]) -> str:
        marker = f"ZXQKEEP{len(found):04d}QXZ"
        found.append((marker, match.group(0)))
        return marker

    return _LITERAL_PATTERN.sub(replace_literal, text), tuple(found)


def _restore_literals(translated: str, literals: tuple[tuple[str, str], ...]) -> str:
    for marker, original in literals:
        if translated.count(marker) != 1:
            raise ValueError("translation_protected_literal_mismatch")
        translated = translated.replace(marker, original)
    return translated


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OllamaLocalTranslator:
    """Translate Arabic turns one at a time; English turns remain byte-identical."""

    def __init__(self, client: OllamaLocalClient, model_tag: str):
        _approved_model_tag(model_tag)
        if model_tag != "translategemma:4b-it-q4_K_M":
            raise ContractError("Ollama local translator requires the approved TranslateGemma 4B tag")
        if not isinstance(getattr(client, "base_url", None), str) or not client.base_url.startswith("http://127.0.0.1:"):
            raise ContractError("local translator client must use the loopback Ollama endpoint")
        self.client = client
        self.descriptor = client.discover_model(model_tag)
        self._identity = ProviderIdentity("ollama-local", model_tag, self.descriptor.digest)

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def translate(self, item: TranslationFacingInput, config: TranslationConfig) -> TranslationOutput:
        if not isinstance(item, TranslationFacingInput):
            raise ContractError("TranslateGemma accepts only transcript-only TranslationFacingInput")
        if config.translator != self.identity or config.pivot_language != "en":
            raise ContractError("TranslateGemma configuration must match the local model and English pivot")
        if config.prompt_version != TRANSLATEGEMMA_PROMPT_VERSION:
            raise ContractError("TranslateGemma prompt version must identify the official prompt and literal-shield procedure")
        parameters = dict(config.decoding_parameters)
        options, think = _request_options(parameters, self.descriptor)
        if think is not None:
            raise ContractError("TranslateGemma translation configuration must omit thinking controls")

        translated_turns = []
        call_records: list[dict[str, object]] = []
        raw_outputs: list[dict[str, object]] = []
        prompt_tokens: list[int] = []
        completion_tokens: list[int] = []
        total_latency_ms = 0.0
        for turn in item.conversation:
            if turn.language != "ar":
                translated_turns.append(replace(turn, language="en"))
                continue
            protected_text, literals = _shield_literals(turn.content)
            prompt = (
                "You are a professional Arabic (ar) to English (en) translator. Your goal is to accurately convey the meaning and nuances of the original Arabic text while adhering to English grammar, vocabulary, and cultural sensitivities.\n"
                "Produce only the English translation, without any additional explanations or commentary. Please translate the following Arabic text into English:\n\n\n"
                f"{protected_text}"
            )
            input_hash = sha256(canonical_json({"item_id": item.item_id, "turn": turn.to_record()}).encode("utf-8")).hexdigest()
            call_id = uuid4().hex
            started_at = _utc_now()
            started_ns = time.perf_counter_ns()
            raw_response: str | None = None
            response: dict[str, object] | None = None
            failure: str | None = None
            try:
                body: dict[str, object] = {
                    "model": self.descriptor.model_tag,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": options,
                    "stream": False,
                }
                result = self.client.chat(body)
                message = result.get("message")
                if not isinstance(message, dict):
                    raise OllamaLocalError("local_translation_content_missing")
                response = result
                refusal = message.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    raw_response = refusal
                    raise OllamaLocalError("translation_refused", raw_response=refusal)
                content = message.get("content")
                if not isinstance(content, str):
                    raise OllamaLocalError("local_translation_content_missing")
                raw_response = content
                if result.get("done") is not True or result.get("done_reason") in {"length", "max_tokens"}:
                    raise OllamaLocalError("translation_output_incomplete", raw_response=raw_response)
                translated = _restore_literals(raw_response.strip(), literals)
                if not translated:
                    raise ValueError("empty_translation")
            except Exception as exc:
                elapsed = max(0, time.perf_counter_ns() - started_ns)
                failure = exc.code if isinstance(exc, ProviderCallError) else str(exc) if str(exc) == "translation_protected_literal_mismatch" else "local_connection_failure"
                ended_at = _utc_now()
                call_records.append(
                    self._call_record(
                        call_id=call_id,
                        config=config,
                        item=item,
                        turn_index=turn.turn_index,
                        input_hash=input_hash,
                        started_at=started_at,
                        completed_at=ended_at,
                        latency_ns=elapsed,
                        status="failure",
                        error_category=failure,
                        retry_decision="outer_retry_policy",
                        raw_response=raw_response or getattr(exc, "raw_response", None),
                        result=response,
                        protected_literal_count=len(literals),
                    )
                )
                raise TranslationCallError(
                    "translation_" + failure,
                    raw_response=raw_response or getattr(exc, "raw_response", None),
                    prompt_tokens=_optional_nonnegative_int(response.get("prompt_eval_count")) if response else None,
                    completion_tokens=_optional_nonnegative_int(response.get("eval_count")) if response else None,
                    cost_usd="0",
                    provider_call_records=tuple(call_records),
                ) from None
            elapsed = max(0, time.perf_counter_ns() - started_ns)
            ended_at = _utc_now()
            prompt_count = _optional_nonnegative_int(response.get("prompt_eval_count")) if response else None
            completion_count = _optional_nonnegative_int(response.get("eval_count")) if response else None
            if prompt_count is not None:
                prompt_tokens.append(prompt_count)
            if completion_count is not None:
                completion_tokens.append(completion_count)
            total_latency_ms += elapsed / 1_000_000
            translated_turns.append(replace(turn, language="en", content=translated))
            call_records.append(
                self._call_record(
                    call_id=call_id,
                    config=config,
                    item=item,
                    turn_index=turn.turn_index,
                    input_hash=input_hash,
                    started_at=started_at,
                    completed_at=ended_at,
                    latency_ns=elapsed,
                    status="success",
                    error_category=None,
                    retry_decision="stop",
                    raw_response=raw_response,
                    result=response,
                    protected_literal_count=len(literals),
                )
            )
            raw_outputs.append({"turn_index": turn.turn_index, "raw_response": raw_response})

        return TranslationOutput(
            translated_turns=tuple(translated_turns),
            raw_output=canonical_json(raw_outputs),
            latency_ms=total_latency_ms,
            prompt_tokens=sum(prompt_tokens) if prompt_tokens else None,
            completion_tokens=sum(completion_tokens) if completion_tokens else None,
            cost_usd="0",
            provider_call_records=tuple(call_records),
        )

    def _call_record(
        self,
        *,
        call_id: str,
        config: TranslationConfig,
        item: TranslationFacingInput,
        turn_index: int,
        input_hash: str,
        started_at: str,
        completed_at: str,
        latency_ns: int,
        status: str,
        error_category: str | None,
        retry_decision: str,
        raw_response: str | None,
        result: Mapping[str, object] | None,
        protected_literal_count: int,
    ) -> dict[str, object]:
        result = result or {}
        return {
            "record_version": "ollama-translation-call-1",
            "call_id": call_id,
            "configuration_hash": config.config_hash,
            "translation_prompt_version": config.prompt_version,
            "input_id": item.item_id,
            "turn_index": turn_index,
            "input_sha256": input_hash,
            "translator": self.identity.to_record(),
            "attempt_number": 1,
            "started_at_utc": started_at,
            "completed_at_utc": completed_at,
            "status": status,
            "error_category": error_category,
            "retry_decision": retry_decision,
            "raw_response": raw_response,
            "prompt_tokens": _optional_nonnegative_int(result.get("prompt_eval_count")),
            "completion_tokens": _optional_nonnegative_int(result.get("eval_count")),
            "prompt_eval_duration_ns": _optional_nonnegative_int(result.get("prompt_eval_duration")),
            "generation_duration_ns": _optional_nonnegative_int(result.get("eval_duration")),
            "load_duration_ns": _optional_nonnegative_int(result.get("load_duration")),
            "total_duration_ns": _optional_nonnegative_int(result.get("total_duration")),
            "completion_reason": result.get("done_reason") if isinstance(result.get("done_reason"), str) else None,
            "response_incomplete": result.get("done") is not True or result.get("done_reason") in {"length", "max_tokens"},
            "cost_usd": "0",
            "latency_ms": latency_ns / 1_000_000,
            "protected_literal_count": protected_literal_count,
        }
