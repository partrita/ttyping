import time
from typing import Any

import pytest

from ttyping.screens import TypingScreen


def test_accuracy_calculation_method() -> None:
    # Setup a TypingScreen with dummy data
    screen = TypingScreen(words=["apple", "banana"], target_accuracy=90.0)
    screen.start_time = time.time() - 60  # 1 minute ago

    # Simulate 100 keystrokes with 10 errors
    screen.total_keystrokes = 100
    screen.total_errors = 10
    screen.uncorrected_errors = 2

    stats = screen._get_current_stats()
    assert stats["accuracy"] == 90.0
    assert stats["keystrokes"] == 100
    assert stats["errors"] == 10
    # WPM: (100/5)/1 = 20 gross, 20 - 2 = 18 net
    assert stats["wpm"] == 18.0


def test_accuracy_drop_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockApp:
        def __init__(self) -> None:
            self.reset_called = False
            self.screen_stack = [1]

        def reset_session_attempt(self, stats: dict[str, Any]) -> None:
            self.reset_called = True

    app = MockApp()
    screen = TypingScreen(words=["apple", "banana"], target_accuracy=95.0)
    
    # Mock query_one to return a mock widget for #accuracy-warning
    class MockWidget:
        def __init__(self) -> None:
            self.styles = type("Styles", (), {"display": "none"})()
    
    warning_widget = MockWidget()
    monkeypatch.setattr(
        screen,
        "query_one",
        lambda sel: warning_widget if sel == "#accuracy-warning" else None,
    )
    
    # Patch the property 'app'
    monkeypatch.setattr(TypingScreen, "app", app)
    # Patch set_timer to execute immediately for testing
    monkeypatch.setattr(screen, "set_timer", lambda delay, callback: callback())
    
    screen.start_time = time.time()

    # 10 keystrokes, 1 error -> 90% accuracy < 95% target
    screen.total_keystrokes = 10
    screen.total_errors = 1

    # Trigger _complete_word
    screen._complete_word("apple")

    assert app.reset_called is True
    assert screen._finished is True
    assert warning_widget.styles.display == "block"


def test_accuracy_pass_no_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockApp:
        def __init__(self) -> None:
            self.reset_called = False
            self.screen_stack = [1, 2]

        def reset_session_attempt(self, stats: dict[str, Any]) -> None:
            self.reset_called = True

        def _end_test(self) -> None:
            pass

        def show_result(self, res: dict[str, Any]) -> None:
            pass

    app = MockApp()
    screen = TypingScreen(words=["apple"], target_accuracy=80.0)
    # Patch the property 'app'
    monkeypatch.setattr(TypingScreen, "app", app)
    # Mocking self.app.show_result in _end_test if it reaches end
    monkeypatch.setattr(screen, "_end_test", lambda: None)
    screen.start_time = time.time()

    # 10 keystrokes, 1 error -> 90% accuracy > 80% target
    screen.total_keystrokes = 10
    screen.total_errors = 1

    screen._complete_word("apple")

    assert app.reset_called is False
