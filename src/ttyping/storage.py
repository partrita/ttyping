"""Local JSON storage for typing results."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORAGE_DIR = Path.home() / ".ttyping"
RESULTS_FILE = STORAGE_DIR / "results.json"
CONFIG_FILE = STORAGE_DIR / "config.json"

_STORAGE_ENSURED: bool = False
_CONFIG_CACHE: dict[str, Any] | None = None
_RESULTS_CACHE: list[TypingResult] | None = None


@dataclass
class TypingResult:
    """A single typing test result."""

    wpm: float
    accuracy: float
    time: float
    lang: str
    words: int
    correct: int
    keystrokes: int
    errors: int
    gross_wpm: float = 0.0
    top_char_errors: list[tuple[str, int]] = field(default_factory=list)
    date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TypingResult:
        """Create a result from a dictionary."""
        # Handle cases where some fields might be missing in older results
        return cls(
            wpm=float(data.get("wpm", 0)),
            accuracy=float(data.get("accuracy", 0)),
            time=float(data.get("time", 0)),
            lang=str(data.get("lang", "en")),
            words=int(data.get("words", 0)),
            correct=int(data.get("correct", 0)),
            keystrokes=int(data.get("keystrokes", 0)),
            errors=int(data.get("errors", 0)),
            gross_wpm=float(data.get("gross_wpm", 0)),
            top_char_errors=data.get("top_char_errors", []),
            date=data.get("date"),
        )


def _ensure_storage() -> None:
    """Ensure storage directory and file exist with correct permissions."""
    global _STORAGE_ENSURED
    if _STORAGE_ENSURED:
        return

    # Security: Ensure storage directory and file have restricted permissions
    # 0o700 for directory (rwx------)
    # 0o600 for file (rw-------)
    STORAGE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (STORAGE_DIR.stat().st_mode & 0o777) != 0o700:
        STORAGE_DIR.chmod(0o700)

    for file_path, default_content in [
        (RESULTS_FILE, "[]"),
        (CONFIG_FILE, "{}"),
    ]:
        if not file_path.exists():
            try:
                # Use os.open to atomically create file with 0o600 permissions
                fd = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(default_content)
            except FileExistsError:
                # File was created between the exists() check and os.open
                pass

        # Ensure permissions are correct even if file already existed
        if (file_path.stat().st_mode & 0o777) != 0o600:
            file_path.chmod(0o600)

    _STORAGE_ENSURED = True


def save_result(result: TypingResult) -> None:
    """Append a result to the local storage."""
    global _RESULTS_CACHE
    _ensure_storage()
    results = load_results()
    if not result.date:
        result.date = datetime.now(timezone.utc).isoformat()
    results.append(result)

    data = [r.to_dict() for r in results]
    RESULTS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_results() -> list[TypingResult]:
    """Load all results from local storage."""
    global _RESULTS_CACHE
    if _RESULTS_CACHE is not None:
        return _RESULTS_CACHE

    _ensure_storage()
    try:
        text = RESULTS_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, list):
            _RESULTS_CACHE = []
            return _RESULTS_CACHE
        _RESULTS_CACHE = [
            TypingResult.from_dict(r) for r in data if isinstance(r, dict)
        ]
        return _RESULTS_CACHE
    except (json.JSONDecodeError, FileNotFoundError):
        _RESULTS_CACHE = []
        return _RESULTS_CACHE


def clear_results() -> None:
    """Delete all stored typing results."""
    global _RESULTS_CACHE
    _ensure_storage()
    try:
        RESULTS_FILE.write_text("[]", encoding="utf-8")
        _RESULTS_CACHE = []
    except OSError:
        pass


def delete_result_by_index(index: int) -> None:
    """Delete a single result entry by its index in the stored list."""
    global _RESULTS_CACHE
    results = load_results()
    if 0 <= index < len(results):
        results.pop(index)
        data = [r.to_dict() for r in results]
        RESULTS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        _RESULTS_CACHE = results


def save_config(config: dict[str, Any]) -> None:
    """Save user configuration to local storage."""
    global _CONFIG_CACHE
    _ensure_storage()
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _CONFIG_CACHE = config


def load_config() -> dict[str, Any]:
    """Load user configuration from local storage."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    _ensure_storage()
    try:
        text = CONFIG_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            _CONFIG_CACHE = {}
            return {}
        _CONFIG_CACHE = data
        return _CONFIG_CACHE
    except (json.JSONDecodeError, FileNotFoundError):
        _CONFIG_CACHE = {}
        return {}


def load_error_stats() -> dict[str, int]:
    """Aggregate cumulative character error counts from all saved results.

    Returns a dict mapping char -> total error count across all sessions.
    """
    results = load_results()
    totals: dict[str, int] = {}
    for result in results:
        for char, count in result.top_char_errors:
            totals[char] = totals.get(char, 0) + count
    return totals
