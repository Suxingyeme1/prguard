from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

import prguard.schemas
from prguard.evaluation import load_shadow_evaluation

pytestmark = pytest.mark.security


def _evidence_root() -> Path:
    return Path(__file__).resolve().parents[2] / "evidence"


def _copy_evidence(tmp_path: Path) -> Path:
    target = tmp_path / "evidence"
    shutil.copytree(_evidence_root(), target)
    return target


def test_evaluator_labels_are_not_exported_as_agent_task_contracts() -> None:
    assert not hasattr(prguard.schemas, "EvaluatorLabel")
    assert "evaluator_label" not in prguard.schemas.FixTask.model_fields
    assert "evaluator_label" not in prguard.schemas.ReviewTask.model_fields


def test_scorecard_rejects_artifact_path_traversal() -> None:
    with pytest.raises(ValueError, match="unsafe evaluator artifact path"):
        load_shadow_evaluation(_evidence_root(), "../shadow-scorecard/cases.json")


def test_scorecard_rejects_tampered_routing_artifact(tmp_path: Path) -> None:
    root = _copy_evidence(tmp_path)
    route = root / "selective-routing" / "prettytable-routing.json"
    route.write_text(route.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_shadow_evaluation(root, "shadow-scorecard/cases.json")


def test_scorecard_rejects_cross_patch_reviewer_join(tmp_path: Path) -> None:
    root = _copy_evidence(tmp_path)
    reviewer_manifest = root / "reviewer-value" / "manifest.json"
    reviewer_payload = json.loads(reviewer_manifest.read_text(encoding="utf-8"))
    reviewer_payload["cases"][0]["candidate_patch_sha256"] = "0" * 64
    reviewer_manifest.write_text(
        json.dumps(reviewer_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    reviewer_hash = hashlib.sha256(reviewer_manifest.read_bytes()).hexdigest()

    dataset_path = root / "shadow-scorecard" / "cases.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    dataset["cases"][2]["reviewer_evidence"]["artifact_sha256"] = reviewer_hash
    dataset_path.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Reviewer and routing candidate Patch do not match"):
        load_shadow_evaluation(root, "shadow-scorecard/cases.json")
