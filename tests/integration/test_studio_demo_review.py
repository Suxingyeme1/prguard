from pathlib import Path

import pytest

from prguard.harness import verify_manifest
from prguard.studio import StudioConfig, StudioService
from tests.integration.test_studio import StudioClient


@pytest.mark.integration
def test_regression_demo_reviews_a_green_patch_and_delivers_code_plus_regression_test(tmp_path):
    client = StudioClient(StudioService(StudioConfig(
        workspace=tmp_path / "runs", enable_independent_review=True,
    )))
    try:
        run_id = client.json("POST", "/api/prepare", {
            "mode": "demo", "demo_case": "review_regression", "workflow": "reviewed_fix",
        })["id"]
        preview = client.wait(run_id, "ready")["preview"]
        assert preview["demo_case"] == "review_regression"
        assert preview["commands"] == [["pytest", "-q", "tests"]]
        assert "normalize" in preview["issue"]
        client.json("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
        result = client.wait(run_id, "completed")["result"]
        assert result["outcome"] == "accepted"
        assert len(result["attempts"]) == 1
        assert result["attempts"][0]["outcome"] == "passed"
        assert "1 passed" in result["attempts"][0]["commands"][0]["stdout"]
        assert result["review_status"] == "accepted_after_repair"
        assert result["review"]["verdict"] == "request_changes"
        assert result["review"]["findings"][0]["symbol"] == "normalize"
        assert "2 passed" in result["review"]["repair"]["commands"][0]["stdout"]
        assert "tests/test_regression.py" in result["patch"]
        assert "+    assert normalize(' HELLO ') == 'hello'" in result["patch"]
        verify_manifest(Path(result["artifact_directory"]) / "issue-to-pr-manifest.json")
    finally:
        client.close()


@pytest.mark.parametrize("payload", [
    {"mode": "demo", "demo_case": "review_regression", "workflow": "fix"},
    {"mode": "demo", "demo_case": "unknown"},
])
def test_demo_selection_cannot_bypass_workflow_or_load_arbitrary_cases(tmp_path, payload):
    client = StudioClient(StudioService(StudioConfig(workspace=tmp_path / "runs")))
    try:
        assert client.request("POST", "/api/prepare", payload)[0] == 400
        assert not client.service.runs
        cases = client.json("GET", "/api/session")["demo_cases"]
        assert [case["id"] for case in cases] == ["clamp"]
    finally:
        client.close()
