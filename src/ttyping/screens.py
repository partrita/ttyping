"""Screens for ttyping: typing test, results, and history."""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, OptionList, Static
from textual.widgets.option_list import Option

from ttyping.storage import load_results, save_result

if TYPE_CHECKING:
    from ttyping.app import TypingApp

# ── Colours (monkeytype-inspired) ─────────────────────────────────────────

COL_BG = "#323437"
COL_DIM = "#909294"
COL_TEXT = "#d1d0c5"
COL_CORRECT = "#d1d0c5"
COL_ERROR = "#ca4754"
COL_ACCENT = "#e2b714"
COL_SUB_BG = "#2c2e31"


# ── TypingScreen ───────────────────────────────────────────────────────────


class TypingScreen(Screen):
    """Main typing test screen."""

    BINDINGS = [
        Binding("tab", "restart", "Restart", priority=True),
        Binding("escape", "quit_app", "Quit", priority=True),
    ]

    DEFAULT_CSS = (
        """
    TypingScreen {
        align: center middle;
    }

    #typing-container {
        width: 76;
        height: auto;
        max-height: 100%;
        align: center middle;
    }

    #stats {
        width: 100%;
        height: 2;
        content-align: center middle;
        text-align: center;
        color: """
        + COL_ACCENT
        + """;
        margin-bottom: 1;
    }

    #text-display {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 8;
        padding: 0 2;
    }

    #input-area {
        width: 100%;
        margin-top: 1;
        border: round """
        + COL_DIM
        + """;
        background: """
        + COL_SUB_BG
        + """;
        color: """
        + COL_TEXT
        + """;
        padding: 0 1;
    }

    #input-area:focus {
        border: round """
        + COL_ACCENT
        + """;
    }

    #hints {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-align: center;
        color: """
        + COL_DIM
        + """;
        margin-top: 1;
    }
    """
    )

    def __init__(
        self,
        words: list[str],
        lang: str = "en",
        duration: int | None = None,
        target_accuracy: float | None = None,
    ) -> None:
        super().__init__()
        self.words = words
        self.lang = lang
        self.duration = duration
        self.target_accuracy = target_accuracy
        self.current_word_idx = 0
        self.current_input = ""
        self.word_correct: list[bool | None] = [None] * len(words)
        self.start_time: float | None = None
        self.total_keystrokes = 0
        self.total_errors = 0
        self.uncorrected_errors = 0
        self._timer_handle: Any = None
        self._finished = False
        self.errors = Counter()  # Tracks characters missed
        self.word_errors = Counter()  # Tracks words missed

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="typing-container"):
                yield Static("", id="stats")
                yield Static("", id="text-display")
                yield Input(placeholder="start typing…", id="input-area")
                yield Static("tab restart · esc quit", id="hints")

    def on_mount(self) -> None:
        self._render_display()
        self.query_one("#input-area", Input).focus()

    # ── input handling ─────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._finished:
            return

        value = event.value

        # Track raw keystrokes and errors
        if len(value) > len(self.current_input):
            added = value[len(self.current_input) :]
            self.total_keystrokes += len(added)

            target_word = self.words[self.current_word_idx]
            for i, char in enumerate(added):
                idx = len(self.current_input) + i
                if idx < len(target_word):
                    if char != target_word[idx]:
                        self.total_errors += 1
                elif char != " ":
                    self.total_errors += 1

        # Space → complete current word
        if value.endswith(" "):
            self._complete_word(value[:-1])
            event.input.value = ""
            return

        # Legacy character error tracking for top errors display
        if value and self.current_word_idx < len(self.words):
            target_word = self.words[self.current_word_idx]
            last_typed_idx = len(value) - 1
            if last_typed_idx < len(target_word):
                if value[last_typed_idx] != target_word[last_typed_idx]:
                    self.errors[target_word[last_typed_idx]] += 1

        self.current_input = value

        # Start timer on first keystroke
        if self.start_time is None and value:
            self.start_time = time.time()
            self._timer_handle = self.set_interval(0.5, self._tick_stats)

        self._render_display()
        self._update_stats()

    def on_key(self, event: events.Key) -> None:
        if self._finished:
            return
        # Enter also completes the current word (handy for last word)
        if event.key == "ctrl+w":
            event.prevent_default()
            self.query_one("#input-area", Input).value = ""
        elif event.key == "enter":
            event.prevent_default()
            inp = self.query_one("#input-area", Input)
            if inp.value:
                self.total_keystrokes += 1
                self._complete_word(inp.value)
                inp.value = ""

    def _get_current_stats(self) -> dict[str, Any]:
        elapsed = time.time() - self.start_time if self.start_time else 0.01
        minutes = elapsed / 60
        if minutes <= 0:
            minutes = 0.001

        gross_wpm = (self.total_keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (self.uncorrected_errors / minutes))
        accuracy = (
            max(
                0,
                (self.total_keystrokes - self.total_errors)
                / max(self.total_keystrokes, 1),
            )
            * 100
        )
        return {
            "wpm": round(net_wpm, 1),
            "gross_wpm": round(gross_wpm, 1),
            "accuracy": round(accuracy, 1),
            "time": round(elapsed, 1),
            "keystrokes": self.total_keystrokes,
            "errors": self.total_errors,
        }

    # ── word completion ────────────────────────────────────────────────

    def _complete_word(self, typed: str) -> None:
        target = self.words[self.current_word_idx]
        is_correct = typed == target

        self.word_correct[self.current_word_idx] = is_correct
        if not is_correct:
            self.uncorrected_errors += 1
            self.word_errors[target] += 1

        self.current_word_idx += 1
        self.current_input = ""

        if self.target_accuracy is not None:
            stats = self._get_current_stats()
            if stats["accuracy"] < self.target_accuracy:
                self._finished = True
                if self._timer_handle:
                    self._timer_handle.stop()
                cast("TypingApp", self.app).reset_session_attempt(stats)
                return

        if self.current_word_idx >= len(self.words):
            self._end_test()
            return

        self._render_display()
        self._update_stats()

    # ── end test ───────────────────────────────────────────────────────

    def _end_test(self) -> None:
        if self._finished:
            return

        self._finished = True
        if self._timer_handle:
            self._timer_handle.stop()

        elapsed = time.time() - self.start_time if self.start_time else 0.01
        minutes = elapsed / 60
        if minutes <= 0:
            minutes = 0.001

        gross_wpm = (self.total_keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (self.uncorrected_errors / minutes))
        accuracy = (
            max(
                0,
                (self.total_keystrokes - self.total_errors)
                / max(self.total_keystrokes, 1),
            )
            * 100
        )
        correct_words = self.current_word_idx - self.uncorrected_errors

        # Get top errors
        top_char_errors = self.errors.most_common(5)
        top_word_errors = self.word_errors.most_common(5)

        result: dict[str, Any] = {
            "wpm": round(net_wpm, 1),
            "gross_wpm": round(gross_wpm, 1),
            "accuracy": round(accuracy, 1),
            "time": round(elapsed, 1),
            "lang": self.lang,
            "words": self.current_word_idx,  # Number of words attempted
            "correct": correct_words,
            "keystrokes": self.total_keystrokes,
            "errors": self.total_errors,
            "top_char_errors": top_char_errors,
            "top_word_errors": top_word_errors,
        }

        save_result(result)
        cast("TypingApp", self.app).show_result(result)

    # ── rendering ──────────────────────────────────────────────────────

    def _render_display(self) -> None:
        # Use a simple line-wrapping approach to show 3 lines:
        # 1. previous line
        # 2. current line (containing active word)
        # 3. next line
        container_width = 72  # matches #typing-container width minus padding

        all_words_text = []
        for i, word in enumerate(self.words):
            t = Text()
            if i < self.current_word_idx:
                if self.word_correct[i]:
                    t.append(word, style=f"dim {COL_CORRECT}")
                else:
                    t.append(word, style=f"{COL_ERROR} strike")
            elif i == self.current_word_idx:
                typed = self.current_input
                for j, ch in enumerate(word):
                    if j < len(typed):
                        if typed[j] == ch:
                            t.append(ch, style=f"bold {COL_CORRECT}")
                        else:
                            t.append(ch, style=f"bold {COL_ERROR}")
                    elif j == len(typed):
                        t.append(ch, style=f"underline {COL_TEXT}")
                    else:
                        t.append(ch, style=COL_TEXT)  # Focused word is more visible
                if len(typed) > len(word):
                    t.append(typed[len(word) :], style=f"bold {COL_ERROR}")
            else:
                t.append(word, style=COL_DIM)
            all_words_text.append(t)

        # Wrap words into lines
        lines = []
        current_line = []
        current_line_len = 0
        active_word_line_idx = 0

        for i, word_text in enumerate(all_words_text):
            word_len = len(self.words[i])
            if current_line_len + word_len + 1 > container_width:
                lines.append(current_line)
                current_line = []
                current_line_len = 0

            if i == self.current_word_idx:
                active_word_line_idx = len(lines)

            current_line.append(word_text)
            current_line_len += word_len + 1
        lines.append(current_line)

        # Build final display text (up to 3 lines)
        display_text = Text()
        start_line = max(0, active_word_line_idx - 1)
        end_line = min(len(lines), start_line + 3)

        # Adjust start_line if we're at the end
        if end_line - start_line < 3 and start_line > 0:
            start_line = max(0, end_line - 3)

        for l_idx in range(start_line, end_line):
            line = lines[l_idx]
            for i, word_text in enumerate(line):
                if i > 0:
                    display_text.append(" ")
                display_text.append(word_text)
            display_text.append("\n")

        self.query_one("#text-display", Static).update(display_text)

    def _update_stats(self) -> None:
        if self.start_time is None:
            self.query_one("#stats", Static).update("")
            return

        elapsed = time.time() - self.start_time
        minutes = elapsed / 60
        if minutes <= 0:
            minutes = 0.001

        gross_wpm = (self.total_keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (self.uncorrected_errors / minutes))
        accuracy = (
            max(
                0,
                (self.total_keystrokes - self.total_errors)
                / max(self.total_keystrokes, 1),
            )
            * 100
        )

        t = Text()
        t.append(f"{net_wpm:.0f}", style=f"bold {COL_ACCENT}")
        t.append(" wpm   ", style=COL_DIM)
        t.append(f"{accuracy:.0f}%", style=f"bold {COL_ACCENT}")
        t.append(" acc   ", style=COL_DIM)

        if self.duration:
            remaining = max(0, self.duration - elapsed)
            t.append(f"{remaining:.0f}s", style=f"bold {COL_ACCENT}")
        else:
            t.append(f"{elapsed:.0f}s", style=f"bold {COL_ACCENT}")

        self.query_one("#stats", Static).update(t)

    def _tick_stats(self) -> None:
        """Called by timer to keep stats ticking even when not typing."""
        if not self._finished:
            if self.duration:
                elapsed = time.time() - self.start_time if self.start_time else 0
                if elapsed >= self.duration:
                    self._end_test()
                    return
            self._update_stats()

    # ── actions ────────────────────────────────────────────────────────

    def action_restart(self) -> None:
        cast("TypingApp", self.app).restart()

    def action_quit_app(self) -> None:
        self.app.exit()


# ── ResultScreen ───────────────────────────────────────────────────────────


class ResultScreen(Screen):
    """Post-test results."""

    BINDINGS = [
        Binding("tab", "retry", "Retry", priority=True),
        Binding("h", "history", "History"),
        Binding("escape", "quit_app", "Quit"),
    ]

    DEFAULT_CSS = (
        """
    ResultScreen {
        align: center middle;
    }

    #result-container {
        width: 60;
        height: auto;
        align: center middle;
        padding: 2 4;
    }

    .result-big {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .result-detail {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
    }

    #top-errors-title {
        width: 100%;
        text-align: center;
        margin-top: 1;
        color: """
        + COL_DIM
        + """;
    }

    #top-errors-graph {
        width: 100%;
        margin-top: 1;
        content-align: center middle;
    }

    #session-table {
        width: 100%;
        height: auto;
        max-height: 10;
        margin-top: 1;
    }

    #result-hints {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
        margin-top: 2;
    }
    """
    )

    def __init__(
        self,
        result: dict[str, Any],
        session_attempts: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.result = result
        self.session_attempts = session_attempts or []

    def compose(self) -> ComposeResult:
        r = self.result
        with Center():
            with Vertical(id="result-container"):
                wpm_text = Text()
                wpm_text.append(f"{r['wpm']:.0f}", style=f"bold {COL_ACCENT}")
                wpm_text.append(" wpm", style=COL_DIM)
                yield Static(wpm_text, classes="result-big")

                acc_text = Text()
                acc_text.append(f"{r['accuracy']:.1f}%", style=f"bold {COL_TEXT}")
                acc_text.append(" accuracy", style=COL_DIM)
                yield Static(acc_text, classes="result-big")

                detail = Text()
                detail.append(f"{r['time']:.1f}s", style=COL_TEXT)
                detail.append(f"  ·  {r['correct']}/{r['words']} words", style=COL_DIM)
                detail.append(f"  ·  {r['lang']}", style=COL_DIM)
                yield Static(detail, classes="result-detail")

                if r.get("top_word_errors"):
                    yield Static("top missed words", id="top-errors-title")
                    yield Static(
                        self._render_bar_graph(r["top_word_errors"]),
                        id="top-errors-graph",
                    )
                elif r.get("top_char_errors"):
                    yield Static("top missed characters", id="top-errors-title")
                    yield Static(
                        self._render_bar_graph(r["top_char_errors"]),
                        id="top-errors-graph",
                    )

                if self.session_attempts:
                    yield Static("session summary", id="top-errors-title")
                    table = DataTable(id="session-table")
                    table.add_columns("Try", "Acc", "KPM", "Err")
                    for i, att in enumerate(self.session_attempts, 1):
                        table.add_row(
                            str(i),
                            f"{att['accuracy']:.1f}%",
                            str(att["keystrokes"]),
                            str(att["errors"]),
                        )
                    # Add current successful attempt
                    table.add_row(
                        str(len(self.session_attempts) + 1),
                        f"{r['accuracy']:.1f}%",
                        str(r.get("keystrokes", "-")),
                        str(r.get("errors", "-")),
                    )
                    yield table

                yield Static(
                    "tab retry · h history · esc quit",
                    id="result-hints",
                )

    def _render_bar_graph(self, data: list[tuple[str, int]]) -> Text:
        from rich.cells import cell_len

        if not data:
            return Text()

        max_val = max(count for _, count in data)
        max_bar_width = 30

        # Determine necessary label cell width
        max_label_cell_len = 0
        for label, _ in data:
            max_label_cell_len = max(max_label_cell_len, cell_len(label))

        # Cap label width and add padding
        label_cell_width = min(max_label_cell_len, 15)

        t = Text()
        for i, (label, count) in enumerate(data):
            if i > 0:
                t.append("\n")

            # Truncate and pad label based on cell width
            curr_cell_len = cell_len(label)
            if curr_cell_len > label_cell_width:
                # Truncate label to fit within label_cell_width-1 cells and add '…'
                display_label = ""
                acc_len = 0
                for char in label:
                    char_len = cell_len(char)
                    if acc_len + char_len > label_cell_width - 1:
                        break
                    display_label += char
                    acc_len += char_len
                display_label += "…"
                padding = " " * (label_cell_width - cell_len(display_label))
            else:
                display_label = label
                padding = " " * (label_cell_width - curr_cell_len)

            bar_len = int((count / max_val) * max_bar_width) if max_val > 0 else 0
            if count > 0 and bar_len == 0:
                bar_len = 1

            bar = "█" * bar_len
            t.append(padding + display_label + " ", style=COL_DIM)
            t.append(bar, style=COL_ERROR)
            t.append(f" {count}", style=COL_TEXT)
        return t

    def action_retry(self) -> None:
        self.app.restart()  # type: ignore[attr-defined]

    def action_history(self) -> None:
        self.app.push_screen(HistoryScreen())

    def action_quit_app(self) -> None:
        self.app.exit()


# ── HistoryScreen ──────────────────────────────────────────────────────────


class HistoryScreen(Screen):
    """Past typing results."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    DEFAULT_CSS = (
        """
    HistoryScreen {
        align: center middle;
    }

    #history-container {
        width: 80;
        height: auto;
        max-height: 90%;
        align: center middle;
    }

    #history-title {
        width: 100%;
        text-align: center;
        color: """
        + COL_ACCENT
        + """;
        text-style: bold;
        margin-bottom: 1;
    }

    #history-table {
        width: 100%;
        height: auto;
        max-height: 20;
        background: """
        + COL_SUB_BG
        + """;
    }

    #history-empty {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
        padding: 2;
    }

    #history-hints {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
        margin-top: 1;
    }
    """
    )

    def compose(self) -> ComposeResult:
        results = load_results()

        with Center():
            with Vertical(id="history-container"):
                yield Static("History", id="history-title")

                if not results:
                    yield Static("No results yet — go type!", id="history-empty")
                else:
                    yield self._create_history_table(results)

                yield Static("esc back", id="history-hints")

    def _create_history_table(self, results: list[dict[str, Any]]) -> DataTable:
        """Create a table showing the last 50 typing results."""
        table = DataTable(id="history-table")
        table.add_columns("Date", "WPM", "Acc", "Lang", "Time", "Words")

        for r in reversed(results[-50:]):
            date_str = ""
            if "date" in r:
                try:
                    dt = datetime.fromisoformat(r["date"])
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(r["date"])[:16]

            table.add_row(
                date_str,
                f"{r.get('wpm', 0):.0f}",
                f"{r.get('accuracy', 0):.1f}%",
                r.get("lang", "?"),
                f"{r.get('time', 0):.0f}s",
                f"{r.get('correct', 0)}/{r.get('words', 0)}",
            )
        return table

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()


# ── MenuScreen ─────────────────────────────────────────────────────────────


class MenuScreen(Screen):
    """Initial menu to select test parameters."""

    DEFAULT_CSS = (
        """
    MenuScreen, ENSubMenu, KOSubMenu {
        align: center middle;
    }

    #menu-container {
        width: 40;
        height: auto;
        border: round """
        + COL_ACCENT
        + """;
        padding: 1 2;
        background: """
        + COL_SUB_BG
        + """;
    }

    #menu-title {
        width: 100%;
        text-align: center;
        color: """
        + COL_ACCENT
        + """;
        text-style: bold;
        margin-bottom: 1;
    }

    OptionList {
        background: """
        + COL_SUB_BG
        + """;
        border: none;
    }

    #menu-hints {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
        margin-top: 1;
    }
    """
    )

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("ttyping", id="menu-title")
                yield OptionList(
                    Option("English (영어)", id="en"),
                    Option("Korean (한글)", id="ko"),
                    Option("View History", id="history"),
                    Option("Quit", id="quit"),
                    id="menu-options",
                )
                yield Static("enter select · esc quit", id="menu-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "quit":
            app.exit_app()
        elif opt_id == "history":
            app.push_screen(HistoryScreen())
        elif opt_id == "en":
            app.push_screen(ENSubMenu())
        elif opt_id == "ko":
            app.push_screen(KOSubMenu())

    def action_quit_app(self) -> None:
        self.app.exit()


class ENSubMenu(Screen):
    """Submenu for English layout selection."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("English Typing", id="menu-title")
                yield OptionList(
                    Option("QWERTY", id="en_qwerty"),
                    Option("DVORAK", id="en_dvorak"),
                    Option("Back", id="back"),
                    id="menu-options",
                )
                yield Static("enter select · esc back", id="menu-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "en_qwerty":
            app.push_screen(PracticeMenu("en_qwerty"))
        elif opt_id == "en_dvorak":
            app.push_screen(PracticeMenu("en_dvorak"))

    def action_quit_app(self) -> None:
        self.app.pop_screen()


class KOSubMenu(Screen):
    """Submenu for Korean layout selection."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("한글 타이핑", id="menu-title")
                yield OptionList(
                    Option("두벌식 (2-set)", id="ko_2set"),
                    Option("세벌식 (3-set)", id="ko_3set"),
                    Option("Back", id="back"),
                    id="menu-options",
                )
                yield Static("enter select · esc back", id="menu-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "ko_2set":
            app.push_screen(PracticeMenu("ko_2set"))
        elif opt_id == "ko_3set":
            app.push_screen(PracticeMenu("ko_3set"))

    def action_quit_app(self) -> None:
        self.app.pop_screen()


class PracticeMenu(Screen):
    """Menu for selecting specific practice sets (hands, rows, etc.)."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    def __init__(self, layout_id: str) -> None:
        super().__init__()
        self.layout_id = layout_id

    def compose(self) -> ComposeResult:
        title = "Practice"
        if self.layout_id == "en_qwerty":
            title = "QWERTY Practice"
            options = [
                Option("Full Words (25)", id="full:25"),
                Option("Full Words (50)", id="full:50"),
                Option("Home Row", id="practice:home_row"),
                Option("Top Row", id="practice:top_row"),
                Option("Bottom Row", id="practice:bottom_row"),
                Option("Left Hand", id="practice:left_hand"),
                Option("Right Hand", id="practice:right_hand"),
                Option("Index Fingers (Left)", id="practice:left_index"),
                Option("Index Fingers (Right)", id="practice:right_index"),
            ]
        elif self.layout_id == "en_dvorak":
            title = "Dvorak Practice"
            options = [
                Option("Full Words (25)", id="full:25"),
                Option("Full Words (50)", id="full:50"),
                Option("Home Row", id="practice:home_row"),
                Option("Top Row", id="practice:top_row"),
                Option("Bottom Row", id="practice:bottom_row"),
                Option("Left Hand", id="practice:left_hand"),
                Option("Right Hand", id="practice:right_hand"),
            ]
        elif self.layout_id == "ko_2set":
            title = "두벌식 연습"
            options = [
                Option("전체 단어 (25)", id="full:25"),
                Option("전체 단어 (50)", id="full:50"),
                Option("가운데 줄 (Home Row)", id="practice:home_row"),
                Option("윗 줄 (Top Row)", id="practice:top_row"),
                Option("아랫 줄 (Bottom Row)", id="practice:bottom_row"),
                Option("왼손 (자음)", id="practice:left_hand"),
                Option("오른손 (모음)", id="practice:right_hand"),
            ]
        elif self.layout_id == "ko_3set":
            title = "세벌식 연습"
            options = [
                Option("전체 단어 (25)", id="full:25"),
                Option("전체 단어 (50)", id="full:50"),
                Option("가운데 줄 (Home Row)", id="practice:home_row"),
                Option("윗 줄 (Top Row)", id="practice:top_row"),
                Option("아랫 줄 (Bottom Row)", id="practice:bottom_row"),
                Option("왼손 (받침)", id="practice:left_hand"),
                Option("오른손 (초성/모음)", id="practice:right_hand"),
            ]
        else:
            options = [Option("25 words", id="full:25")]

        with Center():
            with Vertical(id="menu-container"):
                yield Static(title, id="menu-title")
                yield OptionList(*options, Option("Back", id="back"), id="menu-options")
                yield Static("enter select · esc back", id="menu-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id.startswith("full:"):
            words = int(opt_id.split(":")[1])
            app.start_custom_test(self.layout_id, words, None)
        elif opt_id.startswith("practice:"):
            set_name = opt_id.split(":")[1]
            # Use a prefix to tell get_words to use practice set
            app.start_custom_test(f"{self.layout_id}:{set_name}", 25, None)


class WordCountMenu(Screen):
    """Fallback menu for layouts without specific practice sets."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    def __init__(self, layout_id: str) -> None:
        super().__init__()
        self.layout_id = layout_id

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static(f"{self.layout_id.upper()}", id="menu-title")
                yield OptionList(
                    Option("25 words", id="25"),
                    Option("50 words", id="50"),
                    Option("100 words", id="100"),
                    Option("Back", id="back"),
                    id="menu-options",
                )
                yield Static("enter select · esc back", id="menu-hints")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        else:
            app.start_custom_test(self.layout_id, int(str(opt_id)), None)
