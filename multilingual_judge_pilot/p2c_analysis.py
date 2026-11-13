"""Separate reference-side scoring and scenario-clustered P2C analysis."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
from typing import Callable, Mapping, Sequence

from .judge_inference import ConstraintAssessment, ParseResult, ParseStatus, Verdict, canonical_json
from .p2c_inference import _result_path, load_frozen_inputs
from .p2c_study_config import build_run_configs
from .qualification import sha256_text
from .reference_scoring import score_constraint_coverage


ANALYSIS_VERSION = "p2c-full-study-analysis-1"
BASELINES = ("direct", "translation_first", "structured")
CONDITIONS = ("EN-EN", "AR-AR", "EN-AR", "AR-EN")


class AnalysisError(RuntimeError):
    """Frozen outputs or reference-only analysis inputs are inconsistent."""


def _unique_json_object(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise AnalysisError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object)
    except (OSError, json.JSONDecodeError, AnalysisError) as exc:
        raise AnalysisError(f"analysis input is missing or invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"analysis input must be an object: {path.name}")
    return value


def _verified_reference_file(root: Path, manifest: Mapping[str, object], relative: str) -> dict:
    expected = manifest.get("files", {}).get(relative)
    path = root / relative
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AnalysisError(f"reference analysis file is unavailable: {relative}") from exc
    if hashlib.sha256(raw).hexdigest() != expected:
        raise AnalysisError(f"reference analysis file hash mismatch: {relative}")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, AnalysisError) as exc:
        raise AnalysisError(f"reference analysis file is invalid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"reference analysis file must contain an object: {relative}")
    return value


def _parse_result(final: Mapping[str, object]) -> ParseResult:
    try:
        status = ParseStatus(final["status"])
        verdict = Verdict(final["verdict"]) if final.get("verdict") is not None else None
        tool_contract = final.get("tool_contract")
        assessments = tuple(
            ConstraintAssessment(row["constraint_type"], row["assessment"], tuple(row["source_turn_indices"]))
            for row in final.get("constraint_assessments", [])
        )
        return ParseResult(status, verdict, tool_contract, assessments)
    except (KeyError, TypeError, ValueError) as exc:
        raise AnalysisError("retained final parser result is malformed") from exc


def _result_records(
    root: Path,
    baseline: str,
    expected_hashes: Mapping[str, str],
    input_manifest_sha: str,
    configuration_hash: str,
) -> tuple[dict[str, dict], dict[str, object]]:
    run_root = root / "runs" / baseline
    run_path = run_root / "run-manifest.json"
    output_path = run_root / "run-output-manifest.json"
    if not run_path.exists():
        return {}, {"status": "not_started", "result_count": 0, "manifest_sha256": None}
    if not output_path.exists():
        raise AnalysisError(f"{baseline} has no immutable output manifest; resume the run before analysis")
    run = _read_json(run_path)
    output = _read_json(output_path)
    if (
        run.get("baseline") != baseline
        or run.get("input_manifest_sha256") != input_manifest_sha
        or output.get("input_manifest_sha256") != input_manifest_sha
        or run.get("configuration_hash") != configuration_hash
        or run.get("item_hashes") != dict(expected_hashes)
    ):
        raise AnalysisError(f"{baseline} run is bound to another frozen input manifest")
    if output.get("run_execution_id") != run.get("run_execution_id") or output.get("configuration_hash") != run.get("configuration_hash"):
        raise AnalysisError(f"{baseline} output manifest is not bound to its run manifest")
    if output.get("item_hashes") != dict(expected_hashes) or output.get("status") != run.get("status"):
        raise AnalysisError(f"{baseline} output manifest differs from the immutable run inventory/status")
    output_body = {key: value for key, value in output.items() if key != "manifest_sha256"}
    if sha256_text(canonical_json(output_body)) != output.get("manifest_sha256"):
        raise AnalysisError(f"{baseline} output manifest self-hash is invalid")
    result_hashes = output.get("result_sha256")
    if not isinstance(result_hashes, dict) or set(result_hashes) - set(expected_hashes):
        raise AnalysisError(f"{baseline} output manifest has unknown item IDs")
    directory = run_root / "items"
    observed_files = {path.name for path in directory.glob("*.result.json")} if directory.exists() else set()
    expected_files = {f"{hashlib.sha256(item_id.encode('utf-8')).hexdigest()}.result.json" for item_id in result_hashes}
    if observed_files != expected_files:
        raise AnalysisError(f"{baseline} has unmanifested or missing result files")
    records = {}
    for item_id, digest in result_hashes.items():
        path = _result_path(run_root, item_id)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AnalysisError(f"{baseline} result file is missing") from exc
        if hashlib.sha256(raw).hexdigest() != digest:
            raise AnalysisError(f"{baseline} result file hash mismatch")
        try:
            envelope = json.loads(raw, object_pairs_hook=_unique_json_object)
        except (json.JSONDecodeError, AnalysisError) as exc:
            raise AnalysisError(f"{baseline} result file is invalid JSON") from exc
        if (
            not isinstance(envelope, dict)
            or envelope.get("item_id") != item_id
            or envelope.get("item_sha256") != expected_hashes[item_id]
            or envelope.get("configuration_hash") != run.get("configuration_hash")
            or envelope.get("run_execution_id") != run.get("run_execution_id")
            or not isinstance(envelope.get("run_result"), dict)
            or envelope.get("baseline") != baseline
            or envelope["run_result"].get("item_id") != item_id
            or envelope["run_result"].get("configuration_hash") != configuration_hash
            or envelope.get("execution_id") != hashlib.sha256(f"{run['run_execution_id']}\0{item_id}".encode("utf-8")).hexdigest()
            or envelope["run_result"].get("baseline") != {
                "direct": "direct_multilingual",
                "translation_first": "translation_first",
                "structured": "structured_single_call",
            }[baseline]
        ):
            raise AnalysisError(f"{baseline} result envelope is not hash-bound to its item/run")
        records[item_id] = envelope
    return records, {"status": output.get("status"), "result_count": len(records), "manifest_sha256": output.get("manifest_sha256"), "configuration_hash": run.get("configuration_hash")}


def _score_items(
    item_rows: Sequence[Mapping[str, object]],
    envelopes: Mapping[str, Mapping[str, object]],
    reference: Mapping[str, Mapping[str, object]],
    metadata: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    scored = []
    for item in item_rows:
        item_id = str(item["item_id"])
        if item_id not in reference or item_id not in metadata:
            raise AnalysisError("reference key or analysis metadata is missing a frozen item")
        ref = reference[item_id]
        try:
            ref_label = Verdict(ref["reference_verdict"])
        except (KeyError, ValueError) as exc:
            raise AnalysisError("reference key contains an invalid verdict") from exc
        envelope = envelopes.get(item_id)
        if envelope is None:
            status = "technical_missing"
            prediction = None
            correct = False
            terminal = "missing"
            parse_record = {"status": status, "verdict": None, "tool_contract": None, "constraint_assessments": []}
            coverage = None
        else:
            result = envelope["run_result"]
            final = result.get("final_result")
            if not isinstance(final, Mapping):
                raise AnalysisError("run result has no final parser result")
            parse_result = _parse_result(final)
            status = parse_result.status.value
            prediction = parse_result.verdict.value if parse_result.verdict else None
            correct = prediction == ref_label.value
            terminal = str(result.get("terminal_stage", "judge"))
            parse_record = parse_result.to_record()
            requirements = ref.get("reference_requirements")
            coverage = score_constraint_coverage(parse_result, requirements) if isinstance(requirements, list) else None
        meta = metadata[item_id]
        scored.append({
            "item_id": item_id,
            "scenario_id": meta["scenario_id"],
            "pair_id": meta["pair_id"],
            "history_id": meta["history_id"],
            "history_position": meta["history_position"],
            "partition": meta["partition"],
            "dataset_kind": meta["dataset_kind"],
            "domain": meta["domain"],
            "transition_family": meta["transition_family"],
            "language_condition": item["language_condition"],
            "reference": ref_label.value,
            "prediction": prediction,
            "correct": bool(correct),
            "parse_status": status,
            "terminal_stage": terminal,
            "translation_failure": terminal == "translation",
            "parse_record": parse_record,
            "coverage": coverage,
        })
    return scored


def _confusion(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, int]]:
    matrix = {reference: {prediction: 0 for prediction in ("valid", "invalid", "unparseable")} for reference in ("valid", "invalid")}
    for row in rows:
        predicted = row["prediction"] or "unparseable"
        matrix[row["reference"]][predicted] += 1
    return matrix


def _metrics(rows: Sequence[Mapping[str, object]], *, planned: int | None = None, confidence: bool = False) -> dict[str, object]:
    denominator = planned if planned is not None else len(rows)
    correct = sum(row["correct"] for row in rows)
    valid_total = sum(row["reference"] == "valid" for row in rows)
    invalid_total = sum(row["reference"] == "invalid" for row in rows)
    valid_correct = sum(row["reference"] == "valid" and row["prediction"] == "valid" for row in rows)
    invalid_correct = sum(row["reference"] == "invalid" and row["prediction"] == "invalid" for row in rows)
    result = {
        "planned_denominator": denominator,
        "result_records": len(rows),
        "correct": correct,
        "accuracy": correct / denominator if denominator else None,
        "valid_recall": valid_correct / valid_total if valid_total else None,
        "invalid_recall": invalid_correct / invalid_total if invalid_total else None,
        "valid_count": valid_total,
        "invalid_count": invalid_total,
        "confusion_matrix": _confusion(rows),
        "prediction_distribution": dict(Counter(row["prediction"] or "unparseable" for row in rows)),
        "parse_status_counts": dict(Counter(row["parse_status"] for row in rows)),
        "technical_missing": sum(row["parse_status"] == "technical_missing" for row in rows),
        "translation_failures": sum(row["translation_failure"] for row in rows),
    }
    if confidence:
        result["scenario_clustered_95pct_ci"] = _cluster_bootstrap_ci(rows)
    return result


def _cluster_bootstrap_ci(rows: Sequence[Mapping[str, object]], *, replicates: int = 2000) -> dict[str, object]:
    clusters: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        clusters[str(row["scenario_id"])].append(row)
    ids = sorted(clusters)
    if not ids:
        return {"lower": None, "upper": None, "replicates": replicates, "cluster_count": 0}
    rng = random.Random(20261113)
    samples = []
    for _ in range(replicates):
        selected = [rng.choice(ids) for _ in ids]
        sample = [row for scenario_id in selected for row in clusters[scenario_id]]
        samples.append(sum(row["correct"] for row in sample) / len(sample))
    samples.sort()
    return {
        "lower": samples[max(0, int(0.025 * replicates) - 1)],
        "upper": samples[min(replicates - 1, int(0.975 * replicates) - 1)],
        "replicates": replicates,
        "cluster_count": len(ids),
    }


def _group_metrics(rows: Sequence[Mapping[str, object]], field: str) -> dict[str, object]:
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {key: _metrics(groups[key], confidence=True) for key in sorted(groups)}


def _counterfactual_consistency(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["scenario_id"]), str(row["language_condition"]))].append(row)
    pair_rows = [values for values in groups.values() if len(values) == 2]
    consistent = sum(
        values[0]["prediction"] in {"valid", "invalid"}
        and values[1]["prediction"] in {"valid", "invalid"}
        and values[0]["prediction"] != values[1]["prediction"]
        for values in pair_rows
    )
    return {"consistent_pairs": consistent, "paired_histories": len(pair_rows), "consistency_rate": consistent / len(pair_rows) if pair_rows else None}


def _same_vs_switched(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    same = [row for row in rows if row["language_condition"] in {"EN-EN", "AR-AR"}]
    switched = [row for row in rows if row["language_condition"] in {"EN-AR", "AR-EN"}]
    by_scenario: dict[str, dict[str, list[Mapping[str, object]]]] = defaultdict(lambda: {"same": [], "switched": []})
    for row in same:
        by_scenario[str(row["scenario_id"])]["same"].append(row)
    for row in switched:
        by_scenario[str(row["scenario_id"])]["switched"].append(row)
    deltas = []
    for group in by_scenario.values():
        if group["same"] and group["switched"]:
            same_rate = sum(row["correct"] for row in group["same"]) / len(group["same"])
            switched_rate = sum(row["correct"] for row in group["switched"]) / len(group["switched"])
            deltas.append(switched_rate - same_rate)
    same_rate = sum(row["correct"] for row in same) / len(same) if same else None
    switched_rate = sum(row["correct"] for row in switched) / len(switched) if switched else None
    if deltas:
        rng = random.Random(20261115)
        sampled = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(2000))
        ci = {"lower": sampled[49], "upper": sampled[1949], "replicates": 2000, "cluster_count": len(deltas)}
    else:
        ci = {"lower": None, "upper": None, "replicates": 2000, "cluster_count": 0}
    return {
        "same_language": {"correct": sum(row["correct"] for row in same), "items": len(same), "accuracy": same_rate},
        "code_switched": {"correct": sum(row["correct"] for row in switched), "items": len(switched), "accuracy": switched_rate},
        "paired_scenario_difference_switched_minus_same": sum(deltas) / len(deltas) if deltas else None,
        "scenario_clustered_95pct_ci": ci,
    }


def _paired_baseline_difference(reference_rows: Mapping[str, Mapping[str, object]], other_rows: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    shared = sorted(set(reference_rows) & set(other_rows))
    deltas = [int(other_rows[item_id]["correct"]) - int(reference_rows[item_id]["correct"]) for item_id in shared]
    direct_only = sum(delta < 0 for delta in deltas)
    other_only = sum(delta > 0 for delta in deltas)
    return {
        "paired_items": len(shared),
        "baseline_correct_only": direct_only,
        "comparison_correct_only": other_only,
        "accuracy_difference": sum(deltas) / len(shared) if shared else None,
        "scenario_clustered_95pct_ci": _paired_cluster_ci(reference_rows, other_rows, shared),
    }


def _paired_cluster_ci(left, right, shared: Sequence[str], *, replicates: int = 2000) -> dict[str, object]:
    clusters: dict[str, list[str]] = defaultdict(list)
    for item_id in shared:
        clusters[str(left[item_id]["scenario_id"])].append(item_id)
    ids = sorted(clusters)
    if not ids:
        return {"lower": None, "upper": None, "replicates": replicates, "cluster_count": 0}
    rng = random.Random(20261114)
    values = []
    for _ in range(replicates):
        selected = [rng.choice(ids) for _ in ids]
        picked = [item_id for scenario_id in selected for item_id in clusters[scenario_id]]
        values.append(sum(int(right[item_id]["correct"]) - int(left[item_id]["correct"]) for item_id in picked) / len(picked))
    values.sort()
    return {"lower": values[max(0, int(.025 * replicates) - 1)], "upper": values[min(replicates - 1, int(.975 * replicates) - 1)], "replicates": replicates, "cluster_count": len(ids)}


def analyze_frozen_runs(freeze_root: str | Path, *, partition: str = "locked", output_path: str | Path | None = None) -> dict[str, object]:
    """Score immutable stored runs against the separately stored oracle key."""
    root = Path(freeze_root)
    items, input_manifest, freeze_manifest = load_frozen_inputs(root, partition=partition)
    stem = "locked" if partition == "locked" else "development"
    reference = _verified_reference_file(root, freeze_manifest, f"reference/{stem}-reference-key.json")
    metadata = _verified_reference_file(root, freeze_manifest, f"reference/{stem}-analysis-metadata.json")
    expected = input_manifest["item_hashes"]
    baseline_scores = {}
    item_lookup = {}
    run_status = {}
    for baseline in BASELINES:
        expected_configuration = build_run_configs(input_manifest, str(freeze_manifest["code_revision"]))[baseline][0].config_hash
        envelopes, run_info = _result_records(
            root,
            baseline,
            expected,
            str(input_manifest["manifest_sha256"]),
            expected_configuration,
        )
        run_status[baseline] = run_info
        scored = _score_items(items, envelopes, reference, metadata)
        baseline_scores[baseline] = scored
        item_lookup[baseline] = {row["item_id"]: row for row in scored}

    primary = {name: rows for name, rows in baseline_scores.items()}
    primary_rows_by_baseline = {
        name: [row for row in rows if row["dataset_kind"] == "primary"] for name, rows in primary.items()
    }
    control_rows_by_baseline = {
        name: [row for row in rows if row["dataset_kind"] == "auxiliary_control"] for name, rows in primary.items()
    }
    report: dict[str, object] = {
        "analysis_version": ANALYSIS_VERSION,
        "partition": partition,
        "input_manifest_sha256": input_manifest["manifest_sha256"],
        "freeze_manifest_sha256": hashlib.sha256((root / "freeze-manifest.json").read_bytes()).hexdigest(),
        "planned_items": len(items),
        "primary": {},
        "auxiliary_controls": {},
        "run_status": run_status,
        "paired_baseline_comparisons": {},
    }
    primary_planned = sum(value.get("dataset_kind") == "primary" for value in metadata.values())
    controls_planned = sum(value.get("dataset_kind") == "auxiliary_control" for value in metadata.values())
    for baseline in BASELINES:
        rows = primary_rows_by_baseline[baseline]
        report["primary"][baseline] = {
            "overall": _metrics(rows, planned=primary_planned, confidence=True),
            "by_language_condition": _group_metrics(rows, "language_condition"),
            "by_domain": _group_metrics(rows, "domain"),
            "by_transition_family": _group_metrics(rows, "transition_family"),
            "counterfactual_pair_consistency": _counterfactual_consistency(rows),
            "same_language_vs_code_switched": _same_vs_switched(rows),
        }
        control_rows = control_rows_by_baseline[baseline]
        report["auxiliary_controls"][baseline] = {
            "overall": _metrics(control_rows, planned=controls_planned, confidence=True),
            "by_language_condition": _group_metrics(control_rows, "language_condition"),
            "counterfactual_pair_consistency": _counterfactual_consistency(control_rows),
        }
    for comparison in ("translation_first", "structured"):
        left = {row["item_id"]: row for row in primary_rows_by_baseline["direct"]}
        right = {row["item_id"]: row for row in primary_rows_by_baseline[comparison]}
        report["paired_baseline_comparisons"][f"direct_vs_{comparison}"] = _paired_baseline_difference(left, right)
    structured = primary_rows_by_baseline["structured"]
    parsed = [row for row in structured if row["parse_status"] == ParseStatus.PARSED.value]
    tool_counts = Counter(row["parse_record"].get("tool_contract") for row in parsed)
    reported_types = Counter(
        assessment.get("constraint_type")
        for row in parsed
        for assessment in row["parse_record"].get("constraint_assessments", [])
    )
    report["structured_details"] = {
        "parsed_primary_items": len(parsed),
        "tool_contract_assessment_distribution": dict(tool_counts),
        "reported_constraint_type_distribution": dict(reported_types),
        "constraint_coverage_metric": "available when hash-bound reference_requirements are present; scored post-inference only",
    }
    report["analysis_sha256"] = sha256_text(canonical_json(report))
    if output_path is not None:
        raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target.parent, 0o700)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        digest = hashlib.sha256(raw).hexdigest()
        target.with_suffix(target.suffix + ".sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    return report
