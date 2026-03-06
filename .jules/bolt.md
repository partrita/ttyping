## 2025-05-15 - [Efficient File Word Loading]
**Learning:** Reading and splitting an entire file to extract only a few words is a major bottleneck for large files. Switching to line-by-line reading with early exit significantly improves performance and reduces memory usage.
**Action:** Always prefer streaming or lazy loading when only a subset of data is needed from a file.

## 2025-05-20 - [Optimized Test Mocking]
**Learning:** Forgetting to mock one file in a set of interdependent filesystem constants can lead to leaky tests that try to access the real home directory, causing failures in restricted environments.
**Action:** Always verify that all Path constants related to a directory are mocked together to maintain test isolation.
