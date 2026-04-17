from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ttyping import storage


@pytest.fixture
def mock_storage(tmp_path: Path) -> Generator[tuple[Path, Path, Path], None, None]:
    """Provides a temporary storage environment for testing."""
    storage_dir = tmp_path / ".ttyping"
    results_file = storage_dir / "results.json"
    config_file = storage_dir / "config.json"

    # Reset state variables to ensure isolation between tests
    storage._STORAGE_ENSURED = False
    storage._RESULTS_CACHE = None
    storage._CONFIG_CACHE = None

    with (
        patch("ttyping.storage.STORAGE_DIR", storage_dir),
        patch("ttyping.storage.RESULTS_FILE", results_file),
        patch("ttyping.storage.CONFIG_FILE", config_file),
    ):
        # Optional: ensure storage is initialized if needed by default
        # storage._ensure_storage()
        yield storage_dir, results_file, config_file
