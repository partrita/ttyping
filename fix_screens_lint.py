from pathlib import Path

path = Path("src/ttyping/screens.py")
content = path.read_text()

# 1. Move MenuScreen imports to top
content = content.replace("from textual.widgets import OptionList\nfrom textual.widgets.option_list import Option", "")
content = content.replace("from __future__ import annotations", "from __future__ import annotations\n\nfrom textual.widgets import OptionList\nfrom textual.widgets.option_list import Option")

# 2. Fix multiple statements on one line
content = content.replace("if minutes <= 0: minutes = 0.001", "if minutes <= 0:\n            minutes = 0.001")
content = content.replace('if i > 0: display_text.append(" ")', 'if i > 0:\n                    display_text.append(" ")')

# 3. Fix long lines
content = content.replace(
    "accuracy = max(0, (self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1)) * 100",
    "accuracy = (\n            max(0, (self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1)) * 100\n        )"
)

path.write_text(content)
