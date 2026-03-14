from unittest.mock import patch

from pytest import CaptureFixture

from ttyping.__main__ import main


def test_main_default_args() -> None:
    with patch("sys.argv", ["ttyping"]), patch("ttyping.app.TypingApp") as mock_app:
        main()
        mock_app.assert_called_once_with(
            lang=None,
            file_path=None,
            word_count=None,
            duration=None,
            target_accuracy=None,
            show_history=False,
        )
        mock_app.return_value.run.assert_called_once()


def test_main_with_args() -> None:
    args = [
        "ttyping",
        "--lang",
        "ko",
        "--file",
        "test.txt",
        "--words",
        "50",
        "--time",
        "60",
        "--target-accuracy",
        "95.5",
    ]
    with patch("sys.argv", args), patch("ttyping.app.TypingApp") as mock_app:
        main()
        mock_app.assert_called_once_with(
            lang="ko",
            file_path="test.txt",
            word_count=50,
            duration=60,
            target_accuracy=95.5,
            show_history=False,
        )
        mock_app.return_value.run.assert_called_once()


def test_main_word_limit() -> None:
    args = ["ttyping", "--words", "2000"]
    with patch("sys.argv", args), patch("ttyping.app.TypingApp") as mock_app:
        main()
        mock_app.assert_called_once_with(
            lang=None,
            file_path=None,
            word_count=1000,
            duration=None,
            target_accuracy=None,
            show_history=False,
        )
        mock_app.return_value.run.assert_called_once()


def test_main_history_command() -> None:
    args = ["ttyping", "history"]
    with patch("sys.argv", args), patch("ttyping.app.TypingApp") as mock_app:
        main()
        mock_app.assert_called_once_with(
            lang=None,
            file_path=None,
            word_count=None,
            duration=None,
            target_accuracy=None,
            show_history=True,
        )
        mock_app.return_value.run.assert_called_once()


def test_main_serve_command() -> None:
    with (
        patch("sys.argv", ["ttyping", "serve"]),
        patch("asyncio.run") as mock_asyncio_run,
        patch("ttyping.server.start_server") as mock_start_server,
    ):
        main()
        mock_start_server.assert_called_once()
        # Cannot assert asyncio.run with exactly what it was called with (coroutine)
        assert mock_asyncio_run.call_count == 1


def test_main_serve_keyboard_interrupt() -> None:
    with (
        patch("sys.argv", ["ttyping", "serve"]),
        patch("asyncio.run", side_effect=KeyboardInterrupt),
        patch("ttyping.server.start_server"),
    ):
        # Should not raise
        main()


def test_main_serve_exception(capsys: CaptureFixture[str]) -> None:
    with (
        patch("sys.argv", ["ttyping", "serve"]),
        patch("asyncio.run", side_effect=RuntimeError("serve error")),
        patch("ttyping.server.start_server"),
        patch("sys.exit") as mock_exit,
    ):
        main()
        mock_exit.assert_called_once_with(1)
        captured = capsys.readouterr()
        assert "Sentinel: Server error encountered: serve error" in captured.err


def test_main_app_exception(capsys: CaptureFixture[str]) -> None:
    with (
        patch("sys.argv", ["ttyping"]),
        patch("ttyping.app.TypingApp") as mock_app,
        patch("sys.exit") as mock_exit,
    ):
        mock_app.side_effect = ValueError("app error")
        main()
        mock_exit.assert_called_once_with(1)
        captured = capsys.readouterr()
        assert "Sentinel: Application error encountered: app error" in captured.err


def test_if_name_main() -> None:
    with patch("sys.argv", ["ttyping", "--help"]):
        import runpy

        try:
            runpy.run_module("ttyping.__main__", run_name="__main__")
        except SystemExit:
            pass
