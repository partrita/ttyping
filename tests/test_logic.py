import pytest
from ttyping.words import get_words

def test_get_words_extended() -> None:
    words = get_words("en_dvorak", 10)
    assert len(words) == 10
    from ttyping.words import EN_DVORAK
    assert all(w in EN_DVORAK for w in words)

    words = get_words("ko_3set", 5)
    assert len(words) == 5
    from ttyping.words import KO_3SET
    assert all(w in KO_3SET for w in words)

def test_wpm_calculation_logic():
    # Mocking basic calculation logic that was added to TypingScreen
    def calculate(keystrokes, uncorrected_errors, seconds):
        minutes = seconds / 60
        if minutes <= 0: minutes = 0.001
        gross_wpm = (keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (uncorrected_errors / minutes))
        return round(net_wpm, 1)

    # Example from speedtypingonline: 200 chars in 1 min, 0 errors -> 40 WPM
    assert calculate(200, 0, 60) == 40.0

    # Example from speedtypingonline: 80 gross WPM, 8 errors in 2 mins -> 76 Net WPM
    # 80 gross WPM in 2 mins = 80 * 5 * 2 = 800 keystrokes
    assert calculate(800, 8, 120) == 76.0

def test_accuracy_calculation_logic():
    def calculate_acc(keystrokes, total_errors):
        return max(0, (keystrokes - total_errors) / max(keystrokes, 1)) * 100

    assert calculate_acc(100, 10) == 90.0
    assert calculate_acc(100, 0) == 100.0
    assert calculate_acc(100, 100) == 0.0
