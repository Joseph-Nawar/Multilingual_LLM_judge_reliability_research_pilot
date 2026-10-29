# Research-owner decision record: P0 audit amendments

**Review date:** 2026-10-29  
**Reviewed P0 commit:** `58ff69361ec1db3af2c65d63dc915dfacc0c80bf`  
**Review outcome:** P0 repository foundation approved; amendments R1–R4 required before P1 implementation. This record captures the requested amendment decisions and the uncertainties that remain. It does not claim that the amended commit has received a second research-owner review.

## R1 — No-change linguistic control

**Recorded decision:** Preserve the primary set at 48 canonical scenarios, 96 histories, 384 items, with 12 development and 36 locked primary scenarios. Add a separately identified exploratory control of 12 canonical scenarios, 24 histories, and 96 additional items. Control turns restate or confirm an already active requirement without changing the effective state. Paired control histories start with different active requirements so the same action receives opposite labels without a revision within either history. Keep control results outside the primary estimand and report them separately. Do not claim that this small control fully identifies a causal revision effect.

**Partition proposal, not yet approved:** Keep all 12 controls locked and auxiliary, matched only to locked primary scenarios where feasible. This gives 12 development primary scenarios (96 items), 36 locked primary scenarios (288 items), and 12 locked control scenarios (96 items): 60 canonical scenarios and 480 items total. Research-owner approval is required in P1 before construction.

## R2 — Ordinary baselines

**Recorded decision:** Direct multilingual, translation-first, and structured/decomposed judging are candidate mandatory ordinary-condition baselines. The research owner must explicitly approve which are mandatory before locked evaluation. Cost/feasibility omissions must be documented before locked evaluation and unblinding. A method added after inspecting locked results is exploratory and cannot support an unqualified preplanned H3 claim. Use same-backbone comparisons where feasible, equivalent underlying evidence, frozen prompts/translations, and separate translator/judge cost and token accounting. Keep oracle-state diagnostics separate. Do not claim faithful reproduction of prior work until verified.

**Deferred:** The exact mandatory set, translator and translation procedure, structured rubric, same-backbone feasibility, and cost ceiling are unresolved and must be decided in P3 before the locked protocol is frozen.

## R3 — Template and semantic-recipe dependence

**Recorded decision:** Dataset provenance must include authoring-template and semantic-recipe identifiers, source/derivative relationships, match links, and versions. Detect and adjudicate near duplicates; inventory shared linguistic and constraint structures; report the number and reuse distribution of genuinely distinct templates and recipes. Where feasible, preserve template independence across development and locked partitions and record unavoidable overlap. Scenario-level clustering remains primary, with explicit warning that shared templates may cause it to underestimate uncertainty. Do not inflate nominal sample size using derived items.

**Deferred:** Final template/recipe taxonomy, duplicate-detection procedure, number of distinct templates achievable, and template allocation must be resolved in P1 and reported/validated in P2.

## R4 — Initial language and action representation

**Recorded operational decisions:** Arabic is Modern Standard Arabic. The four conditions are EN–EN, AR–AR, EN–AR, and AR–EN; the initial context uses the first language and the decisive later turn the second. All other turn-language assignments must be fixed in the approved scenario specification. Tool names and structured action representation remain invariant across language conditions; action semantics remain identical within counterfactual pairs. Names, currencies, dates, times, and numeric values are controlled across language variants; dates and times must be unambiguous. Judge instructions are fixed in English across all four conditions. English is the selected initial value for the fixed instruction language and must be confirmed before the P3 prompt freeze. Egyptian Arabic and Arabizi are outside this pilot.

Natural-language user instructions remain localized when they express intent or constraints. Literal code-like technical spans (tool/function and API/field names, IDs, URLs, email addresses, code snippets) remain byte-identical and are marked as invariant literals. If a literal itself carries user-facing meaning, add a localized natural-language statement or exclude the item under a reviewed rule; do not rely on untranslated code-like content as the only evidence.

**Deferred details:** Freeze the exact numeral-glyph and date/time rendering conventions, stable name mappings, ISO currency/date representation, and invariant-literal tagging during P1. The fixed-English judge instruction is an operational control and must remain byte-identical; prompt content and baseline-specific additions are frozen in P3.

## Additional safeguards recorded

- Ordinary inference and reference scoring use separate data-access paths. Gold labels, canonical effective states, and oracle verdicts do not enter ordinary judge prompts or development-time judge/model selection.
- Before judge selection for locked evaluation, run development-only basic English/MSA competence checks on separate screening material with predefined criteria. Do not use locked examples/labels or study gold/state/oracle references for selection.
- Model explanations are observable text, not ground truth about internal reasoning. H2 needs controlled diagnostic evidence, such as a paired ordinary versus oracle-state intervention with labels withheld, and cannot rest on rationales alone.
- The primary comparison reports all four language conditions. The cross-language versus same-language error contrast is exploratory. Controls are secondary and remain separate.
- Canonical scenarios are the primary dependence unit; retain template/recipe clusters for sensitivity analysis. No power calculation or confirmatory claim is invented for this feasibility pilot.

## Remaining uncertainties and resolution milestones

| Uncertainty | Required resolution milestone | Gate condition |
| --- | --- | --- |
| Control all-locked partition, matched primary-control selection, and feasible matching quality | P1 | Research owner approves partition/matching manifest before control construction. |
| Machine-readable template/recipe taxonomy, near-duplicate protocol, actual distinct-template count, and template allocation | P1; report and validate in P2 | Schema and duplicate rules are frozen before construction; P2 reports counts and leakage. |
| Numeral glyphs, date/time/currency rendering, name mappings, literal tagging, and complete assignment of non-decisive turns | P1 | Approved scenario specification fixes them before authoring or translation. |
| Qualified bilingual reviewer requirements and adjudication details for MSA and invariant literals | P2 | Independent validation protocol and adjudication evidence accepted before dataset freeze. |
| Basic language-competence screen, separate materials, and predeclared threshold | P3 | Screen is frozen and kept separate from benchmark items and reference labels before judge selection. |
| Confirmation of English as the fixed judge-instruction language | P3 | Research owner confirms it before prompt freeze; the instruction remains byte-identical across all four conditions. |
| Which candidate baselines are mandatory; translator, rubric, same-backbone feasibility, evidence parity, and cost cap | P3 | Research owner records baseline approvals/omissions before locked evaluation and unblinding. |
| Controlled H2 diagnostic, state-output scoring if used, and reference/inference access separation | P3 | Diagnostic changes only approved state access, with labels withheld; scorer isolation is demonstrated before locked execution. |
| Scenario- and template-aware interval procedure and any detectable-effect analysis | P3 before freeze; report in P5 | Analysis procedure is frozen before locked evaluation; no unsupported power or confirmatory claim. |

No uncertainty above authorizes beginning P1 automatically. The research owner must record approval at the corresponding gate.
