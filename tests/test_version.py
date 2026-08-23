from __future__ import annotations

import subprocess
from pathlib import Path

import tomllib


def get_pyproject_version() -> str:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)

    version = pyproject_data.get("project", {}).get("version")
    assert version is not None, "Version not found in pyproject.toml"
    return str(version)


def test_pyproject_version_format() -> None:
    """Verify that pyproject.toml has a valid non-empty version string."""
    version = get_pyproject_version()
    assert version
    parts = version.split(".")
    assert len(parts) >= 2, f"Version '{version}' is not in semantic version format"


def test_pyproject_version_matches_latest_git_tag() -> None:
    """Verify pyproject.toml version matches the latest git tag if tags exist."""
    repo_root = Path(__file__).parent.parent
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # Git is not installed in the current environment
        return

    if result.returncode != 0 or not result.stdout.strip():
        # No git tags or not a git repository
        return

    latest_tag = result.stdout.strip()
    tag_version = latest_tag.lstrip("v")
    pyproject_version = get_pyproject_version()
    msg = (
        f"pyproject.toml version ({pyproject_version}) "
        f"does not match latest git tag ({latest_tag})"
    )
    assert pyproject_version == tag_version, msg
