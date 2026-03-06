# UX/Accessibility Learning Journal (Palette)

## Task: Target Accuracy Restarts

### UX/A11y Insight
- Problem: Sudden restarts when accuracy drops can be jarring without feedback.
- Insight: The `ResultScreen` now includes a `DataTable` that displays a session summary. This helps the user understand *why* they had to restart and track their progression across attempts.

### Improvement
- Added `session summary` table to `ResultScreen`.
- Ensured that even on the final successful attempt, the keystroke and error data is recorded for the summary.

### Impact
- Clearer visibility into session-level performance.
- Reduced frustration from "silent restarts" by providing post-test data for all failed attempts.
