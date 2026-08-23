from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import OptionList

from ttyping import storage
from ttyping.app import TypingApp
from ttyping.screens import (
    HistoryScreen,
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
    last_result: object = None

    def __init__(self, **kwargs: object) -> None:
        super().__init__()
        self._sound = True

    def show_result(self, result: object) -> None:
        self.last_result = result

    def restart(self) -> None:
        pass

    def reset_session_attempt(self, stats: object) -> None:
        pass

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


def test_export_csv_and_json(tmp_path: Path) -> None:
    from ttyping.storage import (
        TypingResult,
        export_results_csv,
        export_results_json,
        save_result,
    )

    save_result(
        TypingResult(
            wpm=72.5,
            accuracy=95.0,
            time=30.0,
            lang="en",
            words=20,
            correct=19,
            keystrokes=100,
            errors=2,
            top_char_errors=[("a", 1)],
            date="2026-08-23T00:00:00+00:00",
        )
    )
    save_result(
        TypingResult(
            wpm=80.0,
            accuracy=98.0,
            time=25.0,
            lang="ko",
            words=15,
            correct=15,
            keystrokes=90,
            errors=0,
        )
    )

    csv_path = tmp_path / "out.csv"
    assert export_results_csv(csv_path) == 2
    import csv as _csv

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    assert len(rows) == 2
    assert float(rows[0]["wpm"]) == 72.5
    errors = rows[0]["top_char_errors"]
    assert '"a", 1' in errors or "'a', 1" in errors

    json_path = tmp_path / "out.json"
    assert export_results_json(json_path) == 2
    import json as _json

    data = _json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 2
    assert data[1]["lang"] == "ko"


def test_export_empty_returns_zero(tmp_path: Path) -> None:
    from ttyping.storage import export_results_csv, export_results_json

    assert export_results_csv(tmp_path / "e.csv") == 0
    assert export_results_json(tmp_path / "e.json") == 0


def test_history_screen_export_actions() -> None:
    import asyncio

    async def run_test() -> None:
        from ttyping.storage import EXPORT_CSV_FILE, TypingResult, save_result

        save_result(
            TypingResult(
                wpm=50.0,
                accuracy=90.0,
                time=10.0,
                lang="en",
                words=5,
                correct=5,
                keystrokes=30,
                errors=0,
            )
        )
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(HistoryScreen())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryScreen)

            EXPORT_CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
            screen.action_export_csv()
            screen.action_export_json()
            await pilot.pause()

            assert EXPORT_CSV_FILE.exists()

    asyncio.run(run_test())


def test_compute_consistency() -> None:
    from ttyping.screens import compute_consistency

    # Perfectly even rhythm -> high consistency
    even = [{"time": float(i)} for i in range(20)]
    assert compute_consistency(even) == 100.0

    # Erratic rhythm -> low consistency
    erratic = []
    t = 0.0
    for gap in [0.1, 2.0, 0.1, 3.0, 0.2, 0.5, 4.0, 0.1]:
        t += gap
        erratic.append({"time": t})
    assert compute_consistency(erratic) < 50.0

    # Too few samples / empty / malformed -> 0
    assert compute_consistency([]) == 0.0
    assert compute_consistency([{"time": 1.0}]) == 0.0
    assert compute_consistency([{"time": "x"}]) == 0.0


def test_end_test_stores_consistency() -> None:
    import asyncio

    async def run_test() -> None:
        app = SoundTypingApp()
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)
            await pilot.press("a", "p", "p", "l", "e", "space")
            await pilot.press("b", "a", "n", "a", "n", "a")
            screen._end_test()
            result = app.last_result
            assert result is not None
            assert result.consistency >= 0.0

    asyncio.run(run_test())


def test_history_table_has_consistency_column() -> None:
    import asyncio

    async def run_test() -> None:
        from ttyping.storage import TypingResult, save_result

        save_result(
            TypingResult(
                wpm=60.0,
                accuracy=95.0,
                time=12.0,
                lang="en",
                words=6,
                correct=6,
                keystrokes=40,
                errors=0,
            )
        )
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(HistoryScreen())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryScreen)
            table = screen.query_one("#history-table")
            columns = [str(c.label) for c in table.ordered_columns]
            assert "Cons" in columns

    asyncio.run(run_test())
