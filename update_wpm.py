import sys
from pathlib import Path

path = Path("src/ttyping/screens.py")
content = path.read_text()

# 1. Update stats in __init__
content = content.replace(
    "        self.total_correct_chars = 0\n        self.total_keystrokes = 0",
    "        self.total_keystrokes = 0\n        self.total_errors = 0\n        self.uncorrected_errors = 0"
)

# 2. Update on_input_changed
old_on_input = """    def on_input_changed(self, event: Input.Changed) -> None:
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
        self._update_stats()"""

new_on_input = """    def on_input_changed(self, event: Input.Changed) -> None:
        if self._finished:
            return

        value = event.value

        # Track raw keystrokes and errors
        if len(value) > len(self.current_input):
            added = value[len(self.current_input):]
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
        self._update_stats()"""

content = content.replace(old_on_input, new_on_input)

# 3. Update _complete_word
old_complete = """    def _complete_word(self, typed: str) -> None:
        target = self.words[self.current_word_idx]
        is_correct = typed == target

        self.word_correct[self.current_word_idx] = is_correct
        self.total_keystrokes += len(typed) + 1  # +1 for space/enter
        if is_correct:
            self.total_correct_chars += len(target) + 1
        else:
            self.word_errors[target] += 1

        self.current_word_idx += 1"""

new_complete = """    def _complete_word(self, typed: str) -> None:
        target = self.words[self.current_word_idx]
        is_correct = typed == target

        self.word_correct[self.current_word_idx] = is_correct
        if not is_correct:
            self.uncorrected_errors += 1
            self.word_errors[target] += 1

        self.current_word_idx += 1"""

content = content.replace(old_complete, new_complete)

# 4. Update _end_test
old_end = """    def _end_test(self) -> None:
        if self._finished:
            return

        self._finished = True
        if self._timer_handle:
            self._timer_handle.stop()

        elapsed = time.time() - self.start_time if self.start_time else 0.01
        minutes = elapsed / 60
        wpm = (self.total_correct_chars / 5) / minutes if minutes > 0 else 0
        accuracy = (self.total_correct_chars / max(self.total_keystrokes, 1)) * 100
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
        }"""

new_end = """    def _end_test(self) -> None:
        if self._finished:
            return

        self._finished = True
        if self._timer_handle:
            self._timer_handle.stop()

        elapsed = time.time() - self.start_time if self.start_time else 0.01
        minutes = elapsed / 60
        if minutes <= 0: minutes = 0.001

        gross_wpm = (self.total_keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (self.uncorrected_errors / minutes))
        accuracy = max(0, (self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1)) * 100
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
            "top_char_errors": top_char_errors,
            "top_word_errors": top_word_errors,
        }"""

content = content.replace(old_end, new_end)

# 5. Update _update_stats
old_stats = """    def _update_stats(self) -> None:
        if self.start_time is None:
            self.query_one("#stats", Static).update("")
            return

        elapsed = time.time() - self.start_time
        minutes = elapsed / 60
        wpm = (self.total_correct_chars / 5) / minutes if minutes > 0 else 0
        accuracy = (self.total_correct_chars / max(self.total_keystrokes, 1)) * 100

        t = Text()
        t.append(f"{wpm:.0f}", style=f"bold {COL_ACCENT}")
        t.append(" wpm   ", style=COL_DIM)
        t.append(f"{accuracy:.0f}%", style=f"bold {COL_ACCENT}")
        t.append(" acc   ", style=COL_DIM)"""

new_stats = """    def _update_stats(self) -> None:
        if self.start_time is None:
            self.query_one("#stats", Static).update("")
            return

        elapsed = time.time() - self.start_time
        minutes = elapsed / 60
        if minutes <= 0: minutes = 0.001

        gross_wpm = (self.total_keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (self.uncorrected_errors / minutes))
        accuracy = max(0, (self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1)) * 100

        t = Text()
        t.append(f"{net_wpm:.0f}", style=f"bold {COL_ACCENT}")
        t.append(" wpm   ", style=COL_DIM)
        t.append(f"{accuracy:.0f}%", style=f"bold {COL_ACCENT}")
        t.append(" acc   ", style=COL_DIM)"""

content = content.replace(old_stats, new_stats)

# 6. Update on_key for enter
content = content.replace(
    "            if inp.value:\n                self._complete_word(inp.value)",
    "            if inp.value:\n                self.total_keystrokes += 1\n                self._complete_word(inp.value)"
)

path.write_text(content)
