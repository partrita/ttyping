"""Main Textual application for ttyping."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from ttyping.screens import HistoryScreen, TypingScreen
from ttyping.storage import TypingResult
from ttyping.words import get_weak_drill, get_words, words_from_file, words_from_url


class TypingApp(App):
    """A minimal terminal typing test."""

    TITLE = "ttyping"

    BINDINGS = [
        Binding(key="ctrl+q", action="quit", description="Quit", show=True),
    ]

    # ── Dual-theme CSS ─────────────────────────────────────────────────────
    # Light mode (Serika): bg #e1e1e3, sub-bg #d1d0c5, text #323437, dim #646669, accent #e2b714
    # Dark mode (Serika Dark): bg #323437, sub-bg #2c2e31, text #d1d0c5, dim #646669, accent #e2b714
    CSS = """
    /* ── Base ───────────────────────────────────────── */
    Screen               { background: #e1e1e3; color: #323437; }
    .-dark-mode Screen { background: #323437; color: #d1d0c5; }

    /* ── Scrollbars ─────────────────────────────────── */
    ScrollBar {
        background: #e1e1e3;
        color: #646669;
    }
    ScrollBar .scrollbar--thumb {
        background: #646669 50%;
        color: #e2b714;
    }
    ScrollBar .scrollbar--thumb:hover {
        background: #e2b714;
    }
    .-dark-mode ScrollBar {
        background: #323437;
        color: #646669;
    }
    .-dark-mode ScrollBar .scrollbar--thumb {
        background: #646669 50%;
        color: #e2b714;
    }
    .-dark-mode ScrollBar .scrollbar--thumb:hover {
        background: #e2b714;
    }

    /* ── OptionList & Selection ─────────────────────── */
    OptionList {
        border: none;
    }
    OptionList:focus > .option-list--option-highlighted {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }
    OptionList > .option-list--option-highlighted {
        background: #e2b714 30%;
        color: #323437;
    }
    .-dark-mode OptionList:focus > .option-list--option-highlighted {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }
    .-dark-mode OptionList > .option-list--option-highlighted {
        background: #e2b714 30%;
        color: #d1d0c5;
    }

    /* ── Input (All inputs in modals/menus) ─────────── */
    Input {
        border: round #646669;
        background: #e1e1e3;
        color: #323437;
    }
    Input:focus {
        border: round #e2b714;
    }
    .-dark-mode Input {
        border: round #646669;
        background: #323437;
        color: #d1d0c5;
    }
    .-dark-mode Input:focus {
        border: round #e2b714;
    }

    /* ── ProgressBar ────────────────────────────────── */
    ProgressBar .bar--bar {
        color: #e2b714;
        background: #646669 40%;
    }
    ProgressBar .bar--complete {
        color: #e2b714;
    }
    .-dark-mode ProgressBar .bar--bar {
        color: #e2b714;
        background: #646669 40%;
    }
    .-dark-mode ProgressBar .bar--complete {
        color: #e2b714;
    }

    /* ── DataTable ──────────────────────────────────── */
    DataTable {
        border: round #646669;
    }
    .-dark-mode DataTable {
        border: round #646669;
    }
    DataTable:focus {
        border: round #e2b714;
    }
    .-dark-mode DataTable:focus {
        border: round #e2b714;
    }
    DataTable > .datatable--cursor {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }
    .-dark-mode DataTable > .datatable--cursor {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }

    /* ── Typing screen ──────────────────────────────── */
    #stats               { color: #e2b714; }
    .-dark-mode #stats { color: #e2b714; }

    #input-area {
        border: round #646669;
        background: #d1d0c5;
        color: #323437;
    }
    .-dark-mode #input-area {
        border: round #646669;
        background: #2c2e31;
        color: #d1d0c5;
    }
    #input-area:focus          { border: round #e2b714; }
    .-dark-mode #input-area:focus { border: round #e2b714; }

    #hints               { color: #646669; }
    .-dark-mode #hints { color: #646669; }

    /* ── Result screen ──────────────────────────────── */
    .result-detail       { color: #646669; }
    .result-title        { color: #646669; }
    #result-hints        { color: #646669; }
    .-dark-mode .result-detail { color: #646669; }
    .-dark-mode .result-title  { color: #646669; }
    .-dark-mode #result-hints  { color: #646669; }

    /* ── History screen ─────────────────────────────── */
    #history-title { color: #e2b714; }
    .-dark-mode #history-title { color: #e2b714; }

    #history-stats  { color: #646669; }
    #history-hints  { color: #646669; }
    .-dark-mode #history-stats { color: #646669; }
    .-dark-mode #history-hints { color: #646669; }

    #history-table  { background: #d1d0c5; }
    .-dark-mode #history-table { background: #2c2e31; }

    #history-empty  { color: #646669; }
    .-dark-mode #history-empty { color: #646669; }

    /* ── Menu / sub-menu containers ─────────────────── */
    #menu-container {
        border: round #e2b714;
        background: #d1d0c5;
    }
    .-dark-mode #menu-container {
        border: round #e2b714;
        background: #2c2e31;
    }

    #menu-title { color: #e2b714; }
    .-dark-mode #menu-title { color: #e2b714; }

    #menu-hints  { display: none; }

    #menu-options { background: #d1d0c5; }
    .-dark-mode #menu-options { background: #2c2e31; }

    /* ── Confirm delete modal ────────────────────────── */
    #confirm-box {
        background: #d1d0c5;
        border: round #ca4754;
    }
    .-dark-mode #confirm-box {
        background: #2c2e31;
        border: round #ca4754;
    }
    #confirm-title  { color: #ca4754; }
    #confirm-body   { color: #323437; }
    #confirm-hints  { color: #646669; }
    .-dark-mode #confirm-body  { color: #d1d0c5; }
    .-dark-mode #confirm-hints { color: #646669; }

    /* ── Weakness screen ─────────────────────────────── */
    #weakness-container {
        border: round #e2b714;
        background: #d1d0c5;
    }
    .-dark-mode #weakness-container {
        border: round #e2b714;
        background: #2c2e31;
    }
    #weakness-title   { color: #e2b714; }
    .-dark-mode #weakness-title { color: #e2b714; }

    .weakness-section { color: #646669; }
    .-dark-mode .weakness-section { color: #646669; }

    #weakness-options { background: #d1d0c5; }
    .-dark-mode #weakness-options { background: #2c2e31; }

    #weakness-hints  { color: #646669; }
    .-dark-mode #weakness-hints { color: #646669; }

    /* ── About screen ────────────────────────────────── */
    .about-text  { color: #646669; }
    .-dark-mode .about-text { color: #646669; }

    /* ── DataTable global ────────────────────────────── */
    DataTable {
        background: #d1d0c5;
        color: #323437;
        scrollbar-background: #d1d0c5;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    .-dark-mode DataTable {
        background: #2c2e31;
        color: #d1d0c5;
        scrollbar-background: #2c2e31;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    """

    def __init__(
        self,
        lang: str | None = None,
        file_path: str | None = None,
        word_count: int | None = None,
        duration: int | None = None,
        target_accuracy: float | None = None,
        show_history: bool = False,
        url: str | None = None,
    ) -> None:
        super().__init__()
        from ttyping.storage import load_config

        config = load_config()

        # Safe type validation for string configs
        saved_lang = config.get("lang")
        parsed_lang = saved_lang if isinstance(saved_lang, str) else None
        self._lang: str = (
            (lang if isinstance(lang, str) else None) or parsed_lang or "en_qwerty"
        )

        saved_file = config.get("file_path")
        parsed_file = saved_file if isinstance(saved_file, str) else None
        self._file_path: str | None = (
            file_path if isinstance(file_path, str) else None
        ) or parsed_file
        self._url: str | None = url

        # Safe cast for word_count
        saved_wc = config.get("word_count", 25)
        try:
            parsed_wc = int(saved_wc) if saved_wc is not None else 25
        except (ValueError, TypeError):
            parsed_wc = 25
        wc = word_count if word_count is not None else parsed_wc
        self._word_count: int = max(1, min(wc, 1000))

        # Safe cast for duration
        saved_dur = config.get("duration")
        try:
            parsed_dur = int(saved_dur) if saved_dur is not None else None
        except (ValueError, TypeError):
            parsed_dur = None
        dur = duration if duration is not None else parsed_dur
        self._duration: int | None = max(1, min(dur, 3600)) if dur is not None else None
        # Prefer explicit CLI arg, then saved config, then None
        saved_acc = config.get("target_accuracy")
        try:
            parsed_acc = float(saved_acc) if saved_acc is not None else None
        except (ValueError, TypeError):
            parsed_acc = None

        acc = target_accuracy if target_accuracy is not None else parsed_acc
        self._target_accuracy: float | None = (
            max(0.0, min(acc, 100.0)) if acc is not None else None
        )

        saved_wpm = config.get("target_wpm")
        try:
            parsed_target_wpm = int(saved_wpm) if saved_wpm is not None else None
        except (ValueError, TypeError):
            parsed_target_wpm = None
        self._target_wpm: int | None = (
            max(1, min(parsed_target_wpm, 500)) if parsed_target_wpm is not None else None
        )

        self._show_history: bool = show_history
        self._session_attempts: list[TypingResult] = []
        self._current_session_words: list[str] | None = None

        # Apply persisted theme (dark by default)
        saved_theme = config.get("theme", "dark")
        is_dark = (saved_theme if isinstance(saved_theme, str) else "dark") == "dark"
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
        elif self._url:
            words = words_from_url(self._url, count)
        else:
            words = get_words(self._lang, count)

        self._current_session_words = words
        return words

    def _clear_typing_screens(self) -> None:
        """Clear active typing and result screens from the stack."""
        while len(self.screen_stack) > 1 and self.screen.__class__.__name__ in (
            "TypingScreen",
            "ResultScreen",
        ):
            self.pop_screen()

    def restart(self) -> None:
        """Pop current screens and start a new typing test with fresh words."""
        self._clear_typing_screens()
        self._start_typing(keep_words=False)

    def reset_session_attempt(self, stats: TypingResult) -> None:
        """Record a failed attempt (accuracy drop) and restart with SAME words."""
        self._session_attempts.append(stats)
        self._clear_typing_screens()
        self._start_typing(keep_words=True)

    def show_result(self, result: TypingResult) -> None:
        """Replace the typing screen with the result screen after a test."""
        from ttyping.screens import ResultScreen

        self.switch_screen(
            ResultScreen(result, session_attempts=self._session_attempts)
        )

    def start_custom_test(self, lang: str, words: int, duration: int | None) -> None:
        """Start a test with custom parameters and reset session state."""
        self._lang = lang
        self._word_count = words
        self._duration = duration
        self._file_path = None
        self._url = None
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
