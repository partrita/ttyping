import sys
from pathlib import Path

path = Path("src/ttyping/screens.py")
content = path.read_text()

old_render = """    def _render_display(self) -> None:
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
                    text.append(typed[len(word) :], style=f"bold {COL_ERROR}")
            else:
                # Future word
                text.append(word, style=COL_DIM)

        self.query_one("#text-display", Static).update(text)"""

# New render logic: 3-line display, current word always in the middle line
new_render = """    def _render_display(self) -> None:
        # Use a simple line-wrapping approach to show 3 lines:
        # 1. previous line
        # 2. current line (containing active word)
        # 3. next line
        container_width = 72 # matches #typing-container width minus padding

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
                        t.append(ch, style=COL_TEXT) # Focused word is more visible
                if len(typed) > len(word):
                    t.append(typed[len(word):], style=f"bold {COL_ERROR}")
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
                if i > 0: display_text.append(" ")
                display_text.append(word_text)
            display_text.append("\\n")

        self.query_one("#text-display", Static).update(display_text)"""

content = content.replace(old_render, new_render)
path.write_text(content)
