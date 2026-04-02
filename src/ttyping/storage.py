"""Local JSON storage for typing results."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from stat import S_ISREG
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
    char_timings: list[dict[str, Any]] = field(default_factory=list)
    text: str = ""
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
            char_timings=data.get("char_timings", []),
            text=str(data.get("text", "")),
            date=data.get("date"),
        )


def _fchmod_safe(file_path: Path, mode: int = 0o600) -> None:
    """Use file descriptors to safely set permissions, preventing TOCTOU attacks."""
    if hasattr(os, "fchmod") and hasattr(os, "fstat"):
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(file_path, flags)
            if getattr(os, "O_NONBLOCK", 0):
                os.set_blocking(fd, True)
            try:
                st = os.fstat(fd)
                if (st.st_mode & 0o777) != mode:
                    os.fchmod(fd, mode)
                return
            finally:
                os.close(fd)
        except OSError:
            # File deleted, or symlink blocked by O_NOFOLLOW
            return

    # Fallback for platforms without fchmod/fstat (e.g. Windows)
    is_symlink = file_path.is_symlink()
    if not is_symlink and (file_path.stat().st_mode & 0o777) != mode:
        file_path.chmod(mode)


def _secure_append(file_path: Path, content: str) -> None:
    """Safely append content to a file, ensuring 0o600 permissions upon creation."""
    if file_path.is_symlink():
        raise OSError(f"Refusing to write to symlink: {file_path}")

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd = os.open(file_path, flags, 0o600)
    try:
        if getattr(os, "O_NONBLOCK", 0):
            os.set_blocking(fd, True)
        if hasattr(os, "fchmod") and hasattr(os, "fstat"):
            st = os.fstat(fd)
            if (st.st_mode & 0o777) != 0o600:
                os.fchmod(fd, 0o600)
        f = os.fdopen(fd, "a", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        f.write(content)
    _fchmod_safe(file_path)


def _secure_write(file_path: Path, content: str) -> None:
    """Safely write content to a file, ensuring 0o600 permissions upon creation."""
    # Security: Prevent TOCTOU symlink vulnerability
    if file_path.is_symlink():
        raise OSError(f"Refusing to write to symlink: {file_path}")

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    # Use os.open to atomically create file with 0o600 perms, or truncate if exists
    fd = os.open(
        file_path,
        flags,
        0o600,
    )
    try:
        if getattr(os, "O_NONBLOCK", 0):
            os.set_blocking(fd, True)
        # Security: Set permissions on the open file to prevent TOCTOU
        if hasattr(os, "fchmod") and hasattr(os, "fstat"):
            st = os.fstat(fd)
            if (st.st_mode & 0o777) != 0o600:
                os.fchmod(fd, 0o600)
        f = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        f.write(content)
    # Ensure permissions are correct even if file already existed
    _fchmod_safe(file_path)


def _secure_read(file_path: Path) -> str:
    """Safely read a file, verifying it is a regular file and not a symlink."""
    if file_path.is_symlink():
        raise OSError(f"Refusing to read from symlink: {file_path}")

    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd = os.open(file_path, flags)
    try:
        if getattr(os, "O_NONBLOCK", 0):
            os.set_blocking(fd, True)
        f = os.fdopen(fd, "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        st = os.fstat(fd)
        if not S_ISREG(st.st_mode):
            raise OSError(f"Not a regular file: {file_path}")
        if st.st_size > 10_000_000:
            raise OSError(f"'{file_path}' is too large (max 10MB)")
        return f.read()


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

    _fchmod_safe(STORAGE_DIR, mode=0o700)

    for file_path, default_content in [
        (RESULTS_FILE, ""),
        (CONFIG_FILE, "{}"),
    ]:
        if not file_path.exists():
            try:
                # Security: Prevent TOCTOU symlink vulnerability
                if file_path.is_symlink():
                    raise OSError(f"Refusing to write to symlink: {file_path}")

                flags = (
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NONBLOCK", 0)
                )
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW

                # Use os.open to atomically create file with 0o600 permissions
                fd = os.open(file_path, flags, 0o600)
                try:
                    if getattr(os, "O_NONBLOCK", 0):
                        os.set_blocking(fd, True)
                    # Security: Set permissions on the open file to prevent TOCTOU
                    if hasattr(os, "fchmod") and hasattr(os, "fstat"):
                        st = os.fstat(fd)
                        if (st.st_mode & 0o777) != 0o600:
                            os.fchmod(fd, 0o600)
                    f = os.fdopen(fd, "w", encoding="utf-8")
                except BaseException:
                    os.close(fd)
                    raise
                with f:
                    f.write(default_content)
            except FileExistsError:
                # File was created between the exists() check and os.open
                pass

        # Ensure permissions are correct even if file already existed
        _fchmod_safe(file_path)

    _STORAGE_ENSURED = True


def save_result(result: TypingResult) -> None:
    """Append a result to the local storage."""
    global _RESULTS_CACHE
    _ensure_storage()
    results = load_results()
    if not result.date:
        result.date = datetime.now(timezone.utc).isoformat()

    # O(1) append
    jsonl_line = json.dumps(result.to_dict(), ensure_ascii=False) + "\n"
    _secure_append(RESULTS_FILE, jsonl_line)

    # Update cache
    results.append(result)


def load_results() -> list[TypingResult]:
    """Load all results from local storage."""
    global _RESULTS_CACHE
    if _RESULTS_CACHE is not None:
        return _RESULTS_CACHE

    _ensure_storage()
    try:
        text = _secure_read(RESULTS_FILE).strip()
        if not text:
            _RESULTS_CACHE = []
            return _RESULTS_CACHE

        # Migration from legacy JSON array format
        if text.startswith("[") and text.endswith("]"):
            try:
                data = json.loads(text)
                if not isinstance(data, list):
                    _RESULTS_CACHE = []
                    return _RESULTS_CACHE
                _RESULTS_CACHE = [
                    TypingResult.from_dict(r) for r in data if isinstance(r, dict)
                ]
                # Convert to JSONL immediately
                jsonl_data = "\n".join(
                    json.dumps(r.to_dict(), ensure_ascii=False) for r in _RESULTS_CACHE
                )
                _secure_write(RESULTS_FILE, jsonl_data + "\n" if jsonl_data else "")
                return _RESULTS_CACHE
            except json.JSONDecodeError:
                _RESULTS_CACHE = []
                return _RESULTS_CACHE

        # Handle JSONL format
        results = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    results.append(TypingResult.from_dict(data))
            except json.JSONDecodeError:
                continue

        _RESULTS_CACHE = results
        return _RESULTS_CACHE
    except OSError:
        _RESULTS_CACHE = []
        return _RESULTS_CACHE


def clear_results() -> None:
    """Delete all stored typing results."""
    global _RESULTS_CACHE
    _ensure_storage()
    try:
        _secure_write(RESULTS_FILE, "")
        _RESULTS_CACHE = []
    except OSError:
        pass


def delete_result_by_index(index: int) -> None:
    """Delete a single result entry by its index in the stored list."""
    global _RESULTS_CACHE
    results = load_results()
    if 0 <= index < len(results):
        results.pop(index)
        jsonl_data = "\n".join(
            json.dumps(r.to_dict(), ensure_ascii=False) for r in results
        )
        _secure_write(RESULTS_FILE, jsonl_data + "\n" if jsonl_data else "")
        _RESULTS_CACHE = results


def save_config(config: dict[str, Any]) -> None:
    """Save user configuration to local storage."""
    global _CONFIG_CACHE
    _ensure_storage()
    _secure_write(CONFIG_FILE, json.dumps(config, indent=2, ensure_ascii=False))
    _CONFIG_CACHE = config


def load_config() -> dict[str, Any]:
    """Load user configuration from local storage."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    _ensure_storage()
    try:
        text = _secure_read(CONFIG_FILE)
        data = json.loads(text)
        if not isinstance(data, dict):
            _CONFIG_CACHE = {}
            return {}
        _CONFIG_CACHE = data
        return _CONFIG_CACHE
    except (json.JSONDecodeError, OSError):
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
