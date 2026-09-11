"""Loopback-only browser adapter for the existing preparation and Fix pipeline."""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import platform
import re
import secrets
import stat
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field, ValidationError, field_validator

from prguard.demo import _demo_proposals, prepare_demo_task
from prguard.fix import FixRunner
from prguard.harness import verify_manifest
from prguard.harness.artifacts import canonical_json, sha256_bytes
from prguard.implementer.providers import (
    DeepSeekChatProvider,
    OpenAIResponsesProvider,
    ScriptedProvider,
)
from prguard.onboarding import prepare_local_issue
from prguard.schemas import FixReport, FixTask
from prguard.schemas.common import StrictModel

MAX_BODY = 60_000
MAX_ARTIFACT = 10_000_000
ASSETS = ("index.html", "styles.css", "app.js", "i18n.js", "live.js", "data/cases.js")


class StudioError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class PrepareRequest(StrictModel):
    mode: Literal["demo", "local"] = "demo"
    issue: str = Field(default="", max_length=50_000)
    base_commit: str = Field(default="HEAD", min_length=1, max_length=128)

    @field_validator("issue", "base_commit")
    @classmethod
    def no_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("unsupported control character")
        return value.strip()

    @field_validator("base_commit")
    @classmethod
    def safe_ref(cls, value: str) -> str:
        if not value or value.startswith("-") or any(char.isspace() for char in value):
            raise ValueError("invalid Git version")
        return value


class ApprovalRequest(StrictModel):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("explicit confirmation is required")
        return value


@dataclass(frozen=True)
class StudioConfig:
    workspace: Path
    repository: Path | None = None
    trust_host: bool = False
    container_image: str | None = None
    policy_file: Path | None = None
    provider: Literal["deepseek", "openai", "scripted"] = "deepseek"
    model: str | None = None
    proposal_sequence: Path | None = None

    def validate(self) -> None:
        if self.repository is not None:
            if self.trust_host == bool(self.container_image):
                raise StudioError("select --trust-host or --container-image for the repository")
            source = self.repository.expanduser().resolve()
            if self.workspace.expanduser().resolve().is_relative_to(source):
                raise StudioError("Studio workspace must be outside the source repository")
            if self.provider == "scripted" and self.proposal_sequence is None:
                raise StudioError("scripted repository mode requires --proposal-sequence")


@dataclass
class _Run:
    id: str
    mode: str
    root: Path
    state: str = "preparing"
    created: float = field(default_factory=time.monotonic)
    events: list[dict] = field(default_factory=list)
    preview: dict | None = None
    task: bytes | None = None
    task_hash: str | None = None
    result: dict | None = None
    error: str | None = None
    files: dict[str, tuple[Path, str]] = field(default_factory=dict)


class StudioService:
    """One worker; immutable Task approval; bounded, run-scoped artifact reads."""

    def __init__(self, config: StudioConfig) -> None:
        config.validate()
        self.config = config
        self.root = config.workspace.expanduser().resolve() / f"session-{uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prguard-studio")
        self.runs: dict[str, _Run] = {}
        self.current_run_id: str | None = None
        self.closed = False
        self.sensitive = [
            value for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY")
            if (value := os.environ.get(name))
        ]
        self.sensitive.append(self.token)

    def close(self) -> None:
        with self.lock:
            self.closed = True
        # Running verification owns its deadlines and must finish writing its artifacts.
        self.worker.shutdown(wait=True)

    def _safe_text(self, text: str) -> str:
        for value in self.sensitive:
            text = text.replace(value, "[redacted]")
        return text

    def session(self) -> dict:
        with self.lock:
            return {
                "mode": "local-adapter",
                "repository": str(self.config.repository) if self.config.repository else None,
                "provider": self.config.provider if self.config.repository else "scripted",
                "boundary": "container" if self.config.container_image else "host",
                "runtime": f"{platform.python_implementation()} {platform.python_version()}",
                "demo_issue": "clamp() must enforce both lower and upper bounds.",
                "latest_run_id": self.current_run_id,
            }

    def _available(self) -> None:
        if self.closed:
            raise StudioError("Studio is shutting down", 503)
        if any(run.state in {"preparing", "running"} for run in self.runs.values()):
            raise StudioError("A task is already running", 409)

    def prepare(self, request: PrepareRequest) -> str:
        with self.lock:
            self._available()
            if len(self.runs) >= 50:
                raise StudioError("Session limit reached; restart Studio for more tasks", 429)
            if request.mode == "local" and (not self.config.repository or not request.issue):
                raise StudioError("Local mode requires a configured repository and an Issue")
            run_id = uuid4().hex
            run = _Run(run_id, request.mode, self.root / run_id)
            self.runs[run_id] = run
            self.current_run_id = run_id
            self.worker.submit(self._prepare, run, request)
            return run_id

    def _event(self, run: _Run, name: str, data: dict) -> None:
        with self.lock:
            if len(run.events) < 500:
                run.events.append({
                    "sequence": len(run.events), "event": name,
                    "elapsed": round(time.monotonic() - run.created, 2), "data": data,
                })

    def _prepare(self, run: _Run, request: PrepareRequest) -> None:
        try:
            self._event(run, "preparation.started", {})
            if request.mode == "demo":
                run.root.mkdir(mode=0o700)
                task = prepare_demo_task(run.root)
            else:
                preparation = prepare_local_issue(
                    self.config.repository, request.issue, run.root,
                    base_commit=request.base_commit,
                    trust_host=self.config.trust_host,
                    container_image=self.config.container_image,
                    policy_file=self.config.policy_file,
                )
                verify_manifest(run.root / "artifacts" / "preparation-manifest.json")
                task = FixTask.model_validate_json(preparation.task_path.read_bytes())
            payload = canonical_json(task.model_dump(mode="json"))
            (run.root / "approved-task.json").write_bytes(payload)
            with self.lock:
                run.task = payload
                run.task_hash = sha256_bytes(payload)
                run.preview = {
                    "issue": task.issue, "base_commit": task.base_commit,
                    "repository": str(self.config.repository or task.repository),
                    "commands": [command.argv for command in task.commands],
                    "writable_paths": task.writable_paths,
                    "protected_paths": task.protected_paths,
                    "boundary": "container" if task.container else "host",
                    "provider": "scripted" if run.mode == "demo" else self.config.provider,
                    "task_sha256": run.task_hash,
                    "task_timeout_seconds": task.task_timeout_seconds,
                    "max_repair_attempts": task.max_repair_attempts,
                }
                self._event(run, "preparation.completed", {"base_commit": task.base_commit})
                run.state = "ready"
        except Exception as exc:
            self._fail(run, exc)

    def approve(self, run_id: str) -> None:
        with self.lock:
            self._available()
            run = self._get(run_id)
            if run.state != "ready":
                raise StudioError("Only a prepared task can be started once", 409)
            if time.monotonic() - run.created > 1800:
                raise StudioError("Task preview expired; prepare a new task", 409)
            run.state = "running"
            self.current_run_id = run_id
            self.worker.submit(self._execute, run)

    def _provider(self, mode: str):
        if mode == "demo":
            return ScriptedProvider(_demo_proposals())
        if self.config.provider == "scripted":
            return ScriptedProvider.from_file(self.config.proposal_sequence)
        if self.config.provider == "deepseek":
            return DeepSeekChatProvider(
                model=self.config.model or DeepSeekChatProvider.default_model,
            )
        return OpenAIResponsesProvider(model=self.config.model or "gpt-5.6-terra")

    def _execute(self, run: _Run) -> None:
        try:
            if self._read_regular(run.root / "approved-task.json", run.root) != run.task:
                raise StudioError("Prepared task changed; prepare it again", 409)
            task = FixTask.model_validate_json(run.task)
            report = FixRunner(
                run.root / "fix-runs", self._provider(run.mode),
                progress=lambda name, data: self._event(run, name, data),
            ).run(task)
            manifest_path = report.artifact_directory / "fix-manifest.json"
            verify_manifest(manifest_path)
            result = self._result(report)
            files = {}
            for name in ("fix-report.json", "fix-report.md", "fix-manifest.json", "final.patch"):
                path = report.artifact_directory / name
                if not path.exists():
                    continue
                payload = self._read_regular(path, run.root)
                # Downloaded evidence is either byte-exact or blocked, never silently rewritten.
                if self._safe_text(payload.decode("utf-8")) != payload.decode("utf-8"):
                    continue
                files[name] = (path, sha256_bytes(payload))
            result["artifacts"] = [
                {"name": name, "sha256": digest} for name, (_, digest) in files.items()
            ]
            result["manifest_verified"] = True
            self._event(run, "delivery.completed", {"outcome": report.outcome.value})
            (run.root / "studio-events.json").write_bytes(canonical_json(run.events))
            with self.lock:
                run.files = files
                run.result = result
                run.state = "completed"
        except Exception as exc:
            self._fail(run, exc)

    def _result(self, report: FixReport) -> dict:
        attempts = []
        for attempt in report.attempts:
            verification = attempt.verification
            attempts.append({
                "attempt": attempt.attempt + 1,
                "summary": attempt.proposal.proposal.summary if attempt.proposal else None,
                "plan": attempt.proposal.proposal.plan if attempt.proposal else [],
                "error": attempt.error,
                "outcome": verification.outcome.value if verification else "not_run",
                "commands": [{
                    "argv": command.argv, "passed": command.passed,
                    "exit_code": command.exit_code, "timed_out": command.timed_out,
                    "stdout": command.stdout[-6000:], "stderr": command.stderr[-2000:],
                    "duration_seconds": command.duration_seconds,
                } for command in verification.commands] if verification else [],
            })
        patch = ""
        if report.final_patch:
            patch = self._read_regular(
                report.final_patch, report.artifact_directory
            ).decode("utf-8")
        return {
            "outcome": report.outcome.value, "attempts": attempts,
            "base_commit": report.resolved_base_commit, "patch": patch,
            "duration_seconds": report.duration_seconds,
            "token_usage": report.token_usage.model_dump(mode="json"),
            "artifact_directory": str(report.artifact_directory),
            "review_status": "not_run",
        }

    def _fail(self, run: _Run, exc: Exception) -> None:
        with self.lock:
            run.error = self._safe_text(f"{type(exc).__name__}: {exc}")[:1500]
            run.state = "error"
            self._event(run, "adapter.failed", {"error": run.error})

    def _get(self, run_id: str) -> _Run:
        if run_id not in self.runs:
            raise StudioError("Run not found", 404)
        return self.runs[run_id]

    def snapshot(self, run_id: str) -> dict:
        with self.lock:
            run = self._get(run_id)
            payload = json.dumps({
                "id": run.id, "mode": run.mode, "state": run.state,
                "preview": run.preview, "events": run.events,
                "result": run.result, "error": run.error,
            }, ensure_ascii=False)
            return json.loads(self._safe_text(payload))

    @staticmethod
    def _read_regular(path: Path, root: Path) -> bytes:
        if not path.resolve().is_relative_to(root.resolve()):
            raise StudioError("Artifact is outside this run", 403)
        relative = path.relative_to(root)
        if any((root / Path(*relative.parts[:index])).is_symlink()
               for index in range(1, len(relative.parts) + 1)):
            raise StudioError("Symlink artifacts are unavailable", 403)
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        )
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT:
                raise StudioError("Artifact must be a bounded regular file", 403)
            payload = source.read(MAX_ARTIFACT + 1)
            if len(payload) > MAX_ARTIFACT:
                raise StudioError("Artifact exceeds download limit", 403)
            return payload

    def artifact(self, run_id: str, name: str) -> bytes:
        with self.lock:
            run = self._get(run_id)
            if name not in run.files:
                raise StudioError("Artifact is not available for download", 404)
            path, digest = run.files[name]
            payload = self._read_regular(path, run.root)
            if sha256_bytes(payload) != digest:
                raise StudioError("Artifact integrity check failed", 409)
            return payload


def load_assets() -> dict[str, bytes]:
    source = Path(__file__).resolve().parents[2] / "demo-ui" / "dist"
    if not (source / "index.html").is_file():
        source = Path(__file__).parent / "studio_assets"
    return {"/" if name == "index.html" else f"/{name}": (source / name).read_bytes()
            for name in ASSETS}


def create_server(service: StudioService, port: int = 0) -> ThreadingHTTPServer:
    assets = load_assets()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *args) -> None:
            pass  # Do not persist authentication or request bodies in access logs.

        def _check(self) -> None:
            self.connection.settimeout(10)
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get_all("Host") != [expected]:
                raise StudioError("Unexpected Host", 403)
            origin = self.headers.get_all("Origin")
            if origin is not None and origin != [f"http://{expected}"]:
                raise StudioError("Cross-origin requests are not allowed", 403)
            if self.path.startswith("/api/"):
                provided = self.headers.get_all("Authorization")
                if provided is None or len(provided) != 1 or not hmac.compare_digest(
                    provided[0].encode(), f"Bearer {service.token}".encode()
                ):
                    raise StudioError("Open the local Studio URL printed in your terminal", 401)

        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            ))
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, status: int, value: dict) -> None:
            self._send(status, canonical_json(value), "application/json; charset=utf-8")

        def _dispatch(self, post: bool) -> None:
            try:
                self._check()
                if post:
                    self._post()
                elif self.path in assets:
                    content_type = mimetypes.guess_type(self.path)[0] or "text/html"
                    self._send(200, assets[self.path], f"{content_type}; charset=utf-8")
                elif self.path == "/api/session":
                    self._json(200, service.session())
                elif match := re.fullmatch(r"/api/runs/([0-9a-f]{32})", self.path):
                    self._json(200, service.snapshot(match[1]))
                elif match := re.fullmatch(
                    r"/api/runs/([0-9a-f]{32})/artifacts/([a-z.-]+)", self.path
                ):
                    self._send(200, service.artifact(match[1], match[2]),
                               "application/octet-stream")
                else:
                    raise StudioError("Not found", 404)
            except StudioError as exc:
                self._json(exc.status, {"error": str(exc)})
            except (ValidationError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                self._json(400, {"error": "Invalid request; check Issue and version fields"})
            except FileNotFoundError:
                self._json(404, {"error": "Artifact is no longer available"})
            except (OSError, TimeoutError):
                self.close_connection = True

        def _post(self) -> None:
            if self.headers.get_content_type() != "application/json":
                raise StudioError("JSON request required", 415)
            if self.headers.get("Transfer-Encoding"):
                raise StudioError("Transfer encoding is not supported")
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or not lengths[0].isdecimal():
                raise StudioError("Content-Length is required", 411)
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise StudioError("Request exceeds size limit", 413)
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise StudioError("Incomplete request")
            if self.path == "/api/prepare":
                request = PrepareRequest.model_validate_json(payload)
                self._json(202, {"id": service.prepare(request)})
            elif match := re.fullmatch(r"/api/runs/([0-9a-f]{32})/start", self.path):
                ApprovalRequest.model_validate_json(payload)
                service.approve(match[1])
                self._json(202, {"id": match[1]})
            else:
                raise StudioError("Not found", 404)

        def do_GET(self) -> None:
            self._dispatch(False)

        def do_POST(self) -> None:
            self._dispatch(True)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def run_studio(config: StudioConfig, *, port: int = 4318, open_browser: bool = True) -> None:
    service = StudioService(config)
    try:
        server = create_server(service, port)
        url = f"http://127.0.0.1:{server.server_port}/#token={service.token}"
        print(f"PRGuard Studio: {url}", flush=True)
        print("Ctrl+C closes Studio after any active task finishes its verification.", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Waiting for any active verification to finish…", flush=True)
        finally:
            server.server_close()
    finally:
        service.close()
