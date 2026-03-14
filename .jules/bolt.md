## 2026-03-07 - [O(N) Render Optimization in Textual App]
**Learning:** Generating Textual/Rich `Text` objects for ALL words on every keystroke causes significant overhead in UI rendering.
**Action:** When rendering a viewport of text, compute line wraps via string lengths/indices first, and ONLY generate `Text` objects for the lines actually visible on screen.

## Performance Optimization (ttyping/screens.py)
**What**: Cached `#stats` Static widget (`self._stats_widget`) on `TypingScreen.on_mount` instead of calling `self.query_one("#stats", Static)` directly on every invocation of `_update_stats`.
**Why**: `_update_stats` is called very frequently (both via a fast 0.5s timer and repeatedly on every keystroke/completion). The Textual `query_one` method searches the DOM, adding overhead. Storing the reference locally allows bypassing this DOM traversal completely.
**Measured Improvement**: Baseline `_update_stats` benchmark processed 1k calls in ~0.0136s. Using a cached widget processed 1k calls in ~0.0122s, a roughly 1.11x speedup. While small in absolute terms per call, this is a hot path for key interactions, saving CPU cycles and garbage collection overhead during tight loops.
