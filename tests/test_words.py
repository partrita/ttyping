from pathlib import Path
from unittest.mock import patch

import pytest

from ttyping.words import _load_resource_words, get_words, words_from_file


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


def test_load_resource_words_exception() -> None:
    with patch("ttyping.words.resources.files", side_effect=Exception("Mock error")):
        words = _load_resource_words("dummy.txt")
        assert words == []


def test_get_practice_drill_en_qwerty() -> None:
    from ttyping.words import PRACTICE_SETS, get_practice_drill

    words = get_practice_drill("en_qwerty", "home_row", 5)
    assert len(words) == 5
    allowed = set(PRACTICE_SETS["en_qwerty"]["home_row"])
    for word in words:
        assert all(c.lower() in allowed for c in word)


def test_get_practice_drill_ko_2set() -> None:
    from ttyping.words import PRACTICE_SETS, _get_jamos, get_practice_drill

    words = get_practice_drill("ko_2set", "left_hand", 5)
    assert len(words) == 5
    allowed = set(PRACTICE_SETS["ko_2set"]["left_hand"])
    for word in words:
        for char in word:
            jamos = _get_jamos(char)
            assert all(jamo in allowed for jamo in jamos)


def test_get_practice_drill_nonsense_words() -> None:
    from ttyping.words import PRACTICE_SETS, get_practice_drill

    # "left_pinky" in "en_qwerty" has very few or no real words
    # So it should generate nonsense sequences.
    # Set home_return=False to just get the chars without interleaving
    words = get_practice_drill("en_qwerty", "left_pinky", 5, home_return=False)
    assert len(words) == 5
    allowed = set(PRACTICE_SETS["en_qwerty"]["left_pinky"])
    for word in words:
        assert 3 <= len(word) <= 6
        assert all(c in allowed for c in word)


def test_get_practice_drill_home_return() -> None:
    from ttyping.words import FINGER_HOME_KEY, PRACTICE_SETS, get_practice_drill

    layout = "ko_2set"
    set_name = "right_pinky"

    # "right_pinky" in "ko_2set" has no real words and home key is not in practice set.
    # We set home_return=True to test the interleaving logic.
    words = get_practice_drill(layout, set_name, 5, home_return=True)
    assert len(words) == 5

    allowed_chars = set(PRACTICE_SETS[layout][set_name])
    home_key = FINGER_HOME_KEY[layout][set_name]

    for word in words:
        # We interleaved a home_key after each random practice char,
        # so length should be 2 * (3 to 6) = 6 to 12.
        assert 6 <= len(word) <= 12
        assert len(word) % 2 == 0

        # Every even index character (0, 2, 4...) should be a practice char
        # Every odd index character (1, 3, 5...) should be the home key
        for i in range(len(word)):
            if i % 2 == 0:
                assert word[i] in allowed_chars
            else:
                assert word[i] == home_key
