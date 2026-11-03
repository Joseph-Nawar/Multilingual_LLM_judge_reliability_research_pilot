# Multilingual LLM Judge Reliability Research Pilot

This repository establishes the research foundation for a controlled feasibility study of whether LLM judges correctly classify agent actions when validity depends on user constraints introduced, revised, or revoked across English and Arabic. The object of study is the **judge**; no task-performing agent is evaluated here.

The hypotheses are provisional. The study is designed to allow null and negative results. P0, P1, and P2A authoring feasibility have been approved. The four-scenario P2B feasibility pilot is concluded with documented limitations. P2C full-dataset authoring has produced the approved private inventory of 60 scenarios and 480 language items. Independent bilingual validation and research-owner acceptance remain required before dataset freeze; model inference is not authorized.

## Exploratory pilot at a glance

| Design element | Authored private inventory |
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

These are the authored private counts. Scenario text, reference states and labels, and review materials remain under ignored `.research-data/` and are not in the public repository. The 12 controls are assigned to a separate locked auxiliary partition; control results remain outside the primary estimand. The owner approved matching controls only to locked primary scenarios. See the research specifications before changing or implementing the design.

## Research specifications

- [Protocol and hypotheses](docs/research/protocol.md)
- [Dataset and canonical-state specification](docs/research/dataset-spec.md)
- [Evaluation and statistical-analysis plan](docs/research/evaluation-plan.md)
- [Integrity and reproducibility requirements](docs/research/integrity-and-reproducibility.md)
- [Prior-work register](docs/research/prior-work.md)
- [Milestone roadmap and acceptance gates](docs/roadmap.md)

The research documents are authoritative. This README and `AGENTS.md` provide navigation and working guidance only. P0, P1, and P2A feasibility are approved. P2B's four-scenario feasibility pilot is closed; dependence disagreements remain unresolved. P2C full authoring and deterministic checks are complete. Human bilingual quality control, research-owner acceptance, and dataset freeze remain outstanding; no model inference is authorized.

## Development setup

Requires Python 3.11+; the P1 implementation uses the standard library at runtime and pytest for tests. The setup works on Apple Silicon macOS.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

The only development dependency is pytest. P1 provides the typed schema, deterministic oracle, and integrity validators. P2A/P2B provide local preflight, revision, and annotation-review utilities. Actual prototypes, all authored scenarios, language drafts, reviewer records, and reference data are stored only under ignored `.research-data/`; none belong in the public repository.

## Local development-data checks

Read the [authoring protocol](docs/research/authoring-protocol.md), [scenario blueprint](docs/research/scenario-blueprint.md), and [bilingual annotation protocol](docs/research/bilingual-annotation-protocol.md) before working with local data. The four original P2A prototypes received positive semantic and linguistic assessments in the concluded feasibility pilot, but their dependence disagreements remain unresolved. Newly authored P2C variants remain pending independent bilingual quality control; those four pilot-reviewed scenarios are excluded from new review tasks.

With the local research data present, run the deterministic preflight and isolation checks:

```bash
python -m multilingual_judge_pilot.preflight validate
python -m multilingual_judge_pilot.preflight review-packets
python -m multilingual_judge_pilot.preflight audit-annotations
python -m multilingual_judge_pilot.preflight isolation
```

`validate` emits a redacted aggregate report. `review-packets` writes two local label-free packets per prototype. `audit-annotations` checks independent annotations bound to both language-variant and canonical-scenario hashes; an empty or incomplete annotation set remains explicitly incomplete. `isolation` checks that private research-data paths are ignored and not already tracked. Never stage `.research-data/`.

The public reports are the [P2A preflight report](docs/research/p2a-preflight-report.md), [P2B pilot closeout](docs/research/decision-records/2026-11-03-p2b-feasibility-pilot-closeout.md), [P2C development-authoring preflight](docs/research/decision-records/2026-11-03-p2c-development-authoring.md), and [P2C full-authoring closeout](docs/research/decision-records/2026-11-03-p2c-full-dataset-authoring-closeout.md). Structural and oracle checks do not establish language semantic validity.

## Current boundary

P2C full authoring and deterministic validation are complete. Do not alter human review records, reopen pilot disagreements, freeze the dataset, proceed to P3/P4/P5, execute judge inference, or make paid API calls without separate authorization. No inference budget is authorized by this repository setup.
