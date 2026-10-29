from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App

from ttyping import storage
from ttyping.screens import TypingScreen


@pytest.fixture(autouse=True)
def setup_storage(mock_storage: tuple[Path, Path, Path]) -> None:
    storage._ensure_storage()


@pytest.fixture
def test_app() -> App:
    class DummyApp(App):
        def show_result(self, result: object) -> None:
            pass

        def restart(self) -> None:
            pass

        def on_mount(self) -> None:
            self.push_screen(TypingScreen(["apple", "banana"], lang="en"))

    return DummyApp()


def test_typing_screen_app_pilot(test_app: App) -> None:
    import asyncio

    async def run_test() -> None:
        async with test_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)
            assert screen.words == ["apple", "banana"]

            # Test input and word completion
            await pilot.press("a", "p", "p", "l", "e", "space")
            assert screen.current_word_idx == 1
            assert screen.word_correct[0] is True

    asyncio.run(run_test())


def test_typing_screen_wrong_input(test_app: App) -> None:
    import asyncio

    async def run_test() -> None:
        async with test_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)

            # Test wrong input
            await pilot.press("b", "p", "p", "l", "e", "space")
            assert screen.current_word_idx == 1
            assert screen.word_correct[0] is False
            assert screen.total_errors > 0

    asyncio.run(run_test())


def test_typing_screen_backspace(test_app: App) -> None:
    import asyncio

    async def run_test() -> None:
        async with test_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)

            # Test backspace
            await pilot.press("a", "b", "backspace", "p", "p", "l", "e", "space")
            assert screen.current_word_idx == 1
            assert screen.word_correct[0] is True
            assert screen.total_errors == 1  # 1 error for 'b'

    asyncio.run(run_test())


def test_typing_screen_ctrl_w(test_app: App) -> None:
    import asyncio

    async def run_test() -> None:
        async with test_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)

            # Test ctrl+w
            await pilot.press("a", "p", "ctrl+w")
            assert screen.current_input == ""

            await pilot.press("a", "p", "p", "l", "e", "space")
            assert screen.current_word_idx == 1
            assert screen.word_correct[0] is True

    asyncio.run(run_test())


def test_typing_screen_test_completion(test_app: App) -> None:
    import asyncio

    async def run_test() -> None:
        async with test_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)
            mock_show = MagicMock()
            setattr(screen.app, "show_result", mock_show)

            await pilot.press("a", "p", "p", "l", "e", "space")
            await pilot.press("b", "a", "n", "a", "n", "a", "space")

            assert screen._finished is True
            mock_show.assert_called_once()

    asyncio.run(run_test())


def test_typing_screen_restart(test_app: App) -> None:
    import asyncio

    async def run_test() -> None:
        async with test_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)
            mock_restart = MagicMock()
            setattr(screen.app, "restart", mock_restart)

            await pilot.press("a", "p", "tab")
            await pilot.pause(0.1)

            mock_restart.assert_called_once()

    asyncio.run(run_test())


def test_typing_screen_duration() -> None:
    class DurationApp(App):
        def show_result(self, result: object) -> None:
            pass

        def on_mount(self) -> None:
            # 1 second duration
            self.push_screen(TypingScreen(["apple", "banana"], lang="en", duration=1))

    import asyncio

    async def run_test() -> None:
        duration_app = DurationApp()
        async with duration_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)
            mock_show = MagicMock()
            setattr(screen.app, "show_result", mock_show)

            # Type something
            await pilot.press("a")
            # Wait for more than 1 second to trigger test completion
            await pilot.pause(1.5)

            assert screen._finished is True
            mock_show.assert_called_once()

    asyncio.run(run_test())


def test_typing_screen_target_accuracy() -> None:
    class TargetApp(App):
        def __init__(self) -> None:
            super().__init__()
            self.reset_called = False
            self.notified = False

        def reset_session_attempt(self, stats: dict) -> None:
            self.reset_called = True

        def notify(
            self,
            message: str,
            *,
            title: str | None = None,
            severity: str | None = None,
            timeout: float | None = None,
            markup: bool = True,
        ) -> None:
            self.notified = True

        def on_mount(self) -> None:
            self.push_screen(
                TypingScreen(["apple", "banana"], lang="en", target_accuracy=90.0)
            )

    import asyncio

    async def run_test() -> None:
        target_app = TargetApp()
        async with target_app.run_test() as pilot:
            screen = pilot.app.screen
            assert isinstance(screen, TypingScreen)

            # Start typing (long string with many errors to trigger accuracy drop)
            for _ in range(10):
                await pilot.press("x")
            await pilot.press("space")

            assert screen._finished is True

            # Wait for the setTimeout callback to execute reset_session_attempt
            await pilot.pause(1.6)

            assert target_app.reset_called is True

    asyncio.run(run_test())


def test_result_screen_shows_key_hints() -> None:
    """The result screen shows Tab, h and Esc hints without the Footer widget."""
    import asyncio

    from ttyping.screens import ResultScreen
    from ttyping.storage import TypingResult

    result = TypingResult(
        wpm=60.0,
        accuracy=98.0,
        time=30.0,
        lang="en_qwerty",
        words=25,
        correct=25,
        keystrokes=125,
        errors=1,
    )

    class ResultApp(App):
        def on_mount(self) -> None:
            self.push_screen(ResultScreen(result))

    async def run_test() -> None:
        result_app = ResultApp()
        async with result_app.run_test() as pilot:
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, ResultScreen)
            hint = screen.query_one(".result-hint")
            text = str(hint.render())
            assert "Tab" in text
            assert "history" in text
            assert "Esc" in text

    asyncio.run(run_test())
