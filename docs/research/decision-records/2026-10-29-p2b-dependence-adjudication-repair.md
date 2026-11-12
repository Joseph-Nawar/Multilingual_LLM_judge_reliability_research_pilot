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

## Final owner disposition and scheduling-language correction

The research owner accepted the P2B-R1/P2B-R2 repairs and the revised prototype methodology. The flight-booking, hotel-booking, and customer-operations prototypes are accepted for independent bilingual review. A remaining parenthesis defect in the scheduling prototype's initial MSA wording was corrected in all Arabic-initial variants using the owner-approved wording; the full text and hashes are retained only in the ignored local revision history and regenerated reviewer packets.

The approved MSA wording refers to the same UTC offset once and then refers back to that time zone. P1 validation requires the invariant-literal sequence to match across language variants, while the former English initial wording repeated the offset. To preserve both the approved MSA wording and P1 validation, the matching English initial contexts now use an equivalent same-time-zone reference. This narrowly scoped alignment changed only initial-turn language in that scenario. The structured action, formal initial states and events, decisive turns, counterfactual ordering, and oracle-established labels were unchanged; the other three prototypes were unchanged. The semantic-coverage segment references remain valid, and deterministic validation was rerun.

Both reviewer-slot packet sets, blank hash-bound annotation templates, side-by-side presentations, and the local owner-review archive were regenerated from the current content hashes. There are still zero completed human annotations and zero recorded reviewer identities; all 32 variants remain unvalidated. The materials are ready for actual independent human annotation, not evidence that annotation has occurred. The offline bundle remains ignored and unpublished.

This correction does not authorize full dataset construction or model evaluation. No additional study scenarios, controls, locked examples, or model calls were created; P2C, P3, P4, and P5 remain unstarted.
