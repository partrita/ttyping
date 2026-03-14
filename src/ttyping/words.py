"""Word lists and file reader for ttyping."""

from __future__ import annotations

import random
import unicodedata
from functools import lru_cache
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
EN_SENTENCES: list[str] = _load_resource_words("en_sentences.txt")
KO_SENTENCES: list[str] = _load_resource_words("ko_sentences.txt")
EN_LOREM_IPSUM: list[str] = _load_resource_words("en_lorem_ipsum.txt")
KO_LOREM_IPSUM: list[str] = _load_resource_words("ko_lorem_ipsum.txt")
PY_WORDS: list[str] = _load_resource_words("python.txt")
RS_WORDS: list[str] = _load_resource_words("rust.txt")
R_WORDS: list[str] = _load_resource_words("r.txt")


# Practice character sets for different layouts
PRACTICE_SETS: dict[str, dict[str, str]] = {
    "en_qwerty": {
        "home_row": "asdfghjkl;:'\"",
        "top_row": "qwertyuiop[]{}",
        "bottom_row": "zxcvbnm,./<>?",
        "number_row": "1234567890-=",
        "symbol_row": "!@#$%^&*()_+",
        "left_hand": "qwertasdfgzxcvb",
        "right_hand": "yuiophjklmn:;'\"[]{},./?<>",
        "left_index": "rtfgvb45$%",
        "right_index": "yuhjnm67^&",
        "left_middle": "edc3#",
        "right_middle": "ik,8*",
        "left_ring": "wsx2@",
        "right_ring": "ol.9(",
        "left_pinky": "qaz1!",
        "right_pinky": "p;:/?\"'[]{}0)-_=+",
    },
    "ko_2set": {
        "home_row": "ㅁㄴㅇㄹㅎㅗㅓㅏㅣ",
        "top_row": "ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔ",
        "bottom_row": "ㅋㅌㅊㅍㅠㅜㅡ",
        "number_row": "1234567890",
        "symbol_row": "!@#$%^&*()",
        "left_hand": "ㅂㅈㄷㄱㅅㅁㄴㅇㄹㅎㅋㅌㅊㅍ",
        "right_hand": "ㅛㅕㅑㅐㅔㅗㅓㅏㅣㅠㅜㅡ",
        "left_index": "ㄱㅅㄹㅎㅊㅍ45$%",
        "right_index": "ㅛㅕㅗㅓㅠㅜ67^&",
        "left_middle": "ㄷㅇㅌ3#",
        "right_middle": "ㅑㅏㅡ8*",
        "left_ring": "ㅈㄴㅋ2@",
        "right_ring": "ㅐㅣ9(",
        "left_pinky": "ㅂㅁ1!",
        "right_pinky": "ㅔ;:/?\"'[]{}0)-_=+",
    },
    "en_dvorak": {
        "home_row": "aoeuidhtns",
        "top_row": "pyfgcrl",
        "bottom_row": "qjkxbmwvz",
        "number_row": "1234567890",
        "symbol_row": "!@#$%^&*()",
        "left_hand": "aoeuipyqjkx",
        "right_hand": "dhtnsfgcrlbmwvz",
        "left_index": "puiykx45$%",
        "right_index": "dhfgmb67^&",
        "left_middle": "eoj3#",
        "right_middle": "tqw8*",
        "left_ring": "oaq2@",
        "right_ring": "nrv9(",
        "left_pinky": "a1!",
        "right_pinky": "slz0)-_=+",
    },
    "en_colemak": {
        "home_row": "arstdhneio",
        "top_row": "qwfpgjluy;",
        "bottom_row": "zxcvbkm,./",
        "number_row": "1234567890",
        "symbol_row": "!@#$%^&*()",
        "left_hand": "qwfpgarstdzxcvb",
        "right_hand": "jluy;hneiokm,./",
        "left_index": "pgtdvb45$%",
        "right_index": "jlhnkm67^&",
        "left_middle": "fsc3#",
        "right_middle": "ue,8*",
        "left_ring": "wrx2@",
        "right_ring": "yi.9(",
        "left_pinky": "qaz1!",
        "right_pinky": ";o/'[]{}0)-_=+\"",
    },
    "ko_3set": {
        "home_row": "ㅁㄴㅇㄹㅅㅗㅓㅏㅣ",
        "top_row": "ㅎㅆㅂㄱㄷㅛㅐㅕㅔ",
        "bottom_row": "ㅌㅍㅎㅅㅆㅈㅂㅅㄹ",
        "number_row": "1234567890",
        "symbol_row": "!@#$%^&*()",
        "left_hand": "ㅎㅆㅂㄱㄷㅁㄴㅇㄹㅅㅌㅍㅎㅅㅆ",
        "right_hand": "ㅛㅐㅕㅔㄱㅗㅓㅏㅣㅇㄴㅈㅂㅅㄹㅎ",
        "left_index": "ㄱㄷㄹㅅㅅㅆ45$%",
        "right_index": "ㅔㄱㅏㅣㅇㄴ67^&",
        "left_middle": "ㅂㅇㅎ3#",
        "right_middle": "ㅕㅓㅈㅂ8*",
        "left_ring": "ㅆㄴㅍ2@",
        "right_ring": "ㅐㅗㅅㄹ9(",
        "left_pinky": "ㅎㅁㅌ1!",
        "right_pinky": "ㅛㅎ0)-_=+",
    },
}


def get_words(lang: str = "en", count: int = 25) -> list[str]:
    """Return a random selection of words/sentences for the given language or layout."""
    # Sentences are treated as single "words" for practice.
    if lang.endswith("_sentences"):
        sources: dict[str, list[str]] = {
            "en_sentences": EN_SENTENCES,
            "ko_sentences": KO_SENTENCES,
        }
        source = sources.get(lang, EN_SENTENCES)
        if not source:
            source = ["No sentences found."]
        words: list[str] = []
        for s in random.choices(source, k=count):
            words.extend(s.split())
        return words

    if lang.endswith("_lorem_ipsum"):
        sources: dict[str, list[str]] = {
            "en_lorem_ipsum": EN_LOREM_IPSUM,
            "ko_lorem_ipsum": KO_LOREM_IPSUM,
        }
        source = sources.get(lang, EN_LOREM_IPSUM)
        if not source:
            source = ["No lorem ipsum found."]
        words: list[str] = []
        for s in random.choices(source, k=count):
            words.extend(s.split())
        return words

    sources: dict[str, list[str]] = {
        "en": EN_QWERTY,
        "en_qwerty": EN_QWERTY,
        "en_dvorak": EN_DVORAK,
        "en_colemak": EN_QWERTY,
        "ko": KO_2SET,
        "ko_2set": KO_2SET,
        "ko_3set": KO_3SET,
        "python": PY_WORDS,
        "rust": RS_WORDS,
        "r": R_WORDS,
    }

    # Handle practice sets (format: layout:set_name)
    if ":" in lang:
        layout, set_name = lang.split(":", 1)
        if layout in PRACTICE_SETS and set_name in PRACTICE_SETS[layout]:
            return get_practice_drill(layout, set_name, count)

    source = sources.get(lang, EN_QWERTY)
    if not source:
        source = EN_QWERTY
    return random.choices(source, k=count)


def get_practice_drill(
    layout: str, set_name: str, count: int = 25, home_return: bool = True
) -> list[str]:
    """Generate a typing drill for a specific practice set.

    If *home_return* is True and *set_name* is a finger-level key, each
    practice character in the generated words will be followed by that
    finger's home row key, reinforcing the habit of returning to home
    position between keystrokes.
    """
    chars = PRACTICE_SETS[layout][set_name]

    # Try to find real words first
    all_words = []
    if layout == "en_qwerty":
        all_words = EN_QWERTY
    elif layout == "en_dvorak":
        all_words = EN_DVORAK
    elif layout == "ko_2set":
        all_words = KO_2SET
    elif layout == "ko_3set":
        all_words = KO_3SET

    fast_chars = set(chars)

    def is_match(word: str) -> bool:
        if layout.startswith("en"):
            return all(c.lower() in fast_chars for c in word)
        else:
            # Korean decomposition check
            for char in word:
                if any(k not in fast_chars for k in _get_jamos(char)):
                    return False
            return True

    filtered = [w for w in all_words if is_match(w)]

    # If we have enough real words, use them
    if len(filtered) >= count // 2 and len(filtered) > 5:
        return random.choices(filtered, k=count)

    # Otherwise, generate random character combinations (nonsense words)
    # For finger-level sets, interleave each char with the finger's home row key
    # so the user practices returning to home position between keystrokes.
    home_key: str | None = None
    if home_return and set_name in FINGER_LABELS:
        home_key = FINGER_HOME_KEY.get(layout, {}).get(set_name)

    drills = []
    for _ in range(count):
        word_len = random.randint(3, 6)
        if home_key and home_key not in chars:
            # Interleave: each practice char followed by the home row key
            practice_chars = random.choices(chars, k=word_len)
            parts = []
            for ch in practice_chars:
                parts.append(ch)
                parts.append(home_key)
            drills.append("".join(parts))
        else:
            drills.append("".join(random.choices(chars, k=word_len)))
    return drills


JAMO_TO_KEY = {
    "\u1100": "ㄱ",
    "\u1101": "ㄲ",
    "\u1102": "ㄴ",
    "\u1103": "ㄷ",
    "\u1104": "ㄸ",
    "\u1105": "ㄹ",
    "\u1106": "ㅁ",
    "\u1107": "ㅂ",
    "\u1108": "ㅃ",
    "\u1109": "ㅅ",
    "\u110a": "ㅆ",
    "\u110b": "ㅇ",
    "\u110c": "ㅈ",
    "\u110d": "ㅉ",
    "\u110e": "ㅊ",
    "\u110f": "ㅋ",
    "\u1110": "ㅌ",
    "\u1111": "ㅍ",
    "\u1112": "ㅎ",
    "\u1161": "ㅏ",
    "\u1162": "ㅐ",
    "\u1163": "ㅑ",
    "\u1164": "ㅒ",
    "\u1165": "ㅓ",
    "\u1166": "ㅔ",
    "\u1167": "ㅕ",
    "\u1168": "ㅖ",
    "\u1169": "ㅗ",
    "\u116a": "ㅘ",
    "\u116b": "ㅙ",
    "\u116c": "ㅚ",
    "\u116d": "ㅛ",
    "\u116e": "ㅜ",
    "\u116f": "ㅝ",
    "\u1170": "ㅞ",
    "\u1171": "ㅟ",
    "\u1172": "ㅠ",
    "\u1173": "ㅡ",
    "\u1174": "ㅢ",
    "\u1175": "ㅣ",
    "\u11a8": "ㄱ",
    "\u11a9": "ㄲ",
    "\u11aa": "ㄳ",
    "\u11ab": "ㄴ",
    "\u11ac": "ㄵ",
    "\u11ad": "ㄶ",
    "\u11ae": "ㄷ",
    "\u11af": "ㄹ",
    "\u11b0": "ㄺ",
    "\u11b1": "ㄻ",
    "\u11b2": "ㄼ",
    "\u11b3": "ㄽ",
    "\u11b4": "ㄾ",
    "\u11b5": "ㄿ",
    "\u11b6": "ㅀ",
    "\u11b7": "ㅁ",
    "\u11b8": "ㅂ",
    "\u11b9": "ㅄ",
    "\u11ba": "ㅅ",
    "\u11bb": "ㅆ",
    "\u11bc": "ㅇ",
    "\u11bd": "ㅈ",
    "\u11be": "ㅊ",
    "\u11bf": "ㅋ",
    "\u11c0": "ㅌ",
    "\u11c1": "ㅍ",
    "\u11c2": "ㅎ",
}


@lru_cache(maxsize=1024)
def _get_jamos(char: str) -> str:
    """Decompose a Korean character into keyboard jamos and cache it."""
    decomp = unicodedata.normalize("NFD", char)
    return "".join(JAMO_TO_KEY.get(c, c) for c in decomp)


def words_from_file(path: str, count: int = 25) -> list[str]:
    """Read words from a file and return up to `count` words."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"'{path}' is not a regular file")

    if p.stat().st_size > 10_000_000:
        raise ValueError(f"'{path}' is too large (max 10MB)")

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


# Human-readable finger labels
FINGER_LABELS: dict[str, str] = {
    "left_pinky": "Left Pinky",
    "left_ring": "Left Ring",
    "left_middle": "Left Middle",
    "left_index": "Left Index",
    "right_index": "Right Index",
    "right_middle": "Right Middle",
    "right_ring": "Right Ring",
    "right_pinky": "Right Pinky",
}

FINGER_LABELS_KO: dict[str, str] = {
    "left_pinky": "왼손 새끼",
    "left_ring": "왼손 약지",
    "left_middle": "왼손 중지",
    "left_index": "왼손 검지",
    "right_index": "오른손 검지",
    "right_middle": "오른손 중지",
    "right_ring": "오른손 약지",
    "right_pinky": "오른손 새끼",
}


# Home row key for each finger per layout.
# This is the resting key the finger returns to between keystrokes.
FINGER_HOME_KEY: dict[str, dict[str, str]] = {
    "en_qwerty": {
        "left_pinky": "a",
        "left_ring": "s",
        "left_middle": "d",
        "left_index": "f",
        "right_index": "j",
        "right_middle": "k",
        "right_ring": "l",
        "right_pinky": ";",
    },
    "en_dvorak": {
        "left_pinky": "a",
        "left_ring": "o",
        "left_middle": "e",
        "left_index": "u",
        "right_index": "h",
        "right_middle": "t",
        "right_ring": "n",
        "right_pinky": "s",
    },
    "en_colemak": {
        "left_pinky": "a",
        "left_ring": "r",
        "left_middle": "s",
        "left_index": "t",
        "right_index": "n",
        "right_middle": "e",
        "right_ring": "i",
        "right_pinky": "o",
    },
    "ko_2set": {
        "left_pinky": "ㅁ",
        "left_ring": "ㄴ",
        "left_middle": "ㅇ",
        "left_index": "ㄹ",
        "right_index": "ㅗ",
        "right_middle": "ㅏ",
        "right_ring": "ㅣ",
        "right_pinky": "ㅎ",
    },
    "ko_3set": {
        "left_pinky": "ㅁ",
        "left_ring": "ㄴ",
        "left_middle": "ㅇ",
        "left_index": "ㄹ",
        "right_index": "ㅏ",
        "right_middle": "ㅓ",
        "right_ring": "ㅗ",
        "right_pinky": "ㅣ",
    },
}


def chars_to_finger(layout: str, chars: str) -> dict[str, list[str]]:
    """Map a set of characters to their finger groups for the given layout.

    Returns a dict of {finger_key: [chars_belonging_to_that_finger]}.
    Only includes finger-level keys (not row-level keys).
    """
    layout_sets = PRACTICE_SETS.get(layout, PRACTICE_SETS["en_qwerty"])
    finger_keys = [k for k in layout_sets if k in FINGER_LABELS]
    result: dict[str, list[str]] = {}
    for ch in chars:
        for finger in finger_keys:
            if ch in layout_sets[finger]:
                result.setdefault(finger, []).append(ch)
                break
    return result


def get_weak_drill(layout: str, weak_chars: str, count: int = 25) -> list[str]:
    """Generate a drill focused on the given weak characters.

    Tries to find real words from the word list that contain those chars.
    Falls back to random character sequences if not enough real words found.
    """
    sources: dict[str, list[str]] = {
        "en_qwerty": EN_QWERTY,
        "en_dvorak": EN_DVORAK,
        "ko_2set": KO_2SET,
        "ko_3set": KO_3SET,
    }
    all_words = sources.get(layout, EN_QWERTY)

    is_english = layout.startswith("en")

    fast_weak_chars = set(weak_chars)

    def has_weak_char(word: str) -> bool:
        if is_english:
            return any(c.lower() in fast_weak_chars for c in word)
        for char in word:
            if any(k in fast_weak_chars for k in _get_jamos(char)):
                return True
        return False

    filtered = [w for w in all_words if has_weak_char(w)]

    if len(filtered) >= count // 2 and len(filtered) > 3:
        return random.choices(filtered, k=count)

    # Fallback: random combos mixing weak chars with common chars
    drills: list[str] = []
    for _ in range(count):
        word_len = random.randint(3, 6)
        drills.append("".join(random.choices(weak_chars, k=word_len)))
    return drills
