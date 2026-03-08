# ttyping ⌨️

A minimal, monkeytype-inspired terminal typing test for English and Korean, built with Python and [Textual](https://github.com/Textualize/textual).

`ttyping` provides a clean and focused typing practice environment directly in your terminal. It tracks speed (WPM) and accuracy, saving results locally for history viewing.

## ✨ Features

- **Multi-language Support**: Practice English (QWERTY, Dvorak, Colemak) and Korean (2-set, 3-set).
- **Custom Content**: Type from internal word lists, sentences, or your own text files.
- **Finger Practice**: Target specific finger groups to improve muscle memory.
- **Accuracy Focused**: Optional target accuracy mode that restarts on mistakes.
- **Local History**: Keep track of your speed (WPM) and accuracy over time.

## 🚀 Installation

Install using `uv` (recommended):

```bash
uv tool install ttyping
```

Or with `pip`:

```bash
pip install ttyping
```

## 🎮 Usage

Run the app without arguments to start English practice:

```bash
ttyping
```

### CLI Options

| Argument | shorthand | Description |
|----------|-----------|-------------|
| `--file [path]` | | Practice using a custom text file |
| `--words [n]` | | Set number of words (max 1000) |
| `--time [s]` | `-t` | Set test duration in seconds (overrides words) |
| `--target-accuracy [n]` | `-a` | Set target (0-100); restarts on drop below |
| `history` | | View past results directly |

## ⌨️ Keybindings

| Key | Action |
|-----|--------|
| **e, k, w, h, o, q** | Main Menu shortcuts (English, Korean, Weak, History, Options, Quit) |
| **Tab** | Restart the test |
| **Esc** | Go back to previous menu |
| **Ctrl+C** | Quit the application |
| **Space** | Proceed to the next word |
| **Enter** | Select menu option or complete word |

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **TUI Framework**: [Textual](https://github.com/Textualize/textual)
- **Styling**: [Rich](https://github.com/Textualize/rich)
- **Data storage**: `~/.ttyping/results.json`

## 📄 License

Apache-2.0
