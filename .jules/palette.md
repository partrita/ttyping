## 2026-03-07 - Add Keyboard Shortcuts to Main Menu
**Learning:** Terminal TUIs with arrow-key-only navigation can be tedious. Users benefit immensely from single-key shortcuts (`E`, `K`, `W`, `H`, `O`, `Q`) combined with clear label hints.
**Action:** Always consider `BINDINGS` for main OptionLists in Textual to provide immediate, accessible navigation.

## 2026-03-09 - Terminal Input Validation UX
**Learning:** Input fields in TUI frameworks often suffer from persistent error states if not actively cleared. Using native constraints like `type="integer"` with active `on_input_changed` error-clearing prevents users from seeing stale error messages while correcting input.
**Action:** When implementing numeric inputs in TUIs, use strict typing (`type="integer"`) and clear validation errors immediately on subsequent keystrokes (`on_input_changed`).

## 2026-03-14 - Textual OptionList Keyboard Shortcuts
**Learning:** In Textual UI, assigning `BINDINGS` with `show=False` prevents shortcut discoverability. Aligning `[dim][key][/dim]` tags directly inside `OptionList` items via Rich markup is an accessible, elegant pattern to reveal them without cluttering the bottom Footer widget.
**Action:** Use `Text.from_markup` with `[dim]` tags to neatly inline key hints for all Textual `OptionList`s.

## 2024-05-15 - Improve discoverability of hidden keyboard bindings in Textual MenuScreen
**Learning:** In Textual OptionLists, hidden key bindings (where `show=False`) can be explicitly surfaced to the user by appending them to the option label text using Rich markup. This significantly improves keyboard navigation discoverability, making it clearer that users can press a specific key to select an option without relying on the global footer which might be hidden or cluttered. We use a raw string `r"..."` to properly escape the literal bracket `\[` in Rich markup like `[dim]\[e][/dim]`.
**Action:** When implementing or modifying Textual OptionLists that have corresponding hidden keyboard bindings for their selection, consider adding explicit hints to the Option labels using Rich markup to improve UX and accessibility.
