from pathlib import Path

path = Path("src/ttyping/screens.py")
content = path.read_text()

content = content.replace(
    "(self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1)",
    "(self.total_keystrokes - self.total_errors)\n            / max(self.total_keystrokes, 1)"
)

path.write_text(content)
