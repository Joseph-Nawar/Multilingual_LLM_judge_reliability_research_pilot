from hashlib import sha256

from multilingual_judge_pilot.audit import ValidationDisposition, audit_scenario_json
from multilingual_judge_pilot.serialization import scenario_to_json
from p1_fixtures import numerical_revision_pair


def test_malformed_candidate_is_preserved_in_rejection_ledger_with_hash_and_source():
    raw_candidate = '{"schema_version":"1.0","scenario":'

    outcome = audit_scenario_json(
        raw_candidate,
        candidate_id="synthetic-malformed-1",
        source_reference="test-fixture://malformed-1",
        recorded_by="p1-test",
    )

    assert outcome.scenario is None
    assert outcome.raw_candidate_json == raw_candidate
    assert outcome.ledger_entry.disposition is ValidationDisposition.REJECTED
    assert outcome.ledger_entry.payload_sha256 == sha256(raw_candidate.encode("utf-8")).hexdigest()
    assert outcome.ledger_entry.source_reference == "test-fixture://malformed-1"
    assert outcome.ledger_entry.error_codes
    assert outcome.ledger_entry.message


def test_oracle_label_mismatch_is_recorded_as_rejected_candidate():
    import json

    payload = json.loads(scenario_to_json(numerical_revision_pair()))
    payload["scenario"]["histories"][0]["declared_label"] = "valid"
    raw_candidate = json.dumps(payload)

    outcome = audit_scenario_json(
        raw_candidate,
        candidate_id="synthetic-wrong-label-1",
        source_reference="test-fixture://wrong-label-1",
        recorded_by="p1-test",
    )

    assert outcome.scenario is None
    assert outcome.ledger_entry.disposition is ValidationDisposition.REJECTED
    assert "declared label" in outcome.ledger_entry.message
