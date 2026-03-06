import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from ttyping import storage


@pytest.fixture
def mock_storage(tmp_path: Path):
    storage_dir = tmp_path / ".ttyping"
    results_file = storage_dir / "results.json"
    # Reset the ensured flag so each test actually runs _ensure_storage
    storage._STORAGE_ENSURED = False
    with patch("ttyping.storage.STORAGE_DIR", storage_dir), \
         patch("ttyping.storage.CONFIG_FILE", storage_dir / "config.json"), \
         patch("ttyping.storage.RESULTS_FILE", results_file):
        yield storage_dir, results_file


def test_ensure_storage_creates_new(mock_storage):
    storage_dir, results_file = mock_storage

    storage._ensure_storage()

    assert storage_dir.exists()
    assert storage_dir.is_dir()
    # Check permissions (octal)
    assert (storage_dir.stat().st_mode & 0o777) == 0o700

    assert results_file.exists()
    assert results_file.is_file()
    assert (results_file.stat().st_mode & 0o777) == 0o600

    assert results_file.read_text() == "[]"


def test_ensure_storage_fixes_permissions(mock_storage):
    storage_dir, results_file = mock_storage

    # Pre-create with loose permissions
    storage_dir.mkdir(parents=True)
    storage_dir.chmod(0o755)
    results_file.touch()
    results_file.chmod(0o644)
    results_file.write_text("[]")

    storage._ensure_storage()

    assert (storage_dir.stat().st_mode & 0o777) == 0o700
    assert (results_file.stat().st_mode & 0o777) == 0o600


def test_save_result(mock_storage):
    _, results_file = mock_storage

    test_result = {"wpm": 60, "accuracy": 95}
    storage.save_result(test_result)

    data = json.loads(results_file.read_text())
    assert len(data) == 1
    assert data[0]["wpm"] == 60
    assert data[0]["accuracy"] == 95
    assert "date" in data[0]


def test_load_results(mock_storage):
    _, results_file = mock_storage

    # Initially should be empty list (via _ensure_storage called in load_results)
    assert storage.load_results() == []

    # Save some data manually
    results_file.parent.mkdir(parents=True, exist_ok=True)
    data = [{"wpm": 70, "date": "2023-01-01T00:00:00Z"}]
    results_file.write_text(json.dumps(data))

    loaded = storage.load_results()
    assert loaded == data


def test_load_results_invalid_json(mock_storage):
    storage_dir, results_file = mock_storage

    storage_dir.mkdir(parents=True, exist_ok=True)
    results_file.write_text("invalid json")

    # Should return empty list on decode error
    assert storage.load_results() == []
