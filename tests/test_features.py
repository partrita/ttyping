from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import OptionList

from ttyping import storage
from ttyping.app import TypingApp
from ttyping.screens import (
    OptionsScreen,
    TimeLimitInputScreen,
    TimeMenu,
    TypingScreen,
)


@pytest.fixture(autouse=True)
def setup_storage(mock_storage: tuple[Path, Path, Path]) -> None:
    storage._ensure_storage()


def test_time_menu_preset_updates_duration_and_config() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(TimeMenu())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TimeMenu)

            # Highlight "60 seconds" (index 0=Off, 1=15, 2=30, 3=60) and select
            ol = screen.query_one("#menu-options", OptionList)
            ol.highlighted = 3
            await pilot.press("enter")
            await pilot.pause()

            assert app._duration == 60
            cfg = storage.load_config()
            assert cfg["duration"] == 60
            # Menu should have been popped after selection
            assert not isinstance(app.screen, TimeMenu)

    asyncio.run(run_test())


def test_time_menu_off_clears_duration() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(duration=30)
        async with app.run_test() as pilot:
            await app.push_screen(TimeMenu())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TimeMenu)

            ol = screen.query_one("#menu-options", OptionList)
            ol.highlighted = 0  # "Off (Free Practice)"
            await pilot.press("enter")
            await pilot.pause()

            assert app._duration is None
            assert storage.load_config()["duration"] is None

    asyncio.run(run_test())


def test_time_menu_custom_opens_input_screen() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(TimeMenu())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TimeMenu)

            ol = screen.query_one("#menu-options", OptionList)
            ol.highlighted = len(TimeMenu.PRESETS)  # "Custom…" entry
            await pilot.press("enter")
            await pilot.pause()

            # Custom should push the manual input screen instead of popping
            assert isinstance(app.screen, TimeLimitInputScreen)
            assert isinstance(app.screen_stack[-2], TimeMenu)

    asyncio.run(run_test())


class SoundTypingApp(App):
    def __init__(self, **kwargs: object) -> None:
        super().__init__()
        self._sound = True

    def on_mount(self) -> None:
        self.push_screen(TypingScreen(["apple", "banana"], lang="en"))


def test_bell_rings_on_error_when_sound_enabled() -> None:
    import asyncio

    async def run_test() -> None:
        app = SoundTypingApp()
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)
            with patch.object(app, "bell") as mock_bell:
                await pilot.press("b", "p", "p", "l", "e")
                assert mock_bell.called
            assert screen.total_errors > 0

    asyncio.run(run_test())


def test_no_bell_on_correct_input() -> None:
    import asyncio

    async def run_test() -> None:
        app = SoundTypingApp()
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)
            with patch.object(app, "bell") as mock_bell:
                await pilot.press("a", "p", "p", "l", "e")
                assert not mock_bell.called
            assert screen.total_errors == 0

    asyncio.run(run_test())


def test_options_sound_toggle_persists() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp()
        assert app._sound is False
        async with app.run_test() as pilot:
            await app.push_screen(OptionsScreen())
            await pilot.pause()
            screen = app.screen

            screen.on_option_list_option_selected(
                SimpleNamespace(option_id="sound")  # type: ignore[arg-type]
            )
            await pilot.pause()
            assert app._sound is True
            assert storage.load_config()["sound"] is True

            # Toggle back off
            screen.on_option_list_option_selected(
                SimpleNamespace(option_id="sound")  # type: ignore[arg-type]
            )
            await pilot.pause()
            assert app._sound is False
            assert storage.load_config()["sound"] is False

    asyncio.run(run_test())
