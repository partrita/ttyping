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
from textual.widgets import DataTable, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from ttyping.storage import (
    TypingResult,
    clear_results,
    delete_result_by_index,
    load_error_stats,
    load_results,
    save_result,
)

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
        Binding(key="tab", action="restart", description="Restart", priority=True),
        Binding(key="escape", action="go_back", description="Back", priority=True),
    ]

    DEFAULT_CSS = """
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
        padding: 0 1;
    }
    """

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
        self.total_keystrokes: int = 0
        self.total_errors: int = 0
        self.uncorrected_errors: int = 0
        self._timer_handle: Any | None = None  # textual.timer.Timer at runtime
        self._finished: bool = False
        self.errors: Counter[str] = Counter()  # Tracks characters missed
        self._cached_lines: list[list[int]] | None = None
        self._last_container_width: int = 0
        self._stats_widget: Static | None = None

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="typing-container"):
                yield Static("", id="stats")
                yield Static("", id="text-display")
                yield Input(id="input-area", password=False)

        yield Footer()

    def on_mount(self) -> None:
        self._stats_widget = self.query_one("#stats", Static)
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

        self.current_word_idx += 1
        self.current_input = ""

        if self.target_accuracy is not None:
            stats = self._get_current_stats()
            if stats["accuracy"] < self.target_accuracy:
                self._finished = True
                if self._timer_handle:
                    self._timer_handle.stop()

                # Notify and delay restart
                msg = (
                    f"Accuracy {stats['accuracy']:.0f}% below target "
                    f"{self.target_accuracy:.0f}% — restarting"
                )
                self.app.notify(
                    msg,
                    title="Too Low!",
                    severity="warning",
                    timeout=1.5,
                )

                result = TypingResult(
                    wpm=stats["wpm"],
                    gross_wpm=stats["gross_wpm"],
                    accuracy=stats["accuracy"],
                    time=stats["time"],
                    lang=self.lang,
                    words=self.current_word_idx,
                    correct=self.current_word_idx - self.uncorrected_errors,
                    keystrokes=stats["keystrokes"],
                    errors=stats["errors"],
                )

                self.set_timer(
                    0.5,
                    lambda: cast("TypingApp", self.app).reset_session_attempt(result),
                )
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

        result = TypingResult(
            wpm=round(net_wpm, 1),
            gross_wpm=round(gross_wpm, 1),
            accuracy=round(accuracy, 1),
            time=round(elapsed, 1),
            lang=self.lang,
            words=self.current_word_idx,
            correct=correct_words,
            keystrokes=self.total_keystrokes,
            errors=self.total_errors,
            top_char_errors=top_char_errors,
        )

        save_result(result)
        cast("TypingApp", self.app).show_result(result)

    # ── rendering ──────────────────────────────────────────────────────

    def _get_word_text(self, i: int) -> Text:
        word = self.words[i]
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
        return t

    def _wrap_words(self, container_width: int) -> tuple[list[list[int]], int]:
        """Wrap words into lines and return (lines, active_word_line_idx)."""
        if self._cached_lines and container_width == self._last_container_width:
            # Still need to find active_word_line_idx as it changes
            active_word_line_idx = 0
            for i, line in enumerate(self._cached_lines):
                if self.current_word_idx in line:
                    active_word_line_idx = i
                    break
            return self._cached_lines, active_word_line_idx

        lines = []
        current_line = []
        current_line_len = 0
        active_word_line_idx = 0

        for i, word in enumerate(self.words):
            word_len = len(word)
            if current_line_len + word_len + 1 > container_width:
                lines.append(current_line)
                current_line = []
                current_line_len = 0

            if i == self.current_word_idx:
                active_word_line_idx = len(lines)

            current_line.append(i)
            current_line_len += word_len + 1
        lines.append(current_line)

        self._cached_lines = lines
        self._last_container_width = container_width
        return lines, active_word_line_idx

    def _render_display(self) -> None:
        # Use a simple line-wrapping approach to show 3 lines:
        # 1. previous line
        # 2. current line (containing active word)
        # 3. next line
        container_width = 72  # matches #typing-container width minus padding

        lines, active_word_line_idx = self._wrap_words(container_width)

        # Build final display text (up to 3 lines)
        display_text = Text()
        start_line = max(0, active_word_line_idx - 1)
        end_line = min(len(lines), start_line + 3)

        # Adjust start_line if we're at the end
        if end_line - start_line < 3 and start_line > 0:
            start_line = max(0, end_line - 3)

        for l_idx in range(start_line, end_line):
            line = lines[l_idx]
            for i, word_idx in enumerate(line):
                if i > 0:
                    display_text.append(" ")
                display_text.append(self._get_word_text(word_idx))
            display_text.append("\n")

        self.query_one("#text-display", Static).update(display_text)

    def _update_stats(self) -> None:
        if self.start_time is None:
            if self._stats_widget is not None:
                self._stats_widget.update("")
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

        if self._stats_widget is not None:
            self._stats_widget.update(t)

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

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()


# ── ResultScreen ───────────────────────────────────────────────────────────


class ResultScreen(Screen):
    """Post-test results."""

    BINDINGS = [
        Binding(key="tab", action="retry", description="Retry", priority=True),
        Binding(key="h", action="history", description="History", show=False),
        Binding(key="escape", action="go_back", description="Back"),
        # Korean IME support (2-set)
        Binding(key="ㅗ", action="history", show=False),
    ]

    DEFAULT_CSS = """
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
    }

    .result-title {
        width: 100%;
        text-align: center;
        margin-top: 1;
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
    """

    def __init__(
        self,
        result: TypingResult,
        session_attempts: list[TypingResult] | None = None,
    ) -> None:
        super().__init__()
        self.result = result
        self.session_attempts = session_attempts or []

    def compose(self) -> ComposeResult:
        r = self.result
        with Center():
            with Vertical(id="result-container"):
                wpm_text = Text()
                wpm_text.append(f"{r.wpm:.0f}", style=f"bold {COL_ACCENT}")
                wpm_text.append(" wpm", style=COL_DIM)
                yield Static(wpm_text, classes="result-big")
                acc_text = Text()
                acc_text.append(f"{r.accuracy:.1f}%", style=f"bold {COL_TEXT}")
                acc_text.append(" accuracy", style=COL_DIM)
                yield Static(acc_text, classes="result-big")
                detail = Text()
                detail.append(f"{r.time:.1f}s", style=COL_TEXT)
                detail.append(f"  ·  {r.correct}/{r.words} words", style=COL_DIM)
                detail.append(f"  ·  {r.lang}", style=COL_DIM)
                yield Static(detail, classes="result-detail")
                if r.top_char_errors:
                    yield Static("top missed characters", classes="result-title")
                    yield Static(
                        self._render_bar_graph(r.top_char_errors),
                        id="top-errors-graph",
                    )
                if self.session_attempts:
                    yield Static("session summary", classes="result-title")
                    table = DataTable(id="session-table")
                    table.add_columns("Try", "Acc", "WPM", "Err")
                    for i, att in enumerate(self.session_attempts, 1):
                        table.add_row(
                            str(i),
                            f"{att.accuracy:.1f}%",
                            str(att.keystrokes),
                            str(att.errors),
                        )
                    # Add current successful attempt
                    table.add_row(
                        str(len(self.session_attempts) + 1),
                        f"{r.accuracy:.1f}%",
                        str(r.keystrokes),
                        str(r.errors),
                    )
                    yield table

        yield Footer()

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

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()


# ── ConfirmDeleteScreen ────────────────────────────────────────────────────


class ConfirmDeleteScreen(Screen):
    """Confirmation dialog before deleting all history."""

    DEFAULT_CSS = (
        """
    ConfirmDeleteScreen {
        align: center middle;
        background: rgba(0,0,0,0.7);
    }

    #confirm-box {
        width: 50;
        height: auto;
        border: round """
        + COL_ERROR
        + """;
        padding: 2 4;
        background: """
        + COL_SUB_BG
        + """;
        align: center middle;
    }

    #confirm-title {
        width: 100%;
        text-align: center;
        color: """
        + COL_ERROR
        + """;
        text-style: bold;
        margin-bottom: 1;
    }

    #confirm-body {
        width: 100%;
        text-align: center;
        color: """
        + COL_TEXT
        + """;
        margin-bottom: 1;
    }

    #confirm-hints {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
    }
    """
    )

    BINDINGS = [
        Binding(key="y", action="confirm", description="Yes"),
        Binding(key="n", action="cancel", description="No"),
        Binding(key="escape", action="cancel", description="Cancel"),
        # Korean IME support (2-set)
        Binding(key="ㅛ", action="confirm", show=False),
        Binding(key="ㅜ", action="cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="confirm-box"):
                yield Static("Delete History", id="confirm-title")
                yield Static(
                    "This will permanently delete ALL typing history"
                    " and error statistics.",
                    id="confirm-body",
                )

        yield Footer()

    def action_confirm(self) -> None:
        clear_results()
        # Pop both this screen and the HistoryScreen
        self.app.pop_screen()  # pop ConfirmDeleteScreen
        self.app.pop_screen()  # pop HistoryScreen

    def action_cancel(self) -> None:
        self.app.pop_screen()


# ── LineChart ──────────────────────────────────────────────────────────────


class LineChart(Static):
    """A simple line chart using braille characters."""

    DEFAULT_CSS = """
    LineChart {
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        data: list[float],
        color: str,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(**kwargs)
        self.chart_data = data
        self.chart_color = color

    def on_resize(self, event: events.Resize) -> None:
        self._update_chart(event.size.width)

    def on_mount(self) -> None:
        self._update_chart(self.size.width if self.size.width > 0 else 40)

    def _update_chart(self, width: int) -> None:
        if width <= 0 or not self.chart_data:
            self.update("")
            return

        data = self.chart_data
        if len(data) == 1:
            data = [data[0], data[0]]

        # Sample 2 * width points for braille (2 dots wide per char)
        points = 2 * width
        sampled = []
        for i in range(points):
            idx = (i / (points - 1)) * (len(data) - 1)
            idx_int = int(idx)
            rem = idx - idx_int
            if idx_int + 1 < len(data):
                val = data[idx_int] * (1 - rem) + data[idx_int + 1] * rem
            else:
                val = data[idx_int]
            sampled.append(val)

        min_v = min(sampled)
        max_v = max(sampled)
        extent = max_v - min_v if max_v > min_v else 1

        # Braille dot values for 4 rows
        # From bottom to top to match cartesian plane
        left_dots = [0x40, 0x04, 0x02, 0x01]
        right_dots = [0x80, 0x20, 0x10, 0x08]

        res = []
        for i in range(width):
            l_val = sampled[i * 2]
            r_val = sampled[i * 2 + 1]
            l_row = int((l_val - min_v) / extent * 3.99)
            r_row = int((r_val - min_v) / extent * 3.99)

            char_val = 0x2800 | left_dots[l_row] | right_dots[r_row]

            # Connect the dots with a vertical line to make it continuous
            start = min(l_row, r_row)
            end = max(l_row, r_row)
            for row in range(start, end + 1):
                char_val |= left_dots[row]
                char_val |= right_dots[row]

            res.append(chr(char_val))

        self.update(Text("".join(res), style=self.chart_color))


# ── HistoryScreen ──────────────────────────────────────────────────────────


class HistoryScreen(Screen):
    """Past typing results."""

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(
            key="d",
            action="delete_selected",
            description="Delete Selected",
            priority=True,
        ),
        Binding(key="D", action="delete_all", description="Delete All", priority=True),
        # Korean IME support (2-set)
        Binding(key="ㅇ", action="delete_selected", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        # Maps display row index (newest-first) -> original storage index
        self._row_to_storage_idx: list[int] = []

    DEFAULT_CSS = """
    HistoryScreen {
        align: center middle;
    }

    #history-container {
        width: 82;
        height: auto;
        max-height: 90%;
        align: center middle;
    }

    #history-title {
        width: 100%;
        text-align: center;
        text-style: bold;
    }

    #history-stats {
        width: 100%;
        text-align: center;
        margin-bottom: 0;
    }

    .chart-container {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding: 0 4;
    }

    .chart-title {
        width: 100%;
        text-align: center;
        text-style: dim;
    }

    #history-table {
        width: 100%;
        height: auto;
        max-height: 18;
        margin-top: 2;
    }

    .history-hint {
        width: 100%;
        text-align: center;
        margin-top: 1;
        text-style: dim;
    }
    """

    def compose(self) -> ComposeResult:
        results = load_results()
        n = len(results)
        # Build newest-first mapping (up to 50)
        display_count = min(n, 50)
        # storage indices newest-first
        self._row_to_storage_idx = list(range(n - 1, n - 1 - display_count, -1))
        with Center():
            with Vertical(id="history-container"):
                yield Static("History", id="history-title")
                if not results:
                    yield Static("No results yet — go type!", id="history-empty")
                else:
                    avg_wpm = sum(r.wpm for r in results) / n
                    yield Static(
                        f"Tests: {n} · Avg WPM: {avg_wpm:.1f}",
                        id="history-stats",
                    )

                    recent_results = results[-display_count:]
                    with Vertical(classes="chart-container"):
                        yield Static("wpm trend", classes="chart-title")
                        yield LineChart(
                            [r.wpm for r in recent_results],
                            color=COL_ACCENT,
                        )

                    with Vertical(classes="chart-container"):
                        yield Static("accuracy trend", classes="chart-title")
                        yield LineChart(
                            [r.accuracy for r in recent_results],
                            color=COL_TEXT,
                        )

                    yield self._create_history_table(results, self._row_to_storage_idx)

        yield Footer()

    def _create_history_table(
        self,
        results: list[TypingResult],
        row_indices: list[int],
    ) -> DataTable:
        """Create a table showing the last 50 typing results (newest first)."""
        table: DataTable[str] = DataTable(id="history-table")
        table.cursor_type = "row"
        table.add_columns("#", "Date", "WPM", "Acc", "Lang", "Time", "Words")

        for display_idx, storage_idx in enumerate(row_indices, 1):
            r = results[storage_idx]
            date_str = ""
            if r.date:
                try:
                    dt = datetime.fromisoformat(r.date)
                    date_str = dt.strftime("%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(r.date)[:11]

            table.add_row(
                str(display_idx),
                date_str,
                f"{r.wpm:.0f}",
                f"{r.accuracy:.1f}%",
                r.lang,
                f"{r.time:.0f}s",
                f"{r.correct}/{r.words}",
            )
        return table

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()

    def action_delete_selected(self) -> None:
        """Delete the row currently highlighted in the table."""
        try:
            table = self.query_one("#history-table", DataTable)
        except Exception:
            return
        row_idx = table.cursor_row  # 0-based display index
        if 0 <= row_idx < len(self._row_to_storage_idx):
            storage_idx = self._row_to_storage_idx[row_idx]
            delete_result_by_index(storage_idx)
            # Rebuild screen
            self.app.pop_screen()
            self.app.push_screen(HistoryScreen())

    def action_delete_all(self) -> None:
        self.app.push_screen(ConfirmDeleteScreen())


# ── MenuScreen ─────────────────────────────────────────────────────────────


class ActionSelectMixin:
    """Mixin to provide action_select for screens with an OptionList."""

    def action_select(self) -> None:
        """Trigger selection on the OptionList."""
        try:
            ol = self.query_one("#menu-options", OptionList)  # type: ignore[attr-defined]
            ol.action_select()
        except Exception:
            pass


class MenuScreen(ActionSelectMixin, Screen):
    """Initial menu to select test parameters."""

    DEFAULT_CSS = """
    MenuScreen {
        align: center middle;
    }

    #menu-container {
        width: 44;
        height: auto;
        padding: 1 2;
        align: center middle;
    }

    #menu-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    OptionList {
        border: none;
        height: auto;
        max-height: 15;
        text-align: center;
    }

    .about-text {
        width: 100%;
        text-align: center;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="e", action="select_en", description="English", show=False),
        Binding(key="k", action="select_ko", description="Korean", show=False),
        Binding(key="w", action="select_weak", description="Weak Analysis", show=False),
        Binding(key="h", action="select_history", description="History", show=False),
        Binding(key="o", action="select_options", description="Options", show=False),
        Binding(key="p", action="select_code", description="Code", show=False),
        Binding(key="escape", action="quit_app", description="Quit"),
        # Korean IME support (2-set)
        Binding(key="ㄷ", action="select_en", show=False),
        Binding(key="ㅏ", action="select_ko", show=False),
        Binding(key="ㅈ", action="select_weak", show=False),
        Binding(key="ㅗ", action="select_history", show=False),
        Binding(key="ㅐ", action="select_options", show=False),
        Binding(key="ㅔ", action="select_code", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("ttyping", id="menu-title")
                yield OptionList(
                    Option(
                        Text.from_markup("English(영어)"),
                        id="en",
                    ),
                    Option(
                        Text.from_markup("Korean(한국어)"),
                        id="ko",
                    ),
                    Option(
                        Text.from_markup("Code(코드)"),
                        id="code",
                    ),
                    Option(
                        Text.from_markup("Weak word(약점 단어 연습)"),
                        id="weakness",
                    ),
                    Option(
                        Text.from_markup("View History(기록 보기)"),
                        id="history",
                    ),
                    Option(
                        Text.from_markup("Options"),
                        id="options",
                    ),
                    Option(
                        Text.from_markup("Quit"),
                        id="quit",
                    ),
                    id="menu-options",
                )

        yield Footer()

    def on_resume(self) -> None:
        pass  # no dynamic labels needed

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "quit":
            app.exit()
        elif opt_id == "history":
            app.push_screen(HistoryScreen())
        elif opt_id == "weakness":
            app.push_screen(WeaknessScreen())
        elif opt_id == "options":
            app.push_screen(OptionsScreen())
        elif opt_id == "en":
            app.push_screen(ENSubMenu())
        elif opt_id == "ko":
            app.push_screen(KOSubMenu())
        elif opt_id == "code":
            app.push_screen(CodeSubMenu())

    def action_select_en(self) -> None:
        self.app.push_screen(ENSubMenu())

    def action_select_ko(self) -> None:
        self.app.push_screen(KOSubMenu())

    def action_select_code(self) -> None:
        self.app.push_screen(CodeSubMenu())

    def action_select_weak(self) -> None:
        self.app.push_screen(WeaknessScreen())

    def action_select_history(self) -> None:
        self.app.push_screen(HistoryScreen())

    def action_select_options(self) -> None:
        self.app.push_screen(OptionsScreen())

    def action_quit_app(self) -> None:
        self.app.exit()


class CodeSubMenu(ActionSelectMixin, Screen):
    """Submenu for Code language selection."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Code Typing", id="menu-title")
                yield OptionList(
                    Option("Python", id="python"),
                    Option("Rust", id="rust"),
                    Option("R", id="r"),
                    Option("JavaScript", id="javascript"),
                    Option("Julia", id="julia"),
                    Option("Typst", id="typst"),
                    Option("Markdown", id="markdown"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id in (
            "markdown",
            "javascript",
            "julia",
            "python",
            "r",
            "rust",
            "typst",
        ):
            app.start_custom_test(opt_id, app._word_count, app._duration)

    def action_go_back(self) -> None:
        self.app.pop_screen()


class ENSubMenu(ActionSelectMixin, Screen):
    """Submenu for English layout selection."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("English Typing", id="menu-title")
                yield OptionList(
                    Option("Qwerty", id="en_qwerty"),
                    Option("Dvorak", id="en_dvorak"),
                    Option("Colemak", id="en_colemak"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "en_qwerty":
            app.push_screen(PracticeMenu("en_qwerty"))
        elif opt_id == "en_dvorak":
            app.push_screen(PracticeMenu("en_dvorak"))
        elif opt_id == "en_colemak":
            app.push_screen(PracticeMenu("en_colemak"))

    def action_go_back(self) -> None:
        self.app.pop_screen()


class KOSubMenu(ActionSelectMixin, Screen):
    """Submenu for Korean layout selection."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

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

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "ko_2set":
            app.push_screen(PracticeMenu("ko_2set"))
        elif opt_id == "ko_3set":
            app.push_screen(PracticeMenu("ko_3set"))

    def action_go_back(self) -> None:
        self.app.pop_screen()


class PracticeMenu(ActionSelectMixin, Screen):
    """Menu for selecting specific practice sets (hands, rows, etc.)."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS
    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def __init__(self, layout_id: str) -> None:
        super().__init__()
        self.layout_id = layout_id

    def compose(self) -> ComposeResult:
        title = "Practice"
        if self.layout_id == "en_qwerty":
            title = "QWERTY Practice"
            options = [
                Option("Words", id="full:words"),
                Option("Sentences", id="full:sentences"),
                Option("Lorem Ipsum", id="full:lorem_ipsum"),
                Option("Home Row", id="practice:home_row"),
                Option("Top Row", id="practice:top_row"),
                Option("Bottom Row", id="practice:bottom_row"),
                Option("Number Row (1-0)", id="practice:number_row"),
                Option("Symbol Row (!@#...)", id="practice:symbol_row"),
                Option("Left Hand", id="practice:left_hand"),
                Option("Right Hand", id="practice:right_hand"),
                Option("Left Index", id="practice:left_index"),
                Option("Right Index", id="practice:right_index"),
                Option("Left Middle", id="practice:left_middle"),
                Option("Right Middle", id="practice:right_middle"),
                Option("Left Ring", id="practice:left_ring"),
                Option("Right Ring", id="practice:right_ring"),
                Option("Left Pinky", id="practice:left_pinky"),
                Option("Right Pinky", id="practice:right_pinky"),
            ]
        elif self.layout_id == "en_dvorak":
            title = "Dvorak Practice"
            options = [
                Option("Words", id="full:words"),
                Option("Sentences", id="full:sentences"),
                Option("Lorem Ipsum", id="full:lorem_ipsum"),
                Option("Home Row", id="practice:home_row"),
                Option("Top Row", id="practice:top_row"),
                Option("Bottom Row", id="practice:bottom_row"),
                Option("Number Row (1-0)", id="practice:number_row"),
                Option("Symbol Row (!@#...)", id="practice:symbol_row"),
                Option("Left Hand", id="practice:left_hand"),
                Option("Right Hand", id="practice:right_hand"),
                Option("Left Index", id="practice:left_index"),
                Option("Right Index", id="practice:right_index"),
                Option("Left Middle", id="practice:left_middle"),
                Option("Right Middle", id="practice:right_middle"),
                Option("Left Ring", id="practice:left_ring"),
                Option("Right Ring", id="practice:right_ring"),
                Option("Left Pinky", id="practice:left_pinky"),
                Option("Right Pinky", id="practice:right_pinky"),
            ]
        elif self.layout_id == "en_colemak":
            title = "Colemak Practice"
            options = [
                Option("Words", id="full:words"),
                Option("Sentences", id="full:sentences"),
                Option("Lorem Ipsum", id="full:lorem_ipsum"),
                Option("Home Row", id="practice:home_row"),
                Option("Top Row", id="practice:top_row"),
                Option("Bottom Row", id="practice:bottom_row"),
                Option("Number Row (1-0)", id="practice:number_row"),
                Option("Symbol Row (!@#...)", id="practice:symbol_row"),
                Option("Left Hand", id="practice:left_hand"),
                Option("Right Hand", id="practice:right_hand"),
                Option("Left Index", id="practice:left_index"),
                Option("Right Index", id="practice:right_index"),
                Option("Left Middle", id="practice:left_middle"),
                Option("Right Middle", id="practice:right_middle"),
                Option("Left Ring", id="practice:left_ring"),
                Option("Right Ring", id="practice:right_ring"),
                Option("Left Pinky", id="practice:left_pinky"),
                Option("Right Pinky", id="practice:right_pinky"),
            ]
        elif self.layout_id == "ko_2set":
            title = "두벌식 연습"
            options = [
                Option("단어", id="full:words"),
                Option("짧은 글", id="full:sentences"),
                Option("로렘 입숨", id="full:lorem_ipsum"),
                Option("가운데 줄", id="practice:home_row"),
                Option("윗 줄", id="practice:top_row"),
                Option("아랫 줄", id="practice:bottom_row"),
                Option("숫자 줄 (1-0)", id="practice:number_row"),
                Option("특수문자 (!@#...)", id="practice:symbol_row"),
                Option("왼손 자음", id="practice:left_hand"),
                Option("오른손 모음", id="practice:right_hand"),
                Option("왼손 검지", id="practice:left_index"),
                Option("오른손 검지", id="practice:right_index"),
                Option("왼손 중지", id="practice:left_middle"),
                Option("오른손 중지", id="practice:right_middle"),
                Option("왼손 약지", id="practice:left_ring"),
                Option("오른손 약지", id="practice:right_ring"),
                Option("왼손 새끼", id="practice:left_pinky"),
                Option("오른손 새끼", id="practice:right_pinky"),
            ]
        elif self.layout_id == "ko_3set":
            title = "세벌식 연습"
            options = [
                Option("단어", id="full:words"),
                Option("짧은 글", id="full:sentences"),
                Option("로렘 입숨", id="full:lorem_ipsum"),
                Option("가운데 줄", id="practice:home_row"),
                Option("윗 줄", id="practice:top_row"),
                Option("아랫 줄", id="practice:bottom_row"),
                Option("숫자 줄 (1-0)", id="practice:number_row"),
                Option("특수문자 (!@#...)", id="practice:symbol_row"),
                Option("왼손 자음", id="practice:left_hand"),
                Option("오른손 모음", id="practice:right_hand"),
                Option("왼손 검지", id="practice:left_index"),
                Option("오른손 검지", id="practice:right_index"),
                Option("왼손 중지", id="practice:left_middle"),
                Option("오른손 중지", id="practice:right_middle"),
                Option("왼손 약지", id="practice:left_ring"),
                Option("오른손 약지", id="practice:right_ring"),
                Option("왼손 새끼", id="practice:left_pinky"),
                Option("오른손 새끼", id="practice:right_pinky"),
            ]
        else:
            options = [Option("25 words", id="full:25")]
        with Center():
            with Vertical(id="menu-container"):
                yield Static(title, id="menu-title")
                yield OptionList(
                    *options,
                    Option("Back", id="back"),
                    id="menu-options",
                    name="Practice Set Selection",
                )

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "full:words":
            app.start_custom_test(self.layout_id, app._word_count, app._duration)
        elif opt_id == "full:sentences":
            lang = "ko_sentences" if "ko" in self.layout_id else "en_sentences"
            app.start_custom_test(lang, app._word_count, app._duration)
        elif opt_id == "full:lorem_ipsum":
            lang = "ko_lorem_ipsum" if "ko" in self.layout_id else "en_lorem_ipsum"
            app.start_custom_test(lang, app._word_count, app._duration)
        elif opt_id.startswith("practice:"):
            set_name = opt_id.split(":")[1]
            # Use a prefix to tell get_words to use practice set
            app.start_custom_test(
                f"{self.layout_id}:{set_name}", app._word_count, app._duration
            )

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WordCountMenu(ActionSelectMixin, Screen):
    """Fallback menu for layouts without specific practice sets."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def __init__(self, layout_id: str) -> None:
        super().__init__()
        self.layout_id = layout_id

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static(f"{self.layout_id.upper()}", id="menu-title")
                yield OptionList(
                    Option("Words", id=f"{self.layout_id}:words"),
                    Option("Sentences", id=f"{self.layout_id}:sentences"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id.endswith(":words"):
            app.start_custom_test(self.layout_id, app._word_count, app._duration)
        elif opt_id.endswith(":sentences"):
            lang = "ko_sentences" if "ko" in self.layout_id else "en_sentences"
            app.start_custom_test(lang, app._word_count, app._duration)

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()


class AccuracyMenu(ActionSelectMixin, Screen):
    DEFAULT_CSS = MenuScreen.DEFAULT_CSS
    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = app._target_accuracy
        if current is None:
            current_label = "None (Free Practice)"
        else:
            current_label = f"{int(current)}%"
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Target Accuracy", id="menu-title")
                yield Static(
                    f"Current: {current_label}",
                    classes="about-text",
                )
                yield OptionList(
                    Option("None (Free Practice)", id="none"),
                    Option("80%", id="80"),
                    Option("90%", id="90"),
                    Option("95%", id="95"),
                    Option("100% (No Mistakes)", id="100"),
                    id="menu-options",
                )

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from ttyping.storage import load_config, save_config

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "none":
            app._target_accuracy = None
        else:
            app._target_accuracy = float(opt_id)

        # Persist to config
        cfg = load_config()
        cfg["target_accuracy"] = app._target_accuracy
        save_config(cfg)

        label = (
            "None" if app._target_accuracy is None else f"{int(app._target_accuracy)}%"
        )
        app.notify(f"Accuracy set to {label}", title="Saved", timeout=2)
        app.pop_screen()

    def action_quit_app(self) -> None:
        self.app.exit()

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def action_go_back(self) -> None:
        self.app.pop_screen()


class OptionsScreen(ActionSelectMixin, Screen):
    """Options submenu: Words, Time, Accuracy, Theme, About."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def _get_labels(self) -> tuple[str, str, str, str]:
        app = cast("TypingApp", self.app)
        words_label = str(app._word_count)
        time_label = "Off" if app._duration is None else f"{app._duration}s"
        acc = app._target_accuracy
        acc_label = "None" if acc is None else f"{int(acc)}%"
        theme_label = "Dark" if app.theme == "textual-dark" else "Light"
        return words_label, time_label, acc_label, theme_label

    def compose(self) -> ComposeResult:
        words_label, time_label, acc_label, theme_label = self._get_labels()
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Options", id="menu-title")
                yield OptionList(
                    Option(f"Words: {words_label}", id="words"),
                    Option(f"Time: {time_label}", id="time"),
                    Option(f"Accuracy: {acc_label}", id="accuracy"),
                    Option(f"Theme: {theme_label}", id="theme"),
                    Option("About", id="about"),
                    id="menu-options",
                )

        yield Footer()

    def on_resume(self) -> None:
        """Refresh labels when returning from a nested screen."""
        self.refresh(recompose=True)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        if opt_id == "words":
            app.push_screen(WordCountInputScreen())
        elif opt_id == "time":
            app.push_screen(TimeLimitInputScreen())
        elif opt_id == "accuracy":
            app.push_screen(AccuracyMenu())
        elif opt_id == "theme":
            app.push_screen(ThemeScreen())
        elif opt_id == "about":
            app.push_screen(AboutScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()


class ThemeScreen(ActionSelectMixin, Screen):
    """Select dark or light theme."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = "Dark" if app.theme == "textual-dark" else "Light"
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Theme", id="menu-title")
                yield Static(f"Current: {current}", classes="about-text")
                yield OptionList(
                    Option("🌙  Dark", id="dark"),
                    Option("☀️  Light", id="light"),
                    id="menu-options",
                )

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from ttyping.storage import load_config, save_config

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        app.theme = "textual-dark" if opt_id == "dark" else "textual-light"

        cfg = load_config()
        cfg["theme"] = opt_id
        save_config(cfg)

        theme_label = "Dark" if opt_id == "dark" else "Light"
        app.notify(f"Theme set to {theme_label}", title="Saved", timeout=2)
        app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class AboutScreen(Screen):
    """About ttyping description screen."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="enter", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        about_text = [
            "# ttyping",
            "",
            "A minimal, monkeytype-inspired terminal typing test.",
            "",
            "Practice layouts, track WPM/accuracy, and",
            "target specific finger muscle memory.",
            "",
            "Built with Python & Textual.",
            "",
            "---",
            "Apache License 2.0",
        ]
        with Center():
            with Vertical(id="menu-container"):
                yield Static("About ttyping", id="menu-title")
                yield Static("\n".join(about_text), classes="about-text")

        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WordCountInputScreen(Screen):
    """Input screen to set the default word count."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="submit", description="Save"),
        Binding(key="escape", action="go_back", description="Cancel"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Set Word Count", id="menu-title")
                yield Input(
                    value=str(app._word_count),
                    placeholder="Number of words (e.g. 25)",
                    id="words-input",
                    type="integer",
                    max_length=3,
                )

        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear the error border when the user types."""
        self.query_one("#words-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        from ttyping.storage import load_config, save_config

        value = event.value.strip()
        try:
            count = int(value)
            if not 1 <= count <= 200:
                raise ValueError
        except ValueError:
            self.query_one(
                "#words-input", Input
            ).border_title = "⚠ Enter a number from 1 to 200"
            return

        app = cast("TypingApp", self.app)
        app._word_count = count
        cfg = load_config()
        cfg["word_count"] = count
        save_config(cfg)
        app.notify(f"Words set to {count}", title="Saved", timeout=2)
        app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class TimeLimitInputScreen(Screen):
    """Input screen to set the default time limit in seconds."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="submit", description="Save"),
        Binding(key="escape", action="go_back", description="Cancel"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = str(app._duration) if app._duration else ""
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Set Time Limit", id="menu-title")
                yield Input(
                    value=current,
                    placeholder="Seconds (leave blank for no limit)",
                    id="time-input",
                    type="integer",
                    max_length=4,
                )

        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear the error border when the user types."""
        self.query_one("#time-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        from ttyping.storage import load_config, save_config

        value = event.value.strip()

        if not value:
            duration: int | None = None
        else:
            try:
                duration = int(value)
                if not 1 <= duration <= 3600:
                    raise ValueError
            except ValueError:
                self.query_one(
                    "#time-input", Input
                ).border_title = "⚠ Enter a number from 1 to 3600"
                return

        app = cast("TypingApp", self.app)
        app._duration = duration
        cfg = load_config()
        cfg["duration"] = duration
        save_config(cfg)
        msg = "Time limit cleared" if duration is None else f"Time set to {duration}s"
        app.notify(msg, title="Saved", timeout=2)
        app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WeaknessScreen(ActionSelectMixin, Screen):
    """Weak Key Analysis — aggregated error stats with targeted drill."""

    DEFAULT_CSS = """
    WeaknessScreen {
        align: center middle;
    }

    #weakness-container {
        width: 70;
        height: auto;
        align: center middle;
        padding: 1 2;
    }

    #weakness-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .weakness-section {
        width: 100%;
        text-align: center;
        margin-top: 1;
    }

    #weakness-table {
        width: 100%;
        height: auto;
        max-height: 10;
        margin-top: 0;
    }

    #weakness-graph {
        width: 100%;
        margin-top: 0;
        content-align: center middle;
    }

    #weakness-options {
        width: 100%;
        margin-top: 1;
        border: none;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        from ttyping.words import (
            FINGER_LABELS,
            FINGER_LABELS_KO,
            chars_to_finger,
        )

        stats = load_error_stats()
        app = cast("TypingApp", self.app)
        layout = app._lang
        is_ko = layout.startswith("ko")
        labels = FINGER_LABELS_KO if is_ko else FINGER_LABELS
        with Center():
            with Vertical(id="weakness-container"):
                yield Static("Weakness Analysis", id="weakness-title")
                if not stats:
                    yield Static(
                        "Complete more typing tests to build analysis.",
                        classes="weakness-section",
                    )
                else:
                    # Top 10 chars by cumulative error count
                    sorted_chars = sorted(
                        stats.items(), key=lambda x: x[1], reverse=True
                    )[:10]
                    top_chars_str = "".join(c for c, _ in sorted_chars)

                    # Map to fingers
                    finger_map = chars_to_finger(layout, top_chars_str)
                    finger_totals: dict[str, int] = {
                        f: sum(stats.get(c, 0) for c in cs)
                        for f, cs in finger_map.items()
                    }

                    sorted_fingers = sorted(
                        finger_totals.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )

                    # Action options (Practice Menu)
                    options: list[Option] = [
                        Option("Practice All Weak Keys ▶", id="drill:all"),
                    ]
                    for finger, total in sorted_fingers[:3]:
                        finger_chars = "".join(finger_map.get(finger, []))
                        if finger_chars:
                            label = labels.get(finger, finger)
                            options.append(
                                Option(
                                    f"Practice {label} ({total} err) ▶",
                                    id=f"drill:{finger}",
                                )
                            )
                    options.append(Option("← Back", id="back"))

                    yield OptionList(*options, id="menu-options")

                    # Finger breakdown table
                    yield Static("▸ Errors by Finger", classes="weakness-section")
                    table: DataTable[str] = DataTable(id="weakness-table")
                    table.add_columns("Finger", "Weak Keys", "Errors")
                    for finger, total in sorted_fingers:
                        chars_list = finger_map.get(finger, [])
                        chars_display = " ".join(chars_list[:8])
                        label = labels.get(finger, finger)
                        table.add_row(label, chars_display, str(total))
                    yield table

                    # Top missed chars bar chart
                    yield Static("▸ Top Missed Keys", classes="weakness-section")
                    yield Static(
                        self._render_char_bars(sorted_chars[:6]),
                        id="weakness-graph",
                    )
        yield Footer()

    def _render_char_bars(self, data: list[tuple[str, int]]) -> Text:
        from rich.cells import cell_len

        if not data:
            return Text()
        max_val = max(c for _, c in data)
        max_bar = 22
        t = Text()
        for char, count in data:
            bar_len = int((count / max(max_val, 1)) * max_bar)
            pad = " " * (4 - cell_len(char))
            t.append(pad + char + " ", style=COL_TEXT)
            t.append("█" * bar_len, style=COL_ERROR)
            t.append(f" {count}\n", style=COL_DIM)
        return t

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from ttyping.words import chars_to_finger

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        layout = app._lang
        stats = load_error_stats()

        if opt_id == "back":
            app.pop_screen()
            return

        sorted_chars = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]
        top_chars_str = "".join(c for c, _ in sorted_chars)

        if opt_id == "drill:all":
            app.start_weak_drill(layout, top_chars_str)
        elif opt_id.startswith("drill:"):
            finger = opt_id[len("drill:") :]
            finger_map = chars_to_finger(layout, top_chars_str)
            weak_chars = "".join(finger_map.get(finger, []))
            if weak_chars:
                app.start_weak_drill(layout, weak_chars)

    def action_go_back(self) -> None:
        self.app.pop_screen()
