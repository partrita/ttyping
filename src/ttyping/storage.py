"""Local JSON storage for typing results."""

from __future__ import annotations

import json
import os
import threading
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
_RESULTS_DATA_CACHE: list[dict[str, Any]] | None = None
_ERROR_STATS_CACHE: dict[str, int] | None = None

_STORAGE_LOCK = threading.RLock()


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


def _secure_write(file_path: Path, content: str) -> None:
    """Safely write content to a file, ensuring 0o600 permissions upon creation."""
    with _STORAGE_LOCK:
        # Security: Prevent TOCTOU symlink vulnerability
        if file_path.is_symlink():
            raise OSError(f"Refusing to write to symlink: {file_path}")

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        # Use os.open to atomically create file with 0o600 perms, or truncate if exists
        fd = os.open(
            file_path,
            flags,
            0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        # Ensure permissions are correct even if file already existed
        is_symlink = file_path.is_symlink()
        if not is_symlink and (file_path.stat().st_mode & 0o777) != 0o600:
            file_path.chmod(0o600)


def _ensure_storage() -> None:
    """Ensure storage directory and file exist with correct permissions."""
    global _STORAGE_ENSURED
    if _STORAGE_ENSURED:
        return

    # Security: Ensure storage directory and file have restricted permissions
    # 0o700 for directory (rwx------)
    # 0o600 for file (rw-------)

    # Use default permissions for intermediate directories, and explicitly
    # apply 0o700 to the storage directory after creation to avoid
    # unintentionally restricting shared parent directories.
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    if not STORAGE_DIR.is_symlink() and (STORAGE_DIR.stat().st_mode & 0o777) != 0o700:
        STORAGE_DIR.chmod(0o700)

    for file_path, default_content in [
        (RESULTS_FILE, "[]"),
        (CONFIG_FILE, "{}"),
    ]:
        if not file_path.exists():
            try:
                # Security: Prevent TOCTOU symlink vulnerability
                if file_path.is_symlink():
                    raise OSError(f"Refusing to write to symlink: {file_path}")

                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW

                # Use os.open to atomically create file with 0o600 permissions
                fd = os.open(file_path, flags, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(default_content)
            except FileExistsError:
                # File was created between the exists() check and os.open
                pass

        # Ensure permissions are correct even if file already existed
        is_symlink = file_path.is_symlink()
        if not is_symlink and (file_path.stat().st_mode & 0o777) != 0o600:
            file_path.chmod(0o600)

    _STORAGE_ENSURED = True


def save_result(result: TypingResult) -> None:
    """Append a result to the local storage."""
    global _RESULTS_CACHE, _RESULTS_DATA_CACHE, _ERROR_STATS_CACHE
    _ensure_storage()
    results = load_results()

    with _STORAGE_LOCK:
        if not result.date:
            result.date = datetime.now(timezone.utc).isoformat()
        results.append(result)

        # Update raw data cache incrementally to avoid O(N) dict conversion
        if _RESULTS_DATA_CACHE is None:
            _RESULTS_DATA_CACHE = [r.to_dict() for r in results]
        else:
            _RESULTS_DATA_CACHE.append(result.to_dict())

        # Update error stats cache incrementally
        if _ERROR_STATS_CACHE is not None:
            for char, count in result.top_char_errors:
                _ERROR_STATS_CACHE[char] = _ERROR_STATS_CACHE.get(char, 0) + count

        data_str = json.dumps(_RESULTS_DATA_CACHE, indent=2, ensure_ascii=False)
        threading.Thread(
            target=_secure_write,
            args=(RESULTS_FILE, data_str),
            daemon=True,
        ).start()


def load_results() -> list[TypingResult]:
    """Load all results from local storage."""
    global _RESULTS_CACHE, _RESULTS_DATA_CACHE
    with _STORAGE_LOCK:
        if _RESULTS_CACHE is not None:
            return _RESULTS_CACHE

        _ensure_storage()
        try:
            text = RESULTS_FILE.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, list):
                _RESULTS_CACHE = []
                _RESULTS_DATA_CACHE = []
                return _RESULTS_CACHE
            _RESULTS_DATA_CACHE = [r for r in data if isinstance(r, dict)]
            _RESULTS_CACHE = [TypingResult.from_dict(r) for r in _RESULTS_DATA_CACHE]
            return _RESULTS_CACHE
        except (json.JSONDecodeError, FileNotFoundError):
            _RESULTS_CACHE = []
            _RESULTS_DATA_CACHE = []
            return _RESULTS_CACHE


def clear_results() -> None:
    """Delete all stored typing results."""
    global _RESULTS_CACHE, _RESULTS_DATA_CACHE, _ERROR_STATS_CACHE
    _ensure_storage()
    with _STORAGE_LOCK:
        try:
            _secure_write(RESULTS_FILE, "[]")
            _RESULTS_CACHE = []
            _RESULTS_DATA_CACHE = []
            _ERROR_STATS_CACHE = {}
        except OSError:
            pass


def delete_result_by_index(index: int) -> None:
    """Delete a single result entry by its index in the stored list."""
    global _RESULTS_CACHE, _RESULTS_DATA_CACHE, _ERROR_STATS_CACHE
    results = load_results()
    with _STORAGE_LOCK:
        if 0 <= index < len(results):
            results.pop(index)
            if _RESULTS_DATA_CACHE is not None:
                _RESULTS_DATA_CACHE.pop(index)
            else:
                _RESULTS_DATA_CACHE = [r.to_dict() for r in results]

            # Invalidate error stats since we don't know which errors were removed
            # easily without re-aggregating or storing more state.
            _ERROR_STATS_CACHE = None

            _secure_write(
                RESULTS_FILE,
                json.dumps(_RESULTS_DATA_CACHE, indent=2, ensure_ascii=False),
            )
            _RESULTS_CACHE = results


def save_config(config: dict[str, Any]) -> None:
    """Save user configuration to local storage."""
    global _CONFIG_CACHE
    _ensure_storage()
    with _STORAGE_LOCK:
        _secure_write(CONFIG_FILE, json.dumps(config, indent=2, ensure_ascii=False))
        _CONFIG_CACHE = config


def load_config() -> dict[str, Any]:
    """Load user configuration from local storage."""
    global _CONFIG_CACHE
    with _STORAGE_LOCK:
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
    global _ERROR_STATS_CACHE
    with _STORAGE_LOCK:
        if _ERROR_STATS_CACHE is not None:
            return _ERROR_STATS_CACHE

        results = load_results()
        totals: dict[str, int] = {}
        for result in results:
            for char, count in result.top_char_errors:
                totals[char] = totals.get(char, 0) + count
        _ERROR_STATS_CACHE = totals
        return _ERROR_STATS_CACHE
