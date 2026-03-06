"""Local JSON storage for typing results."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORAGE_DIR = Path.home() / ".ttyping"
RESULTS_FILE = STORAGE_DIR / "results.json"
CONFIG_FILE = STORAGE_DIR / "config.json"

_STORAGE_ENSURED = False


def _ensure_storage() -> None:
    """Ensure storage directory and file exist with correct permissions."""
    global _STORAGE_ENSURED
    if _STORAGE_ENSURED:
        return

    # Security: Ensure storage directory and file have restricted permissions
    # 0o700 for directory (rwx------)
    # 0o600 for file (rw-------)
    # We use umask and atomic creation to prevent TOCTOU race conditions.
    old_umask = os.umask(0o077)
    try:
        # Create directory with restricted permissions from the start
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if (STORAGE_DIR.stat().st_mode & 0o777) != 0o700:
            STORAGE_DIR.chmod(0o700)
    finally:
        os.umask(old_umask)

    for file_path, default_content in [
        (RESULTS_FILE, "[]"),
        (CONFIG_FILE, "{}"),
    ]:
        if not file_path.exists():
            file_path.touch(mode=0o600)
            file_path.write_text(default_content, encoding="utf-8")
        elif (file_path.stat().st_mode & 0o777) != 0o600:
            file_path.chmod(0o600)

    _STORAGE_ENSURED = True


def save_result(result: dict[str, Any]) -> None:
    """Append a result to the local storage."""
    _ensure_storage()
    results: list[dict[str, Any]] = load_results()
    result["date"] = datetime.now(timezone.utc).isoformat()
    results.append(result)
    RESULTS_FILE.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_results() -> list[dict[str, Any]]:
    """Load all results from local storage."""
    _ensure_storage()
    text = RESULTS_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        return data
    except json.JSONDecodeError:
        return []


def save_config(config: dict[str, Any]) -> None:
    """Save user configuration to local storage."""
    _ensure_storage()
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_config() -> dict[str, Any]:
    """Load user configuration from local storage."""
    _ensure_storage()
    text = CONFIG_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        return data
    except json.JSONDecodeError:
        return {}
