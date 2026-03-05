"""Word lists and file reader for ttyping."""

from __future__ import annotations

import random
from importlib import resources
from pathlib import Path


def _load_resource_words(filename: str) -> list[str]:
    """Load words from a package resource file."""
    try:
        # Using importlib.resources.files (standard way since 3.9+)
        path = resources.files("ttyping.data").joinpath(filename)
        with path.open(encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        # Fallback to empty list if resource is missing or load fails
        return []


EN_QWERTY: list[str] = _load_resource_words("en_qwerty.txt")
EN_DVORAK: list[str] = _load_resource_words("en_dvorak.txt")
KO_2SET: list[str] = _load_resource_words("ko_2set.txt")
KO_3SET: list[str] = _load_resource_words("ko_3set.txt")


def get_words(lang: str = "en", count: int = 25) -> list[str]:
    """Return a random selection of words for the given language or layout."""
    sources = {
        "en": EN_QWERTY,
        "en_qwerty": EN_QWERTY,
        "en_dvorak": EN_DVORAK,
        "ko": KO_2SET,
        "ko_2set": KO_2SET,
        "ko_3set": KO_3SET,
    }
    source = sources.get(lang, EN_QWERTY)
    if not source:
        # Fallback if the selected source is empty
        source = EN_QWERTY
    return random.choices(source, k=count)


def words_from_file(path: str, count: int = 25) -> list[str]:
    """Read words from a file and return up to `count` words."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"'{path}' is not a regular file")

    if p.stat().st_size > 1_000_000:
        raise ValueError(f"'{path}' is too large (max 1MB)")

    if count <= 0:
        return []

    words: list[str] = []
    # Optimization: Read file line by line and exit early once we have enough words.
    with open(path, encoding="utf-8") as f:
        for line in f:
            for word in line.split():
                words.append(word)
                if len(words) >= count:
                    return words

    if not words:
        raise ValueError(f"No words found in {path}")
    return words
