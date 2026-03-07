from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from ttyping.app import TypingApp
from ttyping.screens import ResultScreen, TypingScreen, WordCountMenu
from ttyping.storage import TypingResult


@pytest.fixture
def mock_app() -> MagicMock:
    # Mock the App object entirely to avoid Textual context issues
    app = MagicMock(spec=TypingApp)
    # Using a list we can manipulate instead of the real property
    app.screen_stack = []
    # Make sure 'screen' property returns the last element of the stack
    type(app).screen = PropertyMock(
        side_effect=lambda: app.screen_stack[-1] if app.screen_stack else None
    )
    return app


def test_action_go_back_safety_typing_screen(mock_app: MagicMock) -> None:
    screen = TypingScreen(words=["test"])
    # Patch the 'app' property on the instance
    with patch.object(TypingScreen, "app", new_callable=PropertyMock) as mock_app_prop:
        mock_app_prop.return_value = mock_app

        # 1. Test when stack has only 1 screen
        mock_app.screen_stack = [screen]
        screen.action_go_back()
        mock_app.pop_screen.assert_not_called()

        # 2. Test when stack has more than 1 screen
        mock_app.screen_stack = [MagicMock(), screen]
        screen.action_go_back()
        mock_app.pop_screen.assert_called_once()


def test_action_go_back_safety_result_screen(mock_app: MagicMock) -> None:
    result = MagicMock(spec=TypingResult)
    screen = ResultScreen(result=result)
    with patch.object(ResultScreen, "app", new_callable=PropertyMock) as mock_app_prop:
        mock_app_prop.return_value = mock_app

        # 1. Test when stack has only 1 screen
        mock_app.screen_stack = [screen]
        screen.action_go_back()
        mock_app.pop_screen.assert_not_called()

        # 2. Test when stack has more than 1 screen
        mock_app.screen_stack = [MagicMock(), screen]
        screen.action_go_back()
        mock_app.pop_screen.assert_called_once()


def test_action_go_back_safety_word_count_menu(mock_app: MagicMock) -> None:
    screen = WordCountMenu(layout_id="en")
    with patch.object(WordCountMenu, "app", new_callable=PropertyMock) as mock_app_prop:
        mock_app_prop.return_value = mock_app

        # 1. Test when stack has only 1 screen
        mock_app.screen_stack = [screen]
        screen.action_go_back()
        mock_app.pop_screen.assert_not_called()

        # 2. Test when stack has more than 1 screen
        mock_app.screen_stack = [MagicMock(), screen]
        screen.action_go_back()
        mock_app.pop_screen.assert_called_once()


def test_app_restart_preserves_menu_stack() -> None:
    with (
        patch("ttyping.storage.load_config", return_value={}),
        patch("ttyping.storage.save_config"),
        patch("ttyping.app.get_words", return_value=["word"]),
    ):
        app = TypingApp()
        menu_screen = MagicMock()
        typing_screen = TypingScreen(words=["word"])

        # Internal state to track the stack
        current_stack = [menu_screen, typing_screen]

        # Use patch.object to mock the screen_stack property
        with (
            patch.object(
                TypingApp, "screen_stack", new_callable=PropertyMock
            ) as mock_stack,
            patch.object(
                TypingApp, "screen", new_callable=PropertyMock
            ) as mock_screen_prop,
            patch.object(TypingApp, "pop_screen") as mock_pop,
            patch.object(TypingApp, "_start_typing") as mock_start,
        ):
            # Configure side effects to update the stack state
            mock_stack.side_effect = lambda: current_stack
            mock_screen_prop.side_effect = lambda: (
                current_stack[-1] if current_stack else None
            )

            def pop_effect() -> None:
                if current_stack:
                    current_stack.pop()

            mock_pop.side_effect = pop_effect

            app.restart()

            # Since TypingScreen is in the stack and is the current screen,
            # pop_screen should have been called once before starting a new test.
            mock_pop.assert_called_once()
            mock_start.assert_called_once_with(keep_words=False)
            # current_stack should now only contain the menu_screen
            assert current_stack == [menu_screen]
