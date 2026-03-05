"""Local JSON storage for typing results."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORAGE_DIR = Path.home() / ".ttyping"
RESULTS_FILE = STORAGE_DIR / "results.json"

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

        if not RESULTS_FILE.exists():
            try:
                # Atomic creation with O_EXCL to prevent race conditions
                fd = os.open(RESULTS_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write("[]")
            except FileExistsError:
                # File was created between the check and os.open, which is fine
                pass

        # Ensure permissions even if file already existed
        if (RESULTS_FILE.stat().st_mode & 0o777) != 0o600:
            RESULTS_FILE.chmod(0o600)
    finally:
        os.umask(old_umask)

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
        return json.loads(text)
    except json.JSONDecodeError:
        return []
