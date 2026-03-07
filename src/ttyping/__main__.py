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
        choices=["en_qwerty", "en_dvorak", "ko_2set", "ko_3set", "en", "ko"],
        help="language for random words",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="path to a text file for typing practice",
    )
    parser.add_argument(
        "--words",
        type=int,
        help="number of words to type (max: 1000)",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=int,
        help="duration of the test in seconds (overrides --words)",
    )
    parser.add_argument(
        "--target-accuracy",
        "-a",
        type=float,
        help="target accuracy percentage (0-100); restart on drop",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["history", "serve"],
        help="subcommand (history: view past results)",
    )

    args = parser.parse_args()

    # Security: Limit number of words to avoid excessive memory allocation
    if args.words and args.words > 1000:
        args.words = 1000

    from ttyping.app import TypingApp

    if args.command == "serve":
        import asyncio

        from ttyping.server import start_server

        try:
            asyncio.run(start_server())
        except KeyboardInterrupt:
            pass
        except Exception as e:
            import sys

            print(f"Sentinel: Server error encountered: {e}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        app = TypingApp(
            lang=args.lang,
            file_path=args.file,
            word_count=args.words,
            duration=args.time,
            target_accuracy=args.target_accuracy,
            show_history=args.command == "history",
        )
        app.run()
    except Exception as e:
        import sys

        print(f"Sentinel: Application error encountered: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
