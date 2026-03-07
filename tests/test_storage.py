import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ttyping import storage


@pytest.fixture
def mock_storage(tmp_path: Path) -> Generator[tuple[Path, Path, Path], None, None]:
    storage_dir = tmp_path / ".ttyping"
    results_file = storage_dir / "results.json"
    config_file = storage_dir / "config.json"
    # Reset the ensured flag so each test actually runs _ensure_storage
    storage._STORAGE_ENSURED = False
    with patch("ttyping.storage.STORAGE_DIR", storage_dir), \
         patch("ttyping.storage.RESULTS_FILE", results_file), \
         patch("ttyping.storage.CONFIG_FILE", config_file):
        yield storage_dir, results_file, config_file


def test_ensure_storage_creates_new(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, config_file = mock_storage

    storage._ensure_storage()

    assert storage_dir.exists()
    assert storage_dir.is_dir()
    # Check permissions (octal)
    assert (storage_dir.stat().st_mode & 0o777) == 0o700

    assert results_file.exists()
    assert results_file.is_file()
    assert (results_file.stat().st_mode & 0o777) == 0o600
    assert results_file.read_text() == "[]"

    assert config_file.exists()
    assert config_file.is_file()
    assert (config_file.stat().st_mode & 0o777) == 0o600
    assert config_file.read_text() == "{}"


def test_ensure_storage_fixes_permissions(
    mock_storage: tuple[Path, Path, Path]
) -> None:
    storage_dir, results_file, config_file = mock_storage

    # Pre-create with loose permissions
    storage_dir.mkdir(parents=True)
    storage_dir.chmod(0o755)
    results_file.touch()
    results_file.chmod(0o644)
    results_file.write_text("[]")
    config_file.touch()
    config_file.chmod(0o644)
    config_file.write_text("{}")

    config_file.touch()
    config_file.chmod(0o644)
    config_file.write_text("{}")

    storage._ensure_storage()

    assert (storage_dir.stat().st_mode & 0o777) == 0o700
    assert (results_file.stat().st_mode & 0o777) == 0o600
    assert (config_file.stat().st_mode & 0o777) == 0o600


def test_save_result(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage

    test_result = {"wpm": 60, "accuracy": 95}
    storage.save_result(test_result)

    data = json.loads(results_file.read_text())
    assert len(data) == 1
    assert data[0]["wpm"] == 60
    assert data[0]["accuracy"] == 95
    assert "date" in data[0]


def test_save_multiple_results(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage

    result1 = {"wpm": 60, "accuracy": 95}
    result2 = {"wpm": 70, "accuracy": 98}

    storage.save_result(result1)
    storage.save_result(result2)

    data = json.loads(results_file.read_text())
    assert len(data) == 2
    assert data[0]["wpm"] == 60
    assert data[1]["wpm"] == 70


def test_save_result_appends_to_existing(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage
    storage_dir.mkdir(parents=True, exist_ok=True)

    existing_data = [{"wpm": 50, "accuracy": 90, "date": "2023-01-01T00:00:00Z"}]
    results_file.write_text(json.dumps(existing_data))

    new_result = {"wpm": 60, "accuracy": 95}
    storage.save_result(new_result)

    data = json.loads(results_file.read_text())
    assert len(data) == 2
    assert data[0]["wpm"] == 50
    assert data[1]["wpm"] == 60


def test_save_result_corrupt_file(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage
    storage_dir.mkdir(parents=True, exist_ok=True)

    results_file.write_text("corrupt json")

    new_result = {"wpm": 60, "accuracy": 95}
    # save_result calls load_results, which handles JSONDecodeError
    # by returning []. So it should just overwrite the corrupt file.
    storage.save_result(new_result)

    data = json.loads(results_file.read_text())
    assert len(data) == 1
    assert data[0]["wpm"] == 60


def test_load_results(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage

    # Initially should be empty list (via _ensure_storage called in load_results)
    assert storage.load_results() == []

    # Save some data manually
    results_file.parent.mkdir(parents=True, exist_ok=True)
    data = [{"wpm": 70, "date": "2023-01-01T00:00:00Z"}]
    results_file.write_text(json.dumps(data))

    loaded = storage.load_results()
    assert loaded == data


def test_load_results_invalid_json(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage

    storage_dir.mkdir(parents=True, exist_ok=True)
    results_file.write_text("invalid json")

    # Should return empty list on decode error
    assert storage.load_results() == []

def test_load_results_wrong_type(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage

    storage_dir.mkdir(parents=True, exist_ok=True)
    # Valid JSON but not a list
    results_file.write_text('{"not": "a list"}')

    assert storage.load_results() == []


def test_load_error_stats_empty(mock_storage: tuple[Path, Path, Path]) -> None:
    """load_error_stats returns empty dict when no results."""
    assert storage.load_error_stats() == {}


def test_load_error_stats_aggregates(
    mock_storage: tuple[Path, Path, Path],
) -> None:
    """load_error_stats correctly sums char errors across runs."""
    storage_dir, results_file, _ = mock_storage
    storage_dir.mkdir(parents=True, exist_ok=True)

    data = [
        {"top_char_errors": [["a", 3], ["s", 1]]},
        {"top_char_errors": [["a", 2], ["d", 4]]},
        {"top_char_errors": []},
    ]
    results_file.write_text(json.dumps(data))

    stats = storage.load_error_stats()
    assert stats["a"] == 5
    assert stats["s"] == 1
    assert stats["d"] == 4


def test_chars_to_finger_en_qwerty() -> None:
    """chars_to_finger maps keys to correct fingers for QWERTY."""
    from ttyping.words import chars_to_finger

    result = chars_to_finger("en_qwerty", "asr")
    # 'a' and 's' belong to known fingers
    assert any("a" in chars for chars in result.values())
    assert any("s" in chars for chars in result.values())


def test_get_weak_drill_returns_words() -> None:
    """get_weak_drill returns a list of the requested length."""
    from ttyping.words import get_weak_drill

    words = get_weak_drill("en_qwerty", "asdf", count=10)
    assert len(words) == 10
    assert all(isinstance(w, str) and len(w) > 0 for w in words)
