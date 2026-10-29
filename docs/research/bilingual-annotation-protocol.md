# Independent bilingual annotation protocol

**Status:** The P2A annotation procedure is retained and extended for P2B-1 review preparation. No revised language draft has been independently reviewed, approved, or adjudicated.

## Reviewer qualifications and separation

Each English/MSA language derivative is reviewed independently by two qualified bilingual reviewers. Record anonymized reviewer IDs, qualifications relevant to English and Modern Standard Arabic, and any conflicts of interest in a separate access-controlled reviewer roster. The research owner may be one reviewer; the second must be a separate qualified human. Reviewer-slot labels in local packets are placeholders, not evidence that a reviewer has been recruited or has annotated anything. Reviewers do not discuss judgments before submitting annotations and must not see model-judge predictions, scores, explanations, or run results. They may consult the canonical semantic specification, the formal action/tool contract, and the paired histories needed to assess controlled differences. They do not receive oracle verdicts in the review packet. Do not show reviewers the authors' provisional complexity classification or rationale before their independent answers.

All prototype language is Codex-authored, machine-assisted draft material. Neither the authoring model nor deterministic structural checks count as a human reviewer. Do not label a draft validated until two independent annotations, disagreement adjudication, required corrections, and re-review are complete.

## Required annotation dimensions

Review each derivative against its canonical formal specification and, where applicable, compare the other language-condition variants for the same history.

### Decisive-update and whole-action dependence

For every history-language derivative, assess both constructs independently. Do not infer either answer from turn count, transition family, or oracle validity. Do not show reviewers the author's provisional classification or rationale for either construct.

**A. Decisive-update dependence** is the prospective primary complexity annotation. Answer: **“Can the effective requirement introduced, revised, revoked, or preserved by the decisive turn be determined without referring to earlier conversational information?”** Record exactly one `decisive_update_dependence` value: `yes`, `no`, or `unclear`, and a separate non-empty `decisive_update_dependence_rationale` identifying the requirement and supporting conversation turn(s). `yes` means the update is directly interpretable; `no` means earlier context is needed to resolve its referent, prior value, scope, permission, or other required context; `unclear` remains unresolved.

**B. Whole-action dependence** retains the prior validity question: **“Can the validity of the entire agent action be determined from the decisive turn, action, and public tool contract alone, or is earlier conversation necessary?”** Record exactly one `whole_action_dependence` value: `yes`, `no`, or `unclear`, plus a separate non-empty `whole_action_dependence_rationale` identifying the requirements and turn(s) needed to assess the whole action. This includes earlier constraints unrelated to the decisive update, such as a separate permission grant.

These constructs can differ. For example, a numerical update can be directly interpretable while whole-action validity depends on an earlier permission. Assess the content and formal referents; do not collapse the two answers or use either as a proxy for the other.

### Semantic relation

Choose exactly one:

- `equivalent`: the language variant preserves the formal meaning and decision-relevant content.
- `meaning_changed`: it asserts a different requirement, event, scope, action condition, or polarity.
- `ambiguous`: a reasonable bilingual reader could interpret the text in materially different ways or cannot determine the intended constraint.

### Linguistic quality

Choose exactly one:

- `natural`: clear, idiomatic MSA or English for the stated context.
- `acceptable_variation`: a natural alternative phrasing whose wording differs without changing the meaning.
- `unnatural_or_unclear`: awkward, overly literal/technical, or difficult to understand; specify whether this also creates ambiguity.

### Issue codes

Select all that apply, or none:

- `incorrect_number`, `incorrect_time`, `incorrect_unit`, `incorrect_permission`, `incorrect_technical_literal`;
- `missing_decision_relevant_information`;
- `incorrect_conversational_chronology`.

Issue codes do not replace the semantic-relation or linguistic-quality judgments. A correction must be recorded even when an issue does not alter the final validity label.

## Independent review checklist

For every variant, reviewers answer each checklist item yes/no and explain every no or uncertainty:

1. Does the conversation match the canonical task, formal initial state, and action contract?
2. Does each English/MSA variant preserve the same user-intended meaning for its language condition?
3. Are all initial requirements and permission grants communicated in the initial judge-visible context?
4. Does the decisive user turn express the associated formal introduction, revision, revocation, or restatement?
5. Are the counterfactual histories controlled as specified, with only the intended decisive meaning differing?
6. Does the identical structured action have the intended interpretation in each history?
7. Does every judge-visible turn precede the action decision point, with no later information included?
8. Is the MSA wording natural and unambiguous?

Check scope, referents, polarity, units, numeric boundaries, currency code and amount, date/time, timezone, permission state, literal identity/order, turn language, and any formal requirement not directly mentioned in the checklist. Confirm that the action is a valid public tool call in both histories; a structurally malformed call is an authoring/schema defect, not a translation failure.

## Annotation records and hashing

Store annotations as UTF-8 JSONL under ignored `.research-data/p2b-1/annotations/`. The updated contracts are `p2b1-review-3`, `p2b1-annotation-2`, and `p2b1-adjudication-2`. Existing review slots contain no completed human annotations and require no migration. Each annotation row includes:

- example/derivative ID and exact SHA-256 of the reviewed language-variant record (`example_sha256`);
- exact SHA-256 of the canonical scenario specification (`canonical_scenario_sha256`), including action, public tool schema, and formal states/events;
- reviewer ID;
- one semantic relation and one linguistic-quality category;
- `decisive_update_dependence` and its supporting `decisive_update_dependence_rationale`;
- `whole_action_dependence` and its separate supporting `whole_action_dependence_rationale`;
- zero or more issue codes;
- all eight checklist booleans and explanatory notes.

The preflight utility rejects unknown or stale variant and canonical-scenario hashes, duplicate reviewer/example rows, unsupported schema versions, invalid dependence categories, missing rationales/checklist answers, and fields containing gold labels or judge predictions. Require two distinct reviewers for each of the 32 prototype variants. A change to either language content or its formal specification invalidates the paired review record. Preserve prior bytes and hashes rather than overwriting them. Do not fill annotation fields until a qualified human has completed that independent review.

## Agreement and adjudication

Report the number of expected and completed annotations, missing reviews, and reviewer IDs. For the nominal semantic-relation category, report raw percent agreement and Cohen's kappa when the complete two-reviewer table makes it defined; state when kappa is undefined or the sample is too small to interpret. Also report decisive-update-dependence and whole-action-dependence agreement separately, plus linguistic quality, issue codes, and checklist items descriptively. Do not treat agreement statistics from four scenarios as reliability evidence for a population.

Any disagreement in semantic relation, either categorical dependence assessment, linguistic quality, issue codes, or checklist responses requires adjudication by someone who can inspect the canonical specification and both independent records. Different rationale wording alone does not require adjudication when the categorical answers agree and both rationales are substantive. The adjudication record must carry the exact `example_sha256` and `canonical_scenario_sha256`; each must match both independent annotations. It also records both reviewer IDs, adjudicator ID, disagreement, rationale, and outcome (`retain`, `revise`, `exclude`, or `unresolved`). Reject duplicate, unknown, stale, unsupported-version, or malformed adjudication records. A `revise` outcome requires new content hashes, retained revision history, and fresh review by both reviewers. An incomplete annotation pair or any `unresolved` disagreement means the review process is incomplete; it must not be reported as completed semantic validation. Even a complete review process is not a positive validation result unless content outcomes support that conclusion.

Preserve excluded, ambiguous, unsuccessful, and revised drafts with reasons and hashes in the local audit trail. Do not delete an inconvenient candidate or substitute a new example based on judge behavior. If a second qualified reviewer cannot be engaged, retain status `pending_independent_review` and stop before claiming P2B validation or dataset readiness.
