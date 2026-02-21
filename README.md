# ttyping

A minimal, monkeytype-inspired terminal typing test. English & Korean.

## Install

```
pip install ttyping
```

Or with uv:

```
uv tool install ttyping
```

## Usage

```
ttyping                    # English, 25 random words
ttyping --lang ko          # Korean random words
ttyping --file path.txt    # Practice from file
ttyping --words 50         # Custom word count
ttyping --time 30          # 30-second timed test
ttyping history            # View past results
```

## Keybindings

| Key   | Action         |
|-------|----------------|
| Tab   | Restart test   |
| Esc   | Quit           |
| Space | Next word      |

Results are saved locally at `~/.ttyping/results.json`.
