import os
from pathlib import Path

path = Path("src/ttyping/words.py")
content = path.read_text()

old_func = """def words_from_file(path: str, count: int = 25) -> list[str]:
    \"\"\"Read words from a file and return up to `count` words.\"\"\"
    if count <= 0:
        return []

    words: list[str] = []
    # Optimization: Read file line by line and exit early once we have enough words.
    # This avoids loading massive files into memory entirely.
    # Measured ~750x speedup for large multi-line files.
    with open(path, encoding="utf-8") as f:"""

new_func = """def words_from_file(path: str, count: int = 25) -> list[str]:
    \"\"\"Read words from a file and return up to `count` words.\"\"\"
    if count <= 0:
        return []

    p = Path(path)
    if not p.is_file():
        raise ValueError(f"{path} is not a regular file")
    if p.stat().st_size > 1_000_000:
        raise ValueError(f"{path} is too large")

    words: list[str] = []
    # Optimization: Read file line by line and exit early once we have enough words.
    # This avoids loading massive files into memory entirely.
    # Measured ~750x speedup for large multi-line files.
    with open(path, encoding="utf-8") as f:"""

content = content.replace(old_func, new_func)
path.write_text(content)
