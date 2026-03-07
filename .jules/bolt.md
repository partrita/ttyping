## 2026-03-07 - [O(N) Render Optimization in Textual App]
**Learning:** Generating Textual/Rich `Text` objects for ALL words on every keystroke causes significant overhead in UI rendering.
**Action:** When rendering a viewport of text, compute line wraps via string lengths/indices first, and ONLY generate `Text` objects for the lines actually visible on screen.
