## 2025-05-15 - [Efficient File Word Loading]
**Learning:** Reading and splitting an entire file to extract only a few words is a major bottleneck for large files. Switching to line-by-line reading with early exit significantly improves performance and reduces memory usage.
**Action:** Always prefer streaming or lazy loading when only a subset of data is needed from a file.
