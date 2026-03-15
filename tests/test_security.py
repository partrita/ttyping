import os
import shutil
from pathlib import Path

import pytest

import ttyping.storage


def test_storage_permissions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Setup temporary storage paths
    test_storage_dir = tmp_path / ".ttyping"
    test_results_file = test_storage_dir / "results.json"
    test_config_file = test_storage_dir / "config.json"

    # Mock the constants in storage module
    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_storage_dir)
    monkeypatch.setattr(ttyping.storage, "RESULTS_FILE", test_results_file)
    monkeypatch.setattr(ttyping.storage, "CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_STORAGE_ENSURED", False)

    # Ensure they don't exist
    if test_storage_dir.exists():
        shutil.rmtree(test_storage_dir)

    # Set a loose umask to see if our code overrides it
    old_umask = os.umask(0o000)
    try:
        # Run ensure_storage
        ttyping.storage._ensure_storage()

        # Verify directory permissions (0o700)
        assert test_storage_dir.exists()
        mode = test_storage_dir.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

        # Verify file permissions (0o600)
        assert test_results_file.exists()
        mode = test_results_file.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

        assert test_config_file.exists()
        mode = test_config_file.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

        # Verify content
        assert test_results_file.read_text() == "[]"
        assert test_config_file.read_text() == "{}"

    finally:
        os.umask(old_umask)


def test_storage_ensured_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_storage_dir = tmp_path / ".ttyping"
    test_results_file = test_storage_dir / "results.json"
    test_config_file = test_storage_dir / "config.json"

    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_storage_dir)
    monkeypatch.setattr(ttyping.storage, "RESULTS_FILE", test_results_file)
    monkeypatch.setattr(ttyping.storage, "CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_STORAGE_ENSURED", False)

    # Run first time
    ttyping.storage._ensure_storage()
    assert ttyping.storage._STORAGE_ENSURED is True

    # Delete the directory
    shutil.rmtree(test_storage_dir)

    # Run again - it should NOT recreate because of the flag
    ttyping.storage._ensure_storage()
    assert not test_storage_dir.exists()


def test_storage_symlink_attack_prevention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_storage_dir = tmp_path / ".ttyping"
    test_results_file = test_storage_dir / "results.json"
    test_config_file = test_storage_dir / "config.json"

    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_storage_dir)
    monkeypatch.setattr(ttyping.storage, "RESULTS_FILE", test_results_file)
    monkeypatch.setattr(ttyping.storage, "CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_STORAGE_ENSURED", False)

    # Create a dummy target file
    target_file = tmp_path / "target.txt"
    target_file.write_text("secret")

    # Create storage dir and make results.json a symlink to target
    test_storage_dir.mkdir(parents=True, exist_ok=True)
    test_results_file.symlink_to(target_file)
    test_config_file.symlink_to(target_file)

    # Make STORAGE_DIR a symlink too
    test_storage_dir2 = tmp_path / ".ttyping2"
    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_storage_dir2)
    test_storage_dir2.symlink_to(test_storage_dir)

    # Run ensure_storage
    ttyping.storage._ensure_storage()

    # Verify STORAGE_DIR symlink was removed
    assert not test_storage_dir2.is_symlink()
    assert test_storage_dir2.is_dir()

    # Verify file symlinks were removed
    assert not test_results_file.is_symlink()
    assert not test_config_file.is_symlink()

    # Verify target file remains unchanged
    assert target_file.read_text() == "secret"
