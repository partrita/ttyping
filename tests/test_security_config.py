import json

from ttyping.app import TypingApp


def test_malformed_config_types(tmp_path: object) -> None:
    import ttyping.storage as storage

    storage_dir = tmp_path / ".ttyping"
    results_file = storage_dir / "results.json"
    config_file = storage_dir / "config.json"

    storage._STORAGE_ENSURED = False
    storage._RESULTS_CACHE = None
    storage._CONFIG_CACHE = None

    import unittest.mock

    with (
        unittest.mock.patch("ttyping.storage.STORAGE_DIR", storage_dir),
        unittest.mock.patch("ttyping.storage.RESULTS_FILE", results_file),
        unittest.mock.patch("ttyping.storage.CONFIG_FILE", config_file),
    ):
        storage._ensure_storage()
        config_file.write_text(
            json.dumps(
                {
                    "word_count": "not an int",
                    "duration": "not an int",
                    "lang": 123,
                    "file_path": 123,
                    "theme": 123,
                }
            ),
            encoding="utf-8",
        )

        app = TypingApp()
        assert app._word_count == 25
        assert app._duration is None
        assert app._lang == "en_qwerty"
        assert app._file_path is None
        assert app.theme == "textual-dark"
