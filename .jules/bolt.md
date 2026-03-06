## 2025-05-15 - [Efficient File Word Loading]
**Learning:** Reading and splitting an entire file to extract only a few words is a major bottleneck for large files. Switching to line-by-line reading with early exit significantly improves performance and reduces memory usage.
**Action:** Always prefer streaming or lazy loading when only a subset of data is needed from a file.

## 2025-05-15 - [Efficient JSON Storage Loading]
**Learning:** For larger JSON data, using `json.load(f)` with an open file handle is more efficient than reading the entire file into memory as a string first. In addition to reducing memory peak usage, it also showed a measurable (~4%) speed improvement for files around 8MB.
**Action:** Use `json.load(f)` for better memory efficiency and performance when loading JSON from local storage.
