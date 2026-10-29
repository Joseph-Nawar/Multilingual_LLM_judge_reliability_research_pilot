# Multilingual LLM Judge Reliability Research Pilot

This repository establishes the research foundation for a controlled feasibility study of whether LLM judges correctly classify agent actions when validity depends on user constraints introduced, revised, or revoked across English and Arabic. The object of study is the **judge**; no task-performing agent is evaluated here.

The hypotheses are provisional. The study is designed to allow null and negative results. P0, P1, and P2A authoring feasibility have been approved. P2B-1 is authorized only for corrections and human-review preparation of the same four local development-only prototypes; it does not authorize additional scenarios, locked examples, the full dataset, or model inference.

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

These are approved future counts, not a dataset currently present in the public repository. The 12 controls are assigned to a locked auxiliary partition; control results remain separate from the primary estimand. The owner approved matching controls only to locked primary scenarios. No control examples are authored in P2A. See the research specifications before changing or implementing the design.

## Research specifications

- [Protocol and hypotheses](docs/research/protocol.md)
- [Dataset and canonical-state specification](docs/research/dataset-spec.md)
- [Evaluation and statistical-analysis plan](docs/research/evaluation-plan.md)
- [Integrity and reproducibility requirements](docs/research/integrity-and-reproducibility.md)
- [Prior-work register](docs/research/prior-work.md)
- [Milestone roadmap and acceptance gates](docs/roadmap.md)

The research documents are authoritative. This README and `AGENTS.md` provide navigation and working guidance only. P0, P1, and P2A feasibility are approved. P2B-1 authorizes prototype corrections and review preparation only; independent validation, P2C dataset authoring, dataset freeze, and model inference require later review and authorization.

## Development setup

Requires Python 3.11+; the P1 implementation uses the standard library at runtime and pytest for tests. The setup works on Apple Silicon macOS.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

The only development dependency is pytest. P1 provides the typed schema, deterministic oracle, and integrity validators. P2A/P2B-1 provide local preflight, revision, and annotation-review utilities. Actual prototypes and their language drafts are stored only under ignored `.research-data/`; the public repository contains no scenario text, translations, reference records, completed reviewer records, or locked data.

## Local prototype review preparation

Read the [authoring protocol](docs/research/authoring-protocol.md), [scenario blueprint](docs/research/scenario-blueprint.md), and [bilingual annotation protocol](docs/research/bilingual-annotation-protocol.md) before working with local prototype data. The four prototypes are development-only, machine-assisted drafts and are not independently linguistically validated.

With the local research data present, run the deterministic preflight and isolation checks:

```bash
python -m multilingual_judge_pilot.preflight validate
python -m multilingual_judge_pilot.preflight review-packets
python -m multilingual_judge_pilot.preflight audit-annotations
python -m multilingual_judge_pilot.preflight isolation
```

`validate` emits a redacted aggregate report. `review-packets` writes two local label-free packets per prototype. `audit-annotations` checks independent annotations bound to both language-variant and canonical-scenario hashes; an empty or incomplete annotation set remains explicitly incomplete. `isolation` checks that private research-data paths are ignored and not already tracked. Never stage `.research-data/`.

The public aggregate report is [the P2A preflight report](docs/research/p2a-preflight-report.md). It reports deterministic structural and oracle checks only; it does not claim semantic validation.

## Current boundary

P2B-1 is the current authorized scope. It permits corrections and human-review preparation for the four existing local primary development prototypes. Do not create additional or locked scenarios or study controls, generate the complete dataset, proceed to P2B validation or P2C/P3/P4/P5, execute judge inference, or make paid API calls without separate authorization. No inference budget is authorized by this repository setup.
