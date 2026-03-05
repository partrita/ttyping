from pathlib import Path

path = Path("src/ttyping/screens.py")
content = path.read_text()

content = content.replace(
    "max(0, (self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1)) * 100",
    "max(0, (self.total_keystrokes - self.total_errors) / max(self.total_keystrokes, 1))\n            * 100"
)

path.write_text(content)
