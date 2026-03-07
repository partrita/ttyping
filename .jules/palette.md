# Palette Persona Learning Journal

## [Current Task] - Unused exit_app function

### Micro-UX/A11y Improvements
- While the task was purely "Code Health", keeping the codebase consistent with standard Textual patterns (calling `app.exit()` instead of custom wrappers) ensures that future developers are less likely to introduce confusion or bugs when adding new UI elements.

### UX/A11y Insights
- Textual's standard keyboard focus and event handling are generally robust. Maintaining a thin app layer helps keep keyboard shortcuts (like `Esc` for quit) simple and reliable across different screens.
