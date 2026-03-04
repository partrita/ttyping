"""CLI entry point for ttyping."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ttyping",
        description="A minimal terminal typing test",
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ko", "alice", "pride"],
        default="en",
        help="language for random words (default: en)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="path to a text file for typing practice",
    )
    parser.add_argument(
        "--words",
        type=int,
        default=25,
        help="number of words to type (default: 25, max: 1000)",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=int,
        default=None,
        help="duration of the test in seconds (overrides --words)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["history", "serve"],
        help="subcommand (history: view past results)",
    )

    args = parser.parse_args()

    # Security: Limit number of words to avoid excessive memory allocation
    if args.words > 1000:
        args.words = 1000

    # If no specific test args provided, show menu
    import sys

    from ttyping.app import TypingApp
    is_default = (len(sys.argv) == 1)

    if args.command == "serve":
        import asyncio

        from ttyping.server import start_server
        try:
            asyncio.run(start_server())
        except KeyboardInterrupt:
            pass
        return

    app = TypingApp(
        lang=args.lang,
        file_path=args.file,
        word_count=args.words,
        duration=args.time,
        show_history=args.command == "history",
        show_menu=is_default
    )
    app.run()


if __name__ == "__main__":
    main()
