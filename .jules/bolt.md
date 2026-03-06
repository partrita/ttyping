# Bolt Learning Journal

## Performance Optimization: importlib optimization
- **Identification:** Moved `import unicodedata` to the top of `src/ttyping/words.py`.
- **Rationale:** Practice drills for Korean layouts (`ko_2set`, `ko_3set`) call `is_match` which used to import `unicodedata` on every word match attempt if not already in cache. While Python caches imports, keeping it at the top is standard and avoids the overhead of checking the cache in a tight loop.
- **Impact:** Negligible for single tests, but improves responsiveness in practice drills with many words.
