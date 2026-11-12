# P2B-2 independent human annotation audit

**Audit date:** 2026-11-01

**Status:** Research-owner approval gate pending. This record summarizes aggregate annotations only; raw submissions and detailed audit artifacts remain under ignored local research data.

## Coverage and agreement

The two submitted reviewer files contain 32 records each, covering all 32 expected development variants (64 annotations total). The reviewer IDs are distinct and each is consistently used in one submission. No categorical disagreements were found: semantic relation, linguistic quality, both dependence assessments, issue-code sets, and each of the eight checklist fields agreed for all 32 paired variants. No adjudication is required for those categorical fields.

All 64 semantic-relation ratings were `equivalent`. Linguistic-quality ratings were `natural` for 40 and `acceptable_variation` for 24; none were marked meaning-changed, ambiguous, or unnatural/unclear. Decisive-update dependence was `yes` for 32 ratings and `no` for 32; whole-action dependence was `no` for 48 and `yes` for 16. Neither dependence assessment was marked `unclear`. No issue codes were selected, and no checklist failures were recorded. Optional notes were empty in all 64 submissions. EN–EN responses to the MSA-naturalness checklist use the agreed N/A convention and are not counted as Arabic-naturalness evidence.

These categorical human ratings support prototype semantic-validation feasibility. They do not validate the full benchmark or establish anything about model-judge reliability.

## Blocking integrity finding

Both required dependence-rationale fields are empty in all 64 records. The records therefore fail the current annotation schema, and the existing audit utility exits with a validation error. Rationale consistency with the dependence classifications cannot be assessed. No rationale was imputed, and the submitted annotations were not edited. P2B-2 must remain pending until rationale-complete, hash-bound reviewer submissions are provided and re-audited.

## Provenance and limitations

The files contain two distinct submission IDs, but no verified person identities, qualification evidence, reviewer independence declarations, conflict disclosures, or reviewer-specific prior-exposure statements. The research owner reports that the reviewers are qualified bilingual humans; this claim is not independently documented in the submissions. The owner also reports participating in prototype design and viewing an AI-assisted worked annotation of one real hotel variant. It is unknown whether the owner corresponds to either submission ID; the exposure remains a potential independence or expectancy limitation.

The blank optional notes are allowed by the schema but leave no supplementary context. The four development prototypes are too few to support general claims about the planned benchmark. The owner-approval gate remains open.

## Scope

Only existing development annotations were audited. No prototype or reference record was modified, no additional examples were created, and no model inference or later research milestone was started.
