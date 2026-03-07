"""Main Textual application for ttyping."""

from __future__ import annotations

from typing import Any

from textual.app import App

from ttyping.screens import HistoryScreen, TypingScreen
from ttyping.words import get_weak_drill, get_words, words_from_file


class TypingApp(App):
    """A minimal terminal typing test."""

    TITLE = "ttyping"

    # ── Dual-theme CSS ─────────────────────────────────────────────────────
    # Light mode rules (no class). Dark overrides use App.-dark-mode prefix.
    CSS = """
    /* ── Base ───────────────────────────────────────── */
    Screen               { background: #eff1f5; }
    App.-dark-mode Screen { background: #323437; }

    /* ── Typing screen ──────────────────────────────── */
    #stats               { color: #c8a010; }
    App.-dark-mode #stats { color: #e2b714; }

    #input-area {
        border: round #7a7b7e;
        background: #e0e1e5;
        color: #323437;
    }
    App.-dark-mode #input-area {
        border: round #909294;
        background: #2c2e31;
        color: #d1d0c5;
    }
    #input-area:focus          { border: round #c8a010; }
    App.-dark-mode #input-area:focus { border: round #e2b714; }

    #hints               { color: #7a7b7e; }
    App.-dark-mode #hints { color: #909294; }

    /* ── Result screen ──────────────────────────────── */
    .result-detail       { color: #7a7b7e; }
    .result-title        { color: #7a7b7e; }
    #result-hints        { color: #7a7b7e; }
    App.-dark-mode .result-detail { color: #909294; }
    App.-dark-mode .result-title  { color: #909294; }
    App.-dark-mode #result-hints  { color: #909294; }

    /* ── History screen ─────────────────────────────── */
    #history-title { color: #c8a010; }
    App.-dark-mode #history-title { color: #e2b714; }

    #history-stats  { color: #7a7b7e; }
    #history-hints  { color: #7a7b7e; }
    App.-dark-mode #history-stats { color: #909294; }
    App.-dark-mode #history-hints { color: #909294; }

    #history-table  { background: #e0e1e5; }
    App.-dark-mode #history-table { background: #2c2e31; }

    #history-empty  { color: #7a7b7e; }
    App.-dark-mode #history-empty { color: #909294; }

    /* ── Menu / sub-menu containers ─────────────────── */
    #menu-container {
        border: round #c8a010;
        background: #e0e1e5;
    }
    App.-dark-mode #menu-container {
        border: round #e2b714;
        background: #2c2e31;
    }

    #menu-title { color: #c8a010; }
    App.-dark-mode #menu-title { color: #e2b714; }

    #menu-hints  { color: #7a7b7e; }
    App.-dark-mode #menu-hints { color: #909294; }

    #menu-options { background: #e0e1e5; }
    App.-dark-mode #menu-options { background: #2c2e31; }

    /* ── Confirm delete modal ────────────────────────── */
    #confirm-box {
        background: #e0e1e5;
        border: round #ca4754;
    }
    App.-dark-mode #confirm-box {
        background: #2c2e31;
        border: round #ca4754;
    }
    #confirm-title  { color: #ca4754; }
    #confirm-body   { color: #323437; }
    #confirm-hints  { color: #7a7b7e; }
    App.-dark-mode #confirm-body  { color: #d1d0c5; }
    App.-dark-mode #confirm-hints { color: #909294; }

    /* ── Weakness screen ─────────────────────────────── */
    #weakness-container {
        border: round #c8a010;
        background: #e0e1e5;
    }
    App.-dark-mode #weakness-container {
        border: round #e2b714;
        background: #2c2e31;
    }
    #weakness-title   { color: #c8a010; }
    App.-dark-mode #weakness-title { color: #e2b714; }

    .weakness-section { color: #7a7b7e; }
    App.-dark-mode .weakness-section { color: #909294; }

    #weakness-options { background: #e0e1e5; }
    App.-dark-mode #weakness-options { background: #2c2e31; }

    #weakness-hints  { color: #7a7b7e; }
    App.-dark-mode #weakness-hints { color: #909294; }

    /* ── About screen ────────────────────────────────── */
    .about-text  { color: #7a7b7e; }
    App.-dark-mode .about-text { color: #909294; }

    /* ── DataTable global ────────────────────────────── */
    DataTable          { background: #e0e1e5; color: #323437; }
    App.-dark-mode DataTable { background: #2c2e31; color: #d1d0c5; }
    """

    def __init__(
        self,
        lang: str | None = None,
        file_path: str | None = None,
        word_count: int | None = None,
        duration: int | None = None,
        target_accuracy: float | None = None,
        show_history: bool = False,
    ) -> None:
        super().__init__()
        from ttyping.storage import load_config

        config = load_config()
        self.TITLE: str = "ttyping"

        self._lang: str = lang or config.get("lang", "en_qwerty")
        self._file_path: str | None = file_path or config.get("file_path")
        self._word_count: int = word_count or config.get("word_count", 25)
        self._duration: int | None = duration or config.get("duration")
        # Prefer explicit CLI arg, then saved config, then None
        saved_acc = config.get("target_accuracy")
        self._target_accuracy: float | None = (
            target_accuracy
            if target_accuracy is not None
            else (float(saved_acc) if saved_acc is not None else None)
        )
        self._show_history: bool = show_history
        self._session_attempts: list[dict[str, Any]] = []
        self._current_session_words: list[str] | None = None

        # Apply persisted theme (dark by default)
        is_dark = config.get("theme", "dark") == "dark"
        self.theme = "textual-dark" if is_dark else "textual-light"

    def on_mount(self) -> None:
        if self._show_history:
            self.push_screen(HistoryScreen())
        else:
            from ttyping.screens import MenuScreen

            self.push_screen(MenuScreen())

    def _start_typing(self, keep_words: bool = False) -> None:
        # Save current settings as default for next run
        from ttyping.storage import load_config, save_config

        config = load_config()
        config.update(
            {
                "lang": self._lang,
                "file_path": self._file_path,
                "word_count": self._word_count,
                "duration": self._duration,
                "target_accuracy": self._target_accuracy,
            }
        )
        save_config(config)

        if not keep_words:
            self._current_session_words = None

        words = self._get_words()
        self.push_screen(
            TypingScreen(
                words,
                lang=self._lang,
                duration=self._duration,
                target_accuracy=self._target_accuracy,
            )
        )

    def _get_words(self) -> list[str]:
        if self._current_session_words:
            return self._current_session_words

        count = self._word_count
        if self._duration:
            count = 500

        words: list[str]
        if self._file_path:
            words = words_from_file(self._file_path, count)
        else:
            words = get_words(self._lang, count)

        self._current_session_words = words
        return words

    def restart(self) -> None:
        """Pop current screens and start a new typing test with fresh words."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self._start_typing(keep_words=False)

    def reset_session_attempt(self, stats: dict[str, Any]) -> None:
        """Record a failed attempt (accuracy drop) and restart with SAME words."""
        self._session_attempts.append(stats)
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self._start_typing(keep_words=True)

    def show_result(self, result: dict[str, Any]) -> None:
        """Push the result screen after a test."""
        from ttyping.screens import ResultScreen

        self.push_screen(ResultScreen(result, session_attempts=self._session_attempts))

    def start_custom_test(self, lang: str, words: int, duration: int | None) -> None:
        """Start a test with custom parameters and reset session state."""
        self._lang = lang
        self._word_count = words
        self._duration = duration
        self._file_path = None
        self._session_attempts = []
        self._current_session_words = None
        self._start_typing(keep_words=False)

    def start_weak_drill(self, layout: str, weak_chars: str) -> None:
        """Start a typing drill targeting the given weak characters."""
        self._session_attempts = []
        drill_words = get_weak_drill(layout, weak_chars, count=30)
        self._current_session_words = drill_words
        self._lang = layout
        self._duration = None
        self.push_screen(
            TypingScreen(
                drill_words,
                lang=layout,
                duration=None,
                target_accuracy=self._target_accuracy,
            )
        )
