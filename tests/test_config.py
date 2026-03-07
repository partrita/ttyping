import json
import os
from pathlib import Path
import ttyping.storage
from ttyping.storage import load_config, save_config
import ttyping.storage

def test_save_load_config(tmp_path, monkeypatch):
    test_dir = tmp_path / ".ttyping"
    test_results_file = test_dir / "results.json"
    test_config_file = test_dir / "config.json"

    monkeypatch.setattr("ttyping.storage.STORAGE_DIR", test_dir)
    monkeypatch.setattr("ttyping.storage.RESULTS_FILE", test_results_file)
    monkeypatch.setattr("ttyping.storage.CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_CONFIG_CACHE", None)

    assert load_config() == {}

    config_data = {"lang": "ko", "words": 50, "time": None, "file": "test.txt"}
    save_config(config_data)

    assert test_config_file.exists()
    with open(test_config_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data == config_data

    if os.name != "nt":
        assert (test_config_file.stat().st_mode & 0o777) == 0o600

    loaded_data = load_config()
    assert loaded_data == config_data

def test_load_config_invalid_json(tmp_path, monkeypatch):
    test_dir = tmp_path / ".ttyping"
    test_results_file = test_dir / "results.json"
    test_config_file = test_dir / "config.json"

    monkeypatch.setattr("ttyping.storage.STORAGE_DIR", test_dir)
    monkeypatch.setattr("ttyping.storage.RESULTS_FILE", test_results_file)
    monkeypatch.setattr("ttyping.storage.CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_CONFIG_CACHE", None)

    test_dir.mkdir(parents=True, exist_ok=True)
    test_config_file.write_text("invalid json", encoding="utf-8")

    assert load_config() == {}

def test_load_config_wrong_type(tmp_path, monkeypatch):
    test_dir = tmp_path / ".ttyping"
    test_results_file = test_dir / "results.json"
    test_config_file = test_dir / "config.json"

    monkeypatch.setattr(ttyping.storage, "STORAGE_DIR", test_dir)
    monkeypatch.setattr(ttyping.storage, "RESULTS_FILE", test_results_file)
    monkeypatch.setattr(ttyping.storage, "CONFIG_FILE", test_config_file)
    monkeypatch.setattr(ttyping.storage, "_STORAGE_ENSURED", False)

    test_dir.mkdir(parents=True, exist_ok=True)
    test_config_file.write_text('["not", "a", "dict"]', encoding="utf-8")

    assert load_config() == {}
