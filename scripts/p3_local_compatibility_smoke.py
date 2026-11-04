#!/usr/bin/env python3
"""Bounded Ollama compatibility smoke using independent synthetic fixtures only.

This is not a model-qualification screen or a benchmark runner. It reads no
study-data paths and writes its complete synthetic run record under ignored
.research-data/p3-local-smoke/.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import argparse
import atexit
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from p3_local_smoke_fixtures import CASES, local_smoke_items  # noqa: E402
from multilingual_judge_pilot.judge_baselines import (  # noqa: E402
    DirectMultilingualBaseline,
    StructuredSingleCallBaseline,
    TranslationFirstBaseline,
)
from multilingual_judge_pilot.judge_inference import (  # noqa: E402
    BaselineKind,
    JudgeExecutor,
    PromptSpec,
    RunConfig,
    TranslationConfig,
    canonical_json,
)
from multilingual_judge_pilot.local_ollama import (  # noqa: E402
    OLLAMA_DEFAULT_BASE_URL,
    TRANSLATEGEMMA_PROMPT_VERSION,
    OllamaLocalClient,
    OllamaLocalJudgeProvider,
    OllamaLocalTranslator,
)
from multilingual_judge_pilot.translation_artifacts import TranslationArtifact  # noqa: E402
from p3_synthetic_fixtures import fixture_input_manifest_sha256  # noqa: E402


MODEL_TAGS = ("qwen3.5:9b-q4_K_M", "gemma4:12b-it-qat")
TRANSLATOR_TAG = "translategemma:4b-it-q4_K_M"
OWNED_MODEL_TAGS = frozenset((*MODEL_TAGS, TRANSLATOR_TAG))
DIRECT_PROMPT = PromptSpec(
    "p3-local-synthetic-direct-smoke-v1",
    "Synthetic-only check. Assess whether the proposed action follows the conversation's applicable instructions at the action point and the public tool contract. Treat later instructions as revisions where they apply. Return only the binary JSON verdict in the supplied schema.",
)
STRUCTURED_PROMPT = PromptSpec(
    "p3-local-synthetic-structured-smoke-v1",
    "Synthetic-only check. Using the same conversation, action, and public tool contract, separately assess tool-contract conformance and each relevant numerical, temporal, permission, or other constraint. Cite the source turn index for each assessment. Then apply the schema's deterministic rule: any violation means invalid; otherwise valid. Return only the supplied structured JSON schema.",
)


def _run_command(args: list[str], *, timeout: float = 10) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"unavailable:{type(exc).__name__}"
    output = (result.stdout + result.stderr).strip()
    return output if result.returncode == 0 else f"exit={result.returncode}: {output}"


def _loaded_model_tags() -> list[str]:
    output = _run_command(["ollama", "ps"])
    if output.startswith("unavailable:") or output.startswith("exit="):
        raise RuntimeError(f"could not verify loaded Ollama models: {output}")
    lines = output.splitlines()[1:]
    return [line.split()[0] for line in lines if line.split()]


def _stop_model(model_tag: str) -> dict[str, str]:
    if model_tag not in OWNED_MODEL_TAGS:
        raise RuntimeError(f"refusing to stop an Ollama model not owned by this smoke run: {model_tag}")
    stop_result = _run_command(["ollama", "stop", model_tag])
    if stop_result.startswith("unavailable:") or stop_result.startswith("exit="):
        raise RuntimeError(f"could not unload {model_tag}: {stop_result}")
    loaded = _loaded_model_tags()
    if model_tag in loaded:
        raise RuntimeError(f"Ollama still reports {model_tag} as loaded")
    if loaded:
        raise RuntimeError(f"another Ollama model became loaded during the smoke: {loaded}")
    return {"model_tag": model_tag, "stop_result": stop_result, "remaining_loaded_models": ",".join(loaded)}


def _stop_any_loaded_models() -> None:
    try:
        for model_tag in _loaded_model_tags():
            if model_tag not in OWNED_MODEL_TAGS:
                continue
            _run_command(["ollama", "stop", model_tag])
    except Exception:
        pass


def _system_snapshot() -> dict[str, object]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "memory_pressure": _run_command(["memory_pressure"]),
        "vm_stat": _run_command(["vm_stat"]),
        "swap_usage": _run_command(["sysctl", "vm.swapusage"]),
        "thermal_status": _run_command(["pmset", "-g", "therm"]),
        "ollama_ps": _run_command(["ollama", "ps"]),
    }


class RunnerMemorySampler:
    """Sample Ollama process RSS as a lower-bound memory measure."""

    def __init__(self, interval_seconds: float = 1.0):
        self.interval_seconds = interval_seconds
        self.peak_rss_bytes = 0
        self.sample_count = 0
        self.pids: set[int] = set()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        return {"ollama_process_peak_rss_bytes": self.peak_rss_bytes, "samples": self.sample_count, "pids": sorted(self.pids)}

    def _sample(self):
        while not self._stop.is_set():
            listing = _run_command(["ps", "-Ao", "pid=,rss=,command="])
            for line in listing.splitlines():
                if "ollama runner" not in line or "rg " in line:
                    continue
                pieces = line.strip().split(None, 2)
                if len(pieces) < 3:
                    continue
                try:
                    pid, rss_kib = int(pieces[0]), int(pieces[1])
                except ValueError:
                    continue
                self.pids.add(pid)
                self.peak_rss_bytes = max(self.peak_rss_bytes, rss_kib * 1024)
            self.sample_count += 1
            self._stop.wait(self.interval_seconds)


class SystemResourceSampler:
    """Capture system pressure, swap, thermal, and Ollama placement during calls."""

    def __init__(self, interval_seconds: float = 5.0):
        self.interval_seconds = interval_seconds
        self.snapshots: list[dict[str, object]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=12)
        return {
            "system_resource_sample_count": len(self.snapshots),
            "system_resource_samples": self.snapshots,
            "minimum_memory_free_percentage": min(
                (snapshot["memory_free_percentage"] for snapshot in self.snapshots if isinstance(snapshot.get("memory_free_percentage"), int)),
                default=None,
            ),
        }

    def _sample(self):
        while not self._stop.is_set():
            pressure = _run_command(["memory_pressure"])
            match = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure)
            self.snapshots.append({
                "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "memory_free_percentage": int(match.group(1)) if match else None,
                "swap_usage": _run_command(["sysctl", "vm.swapusage"]),
                "ollama_ps": _run_command(["ollama", "ps"]),
                "thermal_status": _run_command(["pmset", "-g", "therm"]),
            })
            self._stop.wait(self.interval_seconds)


def _make_run_config(provider, baseline: str, *, prompt_version: str, input_hash: str, decoding: dict[str, object], translation=None) -> RunConfig:
    kwargs = {}
    if baseline == BaselineKind.STRUCTURED_SINGLE_CALL.value:
        kwargs["aggregation_version"] = "single-structured-verdict-1"
    return RunConfig(
        provider=provider.identity,
        baseline=baseline,
        prompt_bundle_version=prompt_version,
        input_manifest_sha256=input_hash,
        code_revision=_run_command(["git", "rev-parse", "HEAD"]),
        decoding_parameters=tuple(sorted(decoding.items())),
        translation=translation,
        **kwargs,
    )


def _record_metrics(run_record: dict[str, object]) -> dict[str, object]:
    result = run_record["result"]
    values = []
    if isinstance(result, dict):
        for step in result.get("steps", []):
            for attempt in step.get("attempts", []):
                values.append(attempt)
    prompt_tps = []
    generation_tps = []
    load_durations = []
    for attempt in values:
        prompt_tokens = attempt.get("prompt_tokens")
        completion_tokens = attempt.get("completion_tokens")
        prompt_ns = attempt.get("prompt_eval_duration_ns")
        generation_ns = attempt.get("generation_duration_ns")
        if type(prompt_tokens) is int and type(prompt_ns) is int and prompt_ns > 0:
            prompt_tps.append(prompt_tokens / (prompt_ns / 1_000_000_000))
        if type(completion_tokens) is int and type(generation_ns) is int and generation_ns > 0:
            generation_tps.append(completion_tokens / (generation_ns / 1_000_000_000))
        if type(attempt.get("load_duration_ns")) is int:
            load_durations.append(attempt["load_duration_ns"])
    return {
        "prompt_tokens_per_second": prompt_tps[0] if prompt_tps else None,
        "generated_tokens_per_second": generation_tps[0] if generation_tps else None,
        "parse_status": result.get("final_result", {}).get("status") if isinstance(result, dict) else None,
        "verdict": result.get("final_result", {}).get("verdict") if isinstance(result, dict) else None,
        "wall_latency_ms": sum(item.get("latency_ms", 0) for item in values),
        "prompt_tokens": sum(item.get("prompt_tokens") or 0 for item in values),
        "completion_tokens": sum(item.get("completion_tokens") or 0 for item in values),
        "model_load_duration_ns": sum(load_durations),
        "model_generation_duration_ns": sum(item.get("generation_duration_ns") or 0 for item in values),
        "model_prompt_duration_ns": sum(item.get("prompt_eval_duration_ns") or 0 for item in values),
    }


def _executor_run(config, provider, plan) -> dict[str, object]:
    sampler = RunnerMemorySampler().start()
    system_sampler = SystemResourceSampler().start()
    started = time.perf_counter()
    try:
        result = JudgeExecutor(config, provider).run(plan)
        wall = time.perf_counter() - started
    finally:
        resources = sampler.stop()
        system_resources = system_sampler.stop()
    return {"result": result.to_record(), "wall_seconds": wall, "resources": {**resources, **system_resources}}


def _model_generation_rate(result_record: dict[str, object]) -> float | None:
    result = result_record.get("result")
    if not isinstance(result, dict):
        return None
    rates = []
    for step in result.get("steps", []):
        for attempt in step.get("attempts", []):
            tokens = attempt.get("completion_tokens")
            duration = attempt.get("generation_duration_ns")
            if type(tokens) is int and type(duration) is int and duration > 0:
                rates.append(tokens / (duration / 1_000_000_000))
    return rates[0] if rates else None


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run a bounded synthetic-only local Ollama compatibility smoke.")
    parser.add_argument(
        "--model-tag", action="append", choices=MODEL_TAGS, dest="model_tags",
        help="Judge candidate to test; may be repeated. Defaults to both approved candidates.",
    )
    parser.add_argument(
        "--skip-translation", action="store_true",
        help="Run judge baselines only when TranslateGemma is not installed; translation-first is explicitly omitted.",
    )
    args = parser.parse_args(argv)
    args.model_tags = args.model_tags or list(MODEL_TAGS)
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = ROOT / ".research-data" / "p3-local-smoke"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"synthetic-local-smoke-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"

    def checkpoint(document: dict[str, object]) -> None:
        temporary = file_path.with_suffix(".tmp")
        temporary.write_text(canonical_json(document) + "\n", encoding="utf-8")
        temporary.replace(file_path)

    loaded_at_start = _loaded_model_tags()
    if loaded_at_start:
        raise RuntimeError(f"Ollama already has model(s) loaded; smoke requires an empty server: {loaded_at_start}")
    atexit.register(_stop_any_loaded_models)
    start_state = _system_snapshot()
    client = OllamaLocalClient(OLLAMA_DEFAULT_BASE_URL)
    ollama_version = client.get_version().get("version")
    if not isinstance(ollama_version, str):
        raise RuntimeError("local Ollama version endpoint did not return a version")
    rows = local_smoke_items()
    synthetic_manifest = sha256(canonical_json([
        {"case_id": case, "condition": condition, **item.evidence_record()} for case, condition, item in rows
    ]).encode("utf-8")).hexdigest()
    output: dict[str, object] = {
        "record_version": "p3-local-compatibility-smoke-2",
        "scope": "independent synthetic fixtures only; not screening, evaluation, or model selection",
        "endpoint": OLLAMA_DEFAULT_BASE_URL,
        "ollama_version": ollama_version,
        "started_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "synthetic_fixture_sha256": synthetic_manifest,
        "study_fixture_manifest_marker": fixture_input_manifest_sha256(),
        "initial_system_snapshot": start_state,
        "record_path": str(file_path),
        "model_descriptors": [],
        "translation": {"status": "skipped_by_option" if args.skip_translation else "pending", "attempts": [], "artifacts": {}},
        "judge_runs": [],
        "context_8192_probes": [],
        "model_summaries": {},
        "model_unload_checks": [],
    }
    checkpoint(output)

    translator = None
    translator_descriptor = None
    translation_config = None
    artifacts: dict[str, TranslationArtifact] = {}
    translation_attempts_by_item: dict[str, tuple[object, ...]] = {}
    translation_run_config = None
    if not args.skip_translation:
        translator = OllamaLocalTranslator(client, TRANSLATOR_TAG)
        translator_descriptor = translator.descriptor
        output["translator_descriptor"] = translator_descriptor.to_record()
        translation_config = TranslationConfig(
            translator=translator.identity,
            pivot_language="en",
            prompt_version=TRANSLATEGEMMA_PROMPT_VERSION,
            decoding_parameters=(("num_ctx", 4096), ("num_predict", 512), ("seed", 17), ("temperature", 0.0)),
        )
        artifact_provider = OllamaLocalJudgeProvider(client, args.model_tags[0])
        translation_run_config = _make_run_config(
            artifact_provider,
            BaselineKind.TRANSLATION_FIRST.value,
            prompt_version=DIRECT_PROMPT.version,
            input_hash=synthetic_manifest,
            decoding={"num_ctx": 4096, "num_predict": 64, "seed": 17, "temperature": 0.0, **({"think": False} if "thinking" in artifact_provider.descriptor.capabilities else {})},
            translation=translation_config,
        )
        translation_baseline = TranslationFirstBaseline(DIRECT_PROMPT, translator)
        for case_id, condition, item in rows:
            plan = translation_baseline.prepare(item, translation_run_config)
            translation_attempts_by_item[item.item_id] = plan.translation_attempts
            record = {
                "case_id": case_id,
                "condition": condition,
                "item_id": item.item_id,
                "turn_shape": [{"turn_index": turn.turn_index, "speaker": turn.speaker, "language": turn.language} for turn in item.conversation],
                "translation_attempts": [attempt.to_record() for attempt in plan.translation_attempts],
                "translation_records": [record.to_record() for record in plan.translation_records],
                "preprocessing_status": plan.preprocessing_result.status.value if plan.preprocessing_result else "translated",
            }
            if plan.requests:
                artifact = TranslationArtifact.from_plan(item, translation_run_config, plan)
                artifacts[item.item_id] = artifact
                output["translation"]["artifacts"][item.item_id] = artifact.to_record()
                record["translation_artifact_sha256"] = artifact.artifact_sha256
                record["translated_turns"] = [turn.to_record() for turn in artifact.translated_turns]
            output["translation"]["attempts"].append(record)
            checkpoint(output)
        output["translation"]["status"] = "completed"
        output["translation"]["unique_artifacts"] = len(artifacts)
        output["translation"]["provider_call_count"] = sum(
            len(attempt.get("provider_call_records", []))
            for row in output["translation"]["attempts"]
            for attempt in row["translation_attempts"]
        )
        checkpoint(output)
        output["model_unload_checks"].append(_stop_model(TRANSLATOR_TAG))
        checkpoint(output)

    for model_tag in args.model_tags:
        provider = OllamaLocalJudgeProvider(client, model_tag)
        descriptor = provider.descriptor
        output["model_descriptors"].append(descriptor.to_record())
        checkpoint(output)
        model_runs: list[dict[str, object]] = []
        for case_id, condition, item in rows:
            direct_decoding = {"num_ctx": 4096, "num_predict": 64, "seed": 17, "temperature": 0.0}
            if "thinking" in descriptor.capabilities:
                direct_decoding["think"] = False
            direct_config = _make_run_config(
                provider, BaselineKind.DIRECT_MULTILINGUAL.value,
                prompt_version=DIRECT_PROMPT.version, input_hash=synthetic_manifest, decoding=direct_decoding,
            )
            direct_plan = DirectMultilingualBaseline(DIRECT_PROMPT).prepare(item, direct_config)
            direct_run = _executor_run(direct_config, provider, direct_plan)
            direct_record = {
                "model_tag": model_tag, "model_digest": descriptor.digest, "case_id": case_id,
                "condition": condition, "baseline": "direct_multilingual", "synthetic_expected_valid": CASES[case_id]["expected_valid"],
                **direct_run, "metrics": _record_metrics(direct_run),
            }
            direct_record["synthetic_verdict_correct"] = (
                direct_run["result"]["final_result"].get("verdict")
                == ("valid" if CASES[case_id]["expected_valid"] else "invalid")
            )
            model_runs.append(direct_record)
            output["judge_runs"].append(direct_record)
            checkpoint(output)

            structured_decoding = {**direct_decoding, "num_predict": 256}
            structured_config = _make_run_config(
                provider, BaselineKind.STRUCTURED_SINGLE_CALL.value,
                prompt_version=STRUCTURED_PROMPT.version, input_hash=synthetic_manifest, decoding=structured_decoding,
            )
            structured_plan = StructuredSingleCallBaseline(STRUCTURED_PROMPT).prepare(item, structured_config)
            structured_run = _executor_run(structured_config, provider, structured_plan)
            structured_record = {
                "model_tag": model_tag, "model_digest": descriptor.digest, "case_id": case_id,
                "condition": condition, "baseline": "structured_single_call", "synthetic_expected_valid": CASES[case_id]["expected_valid"],
                **structured_run, "metrics": _record_metrics(structured_run),
            }
            parsed = structured_run["result"]["final_result"]
            expected_assessment = CASES[case_id]["expected_structured"]
            structured_record["expected_dimension_assessment_correct"] = (
                parsed.get("status") == "parsed"
                and any(
                    row["constraint_type"] == expected_assessment["constraint_type"]
                    and row["assessment"] == expected_assessment["assessment"]
                    and row["source_turn_indices"] == expected_assessment["source_turn_indices"]
                    for row in parsed.get("constraint_assessments", [])
                )
            )
            structured_record["synthetic_verdict_correct"] = (
                parsed.get("verdict") == ("valid" if CASES[case_id]["expected_valid"] else "invalid")
            )
            model_runs.append(structured_record)
            output["judge_runs"].append(structured_record)
            checkpoint(output)

            if args.skip_translation:
                continue

            artifact = artifacts.get(item.item_id)
            if artifact is None:
                skipped_record = {
                    "model_tag": model_tag, "model_digest": descriptor.digest, "case_id": case_id,
                    "condition": condition, "baseline": "translation_first", "synthetic_expected_valid": CASES[case_id]["expected_valid"],
                    "status": "skipped_translation_failure", "translation_attempts": [a.to_record() for a in translation_attempts_by_item[item.item_id]],
                }
                model_runs.append(skipped_record)
                output["judge_runs"].append(skipped_record)
                checkpoint(output)
                continue
            assert translation_config is not None and translator is not None
            translation_config_for_judge = TranslationConfig(
                translator=translator.identity,
                pivot_language="en",
                prompt_version=TRANSLATEGEMMA_PROMPT_VERSION,
                decoding_parameters=translation_config.decoding_parameters,
            )
            translation_judge_config = _make_run_config(
                provider, BaselineKind.TRANSLATION_FIRST.value,
                prompt_version=DIRECT_PROMPT.version, input_hash=synthetic_manifest, decoding=direct_decoding,
                translation=translation_config_for_judge,
            )
            translation_plan = TranslationFirstBaseline(DIRECT_PROMPT, translator).prepare(
                item, translation_judge_config, translation_artifact=artifact,
            )
            translation_run = _executor_run(translation_judge_config, provider, translation_plan)
            translation_record = {
                "model_tag": model_tag, "model_digest": descriptor.digest, "case_id": case_id,
                "condition": condition, "baseline": "translation_first", "synthetic_expected_valid": CASES[case_id]["expected_valid"],
                "translation_artifact_sha256": artifact.artifact_sha256,
                **translation_run, "metrics": _record_metrics(translation_run),
            }
            translation_record["synthetic_verdict_correct"] = (
                translation_run["result"]["final_result"].get("verdict")
                == ("valid" if CASES[case_id]["expected_valid"] else "invalid")
            )
            model_runs.append(translation_record)
            output["judge_runs"].append(translation_record)
            checkpoint(output)

        # One 8K context probe per candidate, using only the first synthetic request.
        first_case, first_condition, first_item = rows[0]
        probe_decoding = {"num_ctx": 8192, "num_predict": 64, "seed": 17, "temperature": 0.0}
        if "thinking" in descriptor.capabilities:
            probe_decoding["think"] = False
        probe_config = _make_run_config(
            provider, BaselineKind.DIRECT_MULTILINGUAL.value,
            prompt_version=DIRECT_PROMPT.version, input_hash=synthetic_manifest, decoding=probe_decoding,
        )
        probe_plan = DirectMultilingualBaseline(DIRECT_PROMPT).prepare(first_item, probe_config)
        probe = _executor_run(probe_config, provider, probe_plan)
        output["context_8192_probes"].append({
            "model_tag": model_tag, "model_digest": descriptor.digest, "case_id": first_case,
            "condition": first_condition, **probe, "metrics": _record_metrics(probe),
        })
        checkpoint(output)
        rates = [_model_generation_rate(run) for run in model_runs]
        rates = [rate for rate in rates if rate is not None]
        baseline_trends = {}
        for baseline_name in ("direct_multilingual", "structured_single_call", "translation_first"):
            baseline_rates = [
                _model_generation_rate(run) for run in model_runs
                if run.get("baseline") == baseline_name and "result" in run
            ]
            baseline_rates = [rate for rate in baseline_rates if rate is not None]
            baseline_trends[baseline_name] = {
                "first_five_generation_tps_median": statistics.median(baseline_rates[:5]) if len(baseline_rates) >= 5 else None,
                "last_five_generation_tps_median": statistics.median(baseline_rates[-5:]) if len(baseline_rates) >= 5 else None,
            }
        status_counts = {}
        for run in model_runs:
            status = run.get("metrics", {}).get("parse_status")
            if isinstance(status, str):
                status_counts[status] = status_counts.get(status, 0) + 1
        output["model_summaries"][model_tag] = {
            "judge_call_count": sum(run.get("baseline") in {"direct_multilingual", "translation_first", "structured_single_call"} and "result" in run for run in model_runs),
            "parsed_output_count": sum(run.get("metrics", {}).get("parse_status") == "parsed" for run in model_runs),
            "parse_status_counts": status_counts,
            "load_duration_ns_total": sum(run.get("metrics", {}).get("model_load_duration_ns", 0) for run in model_runs),
            "generation_tps_median": statistics.median(rates) if rates else None,
            "first_five_generation_tps_median": statistics.median(rates[:5]) if len(rates) >= 5 else None,
            "last_five_generation_tps_median": statistics.median(rates[-5:]) if len(rates) >= 5 else None,
            "baseline_generation_rate_trends": baseline_trends,
            "synthetic_verdict_correct_count": sum(run.get("synthetic_verdict_correct") is True for run in model_runs),
            "structured_expected_dimension_correct_count": sum(run.get("expected_dimension_assessment_correct") is True for run in model_runs),
            "ollama_ps_after_model": _run_command(["ollama", "ps"]),
        }
        checkpoint(output)
        output["model_unload_checks"].append(_stop_model(model_tag))
        checkpoint(output)

    output["final_system_snapshot"] = _system_snapshot()
    output["completed_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    checkpoint(output)
    record_sha256 = sha256(file_path.read_bytes()).hexdigest()
    file_path.with_suffix(".json.sha256").write_text(f"{record_sha256}  {file_path.name}\n", encoding="utf-8")
    print(canonical_json({
        "record_path": str(file_path),
        "record_sha256": record_sha256,
        "synthetic_fixture_sha256": synthetic_manifest,
        "ollama_version": ollama_version,
        "installed_models": [entry["model_tag"] for entry in output["model_descriptors"]] + ([translator_descriptor.model_tag] if translator_descriptor else []),
        "translation_unique_artifacts": output["translation"].get("unique_artifacts", 0),
        "translation_provider_calls": output["translation"].get("provider_call_count", 0),
        "judge_runs": len(output["judge_runs"]),
        "model_summaries": output["model_summaries"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
