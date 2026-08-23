# ttyping ⌨️

[English](README.en.md) | [한국어](README.md)

![](./screenshot.png)

A minimal, monkeytype-inspired terminal typing test for English and Korean, built with Python and [Textual](https://github.com/Textualize/textual).

`ttyping` provides a clean and focused typing practice environment directly in your terminal. It tracks speed (WPM) and accuracy, saving results locally for history viewing.

## ✨ Features

- **Multi-language Support**: Practice English (Qwerty, Dvorak, Colemak), Korean (2-set, 3-set), and various programming languages (Python, Rust, R, JavaScript, TypeScript, Go, C, Julia, Typst, Markdown).
- **Finger & Row Practice**: Target specific finger groups and keyboard rows to improve muscle memory.
- **Various Practice Modes**: Sentences, Quotes, Lorem Ipsum, and Daily Challenge.
- **Accuracy Focused**: Optional target accuracy mode that restarts on mistakes.
- **Detailed Analytics**: Keystroke consistency score, error heatmaps, and character-level speed visualization.
- **Local History & Export**: Keep track of your speed (WPM) and accuracy over time, with CSV/JSON export support.

## 🚀 Installation

Install using `uv` (recommended):

```bash
uv tool install ttyping
```

Or run directly without installation:

```bash
uvx ttyping
```

## 🎮 Usage

### Basic Execution
```bash
# Start English typing practice (default)
uvx ttyping

# Practice Korean
uvx ttyping --lang ko

# Practice code typing (e.g. Python, Rust, Go, TypeScript)
uvx ttyping --lang python

# Set word count limit (1-1000)
uvx ttyping --words 50

# Set time limit (in seconds)
uvx ttyping --time 60

# Set target accuracy mode (restarts if accuracy drops below target)
uvx ttyping --target-accuracy 95

# Practice with a local text file
uvx ttyping --file practice.txt

# Practice with remote text from a URL
uvx ttyping --url https://example.com/text.txt

# View past history
uvx ttyping history
```

## ⌨️ Keybindings

### Main Menu
| Key | Action |
|-----|--------|
| **e** / **ㄷ** | English typing menu |
| **k** / **ㅏ** | Korean typing menu |
| **p** / **ㅔ** | Code typing menu |
| **w** / **ㅈ** | Weakness & error analysis |
| **h** / **ㅗ** | History view |
| **o** / **ㅐ** | Options |
| **q** / **Esc** / **ㅂ** | Quit |

### During Typing
| Key | Action |
|-----|--------|
| **Space** | Complete current word and proceed to next |
| **Enter** | Complete current word / finish |
| **Ctrl+W** | Clear current input |
| **Tab** | Restart current test |
| **Esc** | Return to previous menu |

### History Screen
| Key | Action |
|-----|--------|
| **d** / **ㅇ** | Delete selected record |
| **Shift+D** | Delete all records |
| **x** | Export history to CSV |
| **j** | Export history to JSON |
| **Esc** | Return to previous menu |

## 🗺️ Changelog Highlights

### Practice Modes
- ✅ **Quote Mode**: Full English/Korean quotes with real punctuation and capitalization.
- ✅ **Sentence & Lorem Ipsum Modes**: Natural sentences and classic Lorem Ipsum text generation.
- ✅ **Time Presets**: Quick-select 15s / 30s / 60s / 120s from the Options menu or CLI.

### Feedback & Statistics
- ✅ **Keyboard Heatmap**: Layout-aware map of cumulative errors in Weakness Analysis.
- ✅ **Speed Map**: Character-level color-coded speed visualization on the results screen.

### UX & Customization
- ✅ **Custom Themes**: Clean Dark and Light mode support.
- ✅ **History Export**: Export results easily to CSV (`x`) or JSON (`j`).

### Content
- ✅ **Code Languages**: Python, Rust, R, JavaScript, TypeScript, Go, C, Julia, Typst, Markdown snippets.
- ✅ **Remote Word Lists**: Load practice text directly from HTTP/HTTPS URLs (`--url`).

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **TUI Framework**: [Textual](https://github.com/Textualize/textual)
- **Styling**: [Rich](https://github.com/Textualize/rich)
- **Data storage**: `~/.ttyping/results.json`

## 📄 License

Apache-2.0
