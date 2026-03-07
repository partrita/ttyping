# Performance Learning Journal (Bolt)

## Task: Target Accuracy Restarts

### Performance Observation
- Problem: The application previously did not have a way to automatically restart when accuracy dropped below a certain threshold.
- Observation: Calculating accuracy on every keystroke/word completion is efficient enough for TUI, but the `_get_current_stats` method allows for centralized calculation and potential future optimizations (e.g., caching elapsed time).

### Improvement
- Implemented `_get_current_stats` in `TypingScreen` to provide a single source of truth for accuracy, WPM, and keystrokes.
- Added session-level word list persistence in `TypingApp` to avoid re-fetching/re-randomizing words during accuracy-based restarts.

### Impact
- Accuracy-based gating is now possible with minimal overhead.
- User experience for "perfect practice" is significantly improved.
