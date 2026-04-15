"""Tests for the main module's CLI argument parsing."""

from __future__ import annotations

import pytest

from ttyping.__main__ import parse_args


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.lang is None
    assert args.file is None
    assert args.words is None
    assert args.time is None
    assert args.target_accuracy is None
    assert args.command is None


def test_parse_args_with_options() -> None:
    args = parse_args(
        [
            "--lang",
            "ko_2set",
            "--file",
            "practice.txt",
            "--words",
            "100",
            "--time",
            "60",
            "--target-accuracy",
            "95.5",
        ]
    )
    assert args.lang == "ko_2set"
    assert args.file == "practice.txt"
    assert args.words == 100
    assert args.time == 60
    assert args.target_accuracy == 95.5


def test_parse_args_history_command() -> None:
    args = parse_args(["history"])
    assert args.command == "history"


def test_parse_args_invalid_lang(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--lang", "invalid_lang"])

    captured = capsys.readouterr()
    assert "invalid choice: 'invalid_lang'" in captured.err


def test_parse_args_invalid_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["invalid_command"])

    captured = capsys.readouterr()
    assert "invalid choice: 'invalid_command'" in captured.err


def test_parse_args_negative_words() -> None:
    from unittest.mock import patch

    from ttyping.__main__ import main

    with (
        patch("sys.argv", ["ttyping", "--words", "-10"]),
        patch("ttyping.app.TypingApp") as mock_app,
    ):
        main()
        mock_app.assert_called_once()
        _, kwargs = mock_app.call_args
        assert kwargs["word_count"] == 1
