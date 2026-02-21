import pytest
from ttyping.words import get_words, words_from_file

def test_get_words_en():
    words = get_words("en", 10)
    assert len(words) == 10
    # Check if words are from the English list (at least one check)
    from ttyping.words import ENGLISH
    assert all(w in ENGLISH for w in words)

def test_get_words_ko():
    words = get_words("ko", 5)
    assert len(words) == 5
    from ttyping.words import KOREAN
    assert all(w in KOREAN for w in words)

def test_words_from_file(tmp_path):
    d = tmp_path / "test.txt"
    d.write_text("hello world typing test", encoding="utf-8")
    
    words = words_from_file(str(d), count=2)
    assert len(words) == 2
    assert words == ["hello", "world"]

def test_words_from_file_empty(tmp_path):
    d = tmp_path / "empty.txt"
    d.write_text("", encoding="utf-8")
    
    with pytest.raises(ValueError, match="No words found"):
        words_from_file(str(d))
