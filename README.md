# ttyping ⌨️

![](./screenshot.png)

A minimal, monkeytype-inspired terminal typing test for English and Korean, built with Python and [Textual](https://github.com/Textualize/textual).

`ttyping` provides a clean and focused typing practice environment directly in your terminal. It tracks speed (WPM) and accuracy, saving results locally for history viewing.

## ✨ Features

- **Multi-language Support**: Practice English (Qwerty, Dvorak, Colemak) and Korean (2-set, 3-set).
- **Finger Practice**: Target specific finger groups to improve muscle memory.
- **Accuracy Focused**: Optional target accuracy mode that restarts on mistakes.
- **Local History**: Keep track of your speed (WPM) and accuracy over time.

## 🚀 Installation

Install using `uv` (recommended):

```bash
uv tool install ttyping
```

## 🎮 Usage

Run the app without arguments to start English practice:

```bash
uvx ttyping
```

## ⌨️ Keybindings

| Key | Action |
|-----|--------|
| **e, k, w, h, o, q** | Main Menu shortcuts (English, Korean, Weak, History, Options, Quit) |
| **Tab** | Restart the test |
| **Esc** | Go back to previous menu |
| **Ctrl+C** | Quit the application |
| **Space** | Proceed to the next word |
| **Enter** | Select menu option or complete word |

## 🗺️ Roadmap

Feature ideas planned for upcoming releases:

### Practice Modes
- **Quote Mode**: Type full English/Korean quotes with real punctuation and capitalization.
- **Zen Mode**: Unlimited free typing — no word count, end whenever you want.
- **Time Presets**: Quick-select 15s / 30s / 60s / 120s durations from the menu.
- **Daily Challenge**: A seeded word set that changes once a day.

### Feedback & Statistics
- **Live WPM Graph**: Real-time speed curve rendered while typing.
- **Consistency Score**: Measure keystroke rhythm stability per test.
- **Personal Bests**: Track record WPM/accuracy per language and mode.
- **Keyboard Heatmap**: Visual layout map of cumulative error stats (extends Weakness Analysis).

### UX & Customization
- **Custom Themes**: User-defined accent colors beyond dark/light.
- **Keypress Sound**: Optional audio/tick feedback while typing.
- **History Export**: Export results to CSV/JSON for external analysis.
- **Configurable Keybindings**: Remap shortcuts from the Options menu.

### Content
- **More Code Languages**: Go, C, TypeScript snippets.
- **Remote Word Lists**: Load practice text from a URL, not just local files.
- **Additional Languages**: Japanese (romaji/kana) and other layouts.

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **TUI Framework**: [Textual](https://github.com/Textualize/textual)
- **Styling**: [Rich](https://github.com/Textualize/rich)
- **Data storage**: `~/.ttyping/results.json`

## 📄 License

Apache-2.0
