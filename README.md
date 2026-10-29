# Multilingual LLM Judge Reliability Research Pilot

This repository establishes the research foundation for a controlled feasibility study of whether LLM judges correctly classify agent actions when validity depends on user constraints introduced, revised, or revoked across English and Arabic. The object of study is the **judge**; no task-performing agent is evaluated here.

The hypotheses are provisional. The study is designed to allow null and negative results. P0 has been approved and P1 is authorized; this branch implements schema, oracle, and integrity infrastructure only.

## Exploratory pilot at a glance

| Design element | Planned size |
| --- | ---: |
| Primary consequential-change scenarios | 48 |
| Domains | 3: booking, customer operations, scheduling |
| Constraint-transition families | 4: introduction, numerical revision, permission revocation, temporal revision |
| Counterfactual histories per scenario | 2, with opposite labels for the same action |
| Language conditions | 4: EN–EN, AR–AR, EN–AR, AR–EN |
| Primary derived judge items | 384 |
| Primary development / locked evaluation scenarios | 12 / 36 |
| Separate no-change control scenarios / items | 12 / 96 (approved locked auxiliary set) |
| Total planned scenarios / items | 60 / 480 |

These are approved future counts, not a dataset currently present in the repository. The 12 controls are assigned to a locked auxiliary partition; control results remain separate from the primary estimand. Their matching rules remain reviewable at the P1 gate. See the research specifications before changing or implementing the design.

## Research specifications

- [Protocol and hypotheses](docs/research/protocol.md)
- [Dataset and canonical-state specification](docs/research/dataset-spec.md)
- [Evaluation and statistical-analysis plan](docs/research/evaluation-plan.md)
- [Integrity and reproducibility requirements](docs/research/integrity-and-reproducibility.md)
- [Prior-work register](docs/research/prior-work.md)
- [Milestone roadmap and acceptance gates](docs/roadmap.md)

The research documents are authoritative. This README and `AGENTS.md` provide navigation and working guidance only. P0 is approved; P1 implementation is for independent review and does not freeze the protocol or authorize P2.

## Development setup

Requires Python 3.11+; the P1 implementation uses the standard library at runtime and pytest for tests. The setup works on Apple Silicon macOS.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

The only development dependency is pytest. P1 contains typed schema, deterministic oracle, validation, and test-only synthetic fixtures. It contains no study dataset, translation generator, judge adapter, or model runner.

## Current boundary

P1 may include only synthetic test fixtures. Do not create the study benchmark, generate research-language variants, execute judge inference, or begin P2 until the P1 review gate is recorded. No paid inference is authorized by this repository setup.
