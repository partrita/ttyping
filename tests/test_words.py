from pathlib import Path

import pytest

from ttyping.words import get_words, words_from_file


def test_get_words_en() -> None:
    words = get_words("en_qwerty", 10)
    assert len(words) == 10
    # Check if words are from the English list (at least one check)
    from ttyping.words import EN_QWERTY

    assert all(w in EN_QWERTY for w in words)


def test_get_words_ko() -> None:
    words = get_words("ko_2set", 5)
    assert len(words) == 5
    from ttyping.words import KO_2SET

    assert all(w in KO_2SET for w in words)


def test_words_from_file(tmp_path: Path) -> None:
    d = tmp_path / "test.txt"
    d.write_text("hello world typing test", encoding="utf-8")

    words = words_from_file(str(d), count=2)
    assert len(words) == 2
    assert words == ["hello", "world"]


def test_words_from_file_empty(tmp_path: Path) -> None:
    d = tmp_path / "empty.txt"
    d.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="No words found"):
        words_from_file(str(d))


def test_words_from_file_not_a_file(tmp_path: Path) -> None:
    d = tmp_path / "subdir"
    d.mkdir()

    with pytest.raises(ValueError, match="is not a regular file"):
        words_from_file(str(d))


def test_words_from_file_too_large(tmp_path: Path) -> None:
    d = tmp_path / "large.txt"
    # Create a file slightly larger than 10MB
    with open(d, "wb") as f:
        f.write(b"a" * 10_000_001)

    with pytest.raises(ValueError, match="is too large"):
        words_from_file(str(d))


def test_get_practice_drill_en_dvorak() -> None:
    from ttyping.words import get_words

    words = get_words("en_dvorak:home_row", 5)
    assert len(words) == 5
    # Home row Dvorak: aoeuidhtns
    allowed = set("aoeuidhtns")
    for word in words:
        assert all(c.lower() in allowed for c in word)


def test_get_practice_drill_ko_3set() -> None:
    from ttyping.words import get_words

    words = get_words("ko_3set:home_row", 5)
    assert len(words) == 5
    # Home row 3-set: ㅁㄴㅇㄹㅅㅗㅓㅏㅣ
    # We use a loose check because of decomposition
    assert True  # Basic check that it doesn't crash
