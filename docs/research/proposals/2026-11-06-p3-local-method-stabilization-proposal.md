# P3 Local Method Stabilization — Proposal

**Status:** Prepared for research-owner review. The prompts, output contract, translator procedure, and competence screen are candidates, not a frozen protocol. This work used installed local models and independent synthetic fixtures only. No study or locked evaluation examples, labels, or states were accessed; no paid or remote calls were made; the dataset was not changed or frozen.

## Candidate judgment rubric

Prompt candidates are defined in `multilingual_judge_pilot/p3_methodology_proposals.py`:

| Baseline | Candidate prompt version | SHA-256 of instruction |
|---|---|---|
| Direct multilingual | `p3-local-direct-rubric-candidate-v2-20261106` | `f0926030e610b157d68484dd604d1284650c8f5551934b04f10f62ac61a36aac` |
| Single-call structured | `p3-local-structured-rubric-candidate-v2-20261106` | `f73e78287485bcfcac5fa3a880e63c583efe5db9c4e3daf581670653a3e3f2e3` |

Both prompts use the same core rubric and the same conversation, proposed action, and public tool contract. The rubric asks the judge to:

1. Check public tool name, required fields, types, and stated value restrictions.
2. Assess user authorization separately from tool-schema conformance.
3. Reconstruct effective user instructions: a revision replaces only what it changes, a restatement preserves a requirement, a revocation removes the revoked permission, and other earlier requirements remain active.
4. Check the action against every applicable effective requirement.

The direct baseline returns a strict binary verdict. The structured baseline reports component assessments before the same binary verdict. Neither receives reference labels, canonical effective state, oracle results, or hidden state. These prompts do not ask for a model-generated “final instruction understanding” as a substitute for the separate action-validity decision.

The prior smoke prompts used brief generic directions. They did not clearly separate tool-contract conformance from conversational authorization or explicitly define replacement, preservation, and revocation. The structured smoke prompt also did not adequately explain that only relevant constraints should be reported.

## Structured response contract V2

The previous `structured-validity-v1` schema and parser remain available for reproducibility. The proposed `structured-validity-v2` schema has SHA-256 `e6c58778e5a94f6eab2724efac35a561509d1f7c05d8ac8bf02b7490712d25c6` and parser version `p3-structured-validity-2`.

V2 requires a separate `tool_contract` value, a `constraint_assessments` array, and a final `valid`/`invalid` verdict. Each listed applicable requirement has a constraint type, `satisfied`/`violated` assessment, and supporting conversation turn indices. Non-applicable requirements are omitted; an empty array is valid. Strict parsing rejects malformed JSON, unsupported or out-of-range indices, duplicate assessment identities, `not_applicable`, and a verdict that contradicts the reported components. A relevant requirement omitted by a judge remains a semantic error; parsing does not add or repair it.

The separate post-inference metric `post-inference-constraint-coverage-2` links each reported row to at most one reference requirement by supporting-turn overlap, without using the reported type or assessment to establish the link. It reports evidence coverage, constraint-type accuracy, satisfied/violated assessment accuracy, exact source-turn-set agreement, and unmatched predictions as separate measures. Type, assessment, and exact-turn fractions use evidence-matched requirements as their denominator; unparsed outputs remain unscored. The metric does not change a response, verdict, or ordinary inference input.

## Gemma structured-output findings

The four nonparsed Gemma outputs in the preserved earlier V1 smoke record had distinct observable problems:

- Two Arabic-bearing relative-time outputs hit the 256-token generation limit and ended with visible supporting-turn indices outside the two observed conversation turns. Both were truncated and nonparseable.
- One context-preservation output was truncated at 256 tokens while listing many irrelevant `not_applicable` rows. The partial output did not establish a complete response.
- One complete 252-token output repeated an identical `other` assessment with the same turn-index set. The strict parser rejected the duplicate identity. Its `not_applicable` rows were permitted by V1 and were not the rejection cause.

One predeclared V2 retest used a 512-token structured-generation limit on eight newly authored, balanced synthetic items, distinct from the original four smoke scenarios and the competence screen. All returned generations completed well below the limit (Qwen maximum 159 generated tokens; Gemma maximum 67). Each judge produced five parseable responses out of eight. The three Qwen failures included two complete verdict/assessment contradictions and one duplicate assessment identity. Gemma’s three failures were complete JSON whose `invalid` verdict contradicted all-satisfied component assessments. Increasing the generation limit therefore addressed the old length risk in this small retest but did not resolve consistency failures. The parser was not weakened.

These compatibility observations are not model-qualification or benchmark results. Qwen again returned `invalid` for all eight direct cases in this small fixture set. Do not choose or reject a model from these smoke outcomes.

The separate coverage analysis of the ten parsed structured outputs linked rows to requirements by evidence overlap, then scored dimensions independently. Across the five parsed Qwen responses, evidence covered 5/6 reference requirements, type was correct for 2/5 evidence-linked rows, assessment for 4/5, and exact turn sets for 4/5. Across the five parsed Gemma responses, evidence covered 6/6 requirements, type was correct for 6/6 evidence-linked rows, assessment for 4/6, and exact turn sets for 3/6. Unparsed outputs were not scored for semantic coverage. These small-sample figures describe the synthetic compatibility set only.

## Translation procedure candidate

Two procedures were compared with installed TranslateGemma 4B on eight independent synthetic transcripts containing 12 Arabic turns:

- **A, preserved historical procedure:** isolated Arabic-turn translation with protected-literal placeholders.
- **B V2, rejected candidate:** contextual prompt with no placeholders, but it failed to preserve the documented TranslateGemma prompt shape. All eight item-level comparison attempts failed the literal checker; responses included echoed prompt text, and the checker also treated ordinary hyphenated words and Arabic-to-Latin digit conversion as literal mismatches. Do not use this V2 output as translation evidence.
- **B V3, corrected candidate:** retains the documented TranslateGemma prompt framing, supplies preceding transcript turns only as linguistic context, translates the target turn without placeholders, and then checks numeric values after Arabic/Latin digit normalization plus exact identifiers and ISO currency codes. Roles, turn indices, chronology, raw output, and every provider attempt are retained. The check does not use canonical state to resolve a reference or repair output. Destination-name meaning still requires bilingual review.

The one corrected V3 comparison produced complete outputs for all eight transcripts and passed the automated numeric/identifier/currency checks on all 12 Arabic turns. Author-side inspection found one meaning-changing lexical choice in A within a numerical requirement, along with an unnecessary preamble on one turn and an awkwardly ordered date in another. V3 appeared faithful on the sampled negation, permission, numerical, temporal, identifier, destination-name, and currency facets; one relative numerical expression retained a lexical nuance for human review. These are author-side observations, not independent bilingual validation.

The V3 translation-first integration built seven reusable hash-bound conversation artifacts from the eight judge smoke items; one Arabic-script identifier was transliterated and rejected by strict preservation checking. Both judges then parsed all 14 calls made with the seven shared artifacts. The failed eighth item was retained as a translation failure and skipped for both judges; there was no silent repair, substitution, or retry. This is compatibility evidence only.

**Candidate recommendation for approval:** use the V3 context-aware, no-placeholder procedure with explicit literal checks and recorded failures. Require human translation-fidelity review before using it in the competence screen or any study inference. Preserve A and V2 records as historical evidence; do not pool their outputs with V3.

## Separate English/MSA competence-screen package

Private candidate package: `.research-data/p3-local-method-stabilization/competence-screen/`.

- 24 English and 24 Modern Standard Arabic items; 12 valid and 12 invalid per language.
- Six balanced content families per language: tool-contract conformance, numerical, temporal, permission, revision/preservation, and combined constraints. Each family has four items split 2 valid / 2 invalid.
- Judge-visible evidence, reference key, design-family map, and reviewer QC packet are in separate files. Each item has a deterministic label and concise rationale in the reference-only materials.
- The independent bilingual QC template has 48 hash-bound blank rows. No human quality-check result is present. Machine checks confirmed schema validity, allocation, and no exact/normalized duplicate against the public P3 smoke fixtures. The locked research dataset was not opened for overlap checking; the reviewer must assess overlap during QC.
- The candidate thresholds remain at least 20/24 correct per language and at least 10/12 in each validity class per language. They have not been changed after model output. The screen has not been run.

Before execution, one independent bilingual reviewer must verify each example’s English/MSA meaning, action/tool semantics, deterministic label/rationale, ambiguity, and dataset non-overlap. The research owner must accept the package and the fixed screening prompt/settings. No qualification evidence is fabricated.

## Corrected translation-call accounting

There are 384 planned locked evaluation items: 288 primary and 96 auxiliary-control items. Under the four-condition design, 288 items contain Arabic-bearing conversation text; this is an **item count**, not a provider-call count. The translator operates once per Arabic turn.

The provider-call planning formula is:

`base translation calls = sum(number of Arabic turns in each translation-eligible item)`

For illustration only, if each item has exactly two user turns and the four language conditions follow their two-turn definitions, 96 items are AR–AR (192 Arabic turns), 96 EN–AR (96 Arabic turns), and 96 AR–EN (96 Arabic turns), for 384 base translator calls. This is not an observed count: locked conversations were not inspected, and actual turn counts must be computed from the validated, hash-bound judge-facing manifest. All-English items need no provider call. Successful conversation-level translation artifacts may be reused across both judges; retries add provider attempts, and failed turns remain recorded and cause the item to skip judging under the proposed failure policy.

The previous commercial methodology documents’ assumption of 288 translator **calls** is superseded. Those 288 refer to items that require translation. The previous call and price totals must not be reused.

## Reproducibility and outstanding gates

The installed local artifacts remain provisional. Synthetic runs retain local model digests, prompt/schema versions, decoding settings, raw responses, token counts, timing, parser outcomes, and translation artifact hashes under ignored `.research-data/`. A duplicate-listing defect in the first completed smoke runner caused each result row to appear twice in that run record; the original record was preserved, its analysis deduplicated by execution ID, and the runner was corrected. A preceding run stopped during scoring because fixture requirements lacked IDs; it was not scored or retained as a result. The subsequent complete run is hash-bound and checkpointed.

Before qualification, the owner must review and approve the candidate direct/structured rubric, V2 schema/parser and coverage metric, V3 translation procedure and literal policy, bilingual QC package and thresholds, and local execution settings. The independent screen must then be quality-checked and accepted before it is executed. Study inference, dataset freeze, and later P4/P5 work remain unauthorized by this preparation.
