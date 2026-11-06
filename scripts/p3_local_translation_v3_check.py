#!/usr/bin/env python3
"""Bounded V3 translation check and shared-artifact pipeline test.

Reads only independent synthetic P3 material and one prior synthetic run to
reuse its A-policy outputs. No study references or competence-screen items are
loaded. All provider calls are restricted to the local loopback Ollama server.
"""

from __future__ import annotations

from datetime import datetime, timezone
import atexit
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multilingual_judge_pilot.judge_baselines import DirectMultilingualBaseline, TranslationFirstBaseline  # noqa: E402
from multilingual_judge_pilot.judge_inference import (  # noqa: E402
    BaselineKind,
    ConversationTurn,
    JudgeExecutor,
    JudgeFacingInput,
    RunConfig,
    TranslationConfig,
    TranslationFacingInput,
    canonical_json,
)
from multilingual_judge_pilot.local_ollama import (  # noqa: E402
    OLLAMA_DEFAULT_BASE_URL,
    TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3,
    OllamaLocalClient,
    OllamaLocalJudgeProvider,
    OllamaLocalTranslator,
)
from multilingual_judge_pilot.p3_methodology_proposals import DIRECT_PROMPT_V2  # noqa: E402
from multilingual_judge_pilot.translation_artifacts import TranslationArtifact  # noqa: E402


MODELS = ("qwen3.5:9b-q4_K_M", "gemma4:12b-it-qat")
TRANSLATOR_TAG = "translategemma:4b-it-q4_K_M"


def _cmd(args: list[str], timeout: float = 8) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"unavailable:{type(exc).__name__}"
    output = (result.stdout + result.stderr).strip()
    return output if result.returncode == 0 else f"exit={result.returncode}: {output}"


def _loaded() -> list[str]:
    lines = _cmd(["ollama", "ps"]).splitlines()[1:]
    return [line.split()[0] for line in lines if line.split()]


def _stop(tag: str) -> None:
    if tag not in {*MODELS, TRANSLATOR_TAG}:
        raise RuntimeError("refusing to stop an unapproved local model")
    if tag in _loaded():
        result = _cmd(["ollama", "stop", tag])
        if result.startswith("exit=") or result.startswith("unavailable:"):
            raise RuntimeError(f"could not unload approved local model {tag}")


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _run_config(provider, manifest_hash: str, translation: TranslationConfig) -> RunConfig:
    decoding = {"num_ctx": 4096, "num_predict": 96, "seed": 17, "temperature": 0.0}
    if "thinking" in provider.descriptor.capabilities:
        decoding["think"] = False
    return RunConfig(
        provider=provider.identity,
        baseline=BaselineKind.TRANSLATION_FIRST.value,
        prompt_bundle_version=DIRECT_PROMPT_V2.version,
        input_manifest_sha256=manifest_hash,
        code_revision=_cmd(["git", "rev-parse", "HEAD"]),
        decoding_parameters=tuple(sorted(decoding.items())),
        translation=translation,
        random_seed=17,
    )


def _main() -> int:
    private = ROOT / ".research-data" / "p3-local-method-stabilization"
    runs = private / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    output_path = runs / f"translation-v3-check-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    if _loaded():
        raise RuntimeError("Ollama must be idle before V3 translation check")
    client = OllamaLocalClient(OLLAMA_DEFAULT_BASE_URL)
    translator = OllamaLocalTranslator(client, TRANSLATOR_TAG)
    descriptor = translator.descriptor
    config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
        prompt_version=TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3,
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 512), ("seed", 17), ("temperature", 0.0)),
    )
    content_path = private / "translation_synthetic_items.json"
    translation_items = json.loads(content_path.read_text(encoding="utf-8"))["items"]
    judge_path = private / "judge_synthetic_items.json"
    judge_items = [JudgeFacingInput.from_mapping(row) for row in json.loads(judge_path.read_text(encoding="utf-8"))["items"]]
    evidence = [item.evidence_record() | {"language_condition": item.language_condition} for item in judge_items]
    manifest_hash = _digest(evidence)
    prior_path = runs / "synthetic-method-smoke-20261106T170646Z.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    prior_a = {row["item_id"]: row for row in prior["translation_comparison"]}

    output: dict[str, object] = {
        "record_version": "p3-local-translation-v3-check-1",
        "status": "running",
        "scope": "synthetic translation comparison and shared-artifact integration only; no study or screen data",
        "endpoint": OLLAMA_DEFAULT_BASE_URL,
        "translator": descriptor.to_record(),
        "translation_config": config.to_record(),
        "translation_config_hash": config.config_hash,
        "input_fixture_sha256": _digest(translation_items),
        "prior_A_record_path": str(prior_path),
        "prior_A_record_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
        "translation_comparison": [],
        "translation_first_artifacts": [],
        "translation_first_judge_runs": [],
    }

    def checkpoint() -> None:
        output["last_checkpoint_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        temp = output_path.with_suffix(".tmp")
        temp.write_text(canonical_json(output) + "\n", encoding="utf-8")
        temp.replace(output_path)

    checkpoint()
    atexit.register(checkpoint)

    # Reuse prior A artifacts and make one V3 B attempt per Arabic source turn.
    for row in translation_items:
        turns = tuple(ConversationTurn(**turn) for turn in row["turns"])
        source = TranslationFacingInput(row["item_id"], turns)
        old = prior_a[row["item_id"]]["A_isolated_literal_shield"]
        record: dict[str, object] = {
            "item_id": row["item_id"],
            "review_facets": row["review_facets"],
            "A_isolated_literal_shield": old,
            "A_source_record_sha256": hashlib.sha256(canonical_json(old).encode("utf-8")).hexdigest(),
        }
        started = time.perf_counter()
        try:
            translated = translator.translate(source, config)
            record["B_context_unshielded_v3"] = {
                "status": "success",
                "latency_seconds": time.perf_counter() - started,
                "translated_turns": [turn.to_record() for turn in translated.translated_turns],
                "raw_output": translated.raw_output,
                "provider_call_records": list(translated.provider_call_records),
            }
        except Exception as exc:
            record["B_context_unshielded_v3"] = {
                "status": "failure",
                "error_category": getattr(exc, "category", type(exc).__name__),
                "raw_response": getattr(exc, "raw_response", None),
                "provider_call_records": list(getattr(exc, "provider_call_records", ())),
            }
        output["translation_comparison"].append(record)
        checkpoint()

    _stop(TRANSLATOR_TAG)

    # Create the B-policy artifacts once; reuse them unchanged across both judges.
    first_provider = OllamaLocalJudgeProvider(client, MODELS[0])
    first_config = _run_config(first_provider, manifest_hash, config)
    baseline = TranslationFirstBaseline(DIRECT_PROMPT_V2, translator)
    artifacts: dict[str, TranslationArtifact] = {}
    for item in judge_items:
        plan = baseline.prepare(item, first_config)
        if plan.preprocessing_result is None:
            artifacts[item.item_id] = TranslationArtifact.from_plan(item, first_config, plan)
        output["translation_first_artifacts"].append({
            "item_id": item.item_id,
            "artifact_sha256": artifacts[item.item_id].artifact_sha256 if item.item_id in artifacts else None,
            "translation_attempts": [attempt.to_record() for attempt in plan.translation_attempts],
        })
        checkpoint()
    _stop(TRANSLATOR_TAG)

    for model_tag in MODELS:
        provider = OllamaLocalJudgeProvider(client, model_tag)
        for item in judge_items:
            artifact = artifacts.get(item.item_id)
            if artifact is None:
                output["translation_first_judge_runs"].append({
                    "model_tag": model_tag,
                    "item_id": item.item_id,
                    "status": "skipped_translation_failure",
                })
                checkpoint()
                continue
            run_config = _run_config(provider, manifest_hash, config)
            plan = baseline.prepare(item, run_config, translation_artifact=artifact)
            started = time.perf_counter()
            result = JudgeExecutor(run_config, provider).run(plan)
            output["translation_first_judge_runs"].append({
                "model_tag": model_tag,
                "model_digest": provider.descriptor.digest,
                "item_id": item.item_id,
                "language_condition": item.language_condition,
                "translation_artifact_sha256": artifact.artifact_sha256,
                "configuration_hash": run_config.config_hash,
                "execution_id": result.execution_id,
                "wall_seconds": time.perf_counter() - started,
                "result": result.to_record(),
            })
            checkpoint()
        _stop(model_tag)

    output["status"] = "completed"
    output["completed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    checkpoint()
    print(json.dumps({
        "record_path": str(output_path),
        "record_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "comparison_items": len(output["translation_comparison"]),
        "successful_v3_translations": sum(x["B_context_unshielded_v3"]["status"] == "success" for x in output["translation_comparison"]),
        "shared_translation_artifacts": sum(x["artifact_sha256"] is not None for x in output["translation_first_artifacts"]),
        "judge_runs": sum(x.get("status") != "skipped_translation_failure" for x in output["translation_first_judge_runs"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
