from pathlib import Path

path = Path("src/ttyping/__main__.py")
content = path.read_text()

# Add serve choice
content = content.replace(
    'choices=["history"],',
    'choices=["history", "serve"],'
)

# Handle serve command
old_call = """    app = TypingApp(
        lang=args.lang,
        file_path=args.file,
        word_count=args.words,
        duration=args.time,
        show_history=args.command == "history",
        show_menu=is_default
    )
    app.run()"""

new_call = """    if args.command == "serve":
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
    app.run()"""

content = content.replace(old_call, new_call)

path.write_text(content)
