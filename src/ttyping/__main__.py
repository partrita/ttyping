"""CLI entry point for ttyping."""

from __future__ import annotations

import argparse
import sys

from ttyping.storage import load_config, save_config


def main() -> None:
    config = load_config()

    parser = argparse.ArgumentParser(
        prog="ttyping",
        description="A minimal terminal typing test",
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ko"],
        default=config.get("lang", "en"),
        help="language for random words (default: en)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=config.get("file"),
        help="path to a text file for typing practice",
    )
    parser.add_argument(
        "--words",
        type=int,
        default=config.get("words", 25),
        help="number of words to type (default: 25, max: 1000)",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=int,
        default=config.get("time"),
        help="duration of the test in seconds (overrides --words)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["history"],
        help="subcommand (history: view past results)",
    )

    args = parser.parse_args()

    # If the user explicitly provided one of the mode flags, clear the others
    # to avoid mixing saved state (e.g., if --words is saved, but --time is passed now)
    cli_args = sys.argv[1:]
    if "--time" in cli_args or "-t" in cli_args:
        args.words = 25  # Reset to default if time is explicitly set
        args.file = None
    elif "--words" in cli_args:
        args.time = None
        args.file = None
    elif "--file" in cli_args:
        args.time = None
        args.words = 25

    # Security: Limit number of words to avoid excessive memory allocation
    if args.words > 1000:
        args.words = 1000

    # Save configuration (unless viewing history)
    if args.command != "history":
        new_config = {
            "lang": args.lang,
            "words": args.words,
            "time": args.time,
            "file": args.file,
        }
        save_config(new_config)

    from ttyping.app import TypingApp

    app = TypingApp(
        lang=args.lang,
        file_path=args.file,
        word_count=args.words,
        duration=args.time,
        show_history=args.command == "history",
    )
    app.run()


if __name__ == "__main__":
    main()
