# Project Instructions (for AI Agents)

## Project Overview

`ttyping` provides a clean and focused typing practice environment directly in the terminal. It tracks speed (WPM) and accuracy, saving results locally for history viewing. A minimal, monkeytype-inspired terminal typing test for English and Korean, built with Python and Textual.

## Building and Running

### Development Commands
- Run the app: `uv run ttyping`
- Run with specific options:
    - Korean: `uv run ttyping --lang ko`
    - Custom word count: `uv run ttyping --words 50`
    - Practice from file: `uv run ttyping --file path/to/text.txt`
    - View history: `uv run ttyping history`

### Installation
- Local editable install: `uv pip install -e .`
- Install as a tool: `uv tool install .`

