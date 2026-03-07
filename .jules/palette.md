## 2026-03-07 - Add Keyboard Shortcuts to Main Menu
**Learning:** Terminal TUIs with arrow-key-only navigation can be tedious. Users benefit immensely from single-key shortcuts (`E`, `K`, `W`, `H`, `O`, `Q`) combined with clear label hints.
**Action:** Always consider `BINDINGS` for main OptionLists in Textual to provide immediate, accessible navigation.

## 2026-03-07 - Add Korean IME Support
**Learning:** Korean IME (2-set) requires specific keybindings to function correctly.
**Action:** Add Korean IME support to the app by adding the following keybindings to the `BINDINGS` list:
- `Binding("ㅇ", "delete_selected", show=False)`
- `Binding("ㅗ", "history", show=False)`
- `Binding("ㅛ", "confirm", show=False)`
- `Binding("ㅜ", "cancel", show=False)`
