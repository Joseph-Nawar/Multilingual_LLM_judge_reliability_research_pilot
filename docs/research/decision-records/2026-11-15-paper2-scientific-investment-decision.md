# Paper 2 scientific investment checkpoint

**Date:** 2026-11-15. **Primary recommendation: REVISE.** This is a scientific recommendation to the research owner, not a change to the approved locked configuration or an adjudication of language data.

**Should the owner begin the 448-item human reviews now? No.** First amend and approve the locked analysis design to include one identically prompted, paired withheld-state versus supplied-state diagnostic across the existing 36 locked primary and 12 auxiliary scenarios. Freeze its prompt, state projection, order, parser, and scenario-level analysis before any locked inference. This adds **768 local Gemma calls** (384 items × two arms), **$0 paid API expenditure**, and **no new reviewer rows**; the existing two 448-item reviews remain the validation gate. Do not execute that proposed locked diagnostic before review, resolution, and pre-inference freeze. The present development diagnostic does not amend the locked protocol.

## Novelty challenge

The method of testing both invariance and verdict-changing sensitivity is already established by [Chen et al.](https://arxiv.org/html/2608.24419v1), and paired opposite-label histories are not themselves novel. [Judge-LS](https://arxiv.org/html/2606.14278v1) tests language-switching invariance in English–Chinese pairwise response evaluation. [Fu and Liu](https://aclanthology.org/2025.findings-emnlp.587/) test multilingual judge consistency across tasks and languages, including math questions. [BabelJudge](https://arxiv.org/html/2606.22329v1) includes Arabic and agent-trajectory perturbations. [AgentJudgeBench](https://arxiv.org/html/2608.26623v1) compares tool-call judges with and without *expected tool calls* supplied; its reference exposure and structured-action focus are especially close. [TurnFlow](https://aclanthology.org/2026.findings-emnlp.825/) tests evolving user-state reasoning in *task-performing agents*, with a verifier, rather than treating the action-validity judge as the target.

The potentially distinct contribution is a **joint test of judge sensitivity to consequential user-state changes and invariance to English–Arabic language presentation**, for the *same proposed action*, with the canonical active state supplied in a separate diagnostic that still withholds action validity. That could show whether missing active-state information matters for judging, and whether any effect varies by transition family or language position. It does not identify a hidden reasoning mechanism. A finding limited to “multilingual judges make errors” would duplicate existing work. A null code-switching contrast remains a valid result if the transition and state-access questions are well tested.

## Verified Direct V2 development evidence

I independently joined all 96 retained Direct V2 result records to the private scoring map and separate oracle reference. The reported **80/96** individual accuracy and **32/48** both-correct counterfactual pairs are correct. All responses parsed. Every pair has opposite reference labels, so with binary parsed responses the **32/48 appropriate verdict flips** equal the both-correct count. The four intended semantically equivalent language versions received the same verdict in **22/24 histories**; **19/24** histories were correct in all four. These are observed invariances in author-side, **not independently validated**, variants.

| Direct V2 group | Correct / total |
| --- | ---: |
| EN–EN; AR–AR; EN–AR; AR–EN | 21/24; 19/24; 19/24; 21/24 |
| Introduction; permission revocation | 24/24; 24/24 |
| Numerical revision; temporal revision | 16/24; 16/24 |
| Reference-valid recall; reference-invalid recall | 38/48; 42/48 |

The 16 errors occur in **five of 12 scenarios**: preserved booking numerical (4/8 errors), preserved scheduling temporal (4/8), P2C booking temporal (4/8), P2C customer-operations numerical (2/8), and P2C scheduling numerical (2/8). Thus three scenarios account for 12/16 errors; this is a localized difficulty pattern, not broad evidence of a multilingual failure. The two language-noninvariant histories are both P2C numerical cases. Resampling the **12 scenario clusters** with all derivatives retained (10,000 draws, seed 17) gives descriptive 95% bootstrap intervals: accuracy **70.8%–93.8%**, both-correct pairs **41.7%–87.5%**, and four-language verdict invariance **79.2%–100%**. The 48 scenario-condition pairs are not 48 independent scenarios.

## New shared-prompt state-information diagnostic

The versioned `paper2-h2-shared-state-information-v2-20261115` diagnostic used only the eight existing P2C development scenarios (64 items), excluding the concluded four-scenario pilot and all locked items. Arm A included the original conversation, action, public tool contract, and `effective_state: null`; arm B included identical fields with the canonical active constraints and permissions. The single instruction, binary JSON contract, pinned `gemma4:12b-it-qat` digest, temperature 0, seed 17, thinking disabled, 4,096-token context, and 96-token output limit were identical. A fixed seed randomized the 128 requests; A preceded B in 31 pairs, B preceded A in 33. There was one request per arm and item, no retry or prompt optimization, and no paid or remote inference. All 128 raw responses and the separate scoring records remain private.

| Shared-prompt outcome | Withheld A | Supplied B |
| --- | ---: | ---: |
| Individual accuracy | **55/64** | **63/64** |
| Valid recall | 27/32 | 31/32 |
| Invalid recall | 28/32 | 32/32 |
| Numerical revision | 11/16 | 15/16 |
| Temporal revision | 12/16 | 16/16 |
| Introduction; permission revocation | 16/16; 16/16 | 16/16; 16/16 |
| Parsed / parse failures / technical failures | 64 / 0 / 0 | 64 / 0 / 0 |

Supplying state corrected **9** judgments and damaged **1**, for a net **8/64** accuracy difference. By scenario, the A→B correct counts were: booking temporal **4→8**, customer-operations numerical **5→8**, scheduling numerical **6→7**, and **8→8** in each of the other five. Corrections therefore arose in **three of eight scenarios**, with seven of nine in two scenarios. A scenario bootstrap (10,000 draws, seed 17) gives a descriptive 95% interval of **0.0 to 26.6 percentage points** for B–A accuracy; this tiny, concentrated sample warrants no significance claim. Accuracy intervals were A **71.9%–100%** and B **95.3%–100%**. The sole B error was a reference-valid scheduling numerical case with an action value above an explicitly supplied inclusive minimum; tool-contract interpretation or simple comparison difficulty remains possible. No internal mechanism follows from this behavior or from model explanations.

The supplied-state effect is materially interesting within this fixed diagnostic, but the state object also changes input length and representation. It cannot prove that state reconstruction caused earlier Direct V2 failures. The new A and B share a prompt with each other, **not with historical Direct V2**; their accuracies must not be interpreted as a controlled comparison with that historical run. Formal state/action checks and translation span checks do not establish bilingual semantic validity.

## Decision and publication limits

The current locked plan can estimate four language-condition accuracies, counterfactual sensitivity, and a small matched no-change contrast. It cannot validate the strongest new state-access insight at locked scale because only development H2 inference was authorized. That is the single necessary design revision above. Existing no-change controls are useful but too few and incompletely matched to isolate every arithmetic or temporal difficulty from transition difficulty. The remaining B error makes this alternative explanation live. The revision is justified by the observed behavioral lift, while its concentration prevents a GO on the present design.

Findings-level rigor would still require the commissioned **two independent bilingual reviews**, documented resolution of substantive issues, deterministic revalidation, template and surface-shortcut audits, and a hash-bound pre-inference freeze. Report scenario and, where feasible, template-clustered uncertainty, all negative/null results, failures, and deviations. Generalization beyond Gemma remains **unestablished**: the installed Qwen3.5 judge previously failed the fixed exploratory English/MSA screen (23/48 overall; 1/24 valid), the other Qwen installation is not a qualified independent family, and TranslateGemma is the translator. No suitable second local judge family was available, and none was selected or downloaded. A later independently competent family would be necessary for a broad judge-family claim. The owner must review any methodological amendment; this record does not authorize new locked inference, data changes, or human-validation claims.
