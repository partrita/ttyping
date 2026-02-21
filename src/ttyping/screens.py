"""Screens for ttyping: typing test, results, and history."""

from __future__ import annotations

from collections import Counter
import time
from datetime import datetime, timezone
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static

from ttyping.storage import load_results, save_result

# ── Colours (monkeytype-inspired) ─────────────────────────────────────────

COL_BG = "#323437"
COL_DIM = "#646669"
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
        color: """ + COL_ACCENT + """;
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
        border: round """ + COL_DIM + """;
        background: """ + COL_SUB_BG + """;
        color: """ + COL_TEXT + """;
        padding: 0 1;
    }

    #input-area:focus {
        border: round """ + COL_ACCENT + """;
    }

    #hints {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-align: center;
        color: """ + COL_DIM + """;
        margin-top: 1;
    }
    """

    def __init__(self, words: list[str], lang: str = "en", duration: int | None = None) -> None:
        super().__init__()
        self.words = words
        self.lang = lang
        self.duration = duration
        self.current_word_idx = 0
        self.current_input = ""
        self.word_correct: list[bool | None] = [None] * len(words)
        self.start_time: float | None = None
        self.total_correct_chars = 0
        self.total_keystrokes = 0
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

        # Space → complete current word
        if value.endswith(" "):
            self._complete_word(value[:-1])
            event.input.value = ""
            return

        # Track character errors as they happen
        if value and self.current_word_idx < len(self.words):
            target_word = self.words[self.current_word_idx]
            last_typed_idx = len(value) - 1
            if last_typed_idx < len(target_word):
                if value[last_typed_idx] != target_word[last_typed_idx]:
                    # User typed the wrong character
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
        if event.key == "enter":
            event.prevent_default()
            inp = self.query_one("#input-area", Input)
            if inp.value:
                self._complete_word(inp.value)
                inp.value = ""

    # ── word completion ────────────────────────────────────────────────

    def _complete_word(self, typed: str) -> None:
        target = self.words[self.current_word_idx]
        is_correct = typed == target

        self.word_correct[self.current_word_idx] = is_correct
        self.total_keystrokes += len(typed) + 1  # +1 for space/enter
        if is_correct:
            self.total_correct_chars += len(target) + 1
        else:
            self.word_errors[target] += 1

        self.current_word_idx += 1
        self.current_input = ""

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
        wpm = (self.total_correct_chars / 5) / minutes if minutes > 0 else 0
        accuracy = (
            (self.total_correct_chars / max(self.total_keystrokes, 1)) * 100
        )
        correct_words = sum(1 for w in self.word_correct if w is True)

        # Get top errors
        top_char_errors = self.errors.most_common(5)
        top_word_errors = self.word_errors.most_common(5)

        result: dict[str, Any] = {
            "wpm": round(wpm, 1),
            "accuracy": round(accuracy, 1),
            "time": round(elapsed, 1),
            "lang": self.lang,
            "words": self.current_word_idx,  # Number of words attempted
            "correct": correct_words,
            "top_char_errors": top_char_errors,
            "top_word_errors": top_word_errors,
        }

        save_result(result)
        self.app.show_result(result)  # type: ignore[attr-defined]

    # ── rendering ──────────────────────────────────────────────────────

    def _render_display(self) -> None:
        text = Text()
        # Only show a window of words around current index to keep it clean,
        # especially for long timed tests.
        start = max(0, self.current_word_idx - 10)
        end = min(len(self.words), self.current_word_idx + 20)

        for i in range(start, end):
            word = self.words[i]
            if i > start:
                text.append(" ")

            if i < self.current_word_idx:
                # Past word
                if self.word_correct[i]:
                    text.append(word, style=f"dim {COL_CORRECT}")
                else:
                    text.append(word, style=f"{COL_ERROR} strike")
            elif i == self.current_word_idx:
                # Current word — per-character colouring
                typed = self.current_input
                for j, ch in enumerate(word):
                    if j < len(typed):
                        if typed[j] == ch:
                            text.append(ch, style=f"bold {COL_CORRECT}")
                        else:
                            text.append(ch, style=f"bold {COL_ERROR}")
                    elif j == len(typed):
                        text.append(ch, style=f"underline {COL_TEXT}")
                    else:
                        text.append(ch, style=COL_DIM)
                # Extra chars beyond word length
                if len(typed) > len(word):
                    text.append(typed[len(word):], style=f"bold {COL_ERROR}")
            else:
                # Future word
                text.append(word, style=COL_DIM)

        self.query_one("#text-display", Static).update(text)

    def _update_stats(self) -> None:
        if self.start_time is None:
            self.query_one("#stats", Static).update("")
            return

        elapsed = time.time() - self.start_time
        minutes = elapsed / 60
        wpm = (self.total_correct_chars / 5) / minutes if minutes > 0 else 0
        accuracy = (
            (self.total_correct_chars / max(self.total_keystrokes, 1)) * 100
        )

        t = Text()
        t.append(f"{wpm:.0f}", style=f"bold {COL_ACCENT}")
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
        self.app.restart()  # type: ignore[attr-defined]

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
        color: """ + COL_DIM + """;
    }

    #top-errors-title {
        width: 100%;
        text-align: center;
        margin-top: 1;
        color: """ + COL_DIM + """;
    }

    #top-errors-graph {
        width: 100%;
        margin-top: 1;
        content-align: center middle;
    }

    #result-hints {
        width: 100%;
        text-align: center;
        color: """ + COL_DIM + """;
        margin-top: 2;
    }
    """

    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__()
        self.result = result

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
                    yield Static(self._render_bar_graph(r["top_word_errors"]), id="top-errors-graph")
                elif r.get("top_char_errors"):
                    yield Static("top missed characters", id="top-errors-title")
                    yield Static(self._render_bar_graph(r["top_char_errors"]), id="top-errors-graph")

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

    DEFAULT_CSS = """
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
        color: """ + COL_ACCENT + """;
        text-style: bold;
        margin-bottom: 1;
    }

    #history-table {
        width: 100%;
        height: auto;
        max-height: 20;
        background: """ + COL_SUB_BG + """;
    }

    #history-empty {
        width: 100%;
        text-align: center;
        color: """ + COL_DIM + """;
        padding: 2;
    }

    #history-hints {
        width: 100%;
        text-align: center;
        color: """ + COL_DIM + """;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        results = load_results()

        with Center():
            with Vertical(id="history-container"):
                yield Static("History", id="history-title")

                if not results:
                    yield Static("No results yet — go type!", id="history-empty")
                else:
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
                    yield table

                yield Static("esc back", id="history-hints")

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()
