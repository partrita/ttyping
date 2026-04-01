import os
import shutil
from pathlib import Path
from typing import NoReturn

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


def test_storage_intermediate_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set a deeply nested path
    test_storage_dir = tmp_path / "a" / "b" / "c" / ".ttyping"
    test_results_file = test_storage_dir / "results.json"
    test_config_file = test_storage_dir / "config.json"

    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_storage_dir)
    monkeypatch.setattr(ttyping.storage, "RESULTS_FILE", test_results_file)
    monkeypatch.setattr(ttyping.storage, "CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_STORAGE_ENSURED", False)

    # Set a loose umask to see if our code handles it safely
    old_umask = os.umask(0o000)
    try:
        ttyping.storage._ensure_storage()

        # Verify leaf directory permissions (0o700)
        assert test_storage_dir.exists()
        mode = test_storage_dir.stat().st_mode & 0o777
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

        # Verify intermediate directories inherit umask, they shouldn't be
        # explicitly restricted to 0o700 to prevent breaking shared setups
        parent = test_storage_dir.parent
        while parent != tmp_path:
            assert parent.exists()
            mode = parent.stat().st_mode & 0o777
            assert mode != 0o700, f"Intermediate dir {parent} restricted"
            parent = parent.parent

    finally:
        os.umask(old_umask)


def test_storage_symlink_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_storage_dir = tmp_path / ".ttyping"
    test_results_file = test_storage_dir / "results.json"
    test_config_file = test_storage_dir / "config.json"

    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_storage_dir)
    monkeypatch.setattr(ttyping.storage, "RESULTS_FILE", test_results_file)
    monkeypatch.setattr(ttyping.storage, "CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_STORAGE_ENSURED", False)

    test_storage_dir.mkdir(parents=True)
    test_results_file.write_text("[]")
    test_config_file.write_text("{}")

    # Pre-set loose permissions
    test_storage_dir.chmod(0o777)
    test_results_file.chmod(0o666)
    test_config_file.chmod(0o666)

    # Mock is_symlink to return True so it skips the fallback path
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)

    # Mock os.open so _fchmod_safe simulates a symlink being blocked by O_NOFOLLOW
    def mock_open(*args: object, **kwargs: object) -> NoReturn:
        raise OSError("Too many levels of symbolic links")

    monkeypatch.setattr("os.open", mock_open)

    ttyping.storage._ensure_storage()

    # Permissions should still be loose because chmod was bypassed
    assert (test_storage_dir.stat().st_mode & 0o777) == 0o777
    assert (test_results_file.stat().st_mode & 0o777) == 0o666
    assert (test_config_file.stat().st_mode & 0o777) == 0o666


def test_secure_write_refuses_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_storage_dir = tmp_path / ".ttyping"
    test_storage_dir.mkdir(parents=True)

    target_file = tmp_path / "important_file.txt"
    target_file.write_text("secret_data")

    symlink_file = test_storage_dir / "results.json"
    symlink_file.symlink_to(target_file)

    with pytest.raises(OSError) as excinfo:
        ttyping.storage._secure_write(symlink_file, "hacked")

    err_str = str(excinfo.value)
    assert "Refusing to write to symlink" in err_str or "Too many levels" in err_str

    # Ensure target was not overwritten
    assert target_file.read_text() == "secret_data"


def test_secure_read_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_storage_dir = tmp_path / ".ttyping"
    test_storage_dir.mkdir(parents=True)

    target_file = tmp_path / "important_file.txt"
    target_file.write_text("secret_data")

    symlink_file = test_storage_dir / "results.json"
    symlink_file.symlink_to(target_file)

    with pytest.raises(OSError) as excinfo:
        ttyping.storage._secure_read(symlink_file)

    err_str = str(excinfo.value)
    assert "Refusing to read from symlink" in err_str or "Too many levels" in err_str


def test_secure_read_large_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_storage_dir = tmp_path / ".ttyping"
    test_storage_dir.mkdir(parents=True)

    target_file = test_storage_dir / "results.json"

    with open(target_file, "wb") as f:
        f.truncate(11_000_000)

    with pytest.raises(OSError) as excinfo:
        ttyping.storage._secure_read(target_file)

    err_str = str(excinfo.value)
    assert "is too large" in err_str
