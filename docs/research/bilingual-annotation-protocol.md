# Independent bilingual annotation protocol

**Status:** P2A annotation procedure for review. No P2A language draft has been independently reviewed, approved, or adjudicated.

## Reviewer qualifications and separation

Each English/MSA language derivative is reviewed independently by two qualified bilingual reviewers. Record anonymized reviewer IDs, qualifications relevant to English and Modern Standard Arabic, and any conflicts of interest in a separate access-controlled reviewer roster. Reviewers do not discuss judgments before submitting annotations and must not see model-judge predictions, scores, explanations, or run results. They may consult the canonical semantic specification, the formal action/tool contract, and the paired histories needed to assess controlled differences. They do not receive oracle verdicts in the review packet.

P2A language is Codex-authored, machine-assisted draft material. Neither the authoring model nor deterministic structural checks count as a human reviewer. Do not label a draft validated until two independent annotations, disagreement adjudication, required corrections, and re-review are complete.

## Required annotation dimensions

Review each derivative against its canonical formal specification and, where applicable, compare the other language-condition variants for the same history.

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

Store annotations as UTF-8 JSONL under ignored `.research-data/p2a/annotations/`. Use the tracked annotation schema/template. Each row includes:

- example/derivative ID and exact SHA-256 of the reviewed language-variant record;
- reviewer ID;
- one semantic relation and one linguistic-quality category;
- zero or more issue codes;
- all eight checklist booleans and explanatory notes.

The preflight utility rejects unknown example hashes, duplicate reviewer/example rows, invalid categories, missing checklist answers, and fields containing gold labels or judge predictions. Require two distinct reviewers for each of the 32 prototype variants. The hash binds the review to an exact version; a revision invalidates review of that content. Preserve the prior record and hash rather than overwriting it.

## Agreement and adjudication

Report the number of expected and completed annotations, missing reviews, and reviewer IDs. For the nominal semantic-relation category, report raw percent agreement and Cohen's kappa when the complete two-reviewer table makes it defined; state when kappa is undefined or the sample is too small to interpret. Also report agreement on linguistic quality, issue codes, and checklist items descriptively. Do not treat agreement statistics from four scenarios as reliability evidence for a population.

Any disagreement on semantic relation, linguistic quality, issue codes, or checklist responses is referred to an adjudicator who can inspect the canonical specification and both independent records. Record reviewer IDs, adjudicator ID, exact example hash, disagreement, rationale, and outcome (`retain`, `revise`, `exclude`, or `unresolved`). A `revise` outcome requires a new content hash, retained revision history, and fresh review by both reviewers. A candidate with unresolved disagreement cannot be called independently validated or included in a frozen release without an explicit, predeclared resolution rule approved by the research owner.

Preserve excluded, ambiguous, unsuccessful, and revised drafts with reasons and hashes in the local audit trail. Do not delete an inconvenient candidate or substitute a new example based on judge behavior. If a second qualified reviewer cannot be engaged, retain status `pending_independent_review` and stop before claiming P2B validation or dataset readiness.
