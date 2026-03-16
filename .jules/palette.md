## 2026-03-07 - Add Keyboard Shortcuts to Main Menu
**Learning:** Terminal TUIs with arrow-key-only navigation can be tedious. Users benefit immensely from single-key shortcuts (`E`, `K`, `W`, `H`, `O`, `Q`) combined with clear label hints.
**Action:** Always consider `BINDINGS` for main OptionLists in Textual to provide immediate, accessible navigation.

## 2026-03-09 - Terminal Input Validation UX
**Learning:** Input fields in TUI frameworks often suffer from persistent error states if not actively cleared. Using native constraints like `type="integer"` with active `on_input_changed` error-clearing prevents users from seeing stale error messages while correcting input.
**Action:** When implementing numeric inputs in TUIs, use strict typing (`type="integer"`) and clear validation errors immediately on subsequent keystrokes (`on_input_changed`).

## 2026-03-14 - Textual OptionList Keyboard Shortcuts
**Learning:** In Textual UI, assigning `BINDINGS` with `show=False` prevents shortcut discoverability. Aligning `[dim]\[key][/dim]` tags directly inside `OptionList` items via Rich markup is an accessible, elegant pattern to reveal them without cluttering the bottom Footer widget.
**Action:** Use `Text.from_markup` with `[dim]` tags to neatly inline key hints for all Textual `OptionList`s.

## 2026-03-15 - Multi-language Input State Friction
**Learning:** Users who frequently switch between languages (like English and Korean) often try to trigger English keyboard shortcuts while their system input method is still set to Korean. This causes friction as standard bindings fail.
**Action:** Always map the corresponding alternative language IME keys (e.g., mapping 'ㅂ' when binding 'q' for quit) as hidden bindings (`show=False`) to ensure standard navigation hotkeys work regardless of the active keyboard language.
