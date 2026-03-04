from pathlib import Path

path = Path("src/ttyping/__main__.py")
content = path.read_text()

# Update help for --lang
content = content.replace(
    'choices=["en", "ko"],',
    'choices=["en", "ko", "alice", "pride"],'
)

# Detect if any relevant arguments are provided
old_call = """    from ttyping.app import TypingApp

    app = TypingApp(
        lang=args.lang,
        file_path=args.file,
        word_count=args.words,
        duration=args.time,
        show_history=args.command == "history",
    )"""

new_call = """    from ttyping.app import TypingApp

    # If no specific test args provided, show menu
    import sys
    is_default = (len(sys.argv) == 1)

    app = TypingApp(
        lang=args.lang,
        file_path=args.file,
        word_count=args.words,
        duration=args.time,
        show_history=args.command == "history",
        show_menu=is_default
    )"""

content = content.replace(old_call, new_call)

path.write_text(content)
