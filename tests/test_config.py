import json
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ttyping import storage
from ttyping.storage import load_config, save_config


@pytest.fixture
def mock_storage(tmp_path: Path) -> Generator[tuple[Path, Path, Path], None, None]:
    storage_dir = tmp_path / ".ttyping"
    results_file = storage_dir / "results.json"
    config_file = storage_dir / "config.json"

    # Reset state variables
    storage._STORAGE_ENSURED = False
    storage._RESULTS_CACHE = None
    storage._CONFIG_CACHE = None

    with (
        patch("ttyping.storage.STORAGE_DIR", storage_dir),
        patch("ttyping.storage.RESULTS_FILE", results_file),
        patch("ttyping.storage.CONFIG_FILE", config_file),
    ):
        yield storage_dir, results_file, config_file


def test_save_load_config(mock_storage: tuple[Path, Path, Path]) -> None:
    test_dir, test_results_file, test_config_file = mock_storage

    assert load_config() == {}

    config_data = {"lang": "ko", "words": 50, "time": None, "file": "test.txt"}
    save_config(config_data)

    assert test_config_file.exists()
    with open(test_config_file) as f:
        saved_data = json.load(f)
    assert saved_data == config_data

    if os.name != "nt":
        assert (test_config_file.stat().st_mode & 0o777) == 0o600

    loaded_data = load_config()
    assert loaded_data == config_data


def test_load_config_cache_hit(mock_storage: tuple[Path, Path, Path]) -> None:
    test_dir, test_results_file, test_config_file = mock_storage

    config_data = {"lang": "en", "words": 20}
    storage._CONFIG_CACHE = config_data

    # Should not read from file
    assert load_config() == config_data


def test_load_config_invalid_json(mock_storage: tuple[Path, Path, Path]) -> None:
    test_dir, test_results_file, test_config_file = mock_storage

    storage._ensure_storage()
    test_config_file.write_text("invalid json", encoding="utf-8")

    assert load_config() == {}


def test_load_config_wrong_type(mock_storage: tuple[Path, Path, Path]) -> None:
    test_dir, test_results_file, test_config_file = mock_storage

    storage._ensure_storage()
    test_config_file.write_text('["not", "a", "dict"]', encoding="utf-8")

    assert load_config() == {}


def test_load_config_file_not_found(mock_storage: tuple[Path, Path, Path]) -> None:
    test_dir, test_results_file, test_config_file = mock_storage

    # Ensure storage is initialized so it doesn't create the file during load_config
    storage._ensure_storage()

    # Mock read_text to raise FileNotFoundError directly, bypassing file creation
    with patch.object(Path, "read_text", side_effect=FileNotFoundError):
        assert load_config() == {}
