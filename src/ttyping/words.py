"""단어 목록과 파일 읽기 기능을 제공하는 모듈.

이 모듈의 역할:
1. 패키지 내장 단어장(`src/ttyping/data/*.txt`)을 앱 시작 시 1회만 읽어
   모듈 상수(EN_QWERTY, KO_2SET 등)로 메모리에 올려둔다.
2. 연습 문제 세트(자판 행/손가락별 연습 문자 묶음)를 정의한다.
3. 언어/레이아웃 이름에 맞는 단어 리스트를 무작위로 뽑아 돌려준다.
4. 로컬 파일(--file)과 원격 URL(--url)에서 단어를 읽어온다.
   - 이때 심볼릭 링크 공격(TOCTOU)과 과도한 메모리 사용을 방어한다.

성능 노트:
- 단어장은 모듈 임포트 시점에 1회만 읽힌다(이후 전역 상수 재사용).
- 한글 자모 분해 결과는 ``lru_cache``로 캐싱되어 반복 호출이 O(1)이다.
"""

from __future__ import annotations

import os
import random
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from importlib import resources
from pathlib import Path
from stat import S_ISREG


def _load_resource_words(filename: str) -> list[str]:
    """패키지 리소스 파일에서 단어 목록을 읽어온다.

    한 줄에 단어 하나씩 적혀 있다고 가정하며, 빈 줄은 건너뛴다.
    리소스가 없거나 읽기에 실패하면 앱이 죽지 않도록 빈 리스트를 반환한다.
    """
    try:
        # importlib.resources.files 는 Python 3.9+ 의 표준 리소스 접근 방식.
        path = resources.files("ttyping.data").joinpath(filename)
        with path.open(encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except (ModuleNotFoundError, FileNotFoundError):
        # 리소스 누락/로드 실패 시에도 앱이 동작하도록 빈 리스트로 폴백
        return []


# ── 내장 단어장 (모듈 임포트 시 1회만 로드됨) ──────────────────────────

EN_QWERTY: list[str] = _load_resource_words("en_qwerty.txt")
EN_DVORAK: list[str] = _load_resource_words("en_dvorak.txt")
KO_2SET: list[str] = _load_resource_words("ko_2set.txt")
KO_3SET: list[str] = _load_resource_words("ko_3set.txt")
EN_SENTENCES: list[str] = _load_resource_words("en_sentences.txt")
KO_SENTENCES: list[str] = _load_resource_words("ko_sentences.txt")
EN_LOREM_IPSUM: list[str] = _load_resource_words("en_lorem_ipsum.txt")
KO_LOREM_IPSUM: list[str] = _load_resource_words("ko_lorem_ipsum.txt")
EN_QUOTES: list[str] = _load_resource_words("en_quotes.txt")
KO_QUOTES: list[str] = _load_resource_words("ko_quotes.txt")
PY_WORDS: list[str] = _load_resource_words("python.txt")
RS_WORDS: list[str] = _load_resource_words("rust.txt")
R_WORDS: list[str] = _load_resource_words("r.txt")
JS_WORDS: list[str] = _load_resource_words("javascript.txt")
JL_WORDS: list[str] = _load_resource_words("julia.txt")
TY_WORDS: list[str] = _load_resource_words("typst.txt")
MD_WORDS: list[str] = _load_resource_words("markdown.txt")
GO_WORDS: list[str] = _load_resource_words("go.txt")
C_WORDS: list[str] = _load_resource_words("c.txt")
TS_WORDS: list[str] = _load_resource_words("typescript.txt")


# ── 손가락/자판 행별 연습 문자 세트 ────────────────────────────────────
# 레이아웃 이름 → {연습 세트 이름 → 그 세트에서 연습할 문자들}.
# 예: "en_qwerty" 레이아웃의 "home_row" 연습은 "asdfghjkl;:'\"" 문자만 사용.
# *_index/_middle/_ring/_pinky 키는 손가락별 연습(FINGER_LABELS와 짝을 이룸).
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
        "home_row": "ㅁㄴㅇㄹㅎㅗㅓㅏㅣ;':\"",
        "top_row": "ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔ[]{}",
        "bottom_row": "ㅋㅌㅊㅍㅠㅜㅡ,./<>?",
        "number_row": "1234567890",
        "symbol_row": "!@#$%^&*()-=_+",
        "left_hand": "ㅂㅈㄷㄱㅅㅁㄴㅇㄹㅎㅋㅌㅊㅍ",
        "right_hand": "ㅛㅕㅑㅐㅔㅗㅓㅏㅣㅠㅜㅡ[]{};:,./<>?",
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


# ── 레이아웃 이름 → 단어장 매핑 ────────────────────────────────────────
# "en", "ko_2set", "python" 같은 언어/레이아웃 식별자를 위 단어장에 연결.
# get_words()가 이 표를 보고 어떤 단어장에서 문제를 뽑을지 결정한다.
LAYOUT_TO_WORDS: dict[str, list[str]] = {
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
    "javascript": JS_WORDS,
    "julia": JL_WORDS,
    "typst": TY_WORDS,
    "markdown": MD_WORDS,
    "go": GO_WORDS,
    "c": C_WORDS,
    "typescript": TS_WORDS,
}


def _generate_nonsense_drills(
    count: int, chars: str, home_key: str | None
) -> list[str]:
    """실제 단어가 부족할 때 쓰는 무작위 글자 조합(엉터리 단어) 생성기.

    - 각 엉터리 단어는 ``chars``에서 3~6개 글자를 뽑아 만든다.
    - *home_key*가 주어지면(손가락별 연습) 모든 글자 사이에 홈 키를 끼워 넣어
      "치고 → 홈 포지션 복귀" 습관을 훈련시킨다. 예: a→f 연습 시 "fafaf".
    """
    drills = []
    for _ in range(count):
        word_len = random.randint(3, 6)
        if home_key and home_key not in chars:
            # 글자와 홈 키를 번갈아 배치: [글자, 홈키, 글자, 홈키, ...]
            practice_chars = random.choices(chars, k=word_len)
            parts = []
            for ch in practice_chars:
                parts.append(ch)
                parts.append(home_key)
            drills.append("".join(parts))
        else:
            drills.append("".join(random.choices(chars, k=word_len)))
    return drills


def _words_from_text_pool(
    sources: dict[str, list[str]], lang: str, count: int, fallback_msg: str
) -> list[str]:
    """문장 풀에서 무작위로 *count*개 문장을 골라 단어 단위로 잘라 반환.

    문장 연습(sentences), 로렘 입숨, 명언(quotes) 모드가 공유하는 헬퍼.
    """
    source = sources.get(lang)
    if source is None:
        # 모르는 언어 이름이면 첫 번째 풀로 폴백
        source = next(iter(sources.values()))
    if not source:
        source = [fallback_msg]
    words: list[str] = []
    for s in random.choices(source, k=count):
        words.extend(s.split())
    return words


# ── 문장 단위 연습 모드의 접미사 목록 ──────────────────────────────────
# lang이 아래 접미사로 끝나면 문장 풀에서 문제를 만든다.
# (주의: 단어장 리스트는 get_words()가 "호출되는 시점"에 전역 변수에서
#  읽어야 한다. 미리 딕셔너리로 묶어두면 테스트의 patch() 같은
#  런타임 교체가 반영되지 않으므로 의도적으로 지연 바인딩을 유지한다.)
_SENTENCE_MODES: tuple[tuple[str, str], ...] = (
    ("_sentences", "No sentences found."),
    ("_lorem_ipsum", "No lorem ipsum found."),
    ("_quotes", "No quotes found."),
)


def get_words(lang: str = "en", count: int = 25) -> list[str]:
    """언어/레이아웃 이름(*lang*)에 맞는 연습 문제 *count*개를 무작위로 반환.

    우선순위:
    1. 문장형 모드(``*_sentences`` / ``*_lorem_ipsum`` / ``*_quotes``)
    2. 자판 연습 세트(``practice:<레이아웃>:<세트>`` 또는 ``<레이아웃>:<세트>``)
    3. 일반 단어장(LAYOUT_TO_WORDS 표)
    """
    # 1) 문장 단위 연습 모드: 접미사로 판별해 해당 문장 풀에서 뽑는다.
    for suffix, fallback_msg in _SENTENCE_MODES:
        if lang.endswith(suffix):
            if suffix == "_sentences":
                return _words_from_text_pool(
                    {"en_sentences": EN_SENTENCES, "ko_sentences": KO_SENTENCES},
                    lang,
                    count,
                    fallback_msg,
                )
            if suffix == "_lorem_ipsum":
                return _words_from_text_pool(
                    {
                        "en_lorem_ipsum": EN_LOREM_IPSUM,
                        "ko_lorem_ipsum": KO_LOREM_IPSUM,
                    },
                    lang,
                    count,
                    fallback_msg,
                )
            return _words_from_text_pool(
                {"en_quotes": EN_QUOTES, "ko_quotes": KO_QUOTES},
                lang,
                count,
                fallback_msg,
            )

    # 2) 자판 연습 세트 요청 처리
    #    형식: "practice:<layout>:<set>" 또는 축약형 "<layout>:<set>"
    if ":" in lang:
        parts = lang.split(":")
        if lang.startswith("practice:") and len(parts) == 3:
            _, layout, set_name = parts
        elif len(parts) == 2:
            layout, set_name = parts
        else:
            layout, set_name = "", ""
        if layout in PRACTICE_SETS and set_name in PRACTICE_SETS[layout]:
            return get_practice_drill(layout, set_name, count)

    # 3) 일반 단어장에서 무작위 선택. 알 수 없는 lang은 영어 QWERTY로 폴백.
    source = LAYOUT_TO_WORDS.get(lang, EN_QWERTY)
    if not source:
        source = EN_QWERTY
    return random.choices(source, k=count)


def get_daily_words(lang: str = "en", count: int = 25) -> list[str]:
    """오늘(UTC 기준) 하루 동안 모두 같은 문제를 주는 결정적(deterministic) 단어 세트.

    날짜 문자열로 RNG를 시드한 뒤 원래 RNG 상태를 복원하므로,
    전역 난수 흐름은 오염되지 않는다.
    """
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = random.getstate()
    random.seed(f"ttyping-daily-{day}")
    try:
        return get_words(lang, count)
    finally:
        random.setstate(state)


def _decompose_ko_to_spaced_jamos(word: str) -> str:
    """한글 단어를 자모 단위로 분해하고 자모 사이에 공백을 넣어 반환.

    예: "한글" → "ㅎ ㅏ ㄴ ㄱ ㅡ ㄹ"
    한글 연습 문제는 낱글자 조합(모아쓰기) 대신 자모를 하나씩 치도록
    분리해 개별 자타 연습 효과를 노린다.
    """
    result: list[str] = []
    for char in word:
        result.extend(_get_jamos(char))
    return " ".join(result)


def get_practice_drill(
    layout: str, set_name: str, count: int = 25, home_return: bool = True
) -> list[str]:
    """특정 연습 세트(자판 행/손가락별)에 맞는 연습 문제 *count*개를 생성.

    동작 순서:
    1. 세트 문자만으로 이루어진 **실제 단어**를 단어장에서 찾는다.
       (성능: 전체 단어장을 훑기 전에 무작위 부분집합 300개 정도를 먼저
        필터링해 보고, 부족할 때만 전체 스캔으로 폴백한다.)
    2. 실제 단어가 충분하지 않으면 ``_generate_nonsense_drills``로
       엉터리 단어(글자 조합)를 만든다.
    3. 한글 레이아웃이면 결과를 자모 단위로 분해해 공백으로 구분해 반환.
    """
    chars = PRACTICE_SETS[layout][set_name]

    # 실제 단어 후보 찾기 준비
    all_words = LAYOUT_TO_WORDS.get(layout, [])
    fast_chars = set(chars)  # set 변환 1회로 멤버십 검사를 O(1)로
    is_korean = layout.startswith("ko")

    def is_match(word: str) -> bool:
        if not is_korean:
            # 영어: 단어의 모든 글자가 연습 세트에 포함되는지 확인
            return fast_chars.issuperset(word.lower())
        # 한글: 글자마다 자모 분해 후 모든 자모가 세트에 포함되는지 확인
        for char in word:
            if not fast_chars.issuperset(_get_jamos(char)):
                return False
        return True

    # 최적화: 전체 단어장 O(N) 스캔을 피하기 위해 무작위 부분집합을 먼저 필터링
    subset_size = min(len(all_words), max(300, count * 5))
    subset = random.sample(all_words, subset_size) if all_words else []
    filtered = [w for w in subset if is_match(w)]

    if len(filtered) < count // 2 or len(filtered) <= 5:
        # 부분집합으로 충분하지 않으면 전체 목록 스캔으로 폴백
        filtered = [w for w in all_words if is_match(w)]

    words = []
    if len(filtered) >= count // 2 and len(filtered) > 5:
        # 실제 단어가 충분하면 그 안에서 무작위 선택
        words = random.choices(filtered, k=count)
    else:
        # 아니면 글자 조합(엉터리 단어)으로 대체
        home_key: str | None = None
        if home_return and set_name in FINGER_LABELS:
            home_key = FINGER_HOME_KEY.get(layout, {}).get(set_name)
        words = _generate_nonsense_drills(count, chars, home_key)

    if is_korean:
        # 한글 연습은 낱글자 조합을 피하기 위해 자모를 공백으로 분리해 반환
        decomposed_words = []
        for w in words:
            decomposed_words.extend(_decompose_ko_to_spaced_jamos(w).split())
        return decomposed_words[:count]

    return words


# ── 유니코드 조합용 자모 → 키보드 자모 문자 매핑 ────────────────────────
# unicodedata.normalize("NFD")로 분해된 조합용 자모 코드포인트(U+1100~U+11C2)
# 을 두벌식 키보드의 자모 글자로 바꾼다. 예: U+1100(초성 'ㄱ') → 'ㄱ'.
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
    """한글 글자 하나를 키보드 자모 문자열로 분해해 반환 (결과 캐싱됨).

    예: "한" → "ㅎㅏㄴ"
    lru_cache 덕분에 같은 글자에 대한 반복 호출은 O(1)이며,
    타자 입력 검증(핫패스)에서 매 키 입력마다 불려도 부담이 없다.
    """
    decomp = unicodedata.normalize("NFD", char)
    return "".join(JAMO_TO_KEY.get(c, c) for c in decomp)


def words_from_file(path: str, count: int = 25) -> list[str]:
    """로컬 파일에서 단어를 읽어 최대 *count*개까지 반환.

    보안 조치:
    - 경로 순회(path traversal) 방지: 파일명만 사용해 현재 작업
      디렉터리 밖 접근을 차단한다(os.path.basename).
    - 심볼릭 링크 읽기 거부 + O_NOFOLLOW 플래그로 TOCTOU 경쟁 상태 차단.
    - fstat으로 열린 fd가 실제 일반 파일인지 확인(FIFO 등 거부).
    - 10MB 용량 제한으로 메모리 고갈 방지.
    """

    # 보안: os.path.basename()으로 디렉터리 부분을 제거해
    # 현재 디렉터리 바깥 파일 읽기(경로 순회 공격)를 차단한다.
    path = os.path.basename(path)

    p = Path(path)
    # 보안: 열기 전 심볼릭 링크 선제 검사
    if p.is_symlink():
        raise ValueError(f"Refusing to read from symlink: {path}")

    if count <= 0:
        return []

    words: list[str] = []

    # 보안: os.open + O_NOFOLLOW 로 TOCTOU(검사-사용 사이 링크 교체) 방지
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise ValueError(f"Could not open file: {path}") from e

    try:
        if getattr(os, "O_NONBLOCK", 0):
            os.set_blocking(fd, True)

        # 보안: 열린 fd를 fstat해 일반 파일임을 확인 (FIFO/디바이스 거부)
        st = os.fstat(fd)
        if not S_ISREG(st.st_mode):
            raise ValueError(f"'{path}' is not a regular file")
        if st.st_size > 10_000_000:
            raise ValueError(f"'{path}' is too large (max 10MB)")

        f = os.fdopen(fd, "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise

    with f:
        # 최적화: 한 줄씩 읽으면서 단어 개수가 채워지면 즉시 반환
        # (파일 전체를 메모리에 올리지 않음)
        for line in f:
            for word in line.split():
                words.append(word)
                if len(words) >= count:
                    return words

    if not words:
        raise ValueError(f"No words found in {path}")
    return words


def words_from_url(url: str, count: int = 25) -> list[str]:
    """원격 텍스트 파일을 HTTP(S)로 내려받아 단어를 반환.

    보안 제한: http/https 스킴만 허용, 10초 타임아웃, 10MB 응답 크기 제한.
    """
    from urllib import request as _request
    from urllib.error import URLError

    if count <= 0:
        return []
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs are supported")

    try:
        with _request.urlopen(url, timeout=10) as resp:  # noqa: S310 (scheme-checked)
            data = resp.read(10_000_001)
    except (URLError, OSError) as e:
        raise ValueError(f"Could not fetch URL: {url}") from e

    if len(data) > 10_000_000:
        raise ValueError(f"'{url}' is too large (max 10MB)")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"'{url}' is not valid UTF-8") from e

    words = text.split()
    if not words:
        raise ValueError(f"No words found at {url}")
    return words[:count]


# ── 손가락별 연습 메타데이터 ────────────────────────────────────────────

# 손가락 키 → 화면 표시용 라벨 (영어)
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


# 레이아웃별 손가락 → 홈(기본) 키 매핑.
# 손가락이 다음 타건을 위해 항상 돌아가는 쉬는 자리의 키.
# (예: QWERTY 왼손 검지의 홈 키는 'f')
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
    """문자들을 소속 손가락별로 분류해 반환.

    Returns a dict of {finger_key: [chars_belonging_to_that_finger]}.
    행 단위 키(home_row 등)는 제외하고 손가락 단위 키만 분류한다.
    취약점 분석 화면에서 "어떤 손가락이 약한지" 집계할 때 사용한다.
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
    """약한 글자(*weak_chars*) 집중 연습 문제 *count*개를 생성.

    동작은 get_practice_drill과 유사하되, 필터 조건이
    "세트 문자만으로 구성된 단어"가 아니라 "약한 글자를 1개 이상 포함한 단어"다.
    실제 단어가 부족하면 약한 글자 조합(엉터리 단어)으로 폴백한다.
    """
    all_words = LAYOUT_TO_WORDS.get(layout, EN_QWERTY)

    is_english = layout.startswith("en")

    # set 변환 1회로 멤버십 검사 비용을 낮춘다
    fast_weak_chars = set(weak_chars)

    def has_weak_char(word: str) -> bool:
        if is_english:
            # 영어: 단어에 약한 글자가 하나라도 있는지
            return not fast_weak_chars.isdisjoint(word.lower())
        for char in word:
            # 한글: 자모 분해 결과와 교집합 검사
            if not fast_weak_chars.isdisjoint(_get_jamos(char)):
                return True
        return False

    # 최적화: 전체 단어장 O(N) 스캔을 피하기 위해 무작위 부분집합을 먼저 필터링
    subset_size = min(len(all_words), max(300, count * 5))
    subset = random.sample(all_words, subset_size) if all_words else []
    filtered = [w for w in subset if has_weak_char(w)]

    if len(filtered) < count // 2 or len(filtered) <= 3:
        # 부분집합으로 충분하지 않으면 전체 목록 스캔으로 폴백
        filtered = [w for w in all_words if has_weak_char(w)]

    drills = []
    if len(filtered) >= count // 2 and len(filtered) > 3:
        # 실제 단어가 충분하면 그 안에서 무작위 선택
        drills = random.choices(filtered, k=count)
    else:
        # 폴백: 약한 글자만으로 이루어진 엉터리 단어 생성
        for _ in range(count):
            word_len = random.randint(3, 6)
            random_chars = random.choices(weak_chars, k=word_len)
            drills.append("".join(random_chars))

    if not is_english:
        # 한글 약점 연습도 자모를 공백으로 분리해 낱글자 연습 형태로 반환
        decomposed_drills = []
        for w in drills:
            decomposed_drills.extend(_decompose_ko_to_spaced_jamos(w).split())
        return decomposed_drills[:count]

    return drills
