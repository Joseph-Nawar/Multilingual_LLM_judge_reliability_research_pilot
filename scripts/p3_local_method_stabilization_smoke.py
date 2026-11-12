#!/usr/bin/env python3
"""One bounded local-method retest on independent synthetic material only.

This runner reads only its private P3 synthetic fixture package and writes raw
records under ignored .research-data/. It is not the competence screen or a
study evaluation and has no remote-provider fallback.
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
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multilingual_judge_pilot.judge_baselines import (  # noqa: E402
    DirectMultilingualBaseline,
    StructuredSingleCallBaseline,
    TranslationFirstBaseline,
)
from multilingual_judge_pilot.judge_inference import (  # noqa: E402
    BaselineKind,
    JudgeExecutor,
    JudgeFacingInput,
    PromptSpec,
    RunConfig,
    STRUCTURED_PARSER_VERSION_V2,
    TranslationConfig,
    TranslationFacingInput,
    canonical_json,
)
from multilingual_judge_pilot.local_ollama import (  # noqa: E402
    OLLAMA_DEFAULT_BASE_URL,
    TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3,
    TRANSLATEGEMMA_PROMPT_VERSION,
    OllamaLocalClient,
    OllamaLocalJudgeProvider,
    OllamaLocalTranslator,
)
from multilingual_judge_pilot.p3_methodology_proposals import (  # noqa: E402
    DIRECT_PROMPT_V2,
    STRUCTURED_PROMPT_V2,
)
from multilingual_judge_pilot.reference_scoring import score_constraint_coverage  # noqa: E402
from multilingual_judge_pilot.translation_artifacts import TranslationArtifact  # noqa: E402


MODEL_TAGS = ("qwen3.5:9b-q4_K_M", "gemma4:12b-it-qat")
TRANSLATOR_TAG = "translategemma:4b-it-q4_K_M"
STRUCTURED_DECODING = {"num_ctx": 4096, "num_predict": 512, "seed": 17, "temperature": 0.0}
DIRECT_DECODING = {"num_ctx": 4096, "num_predict": 96, "seed": 17, "temperature": 0.0}


def _cmd(args: list[str], timeout: float = 8) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"unavailable:{type(exc).__name__}"
    value = (result.stdout + result.stderr).strip()
    return value if result.returncode == 0 else f"exit={result.returncode}: {value}"


def _loaded() -> list[str]:
    lines = _cmd(["ollama", "ps"]).splitlines()[1:]
    return [line.split()[0] for line in lines if line.split()]


class ResourceSampler:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self.samples: list[dict[str, object]] = []
        self.peak_runner_rss_bytes = 0

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)
        return {
            "samples": self.samples,
            "sample_count": len(self.samples),
            "peak_ollama_runner_rss_bytes": self.peak_runner_rss_bytes,
        }

    def _sample(self):
        while not self._stop.is_set():
            listing = _cmd(["ps", "-Ao", "rss=,command="])
            for row in listing.splitlines():
                if "ollama runner" in row or "llama-server --model" in row:
                    match = re.match(r"\s*(\d+)\s+", row)
                    if match:
                        self.peak_runner_rss_bytes = max(self.peak_runner_rss_bytes, int(match.group(1)) * 1024)
            pressure = _cmd(["memory_pressure"])
            pct = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure)
            self.samples.append({
                "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "memory_free_percentage": int(pct.group(1)) if pct else None,
                "swap_usage": _cmd(["sysctl", "vm.swapusage"]),
                "ollama_ps": _cmd(["ollama", "ps"]),
                "thermal_status": _cmd(["pmset", "-g", "therm"]),
            })
            self._stop.wait(1.0)


def _input_hash(items: list[dict[str, object]]) -> str:
    return hashlib.sha256(canonical_json(items).encode("utf-8")).hexdigest()


def _config(provider, baseline: str, prompt: PromptSpec, manifest_hash: str, *, translation=None) -> RunConfig:
    common = {
        "provider": provider.identity,
        "baseline": baseline,
        "prompt_bundle_version": prompt.version,
        "input_manifest_sha256": manifest_hash,
        "code_revision": _cmd(["git", "rev-parse", "HEAD"]),
        "random_seed": 17,
    }
    if baseline == BaselineKind.STRUCTURED_SINGLE_CALL.value:
        decoding = dict(STRUCTURED_DECODING)
        if "thinking" in provider.descriptor.capabilities:
            decoding["think"] = False
        common.update({
            "aggregation_version": "single-structured-verdict-2",
            "parser_version": STRUCTURED_PARSER_VERSION_V2,
            "decoding_parameters": tuple(sorted(decoding.items())),
        })
    elif baseline == BaselineKind.TRANSLATION_FIRST.value:
        decoding = dict(DIRECT_DECODING)
        if "thinking" in provider.descriptor.capabilities:
            decoding["think"] = False
        common.update({
            "translation": translation,
            "decoding_parameters": tuple(sorted(decoding.items())),
        })
    else:
        decoding = dict(DIRECT_DECODING)
        if "thinking" in provider.descriptor.capabilities:
            decoding["think"] = False
        common["decoding_parameters"] = tuple(sorted(decoding.items()))
    return RunConfig(**common)


def _run(config, provider, plan):
    started = time.perf_counter()
    result = JudgeExecutor(config, provider).run(plan)
    return result, time.perf_counter() - started


def _main() -> int:
    private = ROOT / ".research-data" / "p3-local-method-stabilization"
    output_dir = private / "runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    output_path = output_dir / f"synthetic-method-smoke-{started.strftime('%Y%m%dT%H%M%SZ')}.json"

    if _loaded():
        raise RuntimeError("Ollama must be idle before the bounded smoke; no unrelated model will be stopped")
    client = OllamaLocalClient(OLLAMA_DEFAULT_BASE_URL)
    version = client.get_version().get("version")
    if not isinstance(version, str):
        raise RuntimeError("local Ollama version is unavailable")
    judge_doc = json.loads((private / "judge_synthetic_items.json").read_text(encoding="utf-8"))
    judge_items = [JudgeFacingInput.from_mapping(row) for row in judge_doc["items"]]
    judge_evidence = [item.evidence_record() | {"language_condition": item.language_condition} for item in judge_items]
    manifest_hash = _input_hash(judge_evidence)
    # The reference key is intentionally opened only after all ordinary requests have been sent.
    records: list[dict[str, object]] = []
    output: dict[str, object] = {
        "record_version": "p3-local-method-stabilization-smoke-1",
        "checkpoint_status": "running",
        "scope": "independent synthetic compatibility only; not a competence screen or study evaluation",
        "endpoint": OLLAMA_DEFAULT_BASE_URL,
        "ollama_version": version,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "judge_fixture_sha256": manifest_hash,
        "prompt_versions": {"direct": DIRECT_PROMPT_V2.version, "structured": STRUCTURED_PROMPT_V2.version},
        "structured_contract": "structured-validity-v2",
        "structured_parser": STRUCTURED_PARSER_VERSION_V2,
        "fixed_generation_settings": {"direct": DIRECT_DECODING, "structured": STRUCTURED_DECODING},
        "model_descriptors": [],
        "translation_comparison": [],
        "judge_runs": [],
        "model_resources": {},
    }

    def checkpoint() -> None:
        output["judge_runs"] = records
        output["last_checkpoint_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        temporary = output_path.with_suffix(".tmp")
        temporary.write_text(canonical_json(output) + "\n", encoding="utf-8")
        temporary.replace(output_path)

    checkpoint()
    atexit.register(checkpoint)

    # Independent translation-fidelity comparison: isolated/protected A vs contextual/unshielded B.
    translator = OllamaLocalTranslator(client, TRANSLATOR_TAG)
    translator_descriptor = translator.descriptor
    translation_doc = json.loads((private / "translation_synthetic_items.json").read_text(encoding="utf-8"))
    translation_rows = translation_doc["items"]
    translation_resource_sampler = ResourceSampler().start()
    translation_started = time.perf_counter()
    for row in translation_rows:
        turns = tuple(
            __import__("multilingual_judge_pilot.judge_inference", fromlist=["ConversationTurn"]).ConversationTurn(**turn)
            for turn in row["turns"]
        )
        source = TranslationFacingInput(row["item_id"], turns)
        outputs: dict[str, object] = {"item_id": row["item_id"], "review_facets": row["review_facets"]}
        for label, prompt_version in (("A_isolated_literal_shield", TRANSLATEGEMMA_PROMPT_VERSION), ("B_context_unshielded", TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3)):
            translation_config = TranslationConfig(
                translator=translator.identity,
                pivot_language="en",
                prompt_version=prompt_version,
                decoding_parameters=(("num_ctx", 4096), ("num_predict", 512), ("seed", 17), ("temperature", 0.0)),
            )
            began = time.perf_counter()
            try:
                translation = translator.translate(source, translation_config)
                outputs[label] = {
                    "status": "success",
                    "config_hash": translation_config.config_hash,
                    "latency_seconds": time.perf_counter() - began,
                    "translated_turns": [t.to_record() for t in translation.translated_turns],
                    "raw_output": translation.raw_output,
                    "provider_call_records": list(translation.provider_call_records),
                }
            except Exception as exc:
                outputs[label] = {
                    "status": "failure",
                    "error_category": getattr(exc, "category", type(exc).__name__),
                    "raw_response": getattr(exc, "raw_response", None),
                    "provider_call_records": list(getattr(exc, "provider_call_records", ())),
                }
        output["translation_comparison"].append(outputs)
        checkpoint()
    translation_resource = translation_resource_sampler.stop()
    output["translation_runtime_seconds"] = time.perf_counter() - translation_started
    output["translation_resources"] = translation_resource
    output["translator_descriptor"] = translator_descriptor.to_record()

    # Build B-policy, hash-bound artifacts once from the judge fixture set for reuse across both judges.
    first_provider = OllamaLocalJudgeProvider(client, MODEL_TAGS[0])
    translator_config = TranslationConfig(
        translator=translator.identity,
        pivot_language="en",
            prompt_version=TRANSLATEGEMMA_CONTEXT_PROMPT_VERSION_V3,
        decoding_parameters=(("num_ctx", 4096), ("num_predict", 512), ("seed", 17), ("temperature", 0.0)),
    )
    artifacts: dict[str, TranslationArtifact] = {}
    translation_baseline = TranslationFirstBaseline(DIRECT_PROMPT_V2, translator)
    artifact_sampler = ResourceSampler().start()
    for item in judge_items:
        config = _config(
            first_provider,
            BaselineKind.TRANSLATION_FIRST.value,
            DIRECT_PROMPT_V2,
            manifest_hash,
            translation=translator_config,
        )
        plan = translation_baseline.prepare(item, config)
        if plan.preprocessing_result is None:
            artifacts[item.item_id] = TranslationArtifact.from_plan(item, config, plan)
        output.setdefault("translation_first_artifacts", []).append({
            "item_id": item.item_id,
            "artifact_sha256": artifacts[item.item_id].artifact_sha256 if item.item_id in artifacts else None,
            "translation_attempts": [x.to_record() for x in plan.translation_attempts],
        })
        checkpoint()
    output["artifact_translation_resources"] = artifact_sampler.stop()

    for model_tag in MODEL_TAGS:
        provider = OllamaLocalJudgeProvider(client, model_tag)
        descriptor = provider.descriptor
        output["model_descriptors"].append(descriptor.to_record())
        sampler = ResourceSampler().start()
        model_started = time.perf_counter()
        model_run_rows = []
        for item in judge_items:
            direct_config = _config(provider, BaselineKind.DIRECT_MULTILINGUAL.value, DIRECT_PROMPT_V2, manifest_hash)
            direct_plan = DirectMultilingualBaseline(DIRECT_PROMPT_V2).prepare(item, direct_config)
            if "expected_valid" in direct_plan.requests[0].to_json() or "canonical_state" in direct_plan.requests[0].to_json():
                raise RuntimeError("reference-only material entered an ordinary judge request")
            direct_result, direct_wall = _run(direct_config, provider, direct_plan)
            direct_row = {
                "model_tag": model_tag,
                "model_digest": descriptor.digest,
                "item_id": item.item_id,
                "language_condition": item.language_condition,
                "baseline": "direct_multilingual",
                "configuration_hash": direct_config.config_hash,
                "execution_id": direct_result.execution_id,
                "wall_seconds": direct_wall,
                "result": direct_result.to_record(),
            }
            records.append(direct_row)
            model_run_rows.append(direct_row)
            checkpoint()

            structured_config = _config(provider, BaselineKind.STRUCTURED_SINGLE_CALL.value, STRUCTURED_PROMPT_V2, manifest_hash)
            structured_plan = StructuredSingleCallBaseline(STRUCTURED_PROMPT_V2).prepare(item, structured_config)
            structured_result, structured_wall = _run(structured_config, provider, structured_plan)
            structured_row = {
                "model_tag": model_tag,
                "model_digest": descriptor.digest,
                "item_id": item.item_id,
                "language_condition": item.language_condition,
                "baseline": "structured_single_call",
                "configuration_hash": structured_config.config_hash,
                "execution_id": structured_result.execution_id,
                "wall_seconds": structured_wall,
                "result": structured_result.to_record(),
            }
            records.append(structured_row)
            model_run_rows.append(structured_row)
            checkpoint()

            artifact = artifacts.get(item.item_id)
            if artifact is not None:
                translation_run_config = _config(
                    provider,
                    BaselineKind.TRANSLATION_FIRST.value,
                    DIRECT_PROMPT_V2,
                    manifest_hash,
                    translation=translator_config,
                )
                translated_plan = translation_baseline.prepare(item, translation_run_config, translation_artifact=artifact)
                translated_result, translated_wall = _run(translation_run_config, provider, translated_plan)
                translated_row = {
                    "model_tag": model_tag,
                    "model_digest": descriptor.digest,
                    "item_id": item.item_id,
                    "language_condition": item.language_condition,
                    "baseline": "translation_first",
                    "translation_artifact_sha256": artifact.artifact_sha256,
                    "configuration_hash": translation_run_config.config_hash,
                    "execution_id": translated_result.execution_id,
                    "wall_seconds": translated_wall,
                    "result": translated_result.to_record(),
                }
                records.append(translated_row)
                model_run_rows.append(translated_row)
                checkpoint()
        resource_record = sampler.stop()
        output["model_resources"][model_tag] = {
            "elapsed_seconds": time.perf_counter() - model_started,
            **resource_record,
            "loaded_model_after_run": _cmd(["ollama", "ps"]),
        }
        if model_tag in _loaded():
            stopped = _cmd(["ollama", "stop", model_tag])
            if stopped.startswith("exit=") or stopped.startswith("unavailable:"):
                raise RuntimeError(f"could not unload model after bounded run: {model_tag}")

    # Reference material is joined only after all ordinary provider calls complete.
    reference_doc = json.loads((private / "judge_synthetic_reference.json").read_text(encoding="utf-8"))
    labels = reference_doc["labels"]
    for row in records:
        ref = labels[row["item_id"]]
        parsed = row["result"]["final_result"]
        row["synthetic_expected_valid"] = ref["expected_valid"]
        row["synthetic_verdict_correct"] = parsed["verdict"] == ("valid" if ref["expected_valid"] else "invalid")
        if row["baseline"] == "structured_single_call" and parsed["status"] == "parsed":
            requirements = [
                {**constraint, "requirement_id": constraint.get("requirement_id", f"{row['item_id']}-requirement-{index + 1}")}
                for index, constraint in enumerate(ref["constraints"])
            ]
            row["constraint_coverage"] = score_constraint_coverage(
                __import__("multilingual_judge_pilot.judge_inference", fromlist=["ParseResult"]).ParseResult(
                    status=__import__("multilingual_judge_pilot.judge_inference", fromlist=["ParseStatus"]).ParseStatus(parsed["status"]),
                    verdict=__import__("multilingual_judge_pilot.judge_inference", fromlist=["Verdict"]).Verdict(parsed["verdict"]),
                    tool_contract=parsed["tool_contract"],
                    structured_assessments=tuple(
                        __import__("multilingual_judge_pilot.judge_inference", fromlist=["ConstraintAssessment"]).ConstraintAssessment(
                            x["constraint_type"],x["assessment"],tuple(x["source_turn_indices"])
                        ) for x in parsed["constraint_assessments"]
                    ),
                ),
                requirements,
            ).__dict__
    output["completed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output["checkpoint_status"] = "completed"
    output["judge_runs"] = records
    checkpoint()
    print(json.dumps({
        "record_path": str(output_path),
        "judge_runs": len(records),
        "translation_comparisons": len(output["translation_comparison"]),
        "shared_artifacts": sum(x["artifact_sha256"] is not None for x in output.get("translation_first_artifacts", [])),
        "run_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
