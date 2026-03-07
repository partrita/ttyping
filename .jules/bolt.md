<<<<<<< cleanup-exit-app-method-4096509055167654963
# Bolt Persona Learning Journal

## [Current Task] - Unused exit_app function

### Performance Improvements Identified
1. **Optimization in `_ensure_storage`**: The original code was potentially making redundant syscalls. I've already implemented a `_STORAGE_ENSURED` flag to prevent re-running expensive initialization logic in the same process session. This reduced the number of redundant disk checks.

### Measurement (Pre/Post)
- Before: Multiple calls to `_ensure_storage()` for every result save or config load. Each call would hit the filesystem with multiple stat/exists/chmod calls.
- After: Only the first call in a process session hits the filesystem. Subsequent calls return immediately.

### Learning Insights
- Even "clean code" fixes can have performance implications. Removing a level of indirection like `exit_app` makes the control flow slightly more direct.
- Global flags in modules should be carefully managed during testing to avoid cross-test contamination.
=======
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
>>>>>>> main
