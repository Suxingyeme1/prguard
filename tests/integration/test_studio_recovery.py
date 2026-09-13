import pytest

from prguard.studio import StudioConfig, StudioService
from tests.integration.test_studio import StudioClient


@pytest.mark.integration
@pytest.mark.parametrize("failure,code", [
    ("missing", "repository_missing"),
    ("dirty", "repository_dirty"),
    ("version", "base_unresolved"),
    ("no_tests", "verification_missing"),
])
def test_preparation_failure_preserves_request_and_never_runs_models(
    make_repo, tmp_path, failure, code,
):
    repo, _ = make_repo({"app.py": "value = 1\n"})
    configured = tmp_path / "missing" if failure == "missing" else repo
    if failure == "dirty":
        (repo / "app.py").write_text("value = 2\n")
    client = StudioClient(StudioService(StudioConfig(
        workspace=tmp_path / "runs", repository=configured, trust_host=True,
    )))
    request = {"mode": "local", "issue": "Keep my request", "base_commit": (
        "no-such-version" if failure == "version" else "HEAD"
    ), "workflow": "fix", "demo_case": "clamp"}
    try:
        run_id = client.json("POST", "/api/prepare", request)["id"]
        failed = client.wait(run_id, "error")
        assert failed["guidance"] == {"code": code, "stage": "preparation"}
        assert failed["request"] == request
        assert failed["preview"] is None
        assert failed["result"] is None
        assert client.request("POST", f"/api/runs/{run_id}/start", {"confirmed": True})[0] == 409
        assert not (client.service.runs[run_id].root / "fix-runs").exists()
        if failure == "dirty":
            assert (repo / "app.py").read_text() == "value = 2\n"
    finally:
        client.close()


@pytest.mark.integration
def test_preview_explains_policy_source_and_warnings(make_repo, tmp_path):
    repo, _ = make_repo({
        "app.py": "value = 1\n", "tests/test_app.py": "def test_app():\n    assert True\n",
    })
    client = StudioClient(StudioService(StudioConfig(
        workspace=tmp_path / "runs", repository=repo, trust_host=True,
    )))
    try:
        run_id = client.json(
            "POST", "/api/prepare", {"mode": "local", "issue": "Fix behavior"}
        )["id"]
        preview = client.wait(run_id, "ready")["preview"]
        assert preview["policy_source"] == "deterministic_discovery"
        assert preview["policy_warnings"]
        assert not (client.service.runs[run_id].root / "fix-runs").exists()
    finally:
        client.close()
