# ttyping

A minimal, monkeytype-inspired terminal typing test for English and Korean, built with Python and Textual.

## Project Overview

`ttyping` provides a clean and focused typing practice environment directly in the terminal. It tracks speed (WPM) and accuracy, saving results locally for history viewing.

### Tech Stack
- **Language:** Python 3.10+
- **TUI Framework:** [Textual](https://github.com/Textualize/textual)
- **Styling/Formatting:** [Rich](https://github.com/Textualize/rich)
- **Dependency Management:** [uv](https://github.com/astral-sh/uv) (recommended) or pip
- **Build System:** Hatchling

### Core Architecture
- **`src/ttyping/__main__.py`**: CLI entry point. Handles argument parsing (`argparse`).
- **`src/ttyping/app.py`**: The main `TypingApp` class. Manages the screen stack and application-level state.
- **`src/ttyping/screens.py`**: Contains the UI logic:
    - `TypingScreen`: The interactive typing test.
    - `ResultScreen`: Summary shown after a test completes.
    - `HistoryScreen`: A table view of past results.
- **`src/ttyping/storage.py`**: Handles persistent storage of results in `~/.ttyping/results.json`.
- **`src/ttyping/words.py`**: Provides internal word lists (English/Korean) and file reading capabilities.

## Building and Running

### Development Commands
- **Run the app:** `uv run ttyping`
- **Run with specific options:**
    - Korean: `uv run ttyping --lang ko`
    - Custom word count: `uv run ttyping --words 50`
    - Practice from file: `uv run ttyping --file path/to/text.txt`
    - View history: `uv run ttyping history`

### Installation
- **Local editable install:** `pip install -e .` or `uv pip install -e .`
- **Install as a tool:** `uv tool install .`

## Development Conventions

### Coding Style
- Uses modern Python features (type hints, `from __future__ import annotations`).
- UI styling is defined via Textual's CSS-like `DEFAULT_CSS` in screen classes or `TypingApp.CSS`.
- Monkeytype-inspired color palette is defined as constants in `screens.py`.

### UI/UX Rules
- **Tab**: Restart the test.
- **Esc**: Quit the application.
- **Space**: Proceed to the next word.
- Results are calculated based on characters per minute (CPM / 5) for WPM and character-level accuracy.

### Data Storage
- Data is stored in JSON format at `~/.ttyping/results.json`.
- Each result entry includes `wpm`, `accuracy`, `lang`, `word_count`, and an ISO-formatted `date`.
