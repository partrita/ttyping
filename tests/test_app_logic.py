from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from ttyping.app import TypingApp


@pytest.fixture
def mock_storage() -> Generator[MagicMock, None, None]:
    with (
        patch("ttyping.storage.load_config") as mock_load,
        patch("ttyping.storage._ensure_storage"),
    ):
        mock_load.return_value = {}
        yield mock_load


def test_get_words_default(mock_storage: MagicMock) -> None:
    app = TypingApp(lang="en", word_count=25)
    with patch("ttyping.app.get_words") as mock_get_words:
        mock_get_words.return_value = ["word"] * 25
        words = app._get_words()
        assert len(words) == 25
        mock_get_words.assert_called_once_with("en", 25)


def test_get_words_duration(mock_storage: MagicMock) -> None:
    # If duration is set, it should return 500 words
    app = TypingApp(lang="en", duration=60)
    with patch("ttyping.app.get_words") as mock_get_words:
        mock_get_words.return_value = ["word"] * 500
        words = app._get_words()
        assert len(words) == 500
        mock_get_words.assert_called_once_with("en", 500)


def test_get_words_from_file(mock_storage: MagicMock) -> None:
    app = TypingApp(file_path="test.txt", word_count=20)
    with patch("ttyping.app.words_from_file") as mock_from_file:
        mock_from_file.return_value = ["file_word"] * 20
        words = app._get_words()
        assert len(words) == 20
        mock_from_file.assert_called_once_with("test.txt", 20)


def test_get_words_from_file_with_duration(mock_storage: MagicMock) -> None:
    # Even with duration, if file_path is set, it uses words_from_file
    app = TypingApp(file_path="test.txt", duration=60)
    with patch("ttyping.app.words_from_file") as mock_from_file:
        mock_from_file.return_value = ["file_word"] * 500
        words = app._get_words()
        assert len(words) == 500
        mock_from_file.assert_called_once_with("test.txt", 500)


def test_get_words_lang_override(mock_storage: MagicMock) -> None:
    app = TypingApp(lang="ko", word_count=10)
    with patch("ttyping.app.get_words") as mock_get_words:
        mock_get_words.return_value = ["ko_word"] * 10
        words = app._get_words()
        assert len(words) == 10
        mock_get_words.assert_called_once_with("ko", 10)
