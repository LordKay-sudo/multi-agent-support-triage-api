from scripts.demo_request import load_payload, run_in_process_demo


def test_demo_request_runs_full_triage_flow() -> None:
    result = run_in_process_demo(load_payload())

    assert result["status"] == "triaged"
    assert result["category"] == "security"
    assert result["priority"] == "critical"
    assert result["escalate"] is True
    assert "risk_review" in result["workflow_path"]
    assert result["recommended_actions"]
