from pathlib import Path

path = Path("src/ttyping/server.py")
content = path.read_text()

# 1. Remove unused imports
content = content.replace("from typing import Any", "")
content = content.replace("from textual.app import App", "")

# 2. Fix long lines
content = content.replace(
    "def terminal_size_changed(self, width: int, height: int, pixwidth: int, pixheight: int) -> None:",
    "def terminal_size_changed(\n        self, width: int, height: int, pixwidth: int, pixheight: int\n    ) -> None:"
)
content = content.replace(
    "# In practice, Textual's SSH serving is often done via a separate command or specialized integration.",
    "# In practice, Textual's SSH serving is often done via a separate\n    # command or specialized integration."
)
content = content.replace(
    "# (This is non-trivial to implement from scratch here, but we'll provide the structure)",
    "# (This is non-trivial to implement from scratch here, but we'll\n    # provide the structure)"
)

# 3. Remove unused variable app
content = content.replace("app = create_app()", "create_app()")

path.write_text(content)
