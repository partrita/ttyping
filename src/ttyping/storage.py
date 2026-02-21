"""Local JSON storage for typing results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORAGE_DIR = Path.home() / ".ttyping"
RESULTS_FILE = STORAGE_DIR / "results.json"


def _ensure_storage() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text("[]", encoding="utf-8")


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
