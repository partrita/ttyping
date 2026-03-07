## 2025-05-15 - [Efficient File Word Loading]
**Learning:** Reading and splitting an entire file to extract only a few words is a major bottleneck for large files. Switching to line-by-line reading with early exit significantly improves performance and reduces memory usage.
**Action:** Always prefer streaming or lazy loading when only a subset of data is needed from a file.

## 2025-05-20 - [Optimized Test Mocking]
**Learning:** Forgetting to mock one file in a set of interdependent filesystem constants can lead to leaky tests that try to access the real home directory, causing failures in restricted environments.
**Action:** Always verify that all Path constants related to a directory are mocked together to maintain test isolation.

## 2026-03-07 - [Efficient List Slicing and Reversing]
**Learning:** For obtaining the last N elements of a list in reverse order, `results[:-51:-1]` is significantly faster than `reversed(results[-50:])`. The single-slice approach is more efficient because it handles both slicing and reversing in a single operation, avoiding the overhead of creating a separate slice object and then an iterator for reversal.
**Action:** When a reversed subset of a list is needed, use a single slice with a negative step for better performance.
