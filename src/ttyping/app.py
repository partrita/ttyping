"""Main Textual application for ttyping."""

from __future__ import annotations

from typing import Any

from textual.app import App

from ttyping.screens import HistoryScreen, TypingScreen
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
        lang: str = "en",
        file_path: str | None = None,
        word_count: int = 25,
        duration: int | None = None,
        show_history: bool = False,
    ) -> None:
        super().__init__()
        self._lang = lang
        self._file_path = file_path
        self._word_count = word_count
        self._duration = duration
        self._show_history = show_history

    def on_mount(self) -> None:
        if self._show_history:
            self.push_screen(HistoryScreen())
        else:
            self._start_typing()

    def _start_typing(self) -> None:
        words = self._get_words()
        self.push_screen(TypingScreen(words, lang=self._lang, duration=self._duration))

    def _get_words(self) -> list[str]:
        count = self._word_count
        if self._duration:
            # For timed tests, provide plenty of words.
            # 500 is likely more than enough for 1-2 minutes.
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
