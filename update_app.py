from pathlib import Path

path = Path("src/ttyping/app.py")
content = path.read_text()

# 1. Update imports
content = content.replace(
    "from ttyping.screens import HistoryScreen, TypingScreen",
    "from ttyping.screens import HistoryScreen, TypingScreen, MenuScreen"
)

# 2. Add show_menu to __init__
content = content.replace(
    "        show_history: bool = False,",
    "        show_history: bool = False,\n        show_menu: bool = False,"
)
content = content.replace(
    "        self._show_history = show_history",
    "        self._show_history = show_history\n        self._show_menu = show_menu"
)

# 3. Update on_mount
old_on_mount = """    def on_mount(self) -> None:
        if self._show_history:
            self.push_screen(HistoryScreen())
        else:
            self._start_typing()"""

new_on_mount = """    def on_mount(self) -> None:
        if self._show_history:
            self.push_screen(HistoryScreen())
        elif self._show_menu:
            self.push_screen(MenuScreen())
        else:
            self._start_typing()"""

content = content.replace(old_on_mount, new_on_mount)

# 4. Add start_custom_test
new_methods = """
    def start_custom_test(self, lang: str, words: int, duration: int | None) -> None:
        \"\"\"Start a test with custom parameters.\"\"\"
        self._lang = lang
        self._word_count = words
        self._duration = duration
        self._start_typing()

    def exit_app(self) -> None:"""

content = content.replace("    def exit_app(self) -> None:", new_methods)

path.write_text(content)
