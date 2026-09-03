import hashlib
import json
from pathlib import Path

from scripts.verify_public_evidence import verify_evidence

EVIDENCE = Path(__file__).resolve().parents[2] / "evidence" / "click-controlled-repair"


def _json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_click_controlled_repair_artifacts_are_hash_bound() -> None:
    assert verify_evidence(EVIDENCE) == 4


def test_repair_summary_binds_one_accepted_repair() -> None:
    summary = _json("repair-summary.json")
    repair = summary["repair"]
    verification = summary["verification"]

    assert repair["outcome"] == "accepted_after_repair"  # type: ignore[index]
    assert repair["attempts"] == 1  # type: ignore[index]
    assert repair["structured_edit_count"] == 4  # type: ignore[index]
    assert verification["full_suite"].startswith("1324 passed")  # type: ignore[index,union-attr]
    assert verification["changed_tests"] == "10 passed"  # type: ignore[index]


def test_final_patch_and_hidden_evaluator_confirm_extension_repair() -> None:
    summary = _json("repair-summary.json")
    evaluator = _json("evaluator-check.json")
    patch = (EVIDENCE / "final.patch").read_bytes()

    assert hashlib.sha256(patch).hexdigest() == summary["final_patch_sha256"]
    assert evaluator["agent_visible"] is False
    assert evaluator["candidate"]["extension_point_honored"] is False  # type: ignore[index]
    assert evaluator["repaired"]["extension_point_honored"] is True  # type: ignore[index]
    assert evaluator["repair_confirmed"] is True
    assert b"ctx.lookup_default" in patch
    assert b"test_lookup_default_override_is_used_for_parameter_default" in patch
