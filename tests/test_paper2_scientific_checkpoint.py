"""Synthetic safety checks for the development-only state intervention."""

from scripts.paper2_scientific_checkpoint import cluster_interval, evidence, safe_state


def test_arms_share_evidence_and_differ_only_in_state():
    item = {
        "item_id": "synthetic-item",
        "conversation": [{"turn_index": 1, "speaker": "user", "content": "Use a limit of 10.", "language": "en"}],
        "action": {"tool": "synthetic"},
        "public_tool_schema": {"name": "synthetic"},
    }
    state = {"active_constraints": [], "active_permissions": []}
    a, b = evidence(item, None), evidence(item, state)
    assert set(a) == set(b)
    assert {k: v for k, v in a.items() if k != "effective_state"} == {k: v for k, v in b.items() if k != "effective_state"}
    assert a["effective_state"] is None
    assert b["effective_state"] == state
    assert "language" not in a["conversation"][0]


def test_disclosed_state_rejects_answer_fields():
    assert safe_state({"active_constraints": [], "active_permissions": []})
    assert not safe_state({"active_constraints": [], "active_permissions": [], "validity": "invalid"})
    assert not safe_state({"active_constraints": [{"reference_verdict": "valid"}], "active_permissions": []})


def test_cluster_interval_uses_scenario_unit():
    rows = ([{"scenario_id": "one", "correct": 1}] * 8
            + [{"scenario_id": "two", "correct": 0}] * 8)
    assert cluster_interval(rows, "correct") == (0.0, 1.0)
