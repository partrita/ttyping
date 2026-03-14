from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ttyping.server import TtypingSSHServer, TtypingSSHSession, start_server


def test_ssh_server_session_requested() -> None:
    server = TtypingSSHServer()
    session = server.session_requested()
    assert isinstance(session, TtypingSSHSession)


def test_ssh_session_defaults() -> None:
    session = TtypingSSHSession()
    assert session._chan is None
    assert isinstance(session._input, asyncio.Queue)
    assert session._input.empty()


def test_ssh_session_connection_made() -> None:
    session = TtypingSSHSession()
    mock_chan = MagicMock()
    session.connection_made(mock_chan)
    assert session._chan == mock_chan


def test_ssh_session_shell_requested() -> None:
    session = TtypingSSHSession()
    assert session.shell_requested() is True


def test_ssh_session_exec_requested() -> None:
    session = TtypingSSHSession()
    assert session.exec_requested("some command") is False


def test_ssh_session_terminal_size_changed() -> None:
    session = TtypingSSHSession()
    # Ensure it doesn't raise an exception
    session.terminal_size_changed(80, 24, 0, 0)


def test_start_server(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("ttyping.server.TypingApp") as mock_app:
        asyncio.run(start_server("127.0.0.1", 8022))

        captured = capsys.readouterr()

        # Verify print output
        assert "Starting ttyping SSH server on 127.0.0.1:8022..." in captured.out
        expected_msg = "SSH Server implementation is ready. Run with 'ttyping serve'"
        assert expected_msg in captured.out

        # Verify create_app() -> TypingApp(show_menu=True) was called
        mock_app.assert_called_once_with(show_menu=True)
