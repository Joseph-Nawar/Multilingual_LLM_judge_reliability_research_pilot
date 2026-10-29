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
    assert "48 × 2 × 4 = 384" in protocol
    assert "12 development scenarios and 36 locked evaluation scenarios" in protocol
    assert "one valid and one invalid item" in dataset
