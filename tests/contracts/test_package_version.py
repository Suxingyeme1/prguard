import tomllib
from pathlib import Path

import prguard


def test_runtime_version_matches_project_metadata() -> None:
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    metadata = tomllib.loads(project.read_text(encoding="utf-8"))

    assert prguard.__version__ == metadata["project"]["version"]
