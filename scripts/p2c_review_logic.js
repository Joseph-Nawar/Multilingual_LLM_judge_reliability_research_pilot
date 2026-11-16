"use strict";

function createP2CReviewLogic(taxonomy) {
  if (!taxonomy || typeof taxonomy !== "object" || !taxonomy.version) {
    throw new Error("review reason taxonomy is missing");
  }

  const ANSWER_FIELDS = [
    "semantic_relation", "linguistic_quality", "decisive_update_dependence",
    "decisive_update_dependence_rationale", "whole_action_dependence",
    "whole_action_dependence_rationale", "issue_codes", "checklist", "notes",
    "q3_selection", "q4_selection", "issue_reports", "other_issue",
    "legacy_rationales", "legacy_notes",
  ];
  const OLD_ANSWER_FIELDS = [
    "semantic_relation", "linguistic_quality", "decisive_update_dependence",
    "decisive_update_dependence_rationale", "whole_action_dependence",
    "whole_action_dependence_rationale", "issue_codes", "checklist", "notes",
  ];
  const CHECKPOINT_FORMAT = "p2c-review-draft-3";
  const STRUCTURED_CHECKPOINT_FORMAT_2 = "p2c-review-draft-2";
  const OLD_CHECKPOINT_FORMAT = "p2c-review-draft-1";
  const GENERIC_EXPLANATIONS = new Set(["wrong", "unclear", "problem", "issue", "other", "not covered", "bad"]);

  function allowedReasons(question, answer) {
    const reasons = taxonomy[question]?.[answer];
    if (!Array.isArray(reasons)) throw new Error("question must be q3/q4 and answer must be yes/no/unclear");
    return reasons;
  }

  function uniqueStrings(value, label, allowEmpty) {
    if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item.trim())) {
      throw new Error(`${label} must be a list of non-empty strings`);
    }
    const cleaned = value.map((item) => item.trim());
    if (new Set(cleaned).size !== cleaned.length) throw new Error(`${label} must contain unique values`);
    if (!allowEmpty && cleaned.length === 0) throw new Error(`at least one ${label} is required`);
    return cleaned;
  }

  function specificExplanation(value, label) {
    if (typeof value !== "string") throw new Error(`${label} requires a specific explanation`);
    const cleaned = value.trim().replace(/\s+/g, " ");
    if (cleaned.length < 20 || GENERIC_EXPLANATIONS.has(cleaned.toLowerCase().replace(/[.!?]+$/, ""))) {
      throw new Error(`${label} requires a specific explanation of at least 20 characters`);
    }
    return cleaned;
  }

  function buildRationale(question, answer, selection, validTurnIndices = null) {
    const allowed = allowedReasons(question, answer);
    const keys = ["reasons", "supporting_turns", "fields", "explanation"];
    if (!selection || typeof selection !== "object" || Array.isArray(selection)
      || Object.keys(selection).length !== keys.length || keys.some((key) => !(key in selection))) {
      throw new Error("reason selection must contain reasons, supporting_turns, fields, and explanation");
    }
    const reasons = uniqueStrings(selection.reasons, "compatible reason", false);
    if (reasons.some((reason) => !allowed.includes(reason))) {
      throw new Error("selected reason is incompatible with the selected answer");
    }
    const turns = selection.supporting_turns;
    if (!Array.isArray(turns) || turns.some((turn) => !Number.isInteger(turn) || turn < 0)) {
      throw new Error("supporting turns must be non-negative integer turn indices");
    }
    if (new Set(turns).size !== turns.length) throw new Error("supporting turns must be unique");
    if (!turns.length) throw new Error("at least one supporting turn is required");
    if (validTurnIndices && turns.some((turn) => !validTurnIndices.includes(turn))) {
      throw new Error("supporting turn does not exist in this item's conversation");
    }
    if (question === "q3" && reasons.includes("multiple_earlier_turns_needed") && turns.length < 2) {
      throw new Error("multiple-turn reasons require at least two distinct supporting turns");
    }
    const fields = uniqueStrings(selection.fields, "requirement/field", true);
    if (question === "q4" && reasons.includes("multiple_earlier_requirements_needed") && fields.length < 2) {
      throw new Error("multiple earlier requirements need at least two selected requirement/field values");
    }
    let explanation = "";
    if (reasons.some((reason) => reason === "other" || reason.startsWith("ambiguous_or_conflicting"))) {
      explanation = specificExplanation(selection.explanation, "Other or ambiguous reasons");
    } else if (selection.explanation !== "" && selection.explanation !== null) {
      explanation = specificExplanation(selection.explanation, "Free-text explanation");
    }

    const catalog = question === "q3" ? taxonomy.q3_labels : taxonomy.q4_labels;
    const parts = [reasons.map((reason) => catalog[reason]).join("; ") + "."];
    parts.push("Supporting turn(s): " + turns.join(", ") + ".");
    if (fields.length) parts.push("Requirement/field: " + fields.join(", ") + ".");
    if (explanation) parts.push("Explanation: " + explanation);
    return parts.join(" ");
  }

  function buildIssueNotes(reports) {
    if (!Array.isArray(reports)) throw new Error("issue reports must be a list");
    return reports.map((report) => {
      const fields = ["type", "turn_index", "field", "expected", "observed", "explanation", "explanation_required"];
      if (!report || typeof report !== "object" || Array.isArray(report)
        || Object.keys(report).length !== fields.length || fields.some((key) => !(key in report))) {
        throw new Error("each issue report must include type, turn_index, field, expected, observed, and explanation");
      }
      const label = taxonomy.issue_types[report.type];
      if (!label) throw new Error("issue report type is not covered by the available options");
      if (!Number.isInteger(report.turn_index) || report.turn_index < 0) {
        throw new Error("every issue report needs a valid supporting turn index");
      }
      if (typeof report.field !== "string" || !report.field.trim()) {
        throw new Error("every issue report needs an affected field or requirement");
      }
      if ([report.expected, report.observed, report.explanation].some((value) => typeof value !== "string")) {
        throw new Error("issue evidence fields must be text");
      }
      if (typeof report.explanation_required !== "boolean") throw new Error("additional-explanation choice must be yes or no");
      const field = report.field.trim().replace(/\s+/g, " ");
      let details = `${label} (turn ${report.turn_index}; field ${JSON.stringify(field)})`;
      if (taxonomy.value_pair_types.includes(report.type)) {
        if (!report.expected.trim() || !report.observed.trim()) {
          throw new Error("this issue type requires expected and observed values");
        }
        details += `: expected ${JSON.stringify(report.expected.trim())}; observed ${JSON.stringify(report.observed.trim())}.`;
        if (report.explanation_required || report.explanation.trim()) {
          details += " Additional explanation: " + specificExplanation(report.explanation, label) + ".";
        }
      } else if (taxonomy.explanation_types.includes(report.type)) {
        details += ": " + specificExplanation(report.explanation, label);
      } else {
        throw new Error("issue report type is not covered by the available options");
      }
      return details;
    }).join("\n");
  }

  function emptySelection() {
    return { reasons: [], supporting_turns: [], fields: [], explanation: "" };
  }

  function emptyAnswer(checklistKeys) {
    return {
      semantic_relation: "", linguistic_quality: "", decisive_update_dependence: "",
      decisive_update_dependence_rationale: "", whole_action_dependence: "",
      whole_action_dependence_rationale: "", issue_codes: [],
      checklist: Object.fromEntries(checklistKeys.map((key) => [key, null])), notes: "",
      q3_selection: emptySelection(), q4_selection: emptySelection(), issue_reports: {},
      other_issue: false, legacy_rationales: { q3: "", q4: "" }, legacy_notes: "",
    };
  }

  function issueTriggers(answer, checklistKeys, checklistLabels) {
    const triggers = [];
    if (answer.semantic_relation === "meaning_changed") {
      triggers.push({ key: "semantic_meaning_changed", type: "semantic_meaning_changed", label: "Meaning changed" });
    } else if (answer.semantic_relation === "ambiguous") {
      triggers.push({ key: "semantic_ambiguity", type: "semantic_ambiguity", label: "Ambiguous meaning" });
    }
    if (answer.linguistic_quality === "unnatural_or_unclear") {
      triggers.push({ key: "linguistic_defect", type: "linguistic_defect", label: "Unnatural or unclear language" });
    }
    for (const code of answer.issue_codes || []) {
      triggers.push({ key: `issue_code:${code}`, type: code, label: taxonomy.issue_types[code] });
    }
    for (const key of checklistKeys) {
      if (answer.checklist?.[key] === false) {
        triggers.push({ key: `checklist:${key}`, type: "failed_checklist_item", label: `Failed checklist: ${checklistLabels[key] || key}` });
      }
    }
    if (answer.other_issue === true) triggers.push({ key: "other", type: "other", label: "Other / not covered" });
    return triggers;
  }

  function reportRecords(answer, checklistKeys, checklistLabels) {
    const records = [];
    for (const trigger of issueTriggers(answer, checklistKeys, checklistLabels)) {
      const selected = answer.issue_reports?.[trigger.key];
      if (!Array.isArray(selected) || !selected.length) {
        throw new Error(`${trigger.label} needs at least one issue report`);
      }
      for (const report of selected) {
        const { field_other, ...evidence } = report;
        records.push({
          type: trigger.type,
          ...evidence,
          field: report.field === "Other / not covered" ? field_other : report.field,
        });
      }
    }
    return records;
  }

  function problems(answer, checklistKeys, checklistLabels = {}, validTurnIndices = null) {
    const issues = [];
    if (!answer || typeof answer !== "object") return ["Review answers"];
    if (!["equivalent", "meaning_changed", "ambiguous"].includes(answer.semantic_relation)) issues.push("Meaning");
    if (!["natural", "acceptable_variation", "unnatural_or_unclear"].includes(answer.linguistic_quality)) issues.push("Language quality");
    if (!["yes", "no", "unclear"].includes(answer.decisive_update_dependence)) {
      answer.decisive_update_dependence_rationale = "";
      issues.push("Decisive-update context");
    }
    else {
      try { answer.decisive_update_dependence_rationale = buildRationale("q3", answer.decisive_update_dependence, answer.q3_selection, validTurnIndices); }
      catch (error) { answer.decisive_update_dependence_rationale = ""; issues.push("Decisive-update rationale: " + error.message); }
    }
    if (!["yes", "no", "unclear"].includes(answer.whole_action_dependence)) {
      answer.whole_action_dependence_rationale = "";
      issues.push("Whole-action context");
    }
    else {
      try { answer.whole_action_dependence_rationale = buildRationale("q4", answer.whole_action_dependence, answer.q4_selection, validTurnIndices); }
      catch (error) { answer.whole_action_dependence_rationale = ""; issues.push("Whole-action rationale: " + error.message); }
    }
    if (!Array.isArray(answer.issue_codes) || answer.issue_codes.some((code) => !taxonomy.issue_codes.includes(code))
      || new Set(answer.issue_codes).size !== answer.issue_codes.length) issues.push("Issue codes");
    const missing = checklistKeys.filter((key) => typeof answer.checklist?.[key] !== "boolean");
    if (missing.length) issues.push(`${missing.length} checklist answer(s)`);
    try {
      const reports = reportRecords(answer, checklistKeys, checklistLabels);
      answer.notes = buildIssueNotes(reports);
    } catch (error) {
      if (issueTriggers(answer, checklistKeys, checklistLabels).length) issues.push("Issue report: " + error.message);
      answer.notes = "";
    }
    return issues;
  }

  function validateSelectionShape(selection) {
    if (!selection || typeof selection !== "object" || Array.isArray(selection)
      || Object.keys(selection).length !== 4 || !["reasons", "supporting_turns", "fields", "explanation"].every((key) => key in selection)) {
      throw new Error("checkpoint contains malformed structured reason selections");
    }
    uniqueStrings(selection.reasons, "reason", true);
    uniqueStrings(selection.fields, "requirement/field", true);
    if (!Array.isArray(selection.supporting_turns) || selection.supporting_turns.some((turn) => !Number.isInteger(turn) || turn < 0)
      || new Set(selection.supporting_turns).size !== selection.supporting_turns.length || typeof selection.explanation !== "string") {
      throw new Error("checkpoint contains malformed reason evidence");
    }
  }

  function validateNewAnswer(answer, checklistKeys, validTurnIndices = null) {
    if (!answer || typeof answer !== "object" || Array.isArray(answer)
      || Object.keys(answer).length !== ANSWER_FIELDS.length || ANSWER_FIELDS.some((key) => !(key in answer))) {
      throw new Error("checkpoint contains a malformed structured answer");
    }
    if (!["", "equivalent", "meaning_changed", "ambiguous"].includes(answer.semantic_relation)
      || !["", "natural", "acceptable_variation", "unnatural_or_unclear"].includes(answer.linguistic_quality)
      || !["", "yes", "no", "unclear"].includes(answer.decisive_update_dependence)
      || !["", "yes", "no", "unclear"].includes(answer.whole_action_dependence)) {
      throw new Error("checkpoint contains unsupported assessment values");
    }
    for (const key of ["decisive_update_dependence_rationale", "whole_action_dependence_rationale", "notes", "legacy_notes"]) {
      if (typeof answer[key] !== "string") throw new Error("checkpoint contains malformed rationale or note text");
    }
    if (!Array.isArray(answer.issue_codes) || answer.issue_codes.some((code) => !taxonomy.issue_codes.includes(code))
      || new Set(answer.issue_codes).size !== answer.issue_codes.length) throw new Error("checkpoint contains invalid issue codes");
    if (!answer.checklist || typeof answer.checklist !== "object" || Array.isArray(answer.checklist)
      || Object.keys(answer.checklist).length !== checklistKeys.length
      || checklistKeys.some((key) => !(key in answer.checklist) || !(answer.checklist[key] === null || typeof answer.checklist[key] === "boolean"))) {
      throw new Error("checkpoint contains malformed checklist answers");
    }
    validateSelectionShape(answer.q3_selection);
    validateSelectionShape(answer.q4_selection);
    if (validTurnIndices) {
      for (const selection of [answer.q3_selection, answer.q4_selection]) {
        if (selection.supporting_turns.some((turn) => !validTurnIndices.includes(turn))) {
          throw new Error("checkpoint references a supporting turn that does not exist in this item's conversation");
        }
      }
    }
    const reportKeys = new Set([
      "semantic_meaning_changed", "semantic_ambiguity", "linguistic_defect", "other",
      ...taxonomy.issue_codes.map((code) => `issue_code:${code}`),
      ...checklistKeys.map((key) => `checklist:${key}`),
    ]);
    if (typeof answer.other_issue !== "boolean" || !answer.issue_reports || typeof answer.issue_reports !== "object" || Array.isArray(answer.issue_reports)
      || Object.keys(answer.issue_reports).some((key) => !reportKeys.has(key))
      || !answer.legacy_rationales || Object.keys(answer.legacy_rationales).length !== 2
      || typeof answer.legacy_rationales.q3 !== "string" || typeof answer.legacy_rationales.q4 !== "string") {
      throw new Error("checkpoint contains malformed issue or legacy evidence");
    }
    for (const reports of Object.values(answer.issue_reports)) {
      if (!Array.isArray(reports)) throw new Error("checkpoint contains malformed issue report lists");
      for (const report of reports) {
        const reportFields = ["turn_index", "field", "field_other", "expected", "observed", "explanation"];
        const expectedReportFields = report && Object.keys(report).length === reportFields.length
          ? reportFields : [...reportFields, "explanation_required"];
        if (!report || typeof report !== "object" || Array.isArray(report)
          || Object.keys(report).length !== expectedReportFields.length || expectedReportFields.some((key) => !(key in report))
          || !(report.turn_index === "" || (Number.isInteger(report.turn_index) && report.turn_index >= 0))
          || reportFields.slice(1).some((key) => typeof report[key] !== "string")) {
          throw new Error("checkpoint contains malformed issue report evidence");
        }
        if ("explanation_required" in report && typeof report.explanation_required !== "boolean") {
          throw new Error("checkpoint contains malformed additional-explanation choice");
        }
        if (!("explanation_required" in report)) report.explanation_required = false;
      }
    }
  }

  function validateLegacyAnswer(answer, checklistKeys) {
    if (!answer || typeof answer !== "object" || Array.isArray(answer)
      || Object.keys(answer).length !== OLD_ANSWER_FIELDS.length || OLD_ANSWER_FIELDS.some((key) => !(key in answer))) {
      throw new Error("legacy checkpoint contains a malformed answer");
    }
    if (!["", "equivalent", "meaning_changed", "ambiguous"].includes(answer.semantic_relation)
      || !["", "natural", "acceptable_variation", "unnatural_or_unclear"].includes(answer.linguistic_quality)
      || !["", "yes", "no", "unclear"].includes(answer.decisive_update_dependence)
      || !["", "yes", "no", "unclear"].includes(answer.whole_action_dependence)) {
      throw new Error("legacy checkpoint contains unsupported assessment values");
    }
    for (const key of ["decisive_update_dependence_rationale", "whole_action_dependence_rationale", "notes"]) {
      if (typeof answer[key] !== "string") throw new Error("legacy checkpoint contains malformed text fields");
    }
    if (!Array.isArray(answer.issue_codes) || answer.issue_codes.some((code) => !taxonomy.issue_codes.includes(code))
      || new Set(answer.issue_codes).size !== answer.issue_codes.length) throw new Error("legacy checkpoint contains invalid issue codes");
    if (!answer.checklist || typeof answer.checklist !== "object" || Array.isArray(answer.checklist)
      || Object.keys(answer.checklist).length !== checklistKeys.length
      || checklistKeys.some((key) => !(key in answer.checklist) || !(answer.checklist[key] === null || typeof answer.checklist[key] === "boolean"))) {
      throw new Error("legacy checkpoint contains malformed checklist answers");
    }
  }

  function migrateLegacyAnswers(answers, checklistKeys) {
    if (!answers || typeof answers !== "object" || Array.isArray(answers)) throw new Error("legacy checkpoint answers must be an object");
    const migrated = {};
    for (const [key, old] of Object.entries(answers)) {
      validateLegacyAnswer(old, checklistKeys);
      migrated[key] = {
        ...emptyAnswer(checklistKeys),
        semantic_relation: old.semantic_relation,
        linguistic_quality: old.linguistic_quality,
        decisive_update_dependence: old.decisive_update_dependence,
        whole_action_dependence: old.whole_action_dependence,
        issue_codes: [...old.issue_codes],
        checklist: { ...old.checklist },
        legacy_rationales: {
          q3: old.decisive_update_dependence_rationale,
          q4: old.whole_action_dependence_rationale,
        },
        legacy_notes: old.notes,
      };
    }
    return migrated;
  }

  function restoreCheckpoint(data, config) {
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("checkpoint must be a JSON object");
    if (data.slot !== config.slot) throw new Error("checkpoint reviewer slot does not match this workspace");
    let answers;
    let legacyImported = false;
    if (data.format === CHECKPOINT_FORMAT || data.format === STRUCTURED_CHECKPOINT_FORMAT_2) {
      if (data.source_fingerprint !== config.source_fingerprint
        && !config.legacy_source_fingerprints?.includes(data.source_fingerprint)) {
        throw new Error("checkpoint source fingerprint does not match this workspace or an approved matching prior source");
      }
      if (data.reason_taxonomy_version !== config.reason_taxonomy_version) throw new Error("checkpoint reason taxonomy version is unsupported");
      if (typeof data.legacy_imported !== "boolean") throw new Error("checkpoint legacy-import status is malformed");
      if (!data.answers || typeof data.answers !== "object" || Array.isArray(data.answers)) throw new Error("checkpoint answers must be an object");
      answers = data.answers;
      for (const [key, answer] of Object.entries(answers)) {
        if (!config.valid_item_ids.includes(key)) throw new Error("checkpoint contains an unknown item ID");
        validateNewAnswer(answer, config.checklist_keys, config.valid_turns_by_item?.[key] || null);
      }
      legacyImported = data.legacy_imported;
    } else if (data.format === OLD_CHECKPOINT_FORMAT) {
      if (!Array.isArray(config.legacy_source_fingerprints)
        || !config.legacy_source_fingerprints.includes(data.source_fingerprint)) {
        throw new Error("checkpoint source fingerprint is not an approved matching prior source");
      }
      if (!Array.isArray(data.position) || data.position.length !== 3 || data.position.some((value) => !Number.isInteger(value))) {
        throw new Error("checkpoint navigation position is malformed");
      }
      for (const key of Object.keys(data.answers || {})) {
        if (!config.valid_item_ids.includes(key)) throw new Error("checkpoint contains an unknown item ID");
      }
      answers = migrateLegacyAnswers(data.answers, config.checklist_keys);
      legacyImported = true;
    } else {
      throw new Error("checkpoint format is unsupported; keep the file and use its matching workspace");
    }
    if (!Array.isArray(data.position) || data.position.length !== 3 || data.position.some((value) => !Number.isInteger(value))) {
      throw new Error("checkpoint navigation position is malformed");
    }
    return {
      answers,
      position: data.position.map((value, index) => Math.max(0, Math.min(index === 0 ? config.scenario_count - 1 : index === 1 ? 1 : 3, value))),
      legacyImported,
    };
  }

  return {
    allowedReasons,
    buildRationale,
    buildIssueNotes,
    emptySelection,
    emptyAnswer,
    problems,
    restoreCheckpoint,
  };
}

if (typeof module !== "undefined" && module.exports) module.exports = createP2CReviewLogic;
if (typeof window !== "undefined") window.createP2CReviewLogic = createP2CReviewLogic;
