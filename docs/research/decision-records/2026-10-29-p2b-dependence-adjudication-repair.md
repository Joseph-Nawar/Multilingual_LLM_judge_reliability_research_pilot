# P2B-1 dependence and adjudication repair decision record

**Review date:** 2026-10-29

**Reviewed implementation:** `7572e535630fbfe5b059a2b2958c8a90288186bb` on `p2/prototype-bilingual-validation`.

**Authorized scope:** repair the two identified P2B-1 methodology issues and prepare the existing four development prototypes for private owner inspection. Full dataset authoring, locked examples, controls, model evaluation, and later milestones remain unauthorized.

## P2B-R1 — Separate dependence constructs

The prior historical-dependence question conflated whether the decisive update itself requires earlier context with whether any earlier fact is needed to evaluate the entire action. The annotation protocol now records two independent categorical answers, each with its own supporting rationale:

1. `decisive_update_dependence`: whether the effective requirement expressed by the decisive turn is determinable without earlier conversation. This is the prospective primary complexity stratification.
2. `whole_action_dependence`: whether full action validity is determinable from the decisive turn, action, and public tool contract alone. This remains a separate diagnostic annotation and may differ from the first answer when another requirement, such as permission, is only stated earlier.

Both reviewers assess both constructs independently. Author-side classifications are excluded from reviewer materials. Neither answer is inferred from turn count, transition family, or oracle validity.

The prospective 24/24 directly interpretable/history-dependent target now refers only to decisive-update dependence. It remains an exploratory allocation target, not a quota that justifies unclear or unnatural examples. Preserve `unclear`; if balanced coverage cannot be achieved in a transition family, record the limitation and obtain research-owner review before locked authoring. Whole-action dependence is summarized separately. Scenario counts and the primary four-language-condition comparison do not change.

## P2B-R2 — Versioned annotation and adjudication

The review packet, annotation, and adjudication contracts are versioned `p2b1-review-3`, `p2b1-annotation-2`, and `p2b1-adjudication-2`. Annotation rows require both dependence categories and non-empty, separate rationales. Agreement for each category is reported separately.

Disagreement on either dependence category, semantic relation, linguistic quality, issue codes, or checklist items requires adjudication. Different rationale wording alone does not. An adjudication carries the exact language-variant and canonical-scenario SHA-256 values; both values must match both independent annotations. Duplicate, unknown, stale, unsupported-version, and malformed records are rejected. Incomplete pairs and unresolved adjudications keep the review process incomplete. A completed review workflow does not by itself establish that content passed semantic validation.

The two existing reviewer slots were blank, so no annotation migration was needed. Their prior packet bytes were preserved locally before refresh. No reviewer identities, qualifications, annotations, or adjudications have been fabricated.

## Owner inspection and research status

A revised offline owner-inspection bundle is prepared at the ignored local path `.research-data/p2b-1/owner-review/p2b-1-owner-review-bundle.zip`. It contains the existing four machine-assisted development prototypes, their 32 language variants, formal specifications, coverage maps, readable bilingual review material, and content hashes. It omits explicit gold labels, oracle verdicts, predictions, and completed reviewer records. It remains local and unpublished for owner inspection.

The four prototypes remain unvalidated pending two independent qualified bilingual reviews. No additional scenarios, locked examples, or auxiliary controls were created. No model inference occurred. P2C, P3, P4, and P5 have not started.
