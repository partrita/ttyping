from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import OptionList

from ttyping import storage
from ttyping.app import TypingApp
from ttyping.screens import (
    CodeSubMenu,
    HistoryScreen,
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


class MockTypingApp(App):
    last_result: object = None

    def __init__(self, **kwargs: object) -> None:
        super().__init__()

    def show_result(self, result: object) -> None:
        self.last_result = result

    def restart(self) -> None:
        pass

    def reset_session_attempt(self, stats: object) -> None:
        pass

    def on_mount(self) -> None:
        self.push_screen(TypingScreen(["apple", "banana"], lang="en"))


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
        app = MockTypingApp()
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


def test_daily_words_deterministic_per_day() -> None:
    from ttyping.words import get_daily_words

    a = get_daily_words("en", count=25)
    b = get_daily_words("en", count=25)
    assert a == b
    assert len(a) == 25

    # Different language yields a different set (different pools)
    ko = get_daily_words("ko_2set", count=25)
    assert ko != a


def test_weakness_screen_compose() -> None:
    import asyncio

    async def run_test() -> None:
        from textual.widgets import DataTable, OptionList

        from ttyping.storage import TypingResult, save_result

        # Save results with error stats
        save_result(
            TypingResult(
                wpm=50.0,
                accuracy=90.0,
                time=10.0,
                lang="en_qwerty",
                words=5,
                correct=4,
                keystrokes=25,
                errors=1,
                top_char_errors=[("f", 5), ("j", 3)],
            )
        )

        app = TypingApp(lang="en_qwerty")
        async with app.run_test() as pilot:
            await app.push_screen(WeaknessScreen())
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, WeaknessScreen)
            assert len(screen.query(DataTable)) == 1
            assert len(screen.query(OptionList)) == 1

    asyncio.run(run_test())


def test_words_from_url_parses_and_caps() -> None:

    from ttyping.words import words_from_url

    class FakeResp:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def read(self, n: int) -> bytes:
            return self.payload[:n]

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *a: object) -> None:
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp(b"alpha beta\ngamma\n")):
        words = words_from_url("https://example.com/words.txt", count=10)
        assert words == ["alpha", "beta", "gamma"]


def test_words_from_url_rejects_non_http() -> None:
    import pytest

    from ttyping.words import words_from_url

    with pytest.raises(ValueError):
        words_from_url("file:///etc/passwd")


def test_words_from_url_count_cap() -> None:

    from ttyping.words import words_from_url

    class FakeResp:
        payload = b"w1 w2 w3 w4 w5"

        def read(self, n: int) -> bytes:
            return self.payload[:n]

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *a: object) -> None:
            pass

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        assert words_from_url("http://x.com/t.txt", count=3) == ["w1", "w2", "w3"]
        assert len(words_from_url("http://x.com/t.txt")) == 5


def test_app_uses_url_words(monkeypatch: object) -> None:
    import asyncio

    async def run_test() -> None:
        app = TypingApp(lang="en_qwerty", word_count=25, url="http://x.com/t.txt")
        async with app.run_test():
            with patch(
                "ttyping.app.words_from_url",
                return_value=["url", "words"],
            ) as m:
                words = app._get_words()
                assert m.called
                assert words == ["url", "words"]

    asyncio.run(run_test())


def test_target_wpm_option_and_progress_bar() -> None:
    import asyncio

    async def run_test() -> None:
        from textual.widgets import Input, ProgressBar

        from ttyping.screens import HistoryScreen, TargetWpmInputScreen
        from ttyping.storage import TypingResult, save_result

        # Save some results to produce an average WPM of 50
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
        save_result(
            TypingResult(
                wpm=60.0,
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
            # Set target WPM to 100 via TargetWpmInputScreen
            target_screen = TargetWpmInputScreen()
            await app.push_screen(target_screen)
            await pilot.pause()
            input_widget = target_screen.query_one("#wpm-input", Input)
            target_screen.on_input_submitted(Input.Submitted(input_widget, "100"))
            await pilot.pause()

            assert app._target_wpm == 100
            assert storage.load_config()["target_wpm"] == 100

            # View History screen -> should display ProgressBar showing 50/100
            history_screen = HistoryScreen()
            await app.push_screen(history_screen)
            await pilot.pause()

            pb = history_screen.query_one(ProgressBar)
            assert pb.total == 100.0
            assert pb.progress == 50.0

    asyncio.run(run_test())
