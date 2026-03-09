## 2026-03-07 - Add Keyboard Shortcuts to Main Menu
**Learning:** Terminal TUIs with arrow-key-only navigation can be tedious. Users benefit immensely from single-key shortcuts (`E`, `K`, `W`, `H`, `O`, `Q`) combined with clear label hints.
**Action:** Always consider `BINDINGS` for main OptionLists in Textual to provide immediate, accessible navigation.

## 2026-03-09 - Terminal Input Validation UX
**Learning:** Input fields in TUI frameworks often suffer from persistent error states if not actively cleared. Using native constraints like `type="integer"` with active `on_input_changed` error-clearing prevents users from seeing stale error messages while correcting input.
**Action:** When implementing numeric inputs in TUIs, use strict typing (`type="integer"`) and clear validation errors immediately on subsequent keystrokes (`on_input_changed`).
