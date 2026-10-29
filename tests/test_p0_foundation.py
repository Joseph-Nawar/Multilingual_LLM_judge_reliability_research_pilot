from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DOCS = (
    "protocol.md",
    "dataset-spec.md",
    "evaluation-plan.md",
    "integrity-and-reproducibility.md",
    "prior-work.md",
)


def test_authoritative_research_documents_exist() -> None:
    research_dir = ROOT / "docs" / "research"
    assert all((research_dir / name).is_file() for name in RESEARCH_DOCS)
    assert (ROOT / "docs" / "roadmap.md").is_file()


def test_project_metadata_keeps_p0_dependencies_minimal() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert config["project"]["requires-python"] == ">=3.11"
    assert config["project"]["dependencies"] == []
    assert config["project"]["optional-dependencies"]["dev"] == ["pytest>=8.0,<9.0"]
    assert config["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_study_counts_and_partition_are_documented() -> None:
    protocol = (ROOT / "docs" / "research" / "protocol.md").read_text()
    dataset = (ROOT / "docs" / "research" / "dataset-spec.md").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "48 canonical scenarios, 96 counterfactual histories, and 384 derived evaluation items" in protocol
    assert "12 development and 36 locked evaluation scenarios" in protocol
    assert "one valid and one invalid item" in dataset
    assert "12 canonical no-change scenarios, 24 histories, and 96 evaluation items" in protocol
    assert "288 locked primary items" in protocol
    assert "12 locked controls (96 items)" in protocol
    assert "Total planned scenarios / items | 60 / 480" in readme


def test_r4_language_and_literal_policies_are_recorded() -> None:
    dataset = (ROOT / "docs" / "research" / "dataset-spec.md").read_text()
    assert "Modern Standard Arabic" in dataset
    assert "Egyptian Arabic and Arabizi" in dataset
    assert "judge instruction language is English" in dataset
    assert "Code-like technical strings" in dataset


def test_research_owner_decision_record_covers_r1_to_r4() -> None:
    record = ROOT / "docs" / "research" / "decision-records" / "2026-10-29-p0-research-audit.md"
    content = record.read_text()
    assert "2026-10-29" in content
    assert "58ff69361ec1db3af2c65d63dc915dfacc0c80bf" in content
    assert all(f"R{i}" in content for i in range(1, 5))


def test_baseline_template_and_reference_access_safeguards_are_documented() -> None:
    evaluation = (ROOT / "docs" / "research" / "evaluation-plan.md").read_text()
    integrity = (ROOT / "docs" / "research" / "integrity-and-reproducibility.md").read_text()
    dataset = (ROOT / "docs" / "research" / "dataset-spec.md").read_text()
    assert "candidate mandatory ordinary-condition baselines" in evaluation
    assert "research owner must explicitly approve" in evaluation
    assert "unqualified preplanned H3 claim" in evaluation
    assert "separate access path" in integrity
    assert "development-time judge/model selection" in integrity
    assert "genuinely distinct authoring templates" in dataset
    assert "template-aware sensitivity analysis" in dataset


def test_p2b1_design_controls_cover_complexity_positions_and_constraint_polarity() -> None:
    blueprint = (ROOT / "docs" / "research" / "scenario-blueprint.md").read_text()
    authoring = (ROOT / "docs" / "research" / "authoring-protocol.md").read_text()
    evaluation = (ROOT / "docs" / "research" / "evaluation-plan.md").read_text()
    annotation = (ROOT / "docs" / "research" / "bilingual-annotation-protocol.md").read_text()
    assert "one directly specified scenario whose valid history is A" in blueprint
    assert "one history-dependent scenario whose valid history is B" in blueprint
    assert "six upper-bound and six lower-bound" in blueprint
    assert "six earliest-bound and six latest-bound" in blueprint
    assert "24 directly specified and 24 history-dependent" in authoring
    assert "UUIDv4" in evaluation
    assert "SHA-256" in evaluation
    assert "Can the action's validity be uniquely determined from the decisive turn" in annotation
    assert "canonical_scenario_sha256" in annotation


def test_p2b1_revision_and_review_data_remain_private() -> None:
    from multilingual_judge_pilot.preflight import verify_research_data_exclusion

    audit = verify_research_data_exclusion(ROOT)

    assert audit.all_private_paths_ignored is True
    assert any("p2b-1/review-packets" in path for path in audit.ignored_paths)
    assert any("p2b-1/annotations" in path for path in audit.ignored_paths)
    assert audit.tracked_private_paths == ()
