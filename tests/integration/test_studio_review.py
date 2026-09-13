"""Browser API integration with the same real Git and review workflow as the CLI."""

import hashlib
import json
from pathlib import Path

import pytest

from prguard.harness import verify_manifest
from prguard.implementer.errors import ProviderError
from prguard.studio import StudioConfig, StudioService
from tests.conftest import run_git
from tests.integration.test_studio import StudioClient


@pytest.mark.integration
def test_studio_reviews_repairs_and_freezes_external_scripted_inputs(make_repo, tmp_path):
    original = "def normalize(value):\n    return value.strip().lower()\n"
    repo, base = make_repo({
        "src/service.py": original,
        "tests/test_service.py": (
            "from service import normalize\n\ndef test_none():\n"
            "    assert normalize(None) == ''\n"
        ),
        "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['src']\n",
    })
    initial = tmp_path / "initial.json"
    repair = tmp_path / "repair.json"
    review = tmp_path / "review.json"
    initial.write_text(json.dumps([{
        "plan": ["Handle None"], "summary": "Handle missing input", "tests_changed": False,
        "edits": [{"operation": "replace_text", "path": "src/service.py",
                   "old_text": "    return value.strip().lower()\n",
                   "new_text": (
                       "    if value is None:\n        return ''\n    return value.strip()\n"
                   )}],
    }]))
    repair.write_text(json.dumps([{
        "plan": ["Restore normalization"], "summary": "Keep lowercase normalization",
        "tests_changed": False,
        "edits": [{"operation": "replace_text", "path": "src/service.py",
                   "old_text": "    return value.strip()\n",
                   "new_text": "    return value.strip().lower()\n"}],
    }]))
    review.write_text(json.dumps({
        "summary": "The candidate loses established lowercase behavior.",
        "findings": [{
            "severity": "P2", "category": "regression", "file": "src/service.py",
            "line": 4, "symbol": "normalize", "claim": "Lowercase normalization was removed.",
            "evidence": "The original return used lower(); the candidate only strips whitespace.",
            "verification": "normalize(' HELLO ') must return 'hello'.", "confidence": 0.99,
        }],
    }))
    client = StudioClient(StudioService(StudioConfig(
        workspace=tmp_path / "studio", repository=repo, trust_host=True,
        provider="scripted", proposal_sequence=initial,
        enable_independent_review=True, review_provider="scripted",
        review_submission=review, review_repair_proposal_sequence=repair,
    )))
    try:
        run_id = client.json("POST", "/api/prepare", {
            "mode": "local", "workflow": "reviewed_fix",
            "issue": "Accept None as empty while preserving normalization.",
        })["id"]
        ready = client.wait(run_id, "ready")
        assert ready["preview"]["base_commit"] == base
        # Mutating external provider fixtures cannot replace an already approved contract.
        for path in (initial, repair, review):
            path.write_text("this must never be loaded during execution")
        client.json("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
        result = client.wait(run_id, "completed")["result"]
        assert result["outcome"] == "accepted"
        assert result["review_status"] == "accepted_after_repair"
        assert result["review"]["verdict"] == "request_changes"
        assert result["review"]["findings"][0]["file"] == "src/service.py"
        assert result["review"]["repair"]["verification_outcome"] == "passed"
        assert result["review"]["repair"]["commands"][0]["passed"]
        assert result["review"]["verification"]["commands"][0]["passed"]
        assert "return value.strip().lower()" in result["patch"]
        assert (repo / "src/service.py").read_text() == original
        assert run_git(repo, "status", "--porcelain") == ""
        manifest = verify_manifest(Path(result["artifact_directory"]) / "issue-to-pr-manifest.json")
        assert any(entry.path.endswith("review-report.json") for entry in manifest.artifacts)
        for artifact in result["artifacts"]:
            status, payload, _ = client.request(
                "GET", f"/api/runs/{run_id}/artifacts/{artifact['name']}"
            )
            assert status == 200
            assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
        # No arbitrary nested evidence paths become HTTP download capabilities.
        assert client.request("GET", f"/api/runs/{run_id}/artifacts/approved-task.json")[0] == 404
    finally:
        client.close()


@pytest.mark.integration
def test_studio_reviewer_failure_does_not_deliver_the_initial_green_patch(tmp_path, monkeypatch):
    def unavailable(_spec):
        raise ProviderError("Reviewer service unavailable")

    monkeypatch.setattr(StudioService, "_reviewer", staticmethod(unavailable))
    client = StudioClient(StudioService(StudioConfig(
        workspace=tmp_path / "studio", enable_independent_review=True,
    )))
    try:
        run_id = client.json("POST", "/api/prepare", {
            "mode": "demo", "workflow": "reviewed_fix",
        })["id"]
        client.wait(run_id, "ready")
        client.json("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
        result = client.wait(run_id, "completed")["result"]
        assert result["attempts"][-1]["outcome"] == "passed"
        assert result["outcome"] == "review_failed"
        assert result["review_status"] == "failed"
        assert result["patch"] == ""
        assert result["manifest_verified"]
        assert "final.patch" not in {file["name"] for file in result["artifacts"]}
        assert client.request("GET", f"/api/runs/{run_id}/artifacts/final.patch")[0] == 404
    finally:
        client.close()


@pytest.mark.security
def test_history_is_authenticated_session_scoped_and_read_only(tmp_path):
    client = StudioClient(StudioService(StudioConfig(workspace=tmp_path / "studio")))
    try:
        assert client.request("GET", "/api/runs", auth=False)[0] == 401
        assert client.request(
            "GET", "/api/runs", headers={"Origin": "https://example.com"}
        )[0] == 403
        first = client.json("POST", "/api/prepare", {"mode": "demo"})["id"]
        client.wait(first, "ready")
        second = client.json("POST", "/api/prepare", {"mode": "demo"})["id"]
        client.wait(second, "ready")
        history = client.json("GET", "/api/runs")
        assert [run["id"] for run in history["runs"]] == [second, first]
        assert history["current_run_id"] == second
        assert history["active_run_id"] is None
        assert history["runs"][0]["state"] == "ready"
        assert not history["runs"][0]["manifest_verified"]
        assert str(client.service.root) not in json.dumps(history)
        assert client.service.runs[first].state == "ready"
        assert client.request("POST", "/api/runs", {"mode": "demo"})[0] == 404
    finally:
        client.close()
