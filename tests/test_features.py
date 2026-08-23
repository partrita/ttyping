from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import OptionList

from ttyping import storage
from ttyping.app import TypingApp
from ttyping.screens import (
    CodeSubMenu,
    HistoryScreen,
    MenuScreen,
    OptionsScreen,
    PracticeMenu,
    TimeLimitInputScreen,
    TimeMenu,
    TypingScreen,
    WeaknessScreen,
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


def test_get_personal_best_excludes_current() -> None:
    from ttyping.storage import TypingResult, get_personal_best, save_result

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
            date="2026-08-23T00:00:01+00:00",
        )
    )
    save_result(
        TypingResult(
            wpm=70.0,
            accuracy=95.0,
            time=10.0,
            lang="en",
            words=5,
            correct=5,
            keystrokes=30,
            errors=0,
            date="2026-08-23T00:00:02+00:00",
        )
    )
    save_result(
        TypingResult(
            wpm=99.0,
            accuracy=95.0,
            time=10.0,
            lang="ko",
            words=5,
            correct=5,
            keystrokes=30,
            errors=0,
            date="2026-08-23T00:00:03+00:00",
        )
    )

    assert get_personal_best("en") == 70.0
    # Excluding the newest en result leaves the older one
    assert get_personal_best("en", exclude_date="2026-08-23T00:00:02+00:00") == 50.0
    # Unknown lang / empty history
    assert get_personal_best("fr") == 0.0


def test_result_screen_shows_pb_badge() -> None:
    import asyncio

    async def run_test() -> None:
        from textual.widget import Widget

        from ttyping.screens import ResultScreen
        from ttyping.storage import TypingResult, save_result

        save_result(
            TypingResult(
                wpm=40.0,
                accuracy=90.0,
                time=10.0,
                lang="en",
                words=5,
                correct=5,
                keystrokes=30,
                errors=0,
            )
        )
        record = TypingResult(
            wpm=80.0,
            accuracy=95.0,
            time=10.0,
            lang="en",
            words=5,
            correct=5,
            keystrokes=30,
            errors=0,
        )
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(ResultScreen(record))
            await pilot.pause()
            texts = [str(w.render()) for w in app.screen.query(Widget)]
            joined = " ".join(texts)
            assert "new personal best!" in joined
            assert "80" in joined

    asyncio.run(run_test())


def test_result_screen_shows_existing_pb() -> None:
    import asyncio

    async def run_test() -> None:
        from textual.widget import Widget

        from ttyping.screens import ResultScreen
        from ttyping.storage import TypingResult, save_result

        save_result(
            TypingResult(
                wpm=90.0,
                accuracy=90.0,
                time=10.0,
                lang="en",
                words=5,
                correct=5,
                keystrokes=30,
                errors=0,
            )
        )
        slower = TypingResult(
            wpm=60.0,
            accuracy=95.0,
            time=10.0,
            lang="en",
            words=5,
            correct=5,
            keystrokes=30,
            errors=0,
        )
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(ResultScreen(slower))
            await pilot.pause()
            joined = " ".join(str(w.render()) for w in app.screen.query(Widget))
            assert "new personal best!" not in joined
            assert "pb 90" in joined

    asyncio.run(run_test())


def test_new_code_languages_loaded() -> None:
    from ttyping.words import C_WORDS, GO_WORDS, TS_WORDS, get_words

    assert len(GO_WORDS) > 20
    assert len(C_WORDS) > 20
    assert len(TS_WORDS) > 20

    for lang, words in [("go", GO_WORDS), ("c", C_WORDS), ("typescript", TS_WORDS)]:
        picked = get_words(lang, count=10)
        assert len(picked) == 10
        assert all(w in words for w in picked)


def test_code_submenu_includes_new_languages() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp()
        async with app.run_test() as pilot:
            await app.push_screen(CodeSubMenu())
            await pilot.pause()
            screen = app.screen
            ol = screen.query_one("#menu-options", OptionList)
            ids = [str(o.id) for o in ol.options]
            assert {"go", "c", "typescript"} <= set(ids)

    asyncio.run(run_test())


def test_quotes_mode() -> None:
    from ttyping.words import EN_QUOTES, KO_QUOTES, get_words

    assert len(EN_QUOTES) >= 10
    assert len(KO_QUOTES) >= 10

    words = get_words("en_quotes", count=5)
    assert len(words) > 0
    # Quotes include punctuation/capitals — verify a word comes from the pool
    pool_words = {w for q in EN_QUOTES for w in q.split()}
    assert all(w in pool_words for w in words)

    ko_words = get_words("ko_quotes", count=3)
    ko_pool = {w for q in KO_QUOTES for w in q.split()}
    assert all(w in ko_pool for w in ko_words)


def test_practice_menu_quotes_selection() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(lang="en_qwerty")
        async with app.run_test() as pilot:
            from types import SimpleNamespace

            await app.push_screen(PracticeMenu("en_qwerty"))
            await pilot.pause()
            screen = app.screen

            screen.on_option_list_option_selected(
                SimpleNamespace(option_id="full:quotes")  # type: ignore[arg-type]
            )
            await pilot.pause()
            assert app._lang == "en_quotes"

    asyncio.run(run_test())


def test_practice_menu_ko_quotes_selection() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(lang="ko_2set")
        async with app.run_test() as pilot:
            from types import SimpleNamespace

            await app.push_screen(PracticeMenu("ko_2set"))
            await pilot.pause()
            screen = app.screen

            screen.on_option_list_option_selected(
                SimpleNamespace(option_id="full:quotes")  # type: ignore[arg-type]
            )
            await pilot.pause()
            assert app._lang == "ko_quotes"

    asyncio.run(run_test())


class ZenApp(App):
    """Minimal host for zen TypingScreen with stubbed app hooks."""

    last_result: object = None

    def show_result(self, result: object) -> None:
        self.last_result = result

    def restart(self) -> None:
        pass

    def reset_session_attempt(self, stats: object) -> None:
        pass

    def _get_more_words(self) -> list[str]:
        return ["beta", "gamma", "delta"]

    def on_mount(self) -> None:
        self.push_screen(TypingScreen(["alpha"], lang="en", zen=True))


def test_zen_mode_extends_words_instead_of_ending() -> None:
    import asyncio

    async def run_test() -> None:
        app = ZenApp()
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)
            assert screen.zen is True

            # Complete the only word — screen should stream more, not end
            await pilot.press("a", "l", "p", "h", "a", "space")
            await pilot.pause()

            assert screen.current_word_idx == 1
            assert len(screen.words) == 4  # alpha + beta gamma delta
            assert screen._finished is False

    asyncio.run(run_test())


def test_zen_mode_manual_finish_saves_result() -> None:
    import asyncio

    async def run_test() -> None:
        app = ZenApp()
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)

            await pilot.press("a", "l", "p", "h", "a", "space")
            await pilot.pause()
            screen.action_finish_zen()
            await pilot.pause()

            assert screen._finished is True
            assert app.last_result is not None
            assert app.last_result.lang == "en"

    asyncio.run(run_test())


def test_menu_has_zen_option_and_binding() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp()
        async with app.run_test() as pilot:
            from textual.widgets import OptionList as OL

            await pilot.pause()
            menu = app.screen
            ol = menu.query_one("#menu-options", OL)
            ids = [str(o.id) for o in ol.options]
            assert "zen" in ids

    asyncio.run(run_test())


def test_daily_words_deterministic_per_day() -> None:
    from ttyping.words import get_daily_words

    a = get_daily_words("en", count=25)
    b = get_daily_words("en", count=25)
    assert a == b
    assert len(a) == 25

    # Different language yields a different set (different pools)
    ko = get_daily_words("ko_2set", count=25)
    assert ko != a


def test_daily_test_pushes_typing_screen() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(lang="en_qwerty", word_count=10)
        async with app.run_test() as pilot:
            await app.push_screen(MenuScreen())
            await pilot.pause()
            app.start_daily_test()
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, TypingScreen)
            assert screen.zen is False
            assert len(screen.words) == 10

    asyncio.run(run_test())


def test_menu_has_daily_option() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp()
        async with app.run_test() as pilot:
            from textual.widgets import OptionList as OL

            await pilot.pause()
            ol = app.screen.query_one("#menu-options", OL)
            ids = [str(o.id) for o in ol.options]
            assert "daily" in ids
            assert "zen" in ids

    asyncio.run(run_test())


def test_live_wpm_chart_samples() -> None:
    import asyncio

    async def run_test() -> None:
        app = SoundTypingApp()
        async with app.run_test() as pilot:
            screen = app.screen
            assert isinstance(screen, TypingScreen)

            chart = screen.query_one("#live-chart")
            from ttyping.screens import LineChart

            assert isinstance(chart, LineChart)
            # Hidden before typing starts
            assert chart.display is False

            await pilot.press("a", "p", "p", "l", "e", "space")

            # Simulate timer ticks (real 0.5s timer may also fire)
            screen._tick_stats()
            screen._tick_stats()

            assert len(screen.wpm_samples) >= 2
            assert all(s >= 0 for s in screen.wpm_samples)
            assert chart.display is True
            assert len(chart.chart_data) == len(screen.wpm_samples)

    asyncio.run(run_test())


def test_keyboard_heatmap_render() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(lang="en_qwerty")
        async with app.run_test() as pilot:
            await app.push_screen(WeaknessScreen())
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, WeaknessScreen)

            # Render function: plain text preserves row structure
            stats = {"f": 10, "j": 5, "a": 1}
            text = screen._render_heatmap("en_qwerty", stats)
            lines = text.plain.split("\n")
            assert len(lines) == 4  # number/top/home/bottom rows
            assert "f" in lines[2] and "j" in lines[2]  # home row

            def style_at(t: object, ch: str) -> list[str]:
                idx = t.plain.find(ch)
                return [str(s.style) for s in t.spans if s.start <= idx < s.end]

            # Hot key styled with strongest heat color
            assert any("ff6b76" in st for st in style_at(text, "f"))
            # Cold key stays dim
            assert any("909294" in st for st in style_at(text, "q"))

    asyncio.run(run_test())


def test_keyboard_heatmap_unknown_layout_empty() -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(lang="python")  # not a keyboard layout
        async with app.run_test() as pilot:
            from rich.text import Text

            await app.push_screen(WeaknessScreen())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WeaknessScreen)
            result = screen._render_heatmap("nonexistent_layout", {"a": 3})
            assert isinstance(result, Text)

    asyncio.run(run_test())


def test_set_accent_validates_hex() -> None:
    from ttyping.screens import get_accent, set_accent

    set_accent("#7bd88f")
    assert get_accent() == "#7bd88f"
    # Invalid values ignored (markup-injection safe)
    set_accent("[red]evil[/]")
    assert get_accent() == "#7bd88f"
    set_accent("not-a-color")
    set_accent("#12345")  # too short
    assert get_accent() == "#7bd88f"
    # Restore default
    set_accent("#e2b714")
    assert get_accent() == "#e2b714"


def test_app_loads_accent_from_config() -> None:
    import asyncio

    async def run_test() -> None:
        storage.save_config({"accent": "#74b6ff"})
        from ttyping.screens import get_accent

        app = TypingApp()
        async with app.run_test():
            assert get_accent() == "#74b6ff"

        # Invalid stored accent falls back without crash
        storage.save_config({"accent": "javascript:alert(1)"})
        app2 = TypingApp()
        async with app2.run_test():
            assert get_accent() in {"#e2b714", "#74b6ff"}

    asyncio.run(run_test())


def test_accent_menu_selection_persists() -> None:
    import asyncio
    from types import SimpleNamespace

    async def run_test() -> None:
        app = TypingApp()
        async with app.run_test() as pilot:
            from ttyping.screens import AccentMenu, get_accent

            await app.push_screen(AccentMenu())
            await pilot.pause()
            screen = app.screen
            screen.on_option_list_option_selected(
                SimpleNamespace(option_id="accent:#ff7597")
            )
            await pilot.pause()

            assert get_accent() == "#ff7597"
            assert storage.load_config()["accent"] == "#ff7597"

    asyncio.run(run_test())
