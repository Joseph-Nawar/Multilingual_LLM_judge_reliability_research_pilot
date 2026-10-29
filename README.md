# Multilingual LLM Judge Reliability Research Pilot

This repository establishes the research foundation for a controlled feasibility study of whether LLM judges correctly classify agent actions when validity depends on user constraints introduced, revised, or revoked across English and Arabic. The object of study is the **judge**; no task-performing agent is evaluated here.

The hypotheses are provisional. The study is designed to allow null and negative results, and no inference or dataset generation is in scope at this stage.

## Exploratory pilot at a glance

| Design element | Planned size |
| --- | ---: |
| Canonical scenarios | 48 |
| Domains | 3: booking, customer operations, scheduling |
| Constraint-transition families | 4: introduction, numerical revision, permission revocation, temporal revision |
| Counterfactual histories per scenario | 2, with opposite labels for the same action |
| Language conditions | 4: EN–EN, AR–AR, EN–AR, AR–EN |
| Derived judge items | 384 |
| Development / locked evaluation scenarios | 12 / 36 |

These counts describe the proposed pilot, not a dataset currently present in the repository. See the research specifications before changing or implementing the design.

## Research specifications

- [Protocol and hypotheses](docs/research/protocol.md)
- [Dataset and canonical-state specification](docs/research/dataset-spec.md)
- [Evaluation and statistical-analysis plan](docs/research/evaluation-plan.md)
- [Integrity and reproducibility requirements](docs/research/integrity-and-reproducibility.md)
- [Prior-work register](docs/research/prior-work.md)
- [Milestone roadmap and acceptance gates](docs/roadmap.md)

The research documents are authoritative. This README and `AGENTS.md` provide navigation and working guidance only. P0 establishes a reviewable foundation; the protocol is not frozen for execution, and the next milestone requires evidence-based review.

## Development setup

Requires Python 3.11+; no model-serving, data-science, or platform-specific dependency is needed for P0. The setup works on Apple Silicon macOS.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

The only development dependency is pytest. P0 contains no benchmark generator or model runner.

## Current boundary

P0 is repository and research documentation only. Do not create benchmark examples, execute judge inference, or start P1 until the P0 review gate is recorded. No paid inference is authorized by this repository setup.
