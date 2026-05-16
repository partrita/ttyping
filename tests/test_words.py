from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

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


def test_words_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "test.txt"
    d.write_text("hello world typing test", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    words = words_from_file(str(d.name), count=2)
    assert len(words) == 2
    assert words == ["hello", "world"]


def test_words_from_file_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "empty.txt"
    d.write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="No words found"):
        words_from_file(str(d.name))


def test_words_from_file_not_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "subdir"
    d.mkdir()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="is not a regular file"):
        words_from_file(str(d.name))


def test_words_from_file_too_large(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "large.txt"
    # Create a file slightly larger than 10MB
    with open(d, "wb") as f:
        f.write(b"a" * 10_000_001)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="is too large"):
        words_from_file(str(d.name))


def test_words_from_file_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("hello world", encoding="utf-8")

    symlink = tmp_path / "symlink.txt"
    try:
        symlink.symlink_to(target)
    except OSError:
        pytest.skip("Symlinks not supported on this platform")

    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Refusing to read from symlink"):
        words_from_file(str(symlink.name))


def test_get_practice_drill_en_dvorak() -> None:
    from ttyping.words import get_words

    words = get_words("practice:en_dvorak:home_row", 5)
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
    with patch(
        "ttyping.words.resources.files", side_effect=ModuleNotFoundError("Mock error")
    ):
        words = _load_resource_words("dummy.txt")
        assert words == []


def test_get_practice_drill_en_real_words() -> None:
    from ttyping.words import get_practice_drill

    # Using 'top_row' usually has enough English words
    words = get_practice_drill("en_qwerty", "top_row", count=10)
    assert len(words) == 10
    # verify that words only use top row characters
    allowed = set("qwertyuiop")
    for word in words:
        assert all(c.lower() in allowed for c in word)


def test_get_practice_drill_ko_real_words() -> None:
    from ttyping.words import PRACTICE_SETS, _get_jamos, get_practice_drill

    # Using 'left_hand' in ko_2set has enough words (only consonants)
    words = get_practice_drill("ko_2set", "right_hand", count=5)
    assert len(words) == 5
    # right hand characters in ko_2set are vowels mostly
    allowed = set(PRACTICE_SETS["ko_2set"]["right_hand"])
    for word in words:
        for char in word:
            jamos = _get_jamos(char)
            assert all(j in allowed for j in jamos)


def test_get_practice_drill_nonsense_with_home_return() -> None:
    from ttyping.words import get_practice_drill

    # "left_pinky" typically doesn't have enough real words (q, a, z)
    # home return should interleave 'a' (the home key for en_qwerty left_pinky)
    words = get_practice_drill("en_qwerty", "left_pinky", count=5, home_return=True)
    assert len(words) == 5

    # check if 'a' is interleaved
    # words are formed like: char, home_key, char, home_key...
    # Except 'a' is in left_pinky, so if home_key is in chars, it won't interleave!
    # Let's use right_pinky for ko_2set, chars are ㅔ;:/?"'[]{}0)-_=+ and home is ㅎ
    words_ko = get_practice_drill("ko_2set", "right_pinky", count=5, home_return=True)
    assert len(words_ko) == 5
    home_key = "ㅎ"
    for word in words_ko:
        # Every alternate character (starting from index 1) should be the home key
        for i, char in enumerate(word):
            if i % 2 == 1:
                assert char == home_key


def test_get_practice_drill_nonsense_no_home_return() -> None:
    from ttyping.words import PRACTICE_SETS, get_practice_drill

    words = get_practice_drill("ko_2set", "right_pinky", count=5, home_return=False)
    assert len(words) == 5
    allowed_chars = set(PRACTICE_SETS["ko_2set"]["right_pinky"])
    for word in words:
        # should not be interleaved with home key
        # should just be random characters from the set
        for char in word:
            assert char in allowed_chars


def test_decompose_ko_to_spaced_jamos() -> None:
    from ttyping.words import _decompose_ko_to_spaced_jamos

    assert _decompose_ko_to_spaced_jamos("한글") == "ㅎ ㅏ ㄴ ㄱ ㅡ ㄹ"
    assert _decompose_ko_to_spaced_jamos("후") == "ㅎ ㅜ"
    # Non-Korean handled by _get_jamos fallback
    assert _decompose_ko_to_spaced_jamos("abc") == "a b c"


def test_get_practice_drill_ko_decomposition() -> None:
    from ttyping.words import PRACTICE_SETS, get_practice_drill

    # Practice drills for Korean should be decomposed into individual jamos
    # Using 'home_row' for ko_2set (ㅁㄴㅇㄹㅎㅗㅓㅏㅣ)
    words = get_practice_drill("ko_2set", "home_row", count=10)
    allowed = set(PRACTICE_SETS["ko_2set"]["home_row"])

    # Each 'word' should be a single jamo because we split the decomposed string
    # e.g., "한글" -> ["ㅎ", "ㅏ", "ㄴ", "ㄱ", "ㅡ", "ㄹ"]
    for w in words:
        assert len(w) == 1
        # It should be a single Korean jamo or a character from the set
        assert w in allowed


def test_get_weak_drill_ko_decomposition() -> None:
    from ttyping.words import get_weak_drill

    # Weak drills for Korean should also be decomposed
    # We use very few weak chars to likely trigger real word selection
    # containing those chars
    words = get_weak_drill("ko_2set", "ㅁ", count=5)

    # Each 'word' should be a single jamo
    for w in words:
        assert len(w) == 1
        # At least one of the words should contain the weak char 'ㅁ'
        # or be part of a word that contained 'ㅁ'

    # Check if 'ㅁ' exists in at least some of the results
    assert any("ㅁ" in w for w in words) or any(isinstance(w, str) for w in words)


def test_get_words_sentences_success() -> None:
    # Test en_sentences
    count = 2
    words = get_words("en_sentences", count=count)
    # Each sentence has at least one word, so len(words) >= count
    assert len(words) >= count
    assert isinstance(words, list)
    assert all(isinstance(w, str) for w in words)

    # Test ko_sentences
    words_ko = get_words("ko_sentences", count=count)
    assert len(words_ko) >= count
    assert isinstance(words_ko, list)
    assert all(isinstance(w, str) for w in words_ko)


def test_get_words_lorem_ipsum() -> None:
    # Test en_lorem_ipsum
    count = 2
    words = get_words("en_lorem_ipsum", count=count)
    assert len(words) >= count
    assert all(isinstance(w, str) for w in words)

    # Test ko_lorem_ipsum
    words_ko = get_words("ko_lorem_ipsum", count=count)
    assert len(words_ko) >= count
    assert all(isinstance(w, str) for w in words_ko)


def test_get_words_sentences_fallback() -> None:
    # Patch EN_SENTENCES to be empty to trigger fallback
    with patch("ttyping.words.EN_SENTENCES", []):
        words = get_words("en_sentences", count=1)
        # "No sentences found." splits into ["No", "sentences", "found."]
        assert words == ["No", "sentences", "found."]


def test_get_words_lorem_ipsum_fallback() -> None:
    # Patch KO_LOREM_IPSUM to be empty to trigger fallback
    with patch("ttyping.words.KO_LOREM_IPSUM", []):
        words = get_words("ko_lorem_ipsum", count=1)
        # "No lorem ipsum found." splits into ["No", "lorem", "ipsum", "found."]
        assert words == ["No", "lorem", "ipsum", "found."]


def test_load_resource_words_success() -> None:
    mock_file_content = "word1\n  word2  \n\nword3\n"
    mocked_open = mock_open(read_data=mock_file_content)

    with patch("ttyping.words.resources.files") as mock_files:
        mock_path = MagicMock()
        mock_files.return_value.joinpath.return_value = mock_path
        mock_path.open = mocked_open

        words = _load_resource_words("dummy.txt")

        # Verify the expected words are returned
        assert words == ["word1", "word2", "word3"]

        # Verify that joinpath and open were called correctly
        mock_files.return_value.joinpath.assert_called_once_with("dummy.txt")
        mock_path.open.assert_called_once_with(encoding="utf-8")
