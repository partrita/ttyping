"""Main Textual application for ttyping."""

from __future__ import annotations

from typing import Any

from textual.app import App

from ttyping.screens import HistoryScreen, MenuScreen, TypingScreen
from ttyping.words import get_words, words_from_file


class TypingApp(App):
    """A minimal terminal typing test."""

    TITLE = "ttyping"

    CSS = """
    Screen {
        background: #323437;
    }
    """

    def __init__(
        self,
        lang: str | None = None,
        file_path: str | None = None,
        word_count: int | None = None,
        duration: int | None = None,
        show_history: bool = False,
    ) -> None:
        super().__init__()
        from ttyping.storage import load_config

        config = load_config()

        self._lang = lang or config.get("lang", "en_qwerty")
        self._file_path = file_path or config.get("file_path")
        self._word_count = word_count or config.get("word_count", 25)
        self._duration = duration or config.get("duration")
        self._show_history = show_history

    def on_mount(self) -> None:
        if self._show_history:
            self.push_screen(HistoryScreen())
        else:
            self.push_screen(MenuScreen())

    def _start_typing(self) -> None:
        # Save current settings as default for next run
        from ttyping.storage import save_config

        save_config(
            {
                "lang": self._lang,
                "file_path": self._file_path,
                "word_count": self._word_count,
                "duration": self._duration,
            }
        )

        words = self._get_words()
        self.push_screen(TypingScreen(words, lang=self._lang, duration=self._duration))

    def _get_words(self) -> list[str]:
        count = self._word_count
        if self._duration:
            count = 500

        if self._file_path:
            return words_from_file(self._file_path, count)
        return get_words(self._lang, count)

    def restart(self) -> None:
        """Pop current screens and start a new typing test."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self._start_typing()

    def show_result(self, result: dict[str, Any]) -> None:
        """Push the result screen after a test."""
        from ttyping.screens import ResultScreen

        self.push_screen(ResultScreen(result))

    def start_custom_test(self, lang: str, words: int, duration: int | None) -> None:
        """Start a test with custom parameters and clear file_path."""
        self._lang = lang
        self._word_count = words
        self._duration = duration
        self._file_path = None
        self._start_typing()
