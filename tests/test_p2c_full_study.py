"""Synthetic-only tests for the P2C full-study pipeline."""

from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from multilingual_judge_pilot.p2c_review import (
    ReviewValidationError,
    build_disagreement_report,
    ingest_submission,
    ingest_adjudications,
    load_current_adjudications,
    parse_submission_jsonl,
)
from multilingual_judge_pilot.p2c_freeze import FreezeInventory, create_freeze, validate_reviews_for_freeze, verify_pre_freeze
from multilingual_judge_pilot.p2c_inference import FrozenExecutionError, load_frozen_inputs, prepare_translations, run_frozen_baseline
from multilingual_judge_pilot.p2c_analysis import AnalysisError, analyze_frozen_runs
from multilingual_judge_pilot.judge_inference import DeterministicMockProvider, ProviderIdentity, ProviderResponse
from multilingual_judge_pilot.judge_baselines import TranslationCallError, TranslationOutput
from multilingual_judge_pilot.preflight import canonical_scenario_sha256, variant_sha256
from multilingual_judge_pilot.p2c_review import ReviewInventory
from multilingual_judge_pilot.schema import LanguageCondition, TextSegment, TextSegmentKind
from multilingual_judge_pilot.serialization import scenario_to_json
from tests.p1_fixtures import numerical_revision_pair, structural_language_variant, with_language_variants


class _SyntheticTranslator:
    def __init__(self):
        self._identity = ProviderIdentity("ollama-local", "translategemma:4b-it-q4_K_M", "sha256:eeb875b066dbbc91ad481f7423c61c23eccc5b96e85b50d6667753bdee726227")
        self.calls = []

    @property
    def identity(self):
        return self._identity

    def translate(self, item, config):
        from dataclasses import replace

        self.calls.append(item.item_id)
        turns = tuple(replace(turn, language="en") for turn in item.conversation)
        return TranslationOutput(turns, "Synthetic fixture translation.", 1.0, 3, 4, "0")


class _OneFailureTranslator(_SyntheticTranslator):
    def translate(self, item, config):
        if not self.calls:
            self.calls.append(item.item_id)
            raise TranslationCallError("synthetic_translation_failure", raw_response="synthetic raw translation error")
        return super().translate(item, config)


def _annotation(item_id: str, slot: str, *, example_hash: str | None = None, semantic: str = "equivalent"):
    return {
        "annotation_schema_version": "p2b1-annotation-2",
        "example_id": item_id,
        "example_sha256": example_hash or ("a" * 64),
        "canonical_scenario_sha256": "b" * 64,
        "reviewer_id": slot,
        "semantic_relation": semantic,
        "linguistic_quality": "natural",
        "decisive_update_dependence": "yes",
        "decisive_update_dependence_rationale": "Synthetic rationale for the visible revision.",
        "whole_action_dependence": "no",
        "whole_action_dependence_rationale": "Synthetic rationale for the complete action evidence.",
        "issue_codes": [],
        "checklist": {
            "matches_formal_spec": True,
            "preserves_cross_language_meaning": True,
            "initial_requirements_communicated": True,
            "decisive_turn_expresses_event": True,
            "counterfactual_differences_controlled": True,
            "action_interpretation_preserved": True,
            "no_post_action_information": True,
            "msa_natural_and_unambiguous": True,
        },
        "notes": "",
    }


def _maps(item_ids: tuple[str, ...] = ("synthetic-a", "synthetic-b")):
    return (
        {item_id: "a" * 64 for item_id in item_ids},
        {item_id: "b" * 64 for item_id in item_ids},
    )


def _jsonl(rows) -> bytes:
    return ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()


def test_submission_parser_rejects_missing_rows_and_preserves_complete_records():
    expected_hashes, scenario_hashes = _maps()
    row = _annotation("synthetic-a", "reviewer_slot_1")

    with pytest.raises(ReviewValidationError, match="complete expected item set"):
        parse_submission_jsonl(_jsonl([row]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    complete = [_annotation(item_id, "reviewer_slot_1") for item_id in expected_hashes]
    parsed = parse_submission_jsonl(_jsonl(complete), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)
    assert [row["example_id"] for row in parsed] == list(expected_hashes)


def test_submission_parser_rejects_duplicate_ids_duplicate_json_keys_wrong_slot_and_stale_hash():
    expected_hashes, scenario_hashes = _maps()
    row = _annotation("synthetic-a", "reviewer_slot_1")

    with pytest.raises(ReviewValidationError, match="duplicate annotation"):
        parse_submission_jsonl(_jsonl([row, row, _annotation("synthetic-b", "reviewer_slot_1")]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    duplicate_key = b'{"example_id":"synthetic-a","example_id":"synthetic-b"}\n'
    with pytest.raises(ReviewValidationError, match="duplicate JSON key"):
        parse_submission_jsonl(duplicate_key, reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    wrong_slot = [_annotation(item_id, "reviewer_slot_2") for item_id in expected_hashes]
    with pytest.raises(ReviewValidationError, match="reviewer slot"):
        parse_submission_jsonl(_jsonl(wrong_slot), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    stale = [_annotation("synthetic-a", "reviewer_slot_1", example_hash="c" * 64), _annotation("synthetic-b", "reviewer_slot_1")]
    with pytest.raises(ReviewValidationError, match="unknown or changed example hash"):
        parse_submission_jsonl(_jsonl(stale), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    corrupt_id = [_annotation("synthetic-a", "reviewer_slot_1"), _annotation("synthetic-b", "reviewer_slot_1")]
    corrupt_id[0]["example_id"] = ["synthetic-a"]
    with pytest.raises(ReviewValidationError, match="example IDs must be strings"):
        parse_submission_jsonl(_jsonl(corrupt_id), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)


def test_submission_requires_explanation_for_detected_problems():
    expected_hashes, scenario_hashes = _maps(("synthetic-a",))
    row = _annotation("synthetic-a", "reviewer_slot_1", semantic="meaning_changed")

    with pytest.raises(ReviewValidationError, match="require an explanatory note"):
        parse_submission_jsonl(_jsonl([row]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)

    row["notes"] = "Synthetic wording changes the intended meaning."
    assert len(parse_submission_jsonl(_jsonl([row]), reviewer_slot="reviewer_slot_1", expected_hashes=expected_hashes, expected_scenario_hashes=scenario_hashes)) == 1


def _complete_review_pair(*, reviewer_a_changes=None, reviewer_b_changes=None):
    ids = tuple(_maps()[0])
    a = [_annotation(item_id, "reviewer_slot_1") for item_id in ids]
    b = [_annotation(item_id, "reviewer_slot_2") for item_id in ids]
    for row in a:
        row.update((reviewer_a_changes or {}).get(row["example_id"], {}))
    for row in b:
        row.update((reviewer_b_changes or {}).get(row["example_id"], {}))
    return {"reviewer_slot_1": a, "reviewer_slot_2": b}


def test_freeze_review_gate_rejects_missing_reviewer_export():
    expected_hashes, scenario_hashes = _maps()

    result = validate_reviews_for_freeze(
        {"reviewer_slot_1": [_annotation(item_id, "reviewer_slot_1") for item_id in expected_hashes]},
        [],
        expected_hashes=expected_hashes,
        expected_scenario_hashes=scenario_hashes,
    )

    assert result["ready"] is False
    assert "both reviewer submissions are required" in result["blockers"]


def test_freeze_review_gate_requires_adjudication_and_clean_content():
    expected_hashes, scenario_hashes = _maps()
    submissions = _complete_review_pair(reviewer_b_changes={"synthetic-b": {"decisive_update_dependence": "no"}})

    unresolved = validate_reviews_for_freeze(
        submissions,
        [],
        expected_hashes=expected_hashes,
        expected_scenario_hashes=scenario_hashes,
    )
    assert unresolved["ready"] is False
    assert any("missing adjudication" in blocker for blocker in unresolved["blockers"])

    adjudication = {
        "adjudication_schema_version": "p2b1-adjudication-2",
        "example_id": "synthetic-b",
        "example_sha256": "a" * 64,
        "canonical_scenario_sha256": "b" * 64,
        "reviewer_ids": ["reviewer_slot_1", "reviewer_slot_2"],
        "adjudicator_id": "synthetic-adjudicator",
        "outcome": "retain",
        "rationale": "Synthetic example: preserve the documented uncertainty after adjudication.",
    }
    adjudicated = validate_reviews_for_freeze(
        submissions,
        [adjudication],
        expected_hashes=expected_hashes,
        expected_scenario_hashes=scenario_hashes,
    )
    assert adjudicated["ready"] is True
    assert adjudicated["disagreement_report"]["disagreement_count"] == 1

    defective = _complete_review_pair(reviewer_a_changes={"synthetic-a": {"semantic_relation": "meaning_changed", "notes": "Synthetic defect."}})
    defect_result = validate_reviews_for_freeze(
        defective,
        [],
        expected_hashes=expected_hashes,
        expected_scenario_hashes=scenario_hashes,
    )
    assert defect_result["ready"] is False
    assert any("content issue" in blocker for blocker in defect_result["blockers"])


def test_disagreement_report_identifies_categorical_difference_without_resolving_it():
    reviewer_a = [_annotation(item_id, "reviewer_slot_1") for item_id in _maps()[0]]
    reviewer_b = [_annotation(item_id, "reviewer_slot_2", semantic="ambiguous" if item_id == "synthetic-b" else "equivalent") for item_id in _maps()[0]]

    report = build_disagreement_report(
        {"reviewer_slot_1": reviewer_a, "reviewer_slot_2": reviewer_b},
        expected_hashes=_maps()[0],
    )

    assert report["disagreement_count"] == 1
    assert report["disagreements"] == [{
        "example_id": "synthetic-b",
        "fields": {"semantic_relation": {"reviewer_slot_1": "equivalent", "reviewer_slot_2": "ambiguous"}},
    }]


def test_submission_import_is_immutable_and_hash_bound(tmp_path: Path):
    expected_hashes, scenario_hashes = _maps()
    source = tmp_path / "review-export.jsonl"
    original = _jsonl([_annotation(item_id, "reviewer_slot_1") for item_id in expected_hashes])
    source.write_bytes(original)

    imported = ingest_submission(
        "reviewer_slot_1",
        source,
        tmp_path / "state",
        expected_hashes=expected_hashes,
        expected_scenario_hashes=scenario_hashes,
    )

    archived = tmp_path / "state" / str(imported["archived_path"])
    assert archived.read_bytes() == original
    assert imported["source_sha256"] == hashlib.sha256(original).hexdigest()
    revised = [_annotation(item_id, "reviewer_slot_1", semantic="equivalent") for item_id in expected_hashes]
    revised[0]["notes"] = "Synthetic export revision."
    source.write_bytes(_jsonl(revised))
    assert archived.read_bytes() == original
    with pytest.raises(ReviewValidationError, match="revision reason"):
        ingest_submission(
            "reviewer_slot_1",
            source,
            tmp_path / "state",
            expected_hashes=expected_hashes,
            expected_scenario_hashes=scenario_hashes,
        )


def test_adjudication_import_is_hash_bound_and_preserves_original_bytes(tmp_path: Path):
    expected_hashes, scenario_hashes = _maps(("synthetic-a",))
    reviewer_a = _annotation("synthetic-a", "reviewer_slot_1")
    reviewer_b = _annotation("synthetic-a", "reviewer_slot_2")
    reviewer_b["decisive_update_dependence"] = "no"
    rows = [reviewer_a, reviewer_b]
    source = tmp_path / "adjudications.jsonl"
    adjudication = {
        "adjudication_schema_version": "p2b1-adjudication-2",
        "example_id": "synthetic-a",
        "example_sha256": expected_hashes["synthetic-a"],
        "canonical_scenario_sha256": scenario_hashes["synthetic-a"],
        "reviewer_ids": ["reviewer_slot_1", "reviewer_slot_2"],
        "adjudicator_id": "synthetic-adjudicator",
        "outcome": "retain",
        "rationale": "Synthetic adjudication note preserving an independently justified decision.",
    }
    original = _jsonl([adjudication])
    source.write_bytes(original)

    imported = ingest_adjudications(source, tmp_path / "state", annotations=rows)
    current = load_current_adjudications(tmp_path / "state")
    assert current["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert current["records"] == [adjudication]
    assert (tmp_path / "state" / current["archived_path"]).read_bytes() == original


def test_cli_status_reports_both_missing_reviewer_exports(tmp_path: Path, monkeypatch, capsys):
    from multilingual_judge_pilot.preflight import blank_annotation_record
    from scripts import p2c_full_study

    dataset = tmp_path / "dataset"
    for slot in ("reviewer_slot_1", "reviewer_slot_2"):
        folder = dataset / "review-package" / slot
        folder.mkdir(parents=True)
        rows = [
            blank_annotation_record(f"synthetic-{index:03d}", "a" * 64, "b" * 64)
            for index in range(448)
        ]
        (folder / "annotation-template.jsonl").write_bytes(_jsonl(rows))
    state = tmp_path / "state"
    monkeypatch.setattr(p2c_full_study, "PRIVATE_ROOT", tmp_path.resolve())
    args = p2c_full_study.build_parser().parse_args([
        "--dataset-root", str(dataset), "--state-root", str(state), "status",
    ])
    assert p2c_full_study.dispatch(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["review_inventory_count"] == 448
    assert report["both_submissions_received"] is False
    assert report["reviewers"]["reviewer_slot_1"]["status"] == "missing"
    assert report["reviewers"]["reviewer_slot_2"]["status"] == "missing"


def _synthetic_freeze_scenario():
    source = numerical_revision_pair(scenario_id="synthetic-freeze")
    variants = []
    for history in source.histories:
        for condition in LanguageCondition:
            variant = structural_language_variant(
                scenario_id=source.scenario_id,
                history_id=history.history_id,
                partition=source.partition,
                condition=condition,
            )
            updated_turns = []
            for turn in variant.turns:
                language = "English" if turn.language.value == "en" else "Arabic"
                content = f"Synthetic {language} initial request." if turn.turn_index == 0 else f"Synthetic {language} revision for "
                segments = tuple(
                    replace(segment, text=content if segment.kind is TextSegmentKind.LOCALIZED_NATURAL_LANGUAGE else segment.text)
                    for segment in turn.segments
                )
                updated_turns.append(replace(turn, segments=segments))
            variants.append(replace(variant, turns=tuple(updated_turns)))
    return with_language_variants(source, tuple(variants))


def _synthetic_review_inventory(scenario):
    variant_hashes = {variant.derivative_id: variant_sha256(variant) for variant in scenario.language_variants}
    scenario_hash = canonical_scenario_sha256(scenario)
    scenario_hashes = {item_id: scenario_hash for item_id in variant_hashes}
    return ReviewInventory(tuple(variant_hashes), variant_hashes, scenario_hashes)


def _synthetic_submissions(inventory):
    submissions = {}
    for slot in ("reviewer_slot_1", "reviewer_slot_2"):
        rows = []
        for item_id in inventory.item_ids:
            row = _annotation(item_id, slot, example_hash=inventory.expected_hashes[item_id])
            row["canonical_scenario_sha256"] = inventory.expected_scenario_hashes[item_id]
            rows.append(row)
        submissions[slot] = rows
    return submissions


def test_freeze_creates_separate_opaque_inference_and_reference_artifacts(tmp_path: Path):
    from multilingual_judge_pilot.p2c_review import ingest_submission

    scenario = _synthetic_freeze_scenario()
    review_inventory = _synthetic_review_inventory(scenario)
    dataset = tmp_path / "dataset"
    (dataset / "primary" / "scenarios").mkdir(parents=True)
    (dataset / "primary" / "scenarios" / f"{scenario.scenario_id}.json").write_text(scenario_to_json(scenario), encoding="utf-8")
    (dataset / "manifest.json").write_text(json.dumps({"dataset_frozen": False, "model_inference_performed": False}), encoding="utf-8")
    submissions = _synthetic_submissions(review_inventory)
    state_root = tmp_path / "review-state"
    for slot, rows in submissions.items():
        source = tmp_path / f"{slot}.jsonl"
        source.write_bytes(_jsonl(rows))
        ingest_submission(
            slot,
            source,
            state_root,
            expected_hashes=review_inventory.expected_hashes,
            expected_scenario_hashes=review_inventory.expected_scenario_hashes,
        )
    inventory = FreezeInventory(1, 0, 1, 0, 1, 8, 0, 8, 0, 8)
    package_validator = lambda _root: {"scenario_count": 1, "package_sha256": "c" * 64}

    frozen = create_freeze(
        dataset,
        state_root,
        tmp_path / "freezes",
        review_inventory=review_inventory,
        expected_inventory=inventory,
        package_validator=package_validator,
        code_revision="synthetic-test-revision",
    )

    root = Path(frozen["freeze_root"])
    inference = [json.loads(line) for line in (root / "locked" / "inference-items.jsonl").read_text().splitlines()]
    reference = json.loads((root / "reference" / "locked-reference-key.json").read_text())
    configs = json.loads((root / "execution" / "run-configs.json").read_text())
    assert len(inference) == 8
    assert len(reference) == 8
    assert set(row["item_id"] for row in inference) == set(reference)
    assert all(set(row) == {"item_id", "language_condition", "action_turn_index", "conversation", "action", "public_tool_schema"} for row in inference)
    assert all("reference_verdict" not in row and "effective_state" not in row for row in inference)
    assert {row["language"] for item in inference for row in item["conversation"]} <= {"en", "ar"}
    assert set(configs["configurations"]) == {"direct", "translation_first", "structured"}
    assert frozen["reference_files_separated_from_inference"] is True


def test_freeze_fails_closed_when_reviewer_export_is_missing(tmp_path: Path):
    scenario = _synthetic_freeze_scenario()
    review_inventory = _synthetic_review_inventory(scenario)
    dataset = tmp_path / "dataset"
    (dataset / "primary" / "scenarios").mkdir(parents=True)
    (dataset / "primary" / "scenarios" / f"{scenario.scenario_id}.json").write_text(scenario_to_json(scenario), encoding="utf-8")
    (dataset / "manifest.json").write_text(json.dumps({"dataset_frozen": False, "model_inference_performed": False}), encoding="utf-8")
    inventory = FreezeInventory(1, 0, 1, 0, 1, 8, 0, 8, 0, 8)
    with pytest.raises(ValueError, match="dataset freeze is blocked"):
        create_freeze(
            dataset,
            tmp_path / "empty-review-state",
            tmp_path / "freezes",
            review_inventory=review_inventory,
            expected_inventory=inventory,
            package_validator=lambda _root: {"scenario_count": 1, "package_sha256": "c" * 64},
            code_revision="synthetic-test-revision",
        )


def test_pre_freeze_rejects_stale_review_hashes_and_oracle_mismatch(tmp_path: Path):
    from multilingual_judge_pilot.schema import ValidityLabel

    scenario = _synthetic_freeze_scenario()
    inventory = FreezeInventory(1, 0, 1, 0, 1, 8, 0, 8, 0, 8)
    dataset = tmp_path / "dataset"
    (dataset / "primary" / "scenarios").mkdir(parents=True)
    (dataset / "manifest.json").write_text(json.dumps({"dataset_frozen": False, "model_inference_performed": False}), encoding="utf-8")
    package_validator = lambda _root: {"scenario_count": 1, "package_sha256": "c" * 64}

    stale = _synthetic_review_inventory(scenario)
    stale_hashes = dict(stale.expected_hashes)
    stale_hashes[stale.item_ids[0]] = "d" * 64
    stale_inventory = ReviewInventory(stale.item_ids, stale_hashes, stale.expected_scenario_hashes)
    (dataset / "primary" / "scenarios" / f"{scenario.scenario_id}.json").write_text(scenario_to_json(scenario), encoding="utf-8")
    stale_result = verify_pre_freeze(
        dataset,
        tmp_path / "reviews",
        review_inventory=stale_inventory,
        expected_inventory=inventory,
        package_validator=package_validator,
    )
    assert not stale_result["ready"]
    assert "reviewer package" in stale_result["blockers"][0]

    malformed_label_record = json.loads(scenario_to_json(scenario))
    malformed_label_record["scenario"]["histories"][1]["declared_label"] = ValidityLabel.INVALID.value
    (dataset / "primary" / "scenarios" / f"{scenario.scenario_id}.json").write_text(json.dumps(malformed_label_record), encoding="utf-8")
    bad_inventory = _synthetic_review_inventory(scenario)
    oracle_result = verify_pre_freeze(
        dataset,
        tmp_path / "reviews",
        review_inventory=bad_inventory,
        expected_inventory=inventory,
        package_validator=package_validator,
    )
    assert not oracle_result["ready"]
    assert "oracle" in oracle_result["blockers"][0] or "declared label" in oracle_result["blockers"][0]


def _create_synthetic_freeze(tmp_path: Path):
    from multilingual_judge_pilot.p2c_review import ingest_submission

    scenario = _synthetic_freeze_scenario()
    review_inventory = _synthetic_review_inventory(scenario)
    dataset = tmp_path / "dataset"
    (dataset / "primary" / "scenarios").mkdir(parents=True)
    (dataset / "primary" / "scenarios" / f"{scenario.scenario_id}.json").write_text(scenario_to_json(scenario), encoding="utf-8")
    (dataset / "manifest.json").write_text(json.dumps({"dataset_frozen": False, "model_inference_performed": False}), encoding="utf-8")
    state_root = tmp_path / "review-state"
    for slot, rows in _synthetic_submissions(review_inventory).items():
        source = tmp_path / f"{slot}.jsonl"
        source.write_bytes(_jsonl(rows))
        ingest_submission(slot, source, state_root, expected_hashes=review_inventory.expected_hashes, expected_scenario_hashes=review_inventory.expected_scenario_hashes)
    frozen = create_freeze(
        dataset,
        state_root,
        tmp_path / "freezes",
        review_inventory=review_inventory,
        expected_inventory=FreezeInventory(1, 0, 1, 0, 1, 8, 0, 8, 0, 8),
        package_validator=lambda _root: {"scenario_count": 1, "package_sha256": "c" * 64},
        code_revision="synthetic-test-revision",
    )
    return Path(frozen["freeze_root"])


def _mock_judge(verdict: str = "valid", *, structured: bool = False, count: int = 8):
    identity = ProviderIdentity("ollama-local", "gemma4:12b-it-qat", "sha256:38044be4f923e5a55264ed7df4eaac2676651a905f735197c504045140c02bd3")
    raw = json.dumps({"tool_contract": "satisfied", "constraint_assessments": [], "verdict": verdict}) if structured else json.dumps({"verdict": verdict})
    return DeterministicMockProvider(identity, [ProviderResponse(raw, prompt_tokens=5, completion_tokens=3, cost_usd="0") for _ in range(count)])


def test_frozen_execution_runs_all_baselines_and_resumes_without_duplicate_calls(tmp_path: Path):
    freeze_root = _create_synthetic_freeze(tmp_path)
    rows, _manifest, _freeze = load_frozen_inputs(freeze_root)
    assert len(rows) == 8
    direct = _mock_judge()
    first = run_frozen_baseline(freeze_root, "direct", direct)
    assert first["completed"] == 8
    assert len(direct.calls) == 8
    resumed = run_frozen_baseline(freeze_root, "direct", direct)
    assert resumed["reused"] == 8
    assert len(direct.calls) == 8

    structured = _mock_judge(structured=True)
    structured_result = run_frozen_baseline(freeze_root, "structured", structured)
    assert structured_result["completed"] == 8
    assert len(structured.calls) == 8
    for request_json, _parameters in direct.calls + structured.calls:
        request = json.loads(request_json)
        assert set(request) == {"response_contract_version", "response_schema", "item_id", "instruction", "conversation", "action", "public_tool_schema"}
        assert "reference_verdict" not in request and "effective_state" not in request

    translator = _SyntheticTranslator()
    translations = prepare_translations(freeze_root, translator)
    assert translations["total"] == 8 and translations["failed"] == 0
    assert len(translator.calls) == 8
    assert prepare_translations(freeze_root, translator)["reused"] == 8
    assert len(translator.calls) == 8
    translated_judge = _mock_judge()
    translated_run = run_frozen_baseline(freeze_root, "translation_first", translated_judge, translator=translator)
    assert translated_run["completed"] == 8
    assert len(translated_judge.calls) == 8
    assert len(translator.calls) == 8

    direct_result_files = sorted((freeze_root / "runs" / "direct" / "items").glob("*.result.json"))
    source_hashes_before_score = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in direct_result_files}
    analysis = analyze_frozen_runs(freeze_root)
    repeated_analysis = analyze_frozen_runs(freeze_root)
    assert repeated_analysis["analysis_sha256"] == analysis["analysis_sha256"]
    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in direct_result_files} == source_hashes_before_score
    direct_metrics = analysis["primary"]["direct"]["overall"]
    assert direct_metrics["planned_denominator"] == 8
    assert direct_metrics["accuracy"] == 0.5
    assert direct_metrics["confusion_matrix"]["invalid"]["valid"] == 4
    assert analysis["primary"]["direct"]["counterfactual_pair_consistency"]["paired_histories"] == 4
    assert analysis["paired_baseline_comparisons"]["direct_vs_structured"]["paired_items"] == 8
    assert analysis["run_status"]["direct"]["status"] == "completed"


def test_translation_failure_is_retained_and_skips_only_its_judge_call(tmp_path: Path):
    freeze_root = _create_synthetic_freeze(tmp_path)
    translator = _OneFailureTranslator()
    translated = prepare_translations(freeze_root, translator)
    assert translated == {"translated": 7, "failed": 1, "reused": 0, "total": 8}
    judge = _mock_judge()
    result = run_frozen_baseline(freeze_root, "translation_first", judge, translator=translator)
    assert result["completed"] == 8
    assert result["translation_failures"] == 1
    assert len(judge.calls) == 7
    analysis = analyze_frozen_runs(freeze_root)
    metrics = analysis["primary"]["translation_first"]["overall"]
    assert metrics["planned_denominator"] == 8
    assert metrics["translation_failures"] == 1
    assert metrics["technical_missing"] == 0


def test_frozen_execution_blocks_tampering_and_ambiguous_resume(tmp_path: Path):
    freeze_root = _create_synthetic_freeze(tmp_path)
    input_path = freeze_root / "locked" / "inference-items.jsonl"
    original = input_path.read_bytes()
    input_path.chmod(0o600)
    input_path.write_bytes(original + b" ")
    with pytest.raises(FrozenExecutionError, match="inference items hash"):
        load_frozen_inputs(freeze_root)
    input_path.write_bytes(original)
    input_path.chmod(0o444)

    rows, manifest, _freeze = load_frozen_inputs(freeze_root)
    first_id = rows[0]["item_id"]
    result_root = freeze_root / "runs" / "structured" / "items"
    result_root.mkdir(parents=True)
    name = hashlib.sha256(first_id.encode()).hexdigest()
    (result_root / f"{name}.result.state.json").write_text(json.dumps({"status": "in_progress"}), encoding="utf-8")
    provider = _mock_judge(structured=True)
    with pytest.raises(FrozenExecutionError, match="ambiguous in-progress"):
        run_frozen_baseline(freeze_root, "structured", provider)
    assert provider.calls == []


def test_analysis_rejects_modified_raw_result_records(tmp_path: Path):
    freeze_root = _create_synthetic_freeze(tmp_path)
    run_frozen_baseline(freeze_root, "direct", _mock_judge())
    result_path = next((freeze_root / "runs" / "direct" / "items").glob("*.result.json"))
    result_path.chmod(0o600)
    result_path.write_bytes(result_path.read_bytes() + b" ")
    result_path.chmod(0o444)
    with pytest.raises(AnalysisError, match="result file hash mismatch"):
        analyze_frozen_runs(freeze_root)
