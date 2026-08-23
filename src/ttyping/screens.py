"""Screens for ttyping: typing test, results, and history."""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import DataTable, Input, OptionList, ProgressBar, Static
from textual.widgets.option_list import Option

from ttyping.storage import (
    TypingResult,
    clear_results,
    delete_result_by_index,
    load_config,
    load_error_stats,
    load_results,
    save_config,
    save_result,
)
from ttyping.words import PRACTICE_SETS, _get_jamos

if TYPE_CHECKING:
    from ttyping.app import TypingApp

# ── Colours (Serika / Serika Dark) ─────────────────────────────────────────

# Serika Dark (Dark Theme)
COL_SERIKA_DARK_BG = "#323437"
COL_SERIKA_DARK_SUB_BG = "#2c2e31"
COL_SERIKA_DARK_TEXT = "#d1d0c5"
COL_SERIKA_DARK_DIM = "#646669"
COL_SERIKA_DARK_ACCENT = "#e2b714"
COL_SERIKA_DARK_ERROR = "#ca4754"

# Serika (Light Theme)
COL_SERIKA_LIGHT_BG = "#e1e1e3"
COL_SERIKA_LIGHT_SUB_BG = "#d1d0c5"
COL_SERIKA_LIGHT_TEXT = "#323437"
COL_SERIKA_LIGHT_DIM = "#646669"
COL_SERIKA_LIGHT_ACCENT = "#e2b714"
COL_SERIKA_LIGHT_ERROR = "#ca4754"

# Default aliases
COL_BG = COL_SERIKA_DARK_BG
COL_DIM = COL_SERIKA_DARK_DIM
COL_TEXT = COL_SERIKA_DARK_TEXT
COL_CORRECT = COL_SERIKA_DARK_TEXT
COL_ERROR = COL_SERIKA_DARK_ERROR
COL_ACCENT = COL_SERIKA_DARK_ACCENT
COL_SUB_BG = COL_SERIKA_DARK_SUB_BG


def get_accent() -> str:
    """Return the active accent color."""
    return COL_ACCENT


def get_theme_colors(app: TypingApp | None = None) -> tuple[str, str, str, str, str, str]:
    """Return (bg, sub_bg, text, dim, accent, error) for the current theme."""
    is_dark = True
    if app is not None:
        is_dark = (app.theme == "textual-dark")
    if is_dark:
        return (
            COL_SERIKA_DARK_BG,
            COL_SERIKA_DARK_SUB_BG,
            COL_SERIKA_DARK_TEXT,
            COL_SERIKA_DARK_DIM,
            COL_SERIKA_DARK_ACCENT,
            COL_SERIKA_DARK_ERROR,
        )
    return (
        COL_SERIKA_LIGHT_BG,
        COL_SERIKA_LIGHT_SUB_BG,
        COL_SERIKA_LIGHT_TEXT,
        COL_SERIKA_LIGHT_DIM,
        COL_SERIKA_LIGHT_ACCENT,
        COL_SERIKA_LIGHT_ERROR,
    )


def compute_consistency(char_timings: list[dict[str, Any]]) -> float:
    """Compute keystroke rhythm consistency (0-100%) from char timings.

    Based on the inverse coefficient of variation of inter-key intervals,
    similar to monkeytype. Long pauses (>5s, e.g. breaks) are ignored.
    """
    diffs = [
        t["time"] - s["time"]
        for s, t in zip(char_timings, char_timings[1:], strict=False)
        if isinstance(s.get("time"), (int, float))
        and isinstance(t.get("time"), (int, float))
    ]
    diffs = [d for d in diffs if 0 <= d <= 5.0]
    if len(diffs) < 2:
        return 0.0

    mean = sum(diffs) / len(diffs)
    if mean <= 0:
        return 0.0
    variance = sum((d - mean) ** 2 for d in diffs) / len(diffs)
    sd = variance**0.5
    return round(max(0.0, min(100.0, 100 * (1 - sd / mean))), 1)


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
        width: 95%;
        max-width: 80;
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

    #input-area.typo {
        background: #5f2120;
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
        self.char_timings: list[dict[str, Any]] = []  # (char, timestamp, is_correct)
        self._cached_lines: list[list[int]] | None = None
        self._last_container_width: int = 0
        self._stats_widget: Static | None = None
        self._display_widget: Static | None = None
        self._input_widget: Input | None = None
        self._shaking: bool = False

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="typing-container"):
                yield Static("", id="stats")
                yield Static("", id="text-display")
                yield Input(id="input-area", password=False)


    def on_mount(self) -> None:
        self._stats_widget = self.query_one("#stats", Static)
        self._display_widget = self.query_one("#text-display", Static)
        self._input_widget = self.query_one("#input-area", Input)
        self._input_widget.focus()
        # Initial render will happen after layout

    def on_resize(self, event: events.Resize) -> None:
        """Force re-render when terminal size changes."""
        self._cached_lines = None
        self._render_display()

    def _shake_input(self) -> None:
        if self._shaking or self._input_widget is None:
            return
        self._shaking = True
        inp = self._input_widget
        inp.add_class("typo")

        # Shake: Move slightly to the right, then left, then back
        self.animate("offset", Offset(1, 0), duration=0.05)
        self.animate("offset", Offset(-1, 0), duration=0.05, delay=0.05)
        self.animate("offset", Offset(0, 0), duration=0.05, delay=0.1)

        def reset_shaking() -> None:
            self._shaking = False
            inp.remove_class("typo")

        self.set_timer(0.2, reset_shaking)

    # ── input handling ─────────────────────────────────────────────────

    def _is_char_correct(self, typed_char: str, target_char: str) -> bool:
        """Compare typed vs target char with Korean IME partial-match support.

        A partially composed syllable (e.g. typing 'ㄱ' toward '가') counts
        as correct so intermediate IME states are not penalized.
        """
        if typed_char == target_char:
            return True
        if self.lang.startswith("ko"):
            c_jamo = _get_jamos(target_char)
            if c_jamo.startswith(_get_jamos(typed_char)):
                return True
        return False

    def _handle_ime_update(self, value: str) -> bool:
        """Handle an IME composition step (length unchanged, content changed).

        Each composition step is one physical keystroke, so it must be
        counted to keep Korean WPM/accuracy accurate.
        """
        has_error = False
        # We update the last timing entry if it's the same position
        if (
            self.char_timings
            and self.char_timings[-1]["word_idx"] == self.current_word_idx
            and self.char_timings[-1]["char_idx"] == len(value) - 1
        ):
            last_idx = len(value) - 1
            target_word = self.words[self.current_word_idx]
            char = value[last_idx]
            is_correct = (
                self._is_char_correct(char, target_word[last_idx])
                if last_idx < len(target_word)
                else (char == " ")
            )

            # Count the physical keystroke behind this composition step
            self.total_keystrokes += 1
            if not is_correct:
                self.total_errors += 1
                has_error = True

            self.char_timings[-1].update(
                {
                    "char": char,
                    "time": time.time(),
                    "correct": is_correct,
                }
            )
        return has_error

    def _handle_normal_addition(self, added: str) -> bool:
        has_error = False
        self.total_keystrokes += len(added)
        target_word = self.words[self.current_word_idx]
        for i, char in enumerate(added):
            idx = len(self.current_input) + i
            is_correct = True
            if idx < len(target_word):
                if not self._is_char_correct(char, target_word[idx]):
                    self.total_errors += 1
                    has_error = True
                    is_correct = False
            elif char != " ":
                self.total_errors += 1
                has_error = True
                is_correct = False

            self.char_timings.append(
                {
                    "char": char,
                    "time": time.time(),
                    "correct": is_correct,
                    "word_idx": self.current_word_idx,
                    "char_idx": idx,
                }
            )
        return has_error

    def _track_legacy_errors(self, value: str) -> None:
        if value and self.current_word_idx < len(self.words):
            target_word = self.words[self.current_word_idx]
            last_typed_idx = len(value) - 1
            if last_typed_idx < len(target_word):
                if value[last_typed_idx] != target_word[last_typed_idx]:
                    self.errors[target_word[last_typed_idx]] += 1

    def _ensure_timer_started(self, value: str) -> None:
        if self.start_time is None and value:
            self.start_time = time.time()
            self._timer_handle = self.set_interval(0.5, self._tick_stats)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._finished:
            return

        value = event.value
        has_error = False

        # Track raw keystrokes and errors
        # Handle IME composition (length might not increase, but content changes)
        if len(value) >= len(self.current_input) and value != self.current_input:
            # We treat any non-deletion as a potential new character/update
            added = (
                value[len(self.current_input) :]
                if len(value) > len(self.current_input)
                else ""
            )

            # If length is same but content changed, it's an IME update (e.g. ㄱ -> 가)
            if len(value) == len(self.current_input):
                has_error = self._handle_ime_update(value)
            else:
                # Normal addition
                has_error = self._handle_normal_addition(added)

        if has_error:
            self._shake_input()

        # Space → complete current word
        if value.endswith(" "):
            self._complete_word(value[:-1])
            event.input.value = ""
            return

        # Legacy character error tracking for top errors display
        self._track_legacy_errors(value)

        self.current_input = value

        # Start timer on first keystroke
        self._ensure_timer_started(value)

        self._render_display()
        self._update_stats()

    def on_key(self, event: events.Key) -> None:
        if self._finished:
            return
        inp = self._input_widget
        # Enter also completes the current word (handy for last word)
        if event.key == "ctrl+w":
            event.prevent_default()
            if inp is not None:
                inp.value = ""
        elif event.key == "enter":
            event.prevent_default()
            if inp is not None and inp.value:
                self.total_keystrokes += 1
                self._complete_word(inp.value)
                inp.value = ""

    def _wpm_parts(self, elapsed: float) -> tuple[float, float, float]:
        """Compute (gross_wpm, net_wpm, accuracy) from the current counters."""
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
        return gross_wpm, net_wpm, accuracy

    def _get_current_stats(self) -> dict[str, Any]:
        elapsed = time.time() - self.start_time if self.start_time else 0.01
        gross_wpm, net_wpm, accuracy = self._wpm_parts(elapsed)
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
                    char_timings=self.char_timings,
                    text=" ".join(self.words[: self.current_word_idx]),
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
        gross_wpm, net_wpm, accuracy = self._wpm_parts(elapsed)
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
            consistency=compute_consistency(self.char_timings),
            top_char_errors=top_char_errors,
            char_timings=self.char_timings,
            text=" ".join(self.words[: self.current_word_idx]),
        )

        save_result(result)
        cast("TypingApp", self.app).show_result(result)

    # ── rendering ──────────────────────────────────────────────────────

    def _get_word_text(self, i: int) -> Text:
        word = self.words[i]
        t = Text()
        app = cast("TypingApp", self.app)
        _, _, col_text, col_dim, col_accent, col_error = get_theme_colors(app)

        if i < self.current_word_idx:
            if self.word_correct[i]:
                t.append(word, style=f"dim {col_text}")
            else:
                t.append(word, style=f"{col_error} strike")
        elif i == self.current_word_idx:
            typed = self.current_input
            for j, ch in enumerate(word):
                if j < len(typed):
                    if self._is_char_correct(typed[j], ch):
                        t.append(ch, style=f"bold {col_text}")
                    else:
                        t.append(ch, style=f"bold {col_error}")
                elif j == len(typed):
                    t.append(ch, style=f"underline {col_text}")
                else:
                    t.append(ch, style=col_text)  # Focused word is more visible
            if len(typed) > len(word):
                t.append(typed[len(word) :], style=f"bold {col_error}")
        else:
            t.append(word, style=col_dim)
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
        display_widget = self._display_widget or self.query_one("#text-display", Static)
        container_width = display_widget.content_size.width
        if container_width <= 0:
            # Fallback for initial render if size not yet calculated
            container_width = 72

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

        display_widget.update(display_text)

    def _update_stats(self) -> None:
        if self.start_time is None:
            if self._stats_widget is not None:
                self._stats_widget.update("")
            return

        elapsed = time.time() - self.start_time
        _, net_wpm, accuracy = self._wpm_parts(elapsed)

        app = cast("TypingApp", self.app)
        _, _, _, col_dim, col_accent, _ = get_theme_colors(app)

        t = Text()
        t.append(f"{net_wpm:.0f}", style=f"bold {col_accent}")
        t.append(" wpm   ", style=col_dim)
        t.append(f"{accuracy:.0f}%", style=f"bold {col_accent}")
        t.append(" acc   ", style=col_dim)

        if self.duration:
            remaining = max(0, self.duration - elapsed)
            t.append(f"{remaining:.0f}s", style=f"bold {col_accent}")
        else:
            t.append(f"{elapsed:.0f}s", style=f"bold {col_accent}")

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
        width: 95%;
        max-width: 72;
        height: auto;
        align: center middle;
        padding: 1 2;
    }

    .result-big {
        width: 100%;
        text-align: center;
        margin-bottom: 0;
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

    #speed-map {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding: 0 1;
        background: #d1d0c5;
        border: round #646669;
    }
    .-dark-mode #speed-map {
        background: #2c2e31;
        border: round #646669;
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
        app = cast("TypingApp", self.app)
        _, _, col_text, col_dim, col_accent, _ = get_theme_colors(app)

        with Center():
            with Vertical(id="result-container"):
                wpm_text = Text()
                wpm_text.append(f"{r.wpm:.0f}", style=f"bold {col_accent}")
                wpm_text.append(" wpm", style=col_dim)
                yield Static(wpm_text, classes="result-big")
                acc_text = Text()
                acc_text.append(f"{r.accuracy:.1f}%", style=f"bold {col_text}")
                acc_text.append(" accuracy", style=col_dim)
                yield Static(acc_text, classes="result-big")
                detail = Text()
                detail.append(f"{r.time:.1f}s", style=col_text)
                detail.append(f"  ·  {r.correct}/{r.words} words", style=col_dim)
                detail.append(f"  ·  {r.lang}", style=col_dim)
                yield Static(detail, classes="result-detail")

                # Speed Map (New)
                if r.char_timings:
                    yield Static("typing speed map", classes="result-title")
                    yield Static(self._render_speed_map(), id="speed-map")

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


    def _render_speed_map(self) -> Text:
        """Render the typed text with character-level speed visualization."""
        if not self.result.char_timings:
            return Text(self.result.text)

        # Calculate time differences between characters
        timings = self.result.char_timings
        diffs = []
        for i in range(len(timings)):
            if i == 0:
                # For the first char, we don't have a previous time.
                # Use a small constant to keep it neutral/green.
                diffs.append(0.1)
            else:
                dt = timings[i]["time"] - timings[i - 1]["time"]
                # Cap long pauses (e.g. user took a break) to not skew normalization
                diffs.append(min(dt, 1.5))

        if not diffs:
            return Text(self.result.text)

        # Normalize speeds using a logarithmic-ish scale or just better min/max
        min_dt = min(diffs)
        max_dt = max(diffs)
        dt_range = max_dt - min_dt if max_dt > min_dt else 1.0

        t = Text()
        for i, entry in enumerate(timings):
            char = entry["char"]
            dt = diffs[i]

            # 0.0 (fastest/green) to 1.0 (slowest/red)
            norm = (dt - min_dt) / dt_range

            # Use a more monkeytype-like palette:
            # Fast: Greenish (#d1d0c5 text, but here we use colors)
            # Slow: Reddish

            if norm < 0.3:
                # Fast: Vibrant Green
                color = "rgb(0,255,100)"
            elif norm < 0.7:
                # Medium: Yellow/Orange
                color = "rgb(255,200,0)"
            else:
                # Slow: Red
                color = "rgb(255,50,50)"

            style = color
            if not entry.get("correct", True):
                # Errors are highlighted with a background or distinct color
                style = f"white on {COL_ERROR}"

            t.append(char, style=style)

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
        width: 90%;
        max-width: 50;
        height: auto;
        border: round """
        + COL_ERROR
        + """;
        padding: 1 2;
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
                yield Static(
                    Text.from_markup(r"[dim]Press \[y] or \[n][/dim]"),
                    id="confirm-hints",
                )


    def action_confirm(self) -> None:
        clear_results()
        # Pop both this screen and the HistoryScreen
        self.app.pop_screen()  # pop ConfirmDeleteScreen
        self.app.pop_screen()  # pop HistoryScreen

    def action_cancel(self) -> None:
        self.app.pop_screen()


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
        Binding(key="x", action="export_csv", description="Export CSV", show=False),
        Binding(key="j", action="export_json", description="Export JSON", show=False),
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
        width: 95%;
        max-width: 100;
        height: auto;
        max-height: 100%;
        align: center middle;
        content-align: center middle;
    }

    #history-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #history-progress-container {
        width: 100%;
        max-width: 60;
        height: auto;
        margin-top: 0;
        margin-bottom: 1;
        align: center middle;
    }

    #history-progress-label {
        width: 100%;
        text-align: center;
        text-style: dim;
        margin-bottom: 0;
    }

    #history-progress-bar {
        width: 100%;
    }

    .history-hint {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        text-style: dim;
    }

    #history-table {
        width: 100%;
        height: auto;
        max-height: 16;
        scrollbar-gutter: stable;
        scrollbar-background: #d1d0c5;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    .-dark-mode #history-table {
        scrollbar-background: #2c2e31;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    """

    def compose(self) -> ComposeResult:
        results = load_results()
        n = len(results)
        # Build newest-first mapping (up to 50)
        display_count = min(n, 50)
        # storage indices newest-first
        self._row_to_storage_idx = list(range(n - 1, n - 1 - display_count, -1))
        app = cast("TypingApp", self.app)

        with Center():
            with Vertical(id="history-container"):
                yield Static("History", id="history-title")
                if not results:
                    yield Static("No results yet — go type!", id="history-empty")
                else:
                    avg_wpm = sum(r.wpm for r in results) / n
                    if app._target_wpm is not None and app._target_wpm > 0:
                        target = float(app._target_wpm)
                        pct = min(100.0, (avg_wpm / target) * 100.0) if target > 0 else 0.0
                        with Vertical(id="history-progress-container"):
                            yield Static(
                                f"Goal WPM: {avg_wpm:.1f} / {app._target_wpm} ({pct:.1f}%)",
                                id="history-progress-label",
                            )
                            yield ProgressBar(
                                total=target,
                                show_eta=False,
                                id="history-progress-bar",
                            )

                    yield Static(
                        "[dim]Press [bold]d[/bold] to delete selected record · [bold]D[/bold] to delete all · [bold]Esc[/bold] to back[/dim]",
                        classes="history-hint",
                    )
                    yield self._create_history_table(results, self._row_to_storage_idx)

    def on_mount(self) -> None:
        app = cast("TypingApp", self.app)
        if app._target_wpm is not None and app._target_wpm > 0:
            results = load_results()
            avg_wpm = sum(r.wpm for r in results) / len(results) if results else 0.0
            try:
                bar = self.query_one("#history-progress-bar", ProgressBar)
                bar.progress = min(float(app._target_wpm), float(avg_wpm))
            except Exception:
                pass


    def _create_history_table(
        self,
        results: list[TypingResult],
        row_indices: list[int],
    ) -> DataTable:
        """Create a table showing the last 50 typing results (newest first)."""
        table: DataTable[str] = DataTable(id="history-table")
        table.cursor_type = "row"
        table.add_columns("#", "Date", "WPM", "Acc", "Cons", "Lang", "Time", "Words")

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
                escape(date_str),
                f"{r.wpm:.0f}",
                f"{r.accuracy:.1f}%",
                f"{r.consistency:.0f}%",
                escape(r.lang),
                f"{r.time:.0f}s",
                f"{r.correct}/{r.words}",
            )
        return table

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show result detail screen when a row is selected."""
        results = load_results()
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._row_to_storage_idx):
            storage_idx = self._row_to_storage_idx[row_idx]
            if 0 <= storage_idx < len(results):
                self.app.push_screen(ResultScreen(results[storage_idx]))

    def action_go_back(self) -> None:
        stack = self.app.screen_stack
        # Opened directly (e.g. `ttyping history`): the only screen beneath
        # is the app's blank default Screen, so exiting is more natural.
        if len(stack) <= 2 and type(stack[0]) is Screen:
            self.app.exit()
        else:
            self.app.pop_screen()

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

    def action_export_csv(self) -> None:
        from ttyping.storage import EXPORT_CSV_FILE, export_results_csv

        count = export_results_csv(EXPORT_CSV_FILE)
        msg = (
            f"Exported {count} results to {EXPORT_CSV_FILE}"
            if count
            else "No results to export"
        )
        self.app.notify(msg, title="Export CSV", timeout=3)

    def action_export_json(self) -> None:
        from ttyping.storage import EXPORT_JSON_FILE, export_results_json

        count = export_results_json(EXPORT_JSON_FILE)
        msg = (
            f"Exported {count} results to {EXPORT_JSON_FILE}"
            if count
            else "No results to export"
        )
        self.app.notify(msg, title="Export JSON", timeout=3)


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


ASCII_LOGO = r"""
 _   _               _             
| |_| |_ _   _ _ __ (_)_ __   __ _ 
| __| __| | | | '_ \| | '_ \ / _` |
| |_| |_| |_| | |_) | | | | | (_| |
 \__|\__|\__, | .__/|_|_| |_|\__, |
         |___/|_|            |___/ 
""".strip("\n")


class MenuScreen(ActionSelectMixin, Screen):
    """Initial menu to select test parameters."""

    DEFAULT_CSS = """
    MenuScreen {
        align: center middle;
    }

    #menu-container {
        width: 90%;
        max-width: 60;
        height: auto;
        padding: 1 2;
        align: center middle;
    }

    #menu-logo {
        width: 100%;
        text-align: center;
        color: #e2b714;
        margin-bottom: 1;
    }

    #menu-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #e2b714;
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
        Binding(key="q", action="quit_app", description="Quit", show=False),
        # Korean IME support (2-set)
        Binding(key="ㄷ", action="select_en", show=False),
        Binding(key="ㅏ", action="select_ko", show=False),
        Binding(key="ㅈ", action="select_weak", show=False),
        Binding(key="ㅗ", action="select_history", show=False),
        Binding(key="ㅐ", action="select_options", show=False),
        Binding(key="ㅔ", action="select_code", show=False),
        Binding(key="ㅂ", action="quit_app", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static(ASCII_LOGO, id="menu-logo")
                yield Static("ttyping", id="menu-title")
                yield OptionList(
                    Option(
                        Text.from_markup(r"English(영어) [dim]\[e][/dim]"),
                        id="en",
                    ),
                    Option(
                        Text.from_markup(r"Korean(한국어) [dim]\[k][/dim]"),
                        id="ko",
                    ),
                    Option(
                        Text.from_markup(r"Code(코드) [dim]\[p][/dim]"),
                        id="code",
                    ),
                    Option(
                        Text.from_markup(r"Weak word(약점 단어 연습) [dim]\[w][/dim]"),
                        id="weakness",
                    ),
                    Option(
                        Text.from_markup(r"View History(기록 보기) [dim]\[h][/dim]"),
                        id="history",
                    ),
                    Option(
                        Text.from_markup(r"Options [dim]\[o][/dim]"),
                        id="options",
                    ),
                    id="menu-options",
                )


    def on_mount(self) -> None:
        self._update_logo_visibility()

    def on_resize(self, event: events.Resize) -> None:
        self._update_logo_visibility()

    def _update_logo_visibility(self) -> None:
        """Hide ASCII logo if terminal is too small."""
        try:
            logo = self.query_one("#menu-logo", Static)
            title = self.query_one("#menu-title", Static)
        except Exception:
            return

        width, height = self.size
        # Fallback if size is not yet available
        if width == 0 or height == 0:
            return

        if height < 20 or width < 40:
            logo.display = False
            title.display = True
        else:
            logo.display = True
            title.display = False

    def on_resume(self) -> None:
        self._update_logo_visibility()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "history":
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
                    Option("TypeScript", id="typescript"),
                    Option("Go", id="go"),
                    Option("C", id="c"),
                    Option("Julia", id="julia"),
                    Option("Typst", id="typst"),
                    Option("Markdown", id="markdown"),
                    Option("Back", id="back"),
                    id="menu-options",
                )


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
            "typescript",
            "go",
            "c",
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


_PRACTICE_TITLES: dict[str, str] = {
    "en_qwerty": "QWERTY Practice",
    "en_dvorak": "Dvorak Practice",
    "en_colemak": "Colemak Practice",
    "ko_2set": "두벌식 연습",
    "ko_3set": "세벌식 연습",
}

_PRACTICE_OPTIONS_EN: list[tuple[str, str]] = [
    ("Words", "full:words"),
    ("Sentences", "full:sentences"),
    ("Lorem Ipsum", "full:lorem_ipsum"),
    ("Quotes", "full:quotes"),
    ("Home Row", "practice:home_row"),
    ("Top Row", "practice:top_row"),
    ("Bottom Row", "practice:bottom_row"),
    ("Number Row (1-0)", "practice:number_row"),
    ("Symbol Row (!@#...)", "practice:symbol_row"),
    ("Left Hand", "practice:left_hand"),
    ("Right Hand", "practice:right_hand"),
    ("Left Index", "practice:left_index"),
    ("Right Index", "practice:right_index"),
    ("Left Middle", "practice:left_middle"),
    ("Right Middle", "practice:right_middle"),
    ("Left Ring", "practice:left_ring"),
    ("Right Ring", "practice:right_ring"),
    ("Left Pinky", "practice:left_pinky"),
    ("Right Pinky", "practice:right_pinky"),
]

_PRACTICE_OPTIONS_KO: list[tuple[str, str]] = [
    ("단어", "full:words"),
    ("짧은 글", "full:sentences"),
    ("로렘 입숨", "full:lorem_ipsum"),
    ("명언", "full:quotes"),
    ("가운데 줄", "practice:home_row"),
    ("윗 줄", "practice:top_row"),
    ("아랫 줄", "practice:bottom_row"),
    ("숫자 줄 (1-0)", "practice:number_row"),
    ("특수문자 (!@#...)", "practice:symbol_row"),
    ("왼손 자음", "practice:left_hand"),
    ("오른손 모음", "practice:right_hand"),
    ("왼손 검지", "practice:left_index"),
    ("오른손 검지", "practice:right_index"),
    ("왼손 중지", "practice:left_middle"),
    ("오른손 중지", "practice:right_middle"),
    ("왼손 약지", "practice:left_ring"),
    ("오른손 약지", "practice:right_ring"),
    ("왼손 새끼", "practice:left_pinky"),
    ("오른손 새끼", "practice:right_pinky"),
]


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
        title = _PRACTICE_TITLES.get(
            self.layout_id, f"{self.layout_id.upper()} Practice"
        )
        entries = (
            _PRACTICE_OPTIONS_KO
            if self.layout_id.startswith("ko")
            else _PRACTICE_OPTIONS_EN
        )
        options = [Option(label, id=opt_id) for label, opt_id in entries]
        with Center():
            with Vertical(id="menu-container"):
                yield Static(escape(title), id="menu-title")
                yield OptionList(
                    *options,
                    Option("Back", id="back"),
                    id="menu-options",
                    name="Practice Set Selection",
                )


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
        elif opt_id == "full:quotes":
            lang = "ko_quotes" if "ko" in self.layout_id else "en_quotes"
            app.start_custom_test(lang, app._word_count, app._duration)
        elif opt_id.startswith("practice:"):
            set_name = opt_id.split(":")[1]
            # Use a prefix to tell get_words to use practice set
            app.start_custom_test(
                f"practice:{self.layout_id}:{set_name}", app._word_count, app._duration
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
                yield Static(escape(self.layout_id.upper()), id="menu-title")
                yield OptionList(
                    Option("Words", id=f"{self.layout_id}:words"),
                    Option("Sentences", id=f"{self.layout_id}:sentences"),
                    Option("Back", id="back"),
                    id="menu-options",
                )


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
                yield Static(escape(f"Current: {current_label}"), classes="about-text")
                yield OptionList(
                    Option("None (Free Practice)", id="none"),
                    Option("80%", id="80"),
                    Option("90%", id="90"),
                    Option("95%", id="95"),
                    Option("100% (No Mistakes)", id="100"),
                    id="menu-options",
                )


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

    def action_go_back(self) -> None:
        self.app.pop_screen()


class OptionsScreen(ActionSelectMixin, Screen):
    """Options submenu: Words, Target WPM, Time, Accuracy, Theme, About."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def _get_labels(self) -> tuple[str, str, str, str, str]:
        app = cast("TypingApp", self.app)
        words_label = str(app._word_count)
        target_wpm = app._target_wpm
        target_wpm_label = "None" if target_wpm is None else f"{target_wpm} WPM"
        time_label = "Off" if app._duration is None else f"{app._duration}s"
        acc = app._target_accuracy
        acc_label = "None" if acc is None else f"{int(acc)}%"
        theme_label = "Dark" if app.theme == "textual-dark" else "Light"
        return words_label, target_wpm_label, time_label, acc_label, theme_label

    def compose(self) -> ComposeResult:
        words_label, target_wpm_label, time_label, acc_label, theme_label = self._get_labels()

        with Center():
            with Vertical(id="menu-container"):
                yield Static("Options", id="menu-title")
                yield OptionList(
                    Option(escape(f"Words: {words_label}"), id="words"),
                    Option(escape(f"Target WPM: {target_wpm_label}"), id="target_wpm"),
                    Option(escape(f"Time: {time_label}"), id="time"),
                    Option(escape(f"Accuracy: {acc_label}"), id="accuracy"),
                    Option(escape(f"Theme: {theme_label}"), id="theme"),
                    Option("About", id="about"),
                    id="menu-options",
                )

    def on_resume(self) -> None:
        """Refresh labels when returning from a nested screen."""
        self.refresh(recompose=True)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        if opt_id == "words":
            app.push_screen(WordCountInputScreen())
        elif opt_id == "target_wpm":
            app.push_screen(TargetWpmInputScreen())
        elif opt_id == "time":
            app.push_screen(TimeMenu())
        elif opt_id == "accuracy":
            app.push_screen(AccuracyMenu())
        elif opt_id == "theme":
            app.push_screen(ThemeScreen())
        elif opt_id == "about":
            app.push_screen(AboutScreen())

    def action_go_back(self) -> None:
        self.app.pop_screen()


class TargetWpmInputScreen(Screen):
    """Input screen to set the target WPM (or 0/empty to disable)."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="submit", description="Save"),
        Binding(key="escape", action="go_back", description="Cancel"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current_wpm = str(app._target_wpm) if app._target_wpm is not None else ""
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Set Target WPM", id="menu-title")
                yield Static(
                    escape("Enter target WPM (1-500) or 0 to disable:"),
                    classes="about-text",
                )
                yield Input(
                    value=current_wpm,
                    placeholder="Target WPM (e.g. 80, 0 to disable)",
                    id="wpm-input",
                    type="integer",
                    max_length=4,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear the error border when the user types."""
        self.query_one("#wpm-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        from ttyping.storage import load_config, save_config

        value = event.value.strip()
        app = cast("TypingApp", self.app)

        if not value or value == "0":
            app._target_wpm = None
            cfg = load_config()
            cfg["target_wpm"] = None
            save_config(cfg)
            app.notify("Target WPM disabled", title="Saved", timeout=2)
            app.pop_screen()
            return

        try:
            target = int(value)
            if not 1 <= target <= 500:
                raise ValueError
        except ValueError:
            self.query_one(
                "#wpm-input", Input
            ).border_title = "⚠ Enter a number from 1 to 500 (or 0)"
            return

        app._target_wpm = target
        cfg = load_config()
        cfg["target_wpm"] = target
        save_config(cfg)
        app.notify(f"Target WPM set to {target}", title="Saved", timeout=2)
        app.pop_screen()

    def action_submit(self) -> None:
        val = self.query_one("#wpm-input", Input).value
        self.on_input_submitted(Input.Submitted(self.query_one("#wpm-input", Input), val))

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
                yield Static(escape(f"Current: {current}"), classes="about-text")
                yield OptionList(
                    Option("🌙  Dark", id="dark"),
                    Option("☀️  Light", id="light"),
                    id="menu-options",
                )


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
                    max_length=4,
                )


    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear the error border when the user types."""
        self.query_one("#words-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        from ttyping.storage import load_config, save_config

        value = event.value.strip()
        try:
            count = int(value)
            if not 1 <= count <= 1000:
                raise ValueError
        except ValueError:
            self.query_one(
                "#words-input", Input
            ).border_title = "⚠ Enter a number from 1 to 1000"
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


class TimeMenu(ActionSelectMixin, Screen):
    """Quick-select menu for common time limit presets."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS
    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    PRESETS: list[tuple[str, int | None]] = [
        ("Off (Free Practice)", 0),
        ("15 seconds", 15),
        ("30 seconds", 30),
        ("60 seconds", 60),
        ("120 seconds", 120),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = "Off" if app._duration is None else f"{app._duration}s"
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Time Limit", id="menu-title")
                yield Static(escape(f"Current: {current}"), classes="about-text")
                options = [
                    Option(label, id=f"time:{value}") for label, value in self.PRESETS
                ]
                yield OptionList(
                    *options,
                    Option("Custom…", id="time:custom"),
                    id="menu-options",
                )


    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from ttyping.storage import load_config, save_config

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "time:custom":
            app.push_screen(TimeLimitInputScreen())
            return
        if not opt_id.startswith("time:"):
            return

        raw = opt_id.split(":", 1)[1]
        duration: int | None = None if raw == "0" else int(raw)

        app._duration = duration
        cfg = load_config()
        cfg["duration"] = duration
        save_config(cfg)
        msg = "Time limit cleared" if duration is None else f"Time set to {duration}s"
        app.notify(msg, title="Saved", timeout=2)
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
    """Weak Key Analysis - aggregated error stats with targeted drill."""

    DEFAULT_CSS = """
    WeaknessScreen {
        align: center middle;
    }

    #weakness-container {
        width: 95%;
        max-width: 70;
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
        max-height: 12;
        margin-top: 0;
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
            PRACTICE_SETS,
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
                                    # Security: Escape untrusted history input
                                    # to prevent Rich Markup Injection (Local DoS)
                                    escape(f"Practice {label} ({total} err) ▶"),
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
                        table.add_row(escape(label), escape(chars_display), str(total))
                    yield table

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
