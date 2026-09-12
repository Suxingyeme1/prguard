import hashlib
import http.client
import json
import threading
import time
from pathlib import Path

import pytest

from prguard.harness import verify_manifest
from prguard.studio import StudioConfig, StudioService, create_server
from tests.conftest import run_git


class StudioClient:
    def __init__(self, service: StudioService) -> None:
        self.service = service
        self.server = create_server(service, 0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.service.close()

    def request(self, method: str, path: str, payload=None, *, auth=True, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        request_headers = {"Content-Type": "application/json"}
        if auth:
            request_headers["Authorization"] = f"Bearer {self.service.token}"
        request_headers.update(headers or {})
        connection.request(
            method, path, body=json.dumps(payload) if payload is not None else None,
            headers=request_headers,
        )
        response = connection.getresponse()
        status, content = response.status, response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return status, content, response_headers

    def json(self, method: str, path: str, payload=None):
        status, content, _ = self.request(method, path, payload)
        assert status in {200, 202}, content
        return json.loads(content)

    def wait(self, run_id: str, target: str) -> dict:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            snapshot = self.json("GET", f"/api/runs/{run_id}")
            if snapshot["state"] == target:
                return snapshot
            assert snapshot["state"] != "error", snapshot
            time.sleep(0.05)
        pytest.fail(f"Studio never reached {target}")


@pytest.fixture
def studio(tmp_path: Path):
    client = StudioClient(StudioService(StudioConfig(workspace=tmp_path / "studio")))
    try:
        yield client
    finally:
        client.close()


@pytest.mark.integration
def test_browser_demo_runs_actual_failed_attempt_repair_and_verified_download(studio) -> None:
    session = studio.json("GET", "/api/session")
    assert session["repository"] is None
    assert session["latest_run_id"] is None
    run_id = studio.json("POST", "/api/prepare", {"mode": "demo"})["id"]
    ready = studio.wait(run_id, "ready")
    assert ready["preview"]["commands"] == [["pytest", "-q", "tests/test_clamp.py"]]
    assert ready["preview"]["provider"] == "scripted"
    assert ready["preview"]["max_repair_attempts"] == 1
    assert not any(event["event"] == "run.started" for event in ready["events"])
    assert not (studio.service.runs[run_id].root / "fix-runs").exists()
    assert studio.json("GET", "/api/session")["latest_run_id"] == run_id
    studio.json("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
    status, _, _ = studio.request("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
    assert status == 409
    completed = studio.wait(run_id, "completed")
    result = completed["result"]
    assert result["outcome"] == "accepted"
    assert result["review_status"] == "not_run"
    assert result["manifest_verified"] is True
    assert [attempt["outcome"] for attempt in result["attempts"]] == [
        "failed_verification", "passed",
    ]
    assert "3 passed" in result["attempts"][1]["commands"][0]["stdout"]
    assert "repair.requested" in [event["event"] for event in completed["events"]]
    events = completed["events"]
    assert [event["sequence"] for event in events] == list(range(len(events)))
    assert events[-1]["event"] == "delivery.completed"
    verify_manifest(Path(result["artifact_directory"]) / "fix-manifest.json")
    for artifact in result["artifacts"]:
        status, content, _ = studio.request(
            "GET", f"/api/runs/{run_id}/artifacts/{artifact['name']}"
        )
        assert status == 200
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
    assert "+    return max(lower, min(value, upper))" in result["patch"]
    # File mutation after delivery must fail integrity checks, not download altered evidence.
    (Path(result["artifact_directory"]) / "final.patch").write_text("changed")
    assert studio.request("GET", f"/api/runs/{run_id}/artifacts/final.patch")[0] == 409


@pytest.mark.integration
def test_configured_repo_uses_approved_commit_even_after_source_head_moves(
    make_repo, tmp_path: Path,
) -> None:
    repo, base = make_repo({
        "src/calc.py": "def add(left, right):\n    return left - right\n",
        "tests/test_calc.py": (
            "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        ),
        "pyproject.toml": "[tool.pytest.ini_options]\npythonpath = ['src']\n",
    })
    proposals = tmp_path / "proposals.json"
    proposals.write_text(json.dumps([{
        "plan": ["Correct add"], "summary": "Add both operands", "tests_changed": False,
        "edits": [{"operation": "replace_text", "path": "src/calc.py",
                   "old_text": "    return left - right\n",
                   "new_text": "    return left + right\n"}],
    }]))
    client = StudioClient(StudioService(StudioConfig(
        workspace=tmp_path / "studio", repository=repo, trust_host=True,
        provider="scripted", proposal_sequence=proposals,
    )))
    try:
        run_id = client.json("POST", "/api/prepare", {
            "mode": "local", "issue": "Fix add", "base_commit": "HEAD",
        })["id"]
        ready = client.wait(run_id, "ready")
        assert ready["preview"]["base_commit"] == base
        (repo / "notes.md").write_text("New source HEAD after approval preview\n")
        run_git(repo, "add", "notes.md")
        run_git(repo, "commit", "-m", "later source version")
        client.json("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
        result = client.wait(run_id, "completed")["result"]
        assert result["outcome"] == "accepted"
        assert result["base_commit"] == base
        assert (repo / "src/calc.py").read_text().endswith("return left - right\n")
        assert run_git(repo, "status", "--porcelain") == ""
    finally:
        client.close()


@pytest.mark.security
@pytest.mark.parametrize("path", ["/api/session", "/api/prepare"])
def test_local_api_requires_session_token(studio, path: str) -> None:
    method = "POST" if path.endswith("prepare") else "GET"
    status, body, _ = studio.request(method, path, {"mode": "demo"}, auth=False)
    assert status == 401
    assert studio.service.token.encode() not in body
    assert studio.service.runs == {}


@pytest.mark.security
@pytest.mark.parametrize("headers", [
    {"Origin": "https://attacker.example"},
    {"Origin": "null"},
    {"Host": "attacker.example"},
    {"Host": "127.0.0.1:1"},
])
def test_cross_origin_and_rebinding_requests_fail_before_preparation(studio, headers) -> None:
    assert studio.request("POST", "/api/prepare", {"mode": "demo"}, headers=headers)[0] == 403
    assert not studio.service.runs


@pytest.mark.security
@pytest.mark.parametrize("payload", [
    {"mode": "demo", "repository": "/etc"},
    {"mode": "demo", "commands": [["sh", "-c", "echo unsafe"]]},
    {"mode": "demo", "base_commit": "--help"},
    {"mode": "demo", "issue": "bad\x00issue"},
    {"mode": "local", "issue": "No repository configured"},
])
def test_request_cannot_expand_configured_authority(studio, payload) -> None:
    assert studio.request("POST", "/api/prepare", payload)[0] == 400
    assert not studio.service.runs


@pytest.mark.security
@pytest.mark.parametrize("confirmed", [False, 1, "true", None])
def test_approval_is_explicit(studio, confirmed) -> None:
    assert studio.request(
        "POST", f"/api/runs/{'a' * 32}/start", {"confirmed": confirmed}
    )[0] == 400


@pytest.mark.security
def test_static_server_has_exact_asset_allowlist_and_security_headers(studio) -> None:
    status, body, headers = studio.request("GET", "/", auth=False)
    assert status == 200
    assert b'id="app"' in body
    assert b"PRGuard Studio" in body
    assert studio.service.token.encode() not in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in headers
    for path in ("/.env", "/../pyproject.toml", "/%2e%2e/.env", "/data/", "/.openai/hosting.json"):
        assert studio.request("GET", path)[0] == 404
    assert studio.request("GET", "/live.js")[0] == 200


@pytest.mark.integration
def test_studio_frontend_separates_recorded_evidence_from_local_adapter(studio) -> None:
    _, locale_source, _ = studio.request("GET", "/i18n.js", auth=False)
    _, app_source, _ = studio.request("GET", "/app.js", auth=False)
    _, adapter_source, _ = studio.request("GET", "/live.js", auth=False)

    assert b"MutationObserver" not in locale_source
    assert b"PRGuardLocale" in locale_source
    assert b"Recorded runs" in locale_source
    assert b"renderExamples" in app_source
    assert b"renderLiveWorkspace" in app_source
    assert b"PRGuardLive" in adapter_source
    assert b"sessionStorage" in adapter_source


@pytest.mark.security
def test_task_tampering_prevents_execution(studio) -> None:
    run_id = studio.json("POST", "/api/prepare", {"mode": "demo"})["id"]
    studio.wait(run_id, "ready")
    root = studio.service.runs[run_id].root
    (root / "approved-task.json").write_text("{}")
    studio.json("POST", f"/api/runs/{run_id}/start", {"confirmed": True})
    snapshot = studio.wait(run_id, "error")
    assert "Prepared task changed" in snapshot["error"]
    assert not (root / "fix-runs").exists()


@pytest.mark.security
def test_symlink_artifact_cannot_read_outside_run(studio, tmp_path: Path) -> None:
    run_id = studio.json("POST", "/api/prepare", {"mode": "demo"})["id"]
    studio.wait(run_id, "ready")
    run = studio.service.runs[run_id]
    outside = tmp_path / "private.txt"
    outside.write_text("must stay private")
    link = run.root / "final.patch"
    link.symlink_to(outside)
    run.files["final.patch"] = (link, hashlib.sha256(outside.read_bytes()).hexdigest())
    status, content, _ = studio.request("GET", f"/api/runs/{run_id}/artifacts/final.patch")
    assert status == 403
    assert b"must stay private" not in content


def test_local_repo_requires_execution_boundary(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="trust-host"):
        StudioService(StudioConfig(workspace=tmp_path / "runs", repository=tmp_path / "repo"))
