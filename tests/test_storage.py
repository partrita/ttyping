import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ttyping import storage
from ttyping.storage import TypingResult


@pytest.fixture
def mock_storage(tmp_path: Path) -> Generator[tuple[Path, Path, Path], None, None]:
    storage_dir = tmp_path / ".ttyping"
    results_file = storage_dir / "results.json"
    config_file = storage_dir / "config.json"
    # Reset the ensured flag so each test actually runs _ensure_storage
    storage._STORAGE_ENSURED = False
    storage._RESULTS_CACHE = None
    with (
        patch("ttyping.storage.STORAGE_DIR", storage_dir),
        patch("ttyping.storage.RESULTS_FILE", results_file),
        patch("ttyping.storage.CONFIG_FILE", config_file),
    ):
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
    assert results_file.read_text() == ""

    assert config_file.exists()
    assert config_file.is_file()
    assert (config_file.stat().st_mode & 0o777) == 0o600
    assert config_file.read_text() == "{}"


def test_ensure_storage_fixes_permissions(
    mock_storage: tuple[Path, Path, Path],
) -> None:
    storage_dir, results_file, config_file = mock_storage

    # Pre-create with loose permissions
    storage_dir.mkdir(parents=True)
    storage_dir.chmod(0o755)
    results_file.touch()
    results_file.chmod(0o644)
    results_file.write_text("")
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

    test_result = TypingResult(
        wpm=60,
        accuracy=95,
        time=10,
        lang="en",
        words=10,
        correct=9,
        keystrokes=50,
        errors=5,
    )
    storage.save_result(test_result)

    # Filter out corrupt lines that cannot be parsed
    data = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(data) == 1
    assert data[0]["wpm"] == 60
    assert data[0]["accuracy"] == 95
    assert "date" in data[0]


def test_save_multiple_results(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage

    result1 = TypingResult(
        wpm=60,
        accuracy=95,
        time=10,
        lang="en",
        words=10,
        correct=9,
        keystrokes=50,
        errors=5,
    )
    result2 = TypingResult(
        wpm=70,
        accuracy=98,
        time=9,
        lang="en",
        words=12,
        correct=11,
        keystrokes=60,
        errors=2,
    )

    storage.save_result(result1)
    storage.save_result(result2)

    # Filter out corrupt lines that cannot be parsed
    data = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(data) == 2
    assert data[0]["wpm"] == 60
    assert data[1]["wpm"] == 70


def test_save_result_appends_to_existing(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage
    storage_dir.mkdir(parents=True, exist_ok=True)

    existing_data = [{"wpm": 50, "accuracy": 90, "date": "2023-01-01T00:00:00Z"}]
    results_file.write_text(
        "\n".join(json.dumps(d) for d in existing_data) + "\n" if existing_data else ""
    )

    new_result = TypingResult(
        wpm=60,
        accuracy=95,
        time=10,
        lang="en",
        words=10,
        correct=9,
        keystrokes=50,
        errors=5,
    )
    storage.save_result(new_result)

    # Filter out corrupt lines that cannot be parsed
    data = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(data) == 2
    assert data[0]["wpm"] == 50
    assert data[1]["wpm"] == 60


def test_save_result_corrupt_file(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage
    storage_dir.mkdir(parents=True, exist_ok=True)

    results_file.write_text("corrupt json\n")

    new_result = TypingResult(
        wpm=60,
        accuracy=95,
        time=10,
        lang="en",
        words=10,
        correct=9,
        keystrokes=50,
        errors=5,
    )
    # save_result calls load_results, which handles JSONDecodeError
    # by returning []. So it should just overwrite the corrupt file,
    # wait no, we changed to JSONL
    # it appends to JSONL. The corrupt line is ignored on load.
    storage.save_result(new_result)

    # Filter out corrupt lines that cannot be parsed
    data = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(data) == 1
    assert data[0]["wpm"] == 60


def test_load_results(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage

    # Initially should be empty list (via _ensure_storage called in load_results)
    assert storage.load_results() == []

    # Save some data manually
    results_file.parent.mkdir(parents=True, exist_ok=True)
    data = [{"wpm": 70, "date": "2023-01-01T00:00:00Z"}]
    results_file.write_text(
        "\n".join(json.dumps(d) for d in data) + "\n" if data else ""
    )
    storage._RESULTS_CACHE = None

    loaded = storage.load_results()
    assert len(loaded) == 1
    assert loaded[0].wpm == 70
    assert loaded[0].date == "2023-01-01T00:00:00Z"


def test_load_results_invalid_json(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage

    storage_dir.mkdir(parents=True, exist_ok=True)
    results_file.write_text("invalid json")

    # Should return empty list on decode error
    assert storage.load_results() == []


def test_load_results_wrong_type(mock_storage: tuple[Path, Path, Path]) -> None:
    storage_dir, results_file, _ = mock_storage

    storage_dir.mkdir(parents=True, exist_ok=True)
    # Valid JSON on a line but not a dict
    results_file.write_text("[1, 2, 3]")

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
    results_file.write_text(
        "\n".join(json.dumps(d) for d in data) + "\n" if data else ""
    )
    storage._RESULTS_CACHE = None

    stats = storage.load_error_stats()
    assert stats["a"] == 5
    assert stats["s"] == 1
    assert stats["d"] == 4


def test_clear_results(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage
    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text('{"wpm": 60}\n')

    storage.clear_results()
    assert results_file.read_text() == ""


def test_clear_results_oserror(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage
    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text('{"wpm": 60}\n')

    # Ensure storage is initialized so it doesn't call write_text in _ensure_storage
    storage._ensure_storage()

    with patch("ttyping.storage._secure_write", side_effect=OSError("Disk full")):
        # Should not raise exception
        storage.clear_results()

    # Content should remain if write failed
    assert results_file.read_text() == '{"wpm": 60}\n'


def test_delete_result_by_index(mock_storage: tuple[Path, Path, Path]) -> None:
    _, results_file, _ = mock_storage
    results_file.parent.mkdir(parents=True, exist_ok=True)
    data = [{"wpm": 60}, {"wpm": 70}, {"wpm": 80}]
    results_file.write_text(
        "\n".join(json.dumps(d) for d in data) + "\n" if data else ""
    )
    storage._RESULTS_CACHE = None

    # Delete middle item
    storage.delete_result_by_index(1)

    updated_data = [
        json.loads(line)
        for line in results_file.read_text().strip().split("\n")
        if line.strip()
    ]
    # Filter out corrupt lines that cannot be parsed
    data = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(updated_data) == 2
    assert updated_data[0]["wpm"] == 60
    assert updated_data[1]["wpm"] == 80


def test_delete_result_by_index_out_of_bounds(
    mock_storage: tuple[Path, Path, Path],
) -> None:
    _, results_file, _ = mock_storage
    results_file.parent.mkdir(parents=True, exist_ok=True)
    data = [{"wpm": 60}]
    results_file.write_text(
        "\n".join(json.dumps(d) for d in data) + "\n" if data else ""
    )
    storage._RESULTS_CACHE = None

    # Try deleting out of bounds
    storage.delete_result_by_index(5)
    storage.delete_result_by_index(-1)

    updated_data = [
        json.loads(line)
        for line in results_file.read_text().strip().split("\n")
        if line.strip()
    ]
    # Filter out corrupt lines that cannot be parsed
    data = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    assert len(updated_data) == 1
    assert updated_data[0]["wpm"] == 60


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


def test_save_config(mock_storage: tuple[Path, Path, Path]) -> None:
    _, _, config_file = mock_storage

    test_config = {"lang": "ko", "theme": "dark"}
    storage.save_config(test_config)

    assert storage._CONFIG_CACHE == test_config

    saved_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_data == test_config


def test_save_config_with_non_ascii(mock_storage: tuple[Path, Path, Path]) -> None:
    _, _, config_file = mock_storage

    test_config = {"message": "안녕하세요"}
    storage.save_config(test_config)

    assert storage._CONFIG_CACHE == test_config

    text = config_file.read_text(encoding="utf-8")
    assert "안녕하세요" in text

    saved_data = json.loads(text)
    assert saved_data == test_config


def test_load_results_migrates_legacy_json(
    mock_storage: tuple[Path, Path, Path],
) -> None:
    storage_dir, results_file, _ = mock_storage
    storage_dir.mkdir(parents=True, exist_ok=True)
    legacy_data = '[{"wpm": 60, "date": "2023-01-01T00:00:00Z"}]'
    results_file.write_text(legacy_data)
    storage._RESULTS_CACHE = None

    loaded = storage.load_results()
    assert len(loaded) == 1
    assert loaded[0].wpm == 60

    # Check that it migrated to JSONL
    new_data = results_file.read_text()
    assert new_data == (
        '{"wpm": 60.0, "accuracy": 0.0, "time": 0.0, "lang": "en", '
        '"words": 0, "correct": 0, "keystrokes": 0, "errors": 0, '
        '"gross_wpm": 0.0, "top_char_errors": [], "char_timings": [], '
        '"text": "", "date": "2023-01-01T00:00:00Z"}\n'
    )


def test_typing_result_from_dict_complete() -> None:
    data = {
        "wpm": 80.5,
        "accuracy": 98.2,
        "time": 30.0,
        "lang": "en_dvorak",
        "words": 40,
        "correct": 190,
        "keystrokes": 200,
        "errors": 10,
        "gross_wpm": 85.0,
        "top_char_errors": [["a", 2], ["e", 1]],
        "char_timings": [{"char": "a", "time": 0.1}],
        "text": "some typed text",
        "date": "2023-10-27T10:00:00Z",
    }
    result = TypingResult.from_dict(data)
    assert result.wpm == 80.5
    assert result.accuracy == 98.2
    assert result.time == 30.0
    assert result.lang == "en_dvorak"
    assert result.words == 40
    assert result.correct == 190
    assert result.keystrokes == 200
    assert result.errors == 10
    assert result.gross_wpm == 85.0
    assert result.top_char_errors == [["a", 2], ["e", 1]]
    assert result.char_timings == [{"char": "a", "time": 0.1}]
    assert result.text == "some typed text"
    assert result.date == "2023-10-27T10:00:00Z"


def test_typing_result_from_dict_missing_fields() -> None:
    data = {}
    result = TypingResult.from_dict(data)
    assert result.wpm == 0.0
    assert result.accuracy == 0.0
    assert result.time == 0.0
    assert result.lang == "en"
    assert result.words == 0
    assert result.correct == 0
    assert result.keystrokes == 0
    assert result.errors == 0
    assert result.gross_wpm == 0.0
    assert result.top_char_errors == []
    assert result.char_timings == []
    assert result.text == ""
    assert result.date is None


def test_typing_result_from_dict_type_conversion() -> None:
    data = {
        "wpm": "80.5",
        "accuracy": "98.2",
        "time": "30",
        "lang": 123,
        "words": "40",
        "correct": "190",
        "keystrokes": "200",
        "errors": "10",
        "gross_wpm": "85.0",
        "text": 456,
    }
    result = TypingResult.from_dict(data)
    assert result.wpm == 80.5
    assert isinstance(result.wpm, float)
    assert result.accuracy == 98.2
    assert isinstance(result.accuracy, float)
    assert result.time == 30.0
    assert isinstance(result.time, float)
    assert result.lang == "123"
    assert isinstance(result.lang, str)
    assert result.words == 40
    assert isinstance(result.words, int)
    assert result.correct == 190
    assert isinstance(result.correct, int)
    assert result.keystrokes == 200
    assert isinstance(result.keystrokes, int)
    assert result.errors == 10
    assert isinstance(result.errors, int)
    assert result.gross_wpm == 85.0
    assert isinstance(result.gross_wpm, float)
    assert result.text == "456"
    assert isinstance(result.text, str)
