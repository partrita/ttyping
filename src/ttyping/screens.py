"""ttyping의 모든 화면(Screen) 구현.

화면 목록:
- ``TypingScreen``  : 타자 연습 본 화면 (핵심 핫패스 — 키 입력마다 실행됨)
- ``ResultScreen``  : 테스트 종료 후 결과 요약
- ``HistoryScreen`` : 최근 50회 기록 표
- ``MenuScreen``    : 메인 메뉴와 각종 서브메뉴(언어/옵션/약점 분석 등)

성능 설계 (중요):
- 타자 입력마다 전체 단어를 다시 렌더링하지 않는다. 줄바꿈 계산은
  인덱스만 담은 캐시(``_cached_lines``)로 재사용하고, 화면에 보이는
  최대 3줄만 Rich Text 객체로 만든다 → O(N)이 아닌 뷰포트 렌더링.
- 통계 위젯(``#stats``) 참조는 on_mount에서 한 번만 찾아 캐싱한다
  (키 입력마다 DOM을 검색하는 query_one 비용 제거).
- 위 두 최적화는 AGENTS.md에 명시된 프로젝트 원칙이므로 리팩토링 시 절대 제거 금지.
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import DataTable, Input, OptionList, ProgressBar, Static
from textual.widgets.option_list import Option

from ttyping.storage import (
    TypingResult,
    clear_results,
    delete_result_by_index,
    load_error_stats,
    load_results,
    save_result,
)
from ttyping.words import _get_jamos

if TYPE_CHECKING:
    from ttyping.app import TypingApp

# ── 색상 팔레트 (Serika / Serika Dark) ──────────────────────────────
# Monkeytype의 시그니처 테마. 프로젝트 표준 팔레트이므로 임의 변경 금지.

# 다크 테마 (Serika Dark)
COL_SERIKA_DARK_BG = "#323437"  # 배경
COL_SERIKA_DARK_SUB_BG = "#2c2e31"  # 서브 배경 (입력창/테이블 등)
COL_SERIKA_DARK_TEXT = "#d1d0c5"  # 본문 글자
COL_SERIKA_DARK_DIM = "#646669"  # 흐린 글자 (안내문/미완 단어)
COL_SERIKA_DARK_ACCENT = "#e2b714"  # 강조색 (Serika Yellow)
COL_SERIKA_DARK_ERROR = "#ca4754"  # 오류 표시

# 라이트 테마 (Serika)
COL_SERIKA_LIGHT_BG = "#e1e1e3"
COL_SERIKA_LIGHT_SUB_BG = "#d1d0c5"
COL_SERIKA_LIGHT_TEXT = "#323437"
COL_SERIKA_LIGHT_DIM = "#646669"
COL_SERIKA_LIGHT_ACCENT = "#e2b714"
COL_SERIKA_LIGHT_ERROR = "#ca4754"

# 코드에서 자주 쓰는 값들의 짧은 별칭 (기본: 다크 테마)
COL_BG = COL_SERIKA_DARK_BG
COL_DIM = COL_SERIKA_DARK_DIM
COL_TEXT = COL_SERIKA_DARK_TEXT
COL_CORRECT = COL_SERIKA_DARK_TEXT
COL_ERROR = COL_SERIKA_DARK_ERROR
COL_ACCENT = COL_SERIKA_DARK_ACCENT
COL_SUB_BG = COL_SERIKA_DARK_SUB_BG


def get_accent() -> str:
    """현재 테마의 강조색(hex)을 반환."""
    return COL_ACCENT


def get_theme_colors(
    app: TypingApp | None = None,
) -> tuple[str, str, str, str, str, str]:
    """현재 테마의 6가지 색을 반환.

    Returns:
        (배경, 서브배경, 글자, 흐린글자, 강조, 오류) hex 색상 6개 튜플.
        *app*이 None이거나 판별 불가하면 다크 테마를 반환한다.
    """
    is_dark = True
    if app is not None:
        is_dark = app.theme == "textual-dark"
    if is_dark:
        return (
            COL_SERIKA_DARK_BG,
            COL_SERIKA_DARK_SUB_BG,
            COL_SERIKA_DARK_TEXT,
            COL_SERIKA_DARK_DIM,
            COL_SERIKA_DARK_ACCENT,
            COL_SERIKA_DARK_ERROR,
        )
    return (
        COL_SERIKA_LIGHT_BG,
        COL_SERIKA_LIGHT_SUB_BG,
        COL_SERIKA_LIGHT_TEXT,
        COL_SERIKA_LIGHT_DIM,
        COL_SERIKA_LIGHT_ACCENT,
        COL_SERIKA_LIGHT_ERROR,
    )


def compute_consistency(char_timings: list[dict[str, Any]]) -> float:
    """키 입력 리듬의 일관성(consistency)을 0~100%로 계산.

    키 사이 간격(inter-key interval)의 **변동계수(CV)의 역수** 기반이다.
    일정한 박자로 치면 100%에 가깝고 들쭉날쭉하면 0%에 가깝다.
    5초 이상의 긴 정지(자리 비움 등)는 평균 왜곡을 막으려고 무시한다.
    """
    # 인접한 두 입력의 시간 차(간격)를 수집. 숫자가 아닌 값은 건너뜀.
    diffs = [
        t["time"] - s["time"]
        for s, t in zip(char_timings, char_timings[1:], strict=False)
        if isinstance(s.get("time"), (int, float))
        and isinstance(t.get("time"), (int, float))
    ]
    diffs = [d for d in diffs if 0 <= d <= 5.0]  # 5초 초과 정지는 제외
    if len(diffs) < 2:
        return 0.0

    mean = sum(diffs) / len(diffs)
    if mean <= 0:
        return 0.0
    variance = sum((d - mean) ** 2 for d in diffs) / len(diffs)
    sd = variance**0.5
    return round(max(0.0, min(100.0, 100 * (1 - sd / mean))), 1)


# ── TypingScreen (타자 연습 본 화면) ────────────────────────────────


class TypingScreen(Screen):
    """타자 연습을 진행하는 메인 화면.

    입력 흐름: Input 위젯의 값이 바뀔 때마다 ``on_input_changed``가 호출되고,
    ① 키 입력/오류 카운트 갱신 → ② 공백이면 단어 완료 → ③ 화면·통계 재렌더링
    순서로 처리된다.
    """

    BINDINGS = [
        Binding(key="tab", action="restart", description="Restart", priority=True),
        Binding(key="escape", action="go_back", description="Back", priority=True),
    ]

    DEFAULT_CSS = """
    TypingScreen {
        align: center middle;
    }

    #typing-container {
        width: 95%;
        max-width: 80;
        height: auto;
        max-height: 100%;
        align: center middle;
    }

    #stats {
        width: 100%;
        height: 2;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
    }

    #text-display {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 8;
        padding: 0 2;
    }

    #input-area {
        width: 100%;
        margin-top: 1;
        padding: 0 1;
    }

    /* 오타 발생 시 입력창 배경을 붉게 물들이는 클래스 */
    #input-area.typo {
        background: #5f2120;
    }
    """

    def __init__(
        self,
        words: list[str],
        lang: str = "en",
        duration: int | None = None,
        target_accuracy: float | None = None,
    ) -> None:
        super().__init__()
        # ── 세션 설정 ──
        self.words = words  # 연습할 단어(문제) 목록
        self.lang = lang  # 언어/레이아웃 식별자 ("ko_2set" 등)
        self.duration = duration  # 시간 제한(초). None이면 무제한
        self.target_accuracy = target_accuracy  # 이 정확도 아래로 내려가면 자동 재시작

        # ── 진행 상태 ──
        self.current_word_idx = 0  # 지금 치고 있는 단어의 인덱스
        self.current_input = ""  # 현재 단어에 대해 입력 중인 글자들
        self.word_correct: list[bool | None] = [None] * len(words)  # 단어별 정/오 기록
        self.start_time: float | None = None  # 첫 타건 시각 (타이머 시작 판정용)
        self._finished: bool = False  # 테스트 종료 여부 (종료 후 입력 차단)

        # ── 통계 누적치 ──
        self.total_keystrokes: int = 0  # 총 키 입력 수 (WPM 분모)
        self.total_errors: int = 0  # 총 오류 수 (정확도 계산용)
        self.uncorrected_errors: int = 0  # 고침 없이 넘어간 잘못된 단어 수

        self.errors: Counter[str] = Counter()  # 글자별 오타 집계 (결과 top errors용)
        self.char_timings: list[dict[str, Any]] = []  # 글자별 (입력글자, 시각, 정오)

        # ── 렌더링 최적화 캐시 ──
        # 줄바꿈 결과(줄 → [단어 인덱스])를 폭이 바뀔 때만 다시 계산한다.
        self._cached_lines: list[list[int]] | None = None
        self._last_container_width: int = 0  # 캐시를 만들었을 때의 컨테이너 폭
        # 아래 위젯 참조들은 on_mount에서 1회만 찾아 캐싱한다 (핫패스 최적화)
        self._stats_widget: Static | None = None
        self._display_widget: Static | None = None
        self._input_widget: Input | None = None

        # ── UI 피드백 상태 ──
        self._timer_handle: Any | None = None  # textual Timer (통계 자동 갱신용)
        self._shaking: bool = False  # 오타 흔들림 애니메이션 진행 중 여부

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="typing-container"):
                yield Static("", id="stats")  # 상단 실시간 WPM/정확도
                yield Static("", id="text-display")  # 연습 문제 텍스트
                yield Input(id="input-area", password=False)

    def on_mount(self) -> None:
        """위젯 참조를 미리 캐싱해 두다 (키 입력 핫패스에서 DOM 검색 제거)."""
        self._stats_widget = self.query_one("#stats", Static)
        self._display_widget = self.query_one("#text-display", Static)
        self._input_widget = self.query_one("#input-area", Input)
        self._input_widget.focus()
        # 초기 렌더는 레이아웃 확정 후 resize 이벤트에서 일어난다

    def on_resize(self, event: events.Resize) -> None:
        """터미널 크기가 바뀌면 줄바꿈 캐시를 버리고 다시 렌더링한다."""
        self._cached_lines = None
        self._render_display()

    def _shake_input(self) -> None:
        """오타 피드백: 입력창을 좌우로 살짝 흔들고 배경을 붉게 칠한다."""
        if self._shaking or self._input_widget is None:
            return
        self._shaking = True
        inp = self._input_widget
        inp.add_class("typo")

        # 흔들림: 오른쪽 → 왼쪽 → 제자리 (각 0.05초)
        self.animate("offset", Offset(1, 0), duration=0.05)
        self.animate("offset", Offset(-1, 0), duration=0.05, delay=0.05)
        self.animate("offset", Offset(0, 0), duration=0.05, delay=0.1)

        def reset_shaking() -> None:
            self._shaking = False
            inp.remove_class("typo")

        self.set_timer(0.2, reset_shaking)

    # ── 입력 처리 (핫패스: 키를 누를 때마다 실행됨) ─────────────────────

    def _is_char_correct(self, typed_char: str, target_char: str) -> bool:
        """입력한 글자와 목표 글자를 비교한다 (한글 IME 부분 조합 허용).

        한글은 'ㄱ'만 친 상태에서도 조합이 진행 중이므로(예: 'ㄱ' → '가'),
        입력 자모가 목표 글자 자모의 **접두어**면 올바른 것으로 간주해
        중간 합성 상태가 오류로 잡히지 않게 한다.
        """
        if typed_char == target_char:
            return True
        if self.lang.startswith("ko"):
            c_jamo = _get_jamos(target_char)
            if c_jamo.startswith(_get_jamos(typed_char)):
                return True
        return False

    def _handle_ime_update(self, value: str) -> bool:
        """IME 조합 단계 업데이트 처리. 오류가 있었으면 True 반환.

        길이는 그대로인데 내용만 바뀐 경우(예: 'ㄱ' → '가')가 한 키 입력이다.
        WPM/정확도 정확도를 위해 이 물리 타건을 반드시 카운트하며,
        마지막 타이밍 기록(char_timings[-1])을 제자리에서 갱신한다.
        """
        has_error = False
        # 마지막 기록이 "지금 위치"에 해당할 때만 갱신 (다른 단어 건드림 방지)
        if (
            self.char_timings
            and self.char_timings[-1]["word_idx"] == self.current_word_idx
            and self.char_timings[-1]["char_idx"] == len(value) - 1
        ):
            last_idx = len(value) - 1
            target_word = self.words[self.current_word_idx]
            char = value[last_idx]
            is_correct = (
                self._is_char_correct(char, target_word[last_idx])
                if last_idx < len(target_word)
                else (char == " ")
            )

            # 이 조합 단계 뒤에 있는 물리 키 입력을 카운트
            self.total_keystrokes += 1
            if not is_correct:
                self.total_errors += 1
                has_error = True

            self.char_timings[-1].update(
                {
                    "char": char,
                    "time": time.time(),
                    "correct": is_correct,
                }
            )
        return has_error

    def _handle_normal_addition(self, added: str) -> bool:
        """새로 추가된 글자들(*added*) 처리. 오류가 있었으면 True 반환.

        글자마다 목표 단어와 비교해 정/오를 판정하고 타이밍 기록을 쌓는다.
        목표 단어보다 더 많이 친 초과 입력은 공백 외엔 모두 오류로 본다.
        """
        has_error = False
        self.total_keystrokes += len(added)
        target_word = self.words[self.current_word_idx]
        for i, char in enumerate(added):
            idx = len(self.current_input) + i  # 이 글자의 목표 단어 내 위치
            is_correct = True
            if idx < len(target_word):
                if not self._is_char_correct(char, target_word[idx]):
                    self.total_errors += 1
                    has_error = True
                    is_correct = False
            elif char != " ":
                # 단어 길이를 넘긴 초과 입력
                self.total_errors += 1
                has_error = True
                is_correct = False

            self.char_timings.append(
                {
                    "char": char,
                    "time": time.time(),
                    "correct": is_correct,
                    "word_idx": self.current_word_idx,
                    "char_idx": idx,
                }
            )
        return has_error

    def _track_legacy_errors(self, value: str) -> None:
        """결과 화면 'top errors' 표시용으로 가장 최근 글자의 오타를 집계한다."""
        if value and self.current_word_idx < len(self.words):
            target_word = self.words[self.current_word_idx]
            last_typed_idx = len(value) - 1
            if last_typed_idx < len(target_word):
                if value[last_typed_idx] != target_word[last_typed_idx]:
                    self.errors[target_word[last_typed_idx]] += 1

    def _ensure_timer_started(self, value: str) -> None:
        """첫 타건에서 통계 갱신 타이머(0.5초 주기)를 시작한다."""
        if self.start_time is None and value:
            self.start_time = time.time()
            self._timer_handle = self.set_interval(0.5, self._tick_stats)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Input 위젯 값 변경마다 호출되는 핵심 핸들러.

        처리 순서:
        1. 키 입력 카운트/오류 판정 (일반 추가 vs IME 조합 단계 구분)
        2. 오류가 있으면 흔들림 피드백
        3. 공백으로 끝나면 현재 단어 완료 처리 후 입력창 비우기
        4. 화면·통계 재렌더링
        """
        if self._finished:
            return

        value = event.value
        has_error = False

        # ── 1. 원시 키 입력/오류 추적 ──
        # 삭제가 아니고 내용이 실제로 바뀐 경우만 처리한다.
        # (길이가 같고 내용만 바뀌면 한글 IME 조합 단계다. 예: 'ㄱ'→'가')
        if len(value) >= len(self.current_input) and value != self.current_input:
            added = (
                value[len(self.current_input) :]
                if len(value) > len(self.current_input)
                else ""
            )

            if len(value) == len(self.current_input):
                # 길이 동일 + 내용 변경 = IME 조합 단계 업데이트
                has_error = self._handle_ime_update(value)
            else:
                # 일반적인 글자 추가
                has_error = self._handle_normal_addition(added)

        if has_error:
            self._shake_input()

        # ── 2. 공백 → 현재 단어 완료 ──
        if value.endswith(" "):
            self._complete_word(value[:-1])
            event.input.value = ""
            return

        # 결과 화면 top errors 집계 (레거시 방식 유지)
        self._track_legacy_errors(value)

        self.current_input = value

        # ── 3. 첫 타건이라면 타이머 시작 ──
        self._ensure_timer_started(value)

        # ── 4. 렌더링 (캐시된 위젯 참조 사용 — query_one 없음) ──
        self._render_display()
        self._update_stats()

    def on_key(self, event: events.Key) -> None:
        """Ctrl+W(단어 지우기), Enter(단어 완료) 등 특수키를 처리한다."""
        if self._finished:
            return
        inp = self._input_widget
        if event.key == "ctrl+w":
            event.prevent_default()
            if inp is not None:
                inp.value = ""
        elif event.key == "enter":
            # Enter도 단어 완료로 취급 (마지막 단어에서 편리함)
            event.prevent_default()
            if inp is not None and inp.value:
                self.total_keystrokes += 1
                self._complete_word(inp.value)
                inp.value = ""
        elif event.key == "enter":
            event.prevent_default()
            if inp is not None and inp.value:
                self.total_keystrokes += 1
                self._complete_word(inp.value)
                inp.value = ""

    # ── 통계 계산 ──────────────────────────────────────────────────────

    def _wpm_parts(self, elapsed: float) -> tuple[float, float, float]:
        """경과 시간(*elapsed*초)으로 (총 WPM, 순 WPM, 정확도%)를 계산.

        - 총 WPM(gross) = (키 입력 수 ÷ 5) ÷ 분  ← 표준 WPM 공식
        - 순 WPM(net)   = 총 WPM − (분당 고치지 않은 오류 수)
        - 정확도        = (정상 입력 ÷ 전체 입력) × 100
        """
        minutes = elapsed / 60
        if minutes <= 0:
            minutes = 0.001  # 0 나눔 방지

        gross_wpm = (self.total_keystrokes / 5) / minutes
        net_wpm = max(0, gross_wpm - (self.uncorrected_errors / minutes))
        accuracy = (
            max(
                0,
                (self.total_keystrokes - self.total_errors)
                / max(self.total_keystrokes, 1),
            )
            * 100
        )
        return gross_wpm, net_wpm, accuracy

    def _get_current_stats(self) -> dict[str, Any]:
        """현재까지의 통계를 딕셔너리로 묶어 반환."""
        elapsed = time.time() - self.start_time if self.start_time else 0.01
        gross_wpm, net_wpm, accuracy = self._wpm_parts(elapsed)
        return {
            "wpm": round(net_wpm, 1),
            "gross_wpm": round(gross_wpm, 1),
            "accuracy": round(accuracy, 1),
            "time": round(elapsed, 1),
            "keystrokes": self.total_keystrokes,
            "errors": self.total_errors,
        }

    # ── 단어 완료 처리 ─────────────────────────────────────────────────

    def _complete_word(self, typed: str) -> None:
        """현재 단어를 *typed*로 확정하고 다음 단어로 넘어간다.

        목표 정확도(target_accuracy)가 설정되어 있고 현재 정확도가 그 아래면
        경고를 보여준 뒤 같은 단어로 재시작하도록 앱에 요청한다.
        """
        target = self.words[self.current_word_idx]
        is_correct = typed == target

        self.word_correct[self.current_word_idx] = is_correct
        if not is_correct:
            self.uncorrected_errors += 1

        self.current_word_idx += 1
        self.current_input = ""

        # ── 목표 정확도 검사 ──
        if self.target_accuracy is not None:
            stats = self._get_current_stats()
            if stats["accuracy"] < self.target_accuracy:
                self._finished = True
                if self._timer_handle:
                    self._timer_handle.stop()

                # 사용자에게 알리고 잠시 후 재시작
                msg = (
                    f"Accuracy {stats['accuracy']:.0f}% below target "
                    f"{self.target_accuracy:.0f}% — restarting"
                )
                self.app.notify(
                    msg,
                    title="Too Low!",
                    severity="warning",
                    timeout=1.5,
                )

                result = TypingResult(
                    wpm=stats["wpm"],
                    gross_wpm=stats["gross_wpm"],
                    accuracy=stats["accuracy"],
                    time=stats["time"],
                    lang=self.lang,
                    words=self.current_word_idx,
                    correct=self.current_word_idx - self.uncorrected_errors,
                    keystrokes=stats["keystrokes"],
                    errors=stats["errors"],
                    char_timings=self.char_timings,
                    text=" ".join(self.words[: self.current_word_idx]),
                )

                # 화면을 닫기 전에 잠깐 알림을 볼 수 있게 0.5초 지연
                self.set_timer(
                    0.5,
                    lambda: cast("TypingApp", self.app).reset_session_attempt(result),
                )
                return

        # 모든 단어를 끝냈으면 테스트 종료
        if self.current_word_idx >= len(self.words):
            self._end_test()
            return

        self._render_display()
        self._update_stats()

    # ── 테스트 종료 ────────────────────────────────────────────────────

    def _end_test(self) -> None:
        """테스트를 마무리한다: 결과 저장 → 결과 화면으로 전환."""
        if self._finished:
            return

        self._finished = True
        if self._timer_handle:
            self._timer_handle.stop()

        elapsed = time.time() - self.start_time if self.start_time else 0.01
        gross_wpm, net_wpm, accuracy = self._wpm_parts(elapsed)
        correct_words = self.current_word_idx - self.uncorrected_errors

        # 가장 많이 틀린 글자 상위 5개
        top_char_errors = self.errors.most_common(5)

        result = TypingResult(
            wpm=round(net_wpm, 1),
            gross_wpm=round(gross_wpm, 1),
            accuracy=round(accuracy, 1),
            time=round(elapsed, 1),
            lang=self.lang,
            words=self.current_word_idx,
            correct=correct_words,
            keystrokes=self.total_keystrokes,
            errors=self.total_errors,
            consistency=compute_consistency(self.char_timings),
            top_char_errors=top_char_errors,
            char_timings=self.char_timings,
            text=" ".join(self.words[: self.current_word_idx]),
        )

        save_result(result)
        cast("TypingApp", self.app).show_result(result)

    # ── 렌더링 ─────────────────────────────────────────────────────────

    def _get_word_text(self, i: int) -> Text:
        """단어 하나를 현재 진행 상태에 맞는 색으로 칠한 Rich Text로 만든다.

        - 이미 완료: 맞으면 흐린 글자, 틀리면 빨강+취소선
        - 현재 입력 중: 글자별로 맞음/틀림 강조, 커서 위치 밑줄
        - 아직 안 온 단어: 흐린 회색
        """
        word = self.words[i]
        t = Text()
        app = cast("TypingApp", self.app)
        _, _, col_text, col_dim, col_accent, col_error = get_theme_colors(app)

        if i < self.current_word_idx:
            if self.word_correct[i]:
                t.append(word, style=f"dim {col_text}")
            else:
                t.append(word, style=f"{col_error} strike")
        elif i == self.current_word_idx:
            typed = self.current_input
            for j, ch in enumerate(word):
                if j < len(typed):
                    # 이미 친 글자: 굵게 + 정오 색
                    if self._is_char_correct(typed[j], ch):
                        t.append(ch, style=f"bold {col_text}")
                    else:
                        t.append(ch, style=f"bold {col_error}")
                elif j == len(typed):
                    # 커서 위치(다음에 칠 글자): 밑줄
                    t.append(ch, style=f"underline {col_text}")
                else:
                    t.append(ch, style=col_text)  # 현재 단어는 더 선명하게
            if len(typed) > len(word):
                # 단어보다 많이 친 초과 입력은 빨간색으로 표시
                t.append(typed[len(word) :], style=f"bold {col_error}")
        else:
            t.append(word, style=col_dim)
        return t

    def _wrap_words(self, container_width: int) -> tuple[list[list[int]], int]:
        """단어들을 *container_width* 폭에 맞춰 줄바꿈 배치한다.

        Returns:
            (줄 목록, 활성 단어가 속한 줄 번호).
            각 줄은 단어 **인덱스**만 담은 리스트다 — Rich Text 객체를
            미리 만들어 두지 않으므로 캐싱 비용이 매우 낮다.

        성능: 폭이 바뀌지 않았으면 계산 결과(``_cached_lines``)를 재사용.
            활성 줄 번호만 매 호출마다 찾는다(평균 몇 줄 순회, O(줄수)).
        """
        if self._cached_lines and container_width == self._last_container_width:
            # 캐시 재사용. 활성 단어의 줄 번호는 진행에 따라 바뀌므로 매번 찾는다.
            active_word_line_idx = 0
            for i, line in enumerate(self._cached_lines):
                if self.current_word_idx in line:
                    active_word_line_idx = i
                    break
            return self._cached_lines, active_word_line_idx

        lines = []
        current_line = []
        current_line_len = 0
        active_word_line_idx = 0

        for i, word in enumerate(self.words):
            word_len = len(word)
            # 이 단어(+공백 1칸)가 줄 폭을 넘기면 새 줄 시작
            if current_line_len + word_len + 1 > container_width:
                lines.append(current_line)
                current_line = []
                current_line_len = 0

            if i == self.current_word_idx:
                active_word_line_idx = len(lines)

            current_line.append(i)
            current_line_len += word_len + 1
        lines.append(current_line)

        self._cached_lines = lines
        self._last_container_width = container_width
        return lines, active_word_line_idx

    def _render_display(self) -> None:
        """연습 문제 텍스트를 화면에 그린다 (뷰포트 방식).

        성능 핵심: 전체 문제가 아니라 **활성 줄 기준 최대 3줄**
        (이전 줄 / 현재 줄 / 다음 줄)만 Rich Text로 조립해 갱신한다.
        줄바꿈 배치 자체는 _wrap_words의 캐시를 재사용한다.
        """
        display_widget = self._display_widget or self.query_one("#text-display", Static)
        container_width = display_widget.content_size.width
        if container_width <= 0:
            # 초기 렌더에서 크기가 아직 계산되지 않았을 때의 폴백값
            container_width = 72

        lines, active_word_line_idx = self._wrap_words(container_width)

        # 표시할 3줄 범위 결정 (화면 끝에서는 범위를 뒤로 당겨 3줄을 유지)
        display_text = Text()
        start_line = max(0, active_word_line_idx - 1)
        end_line = min(len(lines), start_line + 3)

        if end_line - start_line < 3 and start_line > 0:
            start_line = max(0, end_line - 3)

        for l_idx in range(start_line, end_line):
            line = lines[l_idx]
            for i, word_idx in enumerate(line):
                if i > 0:
                    display_text.append(" ")  # 단어 사이 공백
                display_text.append(self._get_word_text(word_idx))
            display_text.append("\n")

        display_widget.update(display_text)

    def _update_stats(self) -> None:
        """상단 통계 줄(WPM · 정확도 · 시간)을 갱신한다.

        성능: query_one 대신 on_mount에서 캐싱한 위젯 참조를 사용한다.
        이 메서드는 키 입력마다 + 0.5초 타이머마다 불린다.
        """
        if self.start_time is None:
            # 아직 타이핑 시작 전이면 통계 대신 빈 화면
            if self._stats_widget is not None:
                self._stats_widget.update("")
            return

        elapsed = time.time() - self.start_time
        _, net_wpm, accuracy = self._wpm_parts(elapsed)

        app = cast("TypingApp", self.app)
        _, _, _, col_dim, col_accent, _ = get_theme_colors(app)

        t = Text()
        t.append(f"{net_wpm:.0f}", style=f"bold {col_accent}")
        t.append(" wpm   ", style=col_dim)
        t.append(f"{accuracy:.0f}%", style=f"bold {col_accent}")
        t.append(" acc   ", style=col_dim)

        # 시간 제한 모드면 남은 시간, 아니면 경과 시간 표시
        if self.duration:
            remaining = max(0, self.duration - elapsed)
            t.append(f"{remaining:.0f}s", style=f"bold {col_accent}")
        else:
            t.append(f"{elapsed:.0f}s", style=f"bold {col_accent}")

        if self._stats_widget is not None:
            self._stats_widget.update(t)

    def _tick_stats(self) -> None:
        """타이머 콜백: 타이핑 없이도 시간/WPM이 흐르게 하고, 제한 도달 시 종료."""
        if not self._finished:
            if self.duration:
                elapsed = time.time() - self.start_time if self.start_time else 0
                if elapsed >= self.duration:
                    self._end_test()
                    return
            self._update_stats()

    # ── 액션 (키 바인딩) ───────────────────────────────────────────────

    def action_restart(self) -> None:
        cast("TypingApp", self.app).restart()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()


# ── ResultScreen (결과 화면) ────────────────────────────────────────


class ResultScreen(Screen):
    """테스트 종료 후 WPM/정확도/속도 지도를 보여주는 화면.

    - Tab: 같은 설정으로 다시 시작
    - h: 기록 화면 열기
    - Esc: 뒤로 가기
    """

    BINDINGS = [
        Binding(key="tab", action="retry", description="Retry", priority=True),
        Binding(key="h", action="history", description="History", show=False),
        Binding(key="escape", action="go_back", description="Back"),
        # 한글 2벌식 IME 지원 ('ㅗ' = 'h' 자리)
        Binding(key="ㅗ", action="history", show=False),
    ]

    DEFAULT_CSS = """
    ResultScreen {
        align: center middle;
    }

    #result-container {
        width: 95%;
        max-width: 72;
        height: auto;
        align: center middle;
        padding: 1 2;
    }

    .result-big {
        width: 100%;
        text-align: center;
        margin-bottom: 0;
    }

    .result-detail {
        width: 100%;
        text-align: center;
    }

    .result-title {
        width: 100%;
        text-align: center;
        margin-top: 1;
    }

    #speed-map {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding: 0 1;
        background: #d1d0c5;
        border: round #646669;
    }
    """

    def __init__(
        self,
        result: TypingResult,
        session_attempts: list[TypingResult] | None = None,
    ) -> None:
        super().__init__()
        self.result = result
        self.session_attempts = session_attempts or []

    def compose(self) -> ComposeResult:
        """결과 요약 위젯들을 배치한다.

        상단부터: 큰 WPM → 정확도 → 부가 정보(시간·단어 수·언어)
        → 타이핑 속도 지도(기록이 있을 때) → 세션 시도 요약(재시작이 있었을 때).
        """
        r = self.result
        app = cast("TypingApp", self.app)
        _, _, col_text, col_dim, col_accent, _ = get_theme_colors(app)

        with Center():
            with Vertical(id="result-container"):
                # 큰 WPM 숫자
                wpm_text = Text()
                wpm_text.append(f"{r.wpm:.0f}", style=f"bold {col_accent}")
                wpm_text.append(" wpm", style=col_dim)
                yield Static(wpm_text, classes="result-big")
                # 정확도
                acc_text = Text()
                acc_text.append(f"{r.accuracy:.1f}%", style=f"bold {col_text}")
                acc_text.append(" accuracy", style=col_dim)
                yield Static(acc_text, classes="result-big")
                # 부가 정보 한 줄
                detail = Text()
                detail.append(f"{r.time:.1f}s", style=col_text)
                detail.append(f"  ·  {r.correct}/{r.words} words", style=col_dim)
                detail.append(f"  ·  {r.lang}", style=col_dim)
                yield Static(detail, classes="result-detail")

                # ── 타이핑 속도 지도 (글자별 색으로 빠르기 시각화) ──
                if r.char_timings:
                    yield Static("typing speed map", classes="result-title")
                    yield Static(self._render_speed_map(), id="speed-map")

                # ── 목표 정확도 재시작이 있었던 세션의 시도 요약 표 ──
                if self.session_attempts:
                    yield Static("session summary", classes="result-title")
                    table = DataTable(id="session-table")
                    table.add_columns("Try", "Acc", "WPM", "Err")
                    for i, att in enumerate(self.session_attempts, 1):
                        table.add_row(
                            str(i),
                            f"{att.accuracy:.1f}%",
                            str(att.keystrokes),
                            str(att.errors),
                        )
                    # 마지막 줄은 성공한 현재 시도
                    table.add_row(
                        str(len(self.session_attempts) + 1),
                        f"{r.accuracy:.1f}%",
                        str(r.keystrokes),
                        str(r.errors),
                    )
                    yield table

    @staticmethod
    def _speed_color(norm: float) -> str:
        """정규화된 입력 간격(0=가장 빠름 ~ 1=가장 느림)에 따라 글자색을 고른다.

        빠름: 초록 → 보통: 노랑/주황 → 느림: 빨강 (Monkeytype 스타일 팔레트)
        """
        if norm < 0.3:
            return "rgb(0,255,100)"  # 빠름
        if norm < 0.7:
            return "rgb(255,200,0)"  # 보통
        return "rgb(255,50,50)"  # 느림

    def _render_speed_map(self) -> Text:
        """입력한 문장을 글자별 '치른 속도' 색으로 칠해 반환한다.

        - 글자 사이 시간 차(dt)를 구하고, 자리 비움 같은 긴 정지는
          1.5초로 잘라 정규화 왜곡을 막는다.
        - 오타 글자는 흰색 글자 + 붉은 배경으로 별도 표시한다.
        """
        if not self.result.char_timings:
            return Text(self.result.text)

        timings = self.result.char_timings

        # 인접 글자 사이 시간 차 계산
        diffs = []
        for i in range(len(timings)):
            if i == 0:
                # 첫 글자엔 이전 기록이 없으므로 중립값 사용
                diffs.append(0.1)
            else:
                dt = timings[i]["time"] - timings[i - 1]["time"]
                diffs.append(min(dt, 1.5))  # 긴 정지 잘라내기

        if not diffs:
            return Text(self.result.text)

        # 최저~최고 간격 기준으로 0.0~1.0 정규화
        min_dt = min(diffs)
        max_dt = max(diffs)
        dt_range = max_dt - min_dt if max_dt > min_dt else 1.0

        t = Text()
        for i, entry in enumerate(timings):
            char = entry["char"]
            norm = (diffs[i] - min_dt) / dt_range

            style = self._speed_color(norm)
            if not entry.get("correct", True):
                # 오류 글자는 붉은 배경으로 강조
                style = f"white on {COL_ERROR}"

            t.append(char, style=style)

        return t

    def action_retry(self) -> None:
        self.app.restart()  # type: ignore[attr-defined]

    def action_history(self) -> None:
        self.app.push_screen(HistoryScreen())

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()


# ── ConfirmDeleteScreen (전체 삭제 확인 대화상자) ───────────────────


class ConfirmDeleteScreen(Screen):
    """기록 전체 삭제 전 확인을 받는 모달 대화상자.

    y: 삭제 확정 / n 또는 Esc: 취소 (한글 자판 ㅛ/ㅜ도 지원)
    """

    DEFAULT_CSS = (
        """
    ConfirmDeleteScreen {
        align: center middle;
        background: rgba(0,0,0,0.7);
    }

    #confirm-box {
        width: 90%;
        max-width: 50;
        height: auto;
        border: round """
        + COL_ERROR
        + """;
        padding: 1 2;
        background: """
        + COL_SUB_BG
        + """;
        align: center middle;
    }

    #confirm-title {
        width: 100%;
        text-align: center;
        color: """
        + COL_ERROR
        + """;
        text-style: bold;
        margin-bottom: 1;
    }

    #confirm-body {
        width: 100%;
        text-align: center;
        color: """
        + COL_TEXT
        + """;
        margin-bottom: 1;
    }

    #confirm-hints {
        width: 100%;
        text-align: center;
        color: """
        + COL_DIM
        + """;
    }
    """
    )

    BINDINGS = [
        Binding(key="y", action="confirm", description="Yes"),
        Binding(key="n", action="cancel", description="No"),
        Binding(key="escape", action="cancel", description="Cancel"),
        # 한글 2벌식 IME 지원 (ㅛ = 'y', ㅜ = 'n' 자리)
        Binding(key="ㅛ", action="confirm", show=False),
        Binding(key="ㅜ", action="cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="confirm-box"):
                yield Static("Delete History", id="confirm-title")
                yield Static(
                    "This will permanently delete ALL typing history"
                    " and error statistics.",
                    id="confirm-body",
                )
                # 파괴적 작업이므로 키 안내를 화면에 명시한다
                yield Static(
                    Text.from_markup(r"[dim]Press \[y] or \[n][/dim]"),
                    id="confirm-hints",
                )

    def action_confirm(self) -> None:
        clear_results()
        # 이 대화상자와 그 아래 HistoryScreen 둘 다 닫는다
        self.app.pop_screen()  # pop ConfirmDeleteScreen
        self.app.pop_screen()  # pop HistoryScreen

    def action_cancel(self) -> None:
        self.app.pop_screen()


# ── HistoryScreen (기록 보기) ───────────────────────────────────────


class HistoryScreen(Screen):
    """최근 50회 타자 기록을 최신순 표로 보여주는 화면.

    조작: d 선택 행 삭제 · D 전체 삭제(확인 후) · x CSV 내보내기
          j JSON 내보내기 · Enter 상세 보기 · Esc 뒤로 가기
    """

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(
            key="d",
            action="delete_selected",
            description="Delete Selected",
            priority=True,
        ),
        Binding(key="D", action="delete_all", description="Delete All", priority=True),
        Binding(key="x", action="export_csv", description="Export CSV", show=False),
        Binding(key="j", action="export_json", description="Export JSON", show=False),
        # 한글 2벌식 IME 지원 ('ㅇ' = 'd' 자리)
        Binding(key="ㅇ", action="delete_selected", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        # 화면 행 번호(최신이 첫 줄) → 저장소 원본 인덱스 매핑.
        # 표는 "최신 우선"으로 보여주지만 저장소는 "오래된 것 먼저"라
        # 인덱스가 뒤집혀 있어서, 삭제 시 올바른 항목을 지우려면 이 변환이 필요하다.
        self._row_to_storage_idx: list[int] = []

    DEFAULT_CSS = """
    HistoryScreen {
        align: center middle;
    }

    #history-container {
        width: 95%;
        max-width: 100;
        height: auto;
        max-height: 100%;
        align: center middle;
        content-align: center middle;
    }

    #history-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #history-progress-container {
        width: 100%;
        max-width: 60;
        height: auto;
        margin-top: 0;
        margin-bottom: 1;
        align: center middle;
    }

    #history-progress-label {
        width: 100%;
        text-align: center;
        text-style: dim;
        margin-bottom: 0;
    }

    #history-progress-bar {
        width: 100%;
    }

    .history-hint {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        text-style: dim;
    }

    #history-table {
        width: 100%;
        height: auto;
        max-height: 16;
        scrollbar-gutter: stable;
        scrollbar-background: #d1d0c5;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    """

    def compose(self) -> ComposeResult:
        """기록 화면을 구성한다: 제목 → 목표 WPM 진행 바(설정 시) → 안내문 → 표."""
        results = load_results()
        n = len(results)
        # 최신 우선 표시용 매핑 생성 (최대 50개)
        display_count = min(n, 50)
        # 저장소 인덱스를 최신(마지막 항목)부터 거꾸로 나열
        self._row_to_storage_idx = list(range(n - 1, n - 1 - display_count, -1))
        app = cast("TypingApp", self.app)

        with Center():
            with Vertical(id="history-container"):
                yield Static("History", id="history-title")
                if not results:
                    yield Static("No results yet — go type!", id="history-empty")
                else:
                    # ── 목표 WPM 진행 바 (설정해 둔 경우에만 표시) ──
                    avg_wpm = sum(r.wpm for r in results) / n
                    if app._target_wpm is not None and app._target_wpm > 0:
                        target = float(app._target_wpm)
                        pct = min(100.0, avg_wpm / target * 100.0)
                        label = (
                            f"Goal WPM: {avg_wpm:.1f} / {app._target_wpm} ({pct:.1f}%)"
                        )
                        with Vertical(id="history-progress-container"):
                            yield Static(
                                label,
                                id="history-progress-label",
                            )
                            yield ProgressBar(
                                total=target,
                                show_eta=False,
                                id="history-progress-bar",
                            )

                    yield Static(
                        "[dim]Press [bold]d[/bold] to delete selected record"
                        " · [bold]D[/bold] to delete all"
                        " · [bold]Esc[/bold] to back[/dim]",
                        classes="history-hint",
                    )
                    yield self._create_history_table(results, self._row_to_storage_idx)

    def on_mount(self) -> None:
        """목표 WPM 진행 바의 현재 값을 평균 WPM으로 채운다."""
        app = cast("TypingApp", self.app)
        if app._target_wpm is not None and app._target_wpm > 0:
            results = load_results()
            avg_wpm = sum(r.wpm for r in results) / len(results) if results else 0.0
            try:
                bar = self.query_one("#history-progress-bar", ProgressBar)
                bar.progress = min(float(app._target_wpm), float(avg_wpm))
            except Exception:
                pass

    def _create_history_table(
        self,
        results: list[TypingResult],
        row_indices: list[int],
    ) -> DataTable:
        """최근 50개 기록(최신 우선)을 담은 DataTable을 만들어 반환.

        표시 열: 번호, 날짜, WPM, 정확도, 일관성, 언어, 시간, 단어 수.
        동적 문자열(언어/날짜)은 escape()로 무력화해 Rich 마크업
        주입(크래시)을 방지한다.
        """
        table: DataTable[str] = DataTable(id="history-table")
        table.cursor_type = "row"
        table.add_columns("#", "Date", "WPM", "Acc", "Cons", "Lang", "Time", "Words")

        for display_idx, storage_idx in enumerate(row_indices, 1):
            r = results[storage_idx]
            # ISO 타임스탬프를 짧게 표시 (파싱 실패 시 원본 앞부분 사용)
            date_str = ""
            if r.date:
                try:
                    dt = datetime.fromisoformat(r.date)
                    date_str = dt.strftime("%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(r.date)[:11]

            table.add_row(
                str(display_idx),
                escape(date_str),
                f"{r.wpm:.0f}",
                f"{r.accuracy:.1f}%",
                f"{r.consistency:.0f}%",
                escape(r.lang),
                f"{r.time:.0f}s",
                f"{r.correct}/{r.words}",
            )
        return table

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """행 선택(Enter) 시 해당 기록의 상세 화면(ResultScreen)을 연다."""
        results = load_results()
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._row_to_storage_idx):
            storage_idx = self._row_to_storage_idx[row_idx]
            if 0 <= storage_idx < len(results):
                self.app.push_screen(ResultScreen(results[storage_idx]))

    def action_go_back(self) -> None:
        stack = self.app.screen_stack
        # `ttyping history`로 곧바로 열린 경우: 아래에 남는 것은 앱의 빈
        # 기본 Screen뿐이므로 pop 대신 앱을 종료하는 게 자연스럽다.
        if len(stack) <= 2 and type(stack[0]) is Screen:
            self.app.exit()
        else:
            self.app.pop_screen()

    def action_delete_selected(self) -> None:
        """커서가 놓인 행의 기록을 삭제하고 표를 다시 만든다."""
        try:
            table = self.query_one("#history-table", DataTable)
        except Exception:
            return  # 표가 없는 상태(기록 없음)면 무시
        row_idx = table.cursor_row  # 화면 기준 0-based 행 번호
        if 0 <= row_idx < len(self._row_to_storage_idx):
            storage_idx = self._row_to_storage_idx[row_idx]
            delete_result_by_index(storage_idx)
            # 삭제 반영을 위해 화면을 새로 구성
            self.app.pop_screen()
            self.app.push_screen(HistoryScreen())

    def action_delete_all(self) -> None:
        self.app.push_screen(ConfirmDeleteScreen())

    def action_export_csv(self) -> None:
        from ttyping.storage import EXPORT_CSV_FILE, export_results_csv

        count = export_results_csv(EXPORT_CSV_FILE)
        msg = (
            f"Exported {count} results to {EXPORT_CSV_FILE}"
            if count
            else "No results to export"
        )
        self.app.notify(msg, title="Export CSV", timeout=3)

    def action_export_json(self) -> None:
        from ttyping.storage import EXPORT_JSON_FILE, export_results_json

        count = export_results_json(EXPORT_JSON_FILE)
        msg = (
            f"Exported {count} results to {EXPORT_JSON_FILE}"
            if count
            else "No results to export"
        )
        self.app.notify(msg, title="Export JSON", timeout=3)


# ── MenuScreen (메인 메뉴) ──────────────────────────────────────────


class ActionSelectMixin:
    """Enter 키로 OptionList 항목을 선택하는 동작을 끼워 넣는 믹스인."""

    def action_select(self) -> None:
        """현재 포커스된 OptionList의 선택 액션을 실행한다."""
        try:
            ol = self.query_one("#menu-options", OptionList)  # type: ignore[attr-defined]
            ol.action_select()
        except Exception:
            pass


ASCII_LOGO = r"""
 _   _               _
| |_| |_ _   _ _ __ (_)_ __   __ _
| __| __| | | | '_ \| | '_ \ / _` |
| |_| |_| |_| | |_) | | | | | (_| |
 \__|\__|\__, | .__/|_|_| |_|\__, |
          |___/|_|            |___/
""".strip("\n")


class MenuScreen(ActionSelectMixin, Screen):
    """앱 시작 시 처음 보이는 메인 메뉴.

    단일 키 숏컷으로 바로 이동 가능:
    e 영어 · k 한국어 · p 코드 · w 약점 분석 · h 기록 · o 옵션 · q/Esc 종료
    (한글 자판: ㄷ · ㅏ · ㅔ · ㅈ · ㅗ · ㅐ · ㅂ)
    """

    DEFAULT_CSS = """
    MenuScreen {
        align: center middle;
    }

    #menu-container {
        width: 90%;
        max-width: 60;
        height: auto;
        padding: 1 2;
        align: center middle;
    }

    #menu-logo {
        width: 100%;
        text-align: center;
        color: #e2b714;
        margin-bottom: 1;
    }

    #menu-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #e2b714;
        margin-bottom: 1;
    }

    OptionList {
        border: none;
        height: auto;
        max-height: 15;
        text-align: center;
    }

    .about-text {
        width: 100%;
        text-align: center;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="e", action="select_en", description="English", show=False),
        Binding(key="k", action="select_ko", description="Korean", show=False),
        Binding(key="w", action="select_weak", description="Weak Analysis", show=False),
        Binding(key="h", action="select_history", description="History", show=False),
        Binding(key="o", action="select_options", description="Options", show=False),
        Binding(key="p", action="select_code", description="Code", show=False),
        Binding(key="escape", action="quit_app", description="Quit"),
        Binding(key="q", action="quit_app", description="Quit", show=False),
        # 한글 2벌식 자판 매핑 (영문 숏컷과 같은 물리 키 위치)
        Binding(key="ㄷ", action="select_en", show=False),
        Binding(key="ㅏ", action="select_ko", show=False),
        Binding(key="ㅈ", action="select_weak", show=False),
        Binding(key="ㅗ", action="select_history", show=False),
        Binding(key="ㅐ", action="select_options", show=False),
        Binding(key="ㅔ", action="select_code", show=False),
        Binding(key="ㅂ", action="quit_app", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static(ASCII_LOGO, id="menu-logo")
                yield Static("ttyping", id="menu-title")
                yield OptionList(
                    Option(
                        Text.from_markup(r"English(영어) [dim]\[e][/dim]"),
                        id="en",
                    ),
                    Option(
                        Text.from_markup(r"Korean(한국어) [dim]\[k][/dim]"),
                        id="ko",
                    ),
                    Option(
                        Text.from_markup(r"Code(코드) [dim]\[p][/dim]"),
                        id="code",
                    ),
                    Option(
                        Text.from_markup(r"Weak word(약점 단어 연습) [dim]\[w][/dim]"),
                        id="weakness",
                    ),
                    Option(
                        Text.from_markup(r"View History(기록 보기) [dim]\[h][/dim]"),
                        id="history",
                    ),
                    Option(
                        Text.from_markup(r"Options [dim]\[o][/dim]"),
                        id="options",
                    ),
                    id="menu-options",
                )

    def on_mount(self) -> None:
        self._update_logo_visibility()

    def on_resize(self, event: events.Resize) -> None:
        self._update_logo_visibility()

    def _update_logo_visibility(self) -> None:
        """터미널이 좁거나 낮으면 ASCII 로고 대신 짧은 제목을 보여준다."""
        try:
            logo = self.query_one("#menu-logo", Static)
            title = self.query_one("#menu-title", Static)
        except Exception:
            return

        width, height = self.size
        if width == 0 or height == 0:
            return  # 크기 계산 전 폴백

        if height < 20 or width < 40:
            logo.display = False
            title.display = True
        else:
            logo.display = True
            title.display = False

    def on_resume(self) -> None:
        """서브 화면에서 돌아올 때도 로고 표시 여부를 다시 판단한다."""
        self._update_logo_visibility()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """메뉴 항목 선택 시 해당 화면으로 이동한다."""
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "history":
            app.push_screen(HistoryScreen())
        elif opt_id == "weakness":
            app.push_screen(WeaknessScreen())
        elif opt_id == "options":
            app.push_screen(OptionsScreen())
        elif opt_id == "en":
            app.push_screen(ENSubMenu())
        elif opt_id == "ko":
            app.push_screen(KOSubMenu())
        elif opt_id == "code":
            app.push_screen(CodeSubMenu())

    def action_select_en(self) -> None:
        self.app.push_screen(ENSubMenu())

    def action_select_ko(self) -> None:
        self.app.push_screen(KOSubMenu())

    def action_select_code(self) -> None:
        self.app.push_screen(CodeSubMenu())

    def action_select_weak(self) -> None:
        self.app.push_screen(WeaknessScreen())

    def action_select_history(self) -> None:
        self.app.push_screen(HistoryScreen())

    def action_select_options(self) -> None:
        self.app.push_screen(OptionsScreen())

    def action_quit_app(self) -> None:
        self.app.exit()


class _SubMenuScreen(ActionSelectMixin, Screen):
    """OptionList 하나를 띄우는 단순 서브메뉴의 공통 베이스 클래스.

    - 메뉴 컨테이너·타이틀 CSS를 MenuScreen과 공유한다.
    - Enter(선택) / Esc(뒤로 가기) 바인딩과 pop_screen 동작을 공통 제공.
    - 실제 메뉴 항목 구성은 각 서브클래스의 compose()가 담당한다.
    """

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="select", description="Select"),
        Binding(key="escape", action="go_back", description="Back"),
    ]

    def action_go_back(self) -> None:
        self.app.pop_screen()


class CodeSubMenu(_SubMenuScreen):
    """코드 연습용 언어(Python, Rust 등) 선택 서브메뉴."""

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Code Typing", id="menu-title")
                yield OptionList(
                    Option("Python", id="python"),
                    Option("Rust", id="rust"),
                    Option("R", id="r"),
                    Option("JavaScript", id="javascript"),
                    Option("TypeScript", id="typescript"),
                    Option("Go", id="go"),
                    Option("C", id="c"),
                    Option("Julia", id="julia"),
                    Option("Typst", id="typst"),
                    Option("Markdown", id="markdown"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id in (
            "markdown",
            "javascript",
            "julia",
            "python",
            "r",
            "rust",
            "typst",
            "typescript",
            "go",
            "c",
        ):
            app.start_custom_test(opt_id, app._word_count, app._duration)


class ENSubMenu(_SubMenuScreen):
    """영어 자판 배열(Qwerty/Dvorak/Colemak) 선택 서브메뉴."""

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("English Typing", id="menu-title")
                yield OptionList(
                    Option("Qwerty", id="en_qwerty"),
                    Option("Dvorak", id="en_dvorak"),
                    Option("Colemak", id="en_colemak"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "en_qwerty":
            app.push_screen(PracticeMenu("en_qwerty"))
        elif opt_id == "en_dvorak":
            app.push_screen(PracticeMenu("en_dvorak"))
        elif opt_id == "en_colemak":
            app.push_screen(PracticeMenu("en_colemak"))


class KOSubMenu(_SubMenuScreen):
    """한글 자판 배열(두벌식/세벌식) 선택 서브메뉴."""

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static("한글 타이핑", id="menu-title")
                yield OptionList(
                    Option("두벌식 (2-set)", id="ko_2set"),
                    Option("세벌식 (3-set)", id="ko_3set"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option_id
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "ko_2set":
            app.push_screen(PracticeMenu("ko_2set"))
        elif opt_id == "ko_3set":
            app.push_screen(PracticeMenu("ko_3set"))


# ── 연습 세트 메뉴 및 옵션 화면들 ───────────────────────────────────

# 연습 세트 메뉴 제목 (레이아웃별)
_PRACTICE_TITLES: dict[str, str] = {
    "en_qwerty": "QWERTY Practice",
    "en_dvorak": "Dvorak Practice",
    "en_colemak": "Colemak Practice",
    "ko_2set": "두벌식 연습",
    "ko_3set": "세벌식 연습",
}

# 연습 세트 항목 (표시 라벨, 옵션 ID) 목록 — 영문 UI용.
# ID 형식: "full:<모드>" 또는 "practice:<세트이름>"
_PRACTICE_OPTIONS_EN: list[tuple[str, str]] = [
    ("Words", "full:words"),
    ("Sentences", "full:sentences"),
    ("Lorem Ipsum", "full:lorem_ipsum"),
    ("Quotes", "full:quotes"),
    ("Home Row", "practice:home_row"),
    ("Top Row", "practice:top_row"),
    ("Bottom Row", "practice:bottom_row"),
    ("Number Row (1-0)", "practice:number_row"),
    ("Symbol Row (!@#...)", "practice:symbol_row"),
    ("Left Hand", "practice:left_hand"),
    ("Right Hand", "practice:right_hand"),
    ("Left Index", "practice:left_index"),
    ("Right Index", "practice:right_index"),
    ("Left Middle", "practice:left_middle"),
    ("Right Middle", "practice:right_middle"),
    ("Left Ring", "practice:left_ring"),
    ("Right Ring", "practice:right_ring"),
    ("Left Pinky", "practice:left_pinky"),
    ("Right Pinky", "practice:right_pinky"),
]

# 연습 세트 항목 — 한글 UI용
_PRACTICE_OPTIONS_KO: list[tuple[str, str]] = [
    ("단어", "full:words"),
    ("짧은 글", "full:sentences"),
    ("로렘 입숨", "full:lorem_ipsum"),
    ("명언", "full:quotes"),
    ("가운데 줄", "practice:home_row"),
    ("윗 줄", "practice:top_row"),
    ("아랫 줄", "practice:bottom_row"),
    ("숫자 줄 (1-0)", "practice:number_row"),
    ("특수문자 (!@#...)", "practice:symbol_row"),
    ("왼손 자음", "practice:left_hand"),
    ("오른손 모음", "practice:right_hand"),
    ("왼손 검지", "practice:left_index"),
    ("오른손 검지", "practice:right_index"),
    ("왼손 중지", "practice:left_middle"),
    ("오른손 중지", "practice:right_middle"),
    ("왼손 약지", "practice:left_ring"),
    ("오른손 약지", "practice:right_ring"),
    ("왼손 새끼", "practice:left_pinky"),
    ("오른손 새끼", "practice:right_pinky"),
]


class PracticeMenu(_SubMenuScreen):
    """특정 레이아웃의 연습 세트(자판 행·손가락별)를 고르는 메뉴."""

    def __init__(self, layout_id: str) -> None:
        super().__init__()
        self.layout_id = layout_id  # 대상 레이아웃 (예: "ko_2set")

    def compose(self) -> ComposeResult:
        title = _PRACTICE_TITLES.get(
            self.layout_id, f"{self.layout_id.upper()} Practice"
        )
        # 한글 레이아웃이면 한글 라벨 목록 사용
        entries = (
            _PRACTICE_OPTIONS_KO
            if self.layout_id.startswith("ko")
            else _PRACTICE_OPTIONS_EN
        )
        options = [Option(label, id=opt_id) for label, opt_id in entries]
        with Center():
            with Vertical(id="menu-container"):
                yield Static(escape(title), id="menu-title")
                yield OptionList(
                    *options,
                    Option("Back", id="back"),
                    id="menu-options",
                    name="Practice Set Selection",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id == "full:words":
            app.start_custom_test(self.layout_id, app._word_count, app._duration)
        elif opt_id == "full:sentences":
            lang = "ko_sentences" if "ko" in self.layout_id else "en_sentences"
            app.start_custom_test(lang, app._word_count, app._duration)
        elif opt_id == "full:lorem_ipsum":
            lang = "ko_lorem_ipsum" if "ko" in self.layout_id else "en_lorem_ipsum"
            app.start_custom_test(lang, app._word_count, app._duration)
        elif opt_id == "full:quotes":
            lang = "ko_quotes" if "ko" in self.layout_id else "en_quotes"
            app.start_custom_test(lang, app._word_count, app._duration)
        elif opt_id.startswith("practice:"):
            set_name = opt_id.split(":")[1]
            # get_words()가 practice 세트로 인식하도록 접두어를 붙여 전달
            app.start_custom_test(
                f"practice:{self.layout_id}:{set_name}", app._word_count, app._duration
            )

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WordCountMenu(_SubMenuScreen):
    """전용 연습 세트가 없는 레이아웃을 위한 단순 대체 메뉴."""

    def __init__(self, layout_id: str) -> None:
        super().__init__()
        self.layout_id = layout_id

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="menu-container"):
                yield Static(escape(self.layout_id.upper()), id="menu-title")
                yield OptionList(
                    Option("Words", id=f"{self.layout_id}:words"),
                    Option("Sentences", id=f"{self.layout_id}:sentences"),
                    Option("Back", id="back"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "back":
            app.pop_screen()
        elif opt_id.endswith(":words"):
            app.start_custom_test(self.layout_id, app._word_count, app._duration)
        elif opt_id.endswith(":sentences"):
            lang = "ko_sentences" if "ko" in self.layout_id else "en_sentences"
            app.start_custom_test(lang, app._word_count, app._duration)

    def action_go_back(self) -> None:
        # 베이스 동작에 안전 장치 추가: 스택이 비면 pop하지 않는다
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()


class AccuracyMenu(_SubMenuScreen):
    """목표 정확도를 고르는 메뉴 (미달 시 자동 재시작 기능의 기준값)."""

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = app._target_accuracy
        if current is None:
            current_label = "None (Free Practice)"
        else:
            current_label = f"{int(current)}%"
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Target Accuracy", id="menu-title")
                yield Static(escape(f"Current: {current_label}"), classes="about-text")
                yield OptionList(
                    Option("None (Free Practice)", id="none"),
                    Option("80%", id="80"),
                    Option("90%", id="90"),
                    Option("95%", id="95"),
                    Option("100% (No Mistakes)", id="100"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """선택한 정확도를 앱 상태와 설정 파일에 저장한다."""
        from ttyping.storage import load_config, save_config

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "none":
            app._target_accuracy = None
        else:
            app._target_accuracy = float(opt_id)

        # 설정 파일에 영속화
        cfg = load_config()
        cfg["target_accuracy"] = app._target_accuracy
        save_config(cfg)

        label = (
            "None" if app._target_accuracy is None else f"{int(app._target_accuracy)}%"
        )
        app.notify(f"Accuracy set to {label}", title="Saved", timeout=2)
        app.pop_screen()


class OptionsScreen(_SubMenuScreen):
    """옵션 메뉴: 단어 수 · 목표 WPM · 시간 · 정확도 · 테마 · 정보.

    하위 화면에서 돌아오면(on_resume) 현재 값으로 라벨을 다시 그린다.
    """

    def _get_labels(self) -> tuple[str, str, str, str, str]:
        """각 옵션의 현재 값을 화면 표시용 라벨로 만들어 반환."""
        app = cast("TypingApp", self.app)
        words_label = str(app._word_count)
        target_wpm = app._target_wpm
        wpm_label = "None" if target_wpm is None else f"{target_wpm} WPM"
        time_label = "Off" if app._duration is None else f"{app._duration}s"
        acc = app._target_accuracy
        acc_label = "None" if acc is None else f"{int(acc)}%"
        theme_label = "Dark" if app.theme == "textual-dark" else "Light"
        return words_label, wpm_label, time_label, acc_label, theme_label

    def compose(self) -> ComposeResult:
        words_label, wpm_label, time_label, acc_label, theme_label = self._get_labels()
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Options", id="menu-title")
                yield OptionList(
                    Option(escape(f"Words: {words_label}"), id="words"),
                    Option(escape(f"Target WPM: {wpm_label}"), id="target_wpm"),
                    Option(escape(f"Time: {time_label}"), id="time"),
                    Option(escape(f"Accuracy: {acc_label}"), id="accuracy"),
                    Option(escape(f"Theme: {theme_label}"), id="theme"),
                    Option("About", id="about"),
                    id="menu-options",
                )

    def on_resume(self) -> None:
        """하위 화면(예: 단어 수 변경)에서 돌아오면 라벨을 새로 고친다."""
        self.refresh(recompose=True)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """선택한 옵션에 대응하는 설정 화면을 연다."""
        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        if opt_id == "words":
            app.push_screen(WordCountInputScreen())
        elif opt_id == "target_wpm":
            app.push_screen(TargetWpmInputScreen())
        elif opt_id == "time":
            app.push_screen(TimeMenu())
        elif opt_id == "accuracy":
            app.push_screen(AccuracyMenu())
        elif opt_id == "theme":
            app.push_screen(ThemeScreen())
        elif opt_id == "about":
            app.push_screen(AboutScreen())


class TargetWpmInputScreen(Screen):
    """목표 WPM을 입력받는 화면 (0 또는 빈 값 입력 시 해제)."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="submit", description="Save"),
        Binding(key="escape", action="go_back", description="Cancel"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current_wpm = str(app._target_wpm) if app._target_wpm is not None else ""
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Set Target WPM", id="menu-title")
                yield Static(
                    escape("Enter target WPM (1-500) or 0 to disable:"),
                    classes="about-text",
                )
                yield Input(
                    value=current_wpm,
                    placeholder="Target WPM (e.g. 80, 0 to disable)",
                    id="wpm-input",
                    type="integer",
                    max_length=4,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """입력 중에는 이전 오류 안내(border_title)를 즉시 지운다."""
        self.query_one("#wpm-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter로 값 확정: 0/빈 값이면 해제, 1~500이면 저장한다."""
        from ttyping.storage import load_config, save_config

        value = event.value.strip()
        app = cast("TypingApp", self.app)

        if not value or value == "0":
            app._target_wpm = None
            cfg = load_config()
            cfg["target_wpm"] = None
            save_config(cfg)
            app.notify("Target WPM disabled", title="Saved", timeout=2)
            app.pop_screen()
            return

        try:
            target = int(value)
            if not 1 <= target <= 500:
                raise ValueError
        except ValueError:
            # 잘못된 입력: 입력창에 오류 안내 표시 후 대기
            self.query_one(
                "#wpm-input", Input
            ).border_title = "⚠ Enter a number from 1 to 500 (or 0)"
            return

        app._target_wpm = target
        cfg = load_config()
        cfg["target_wpm"] = target
        save_config(cfg)
        app.notify(f"Target WPM set to {target}", title="Saved", timeout=2)
        app.pop_screen()

    def action_submit(self) -> None:
        inp = self.query_one("#wpm-input", Input)
        self.on_input_submitted(Input.Submitted(inp, inp.value))

    def action_go_back(self) -> None:
        self.app.pop_screen()


class ThemeScreen(_SubMenuScreen):
    """다크/라이트 테마를 고르는 메뉴 (선택 즉시 설정 파일에 저장)."""

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = "Dark" if app.theme == "textual-dark" else "Light"
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Theme", id="menu-title")
                yield Static(escape(f"Current: {current}"), classes="about-text")
                yield OptionList(
                    Option("🌙  Dark", id="dark"),
                    Option("☀️  Light", id="light"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """선택한 테마를 앱에 적용하고 설정 파일에 저장한다."""
        from ttyping.storage import load_config, save_config

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        app.theme = "textual-dark" if opt_id == "dark" else "textual-light"

        cfg = load_config()
        cfg["theme"] = opt_id
        save_config(cfg)

        theme_label = "Dark" if opt_id == "dark" else "Light"
        app.notify(f"Theme set to {theme_label}", title="Saved", timeout=2)
        app.pop_screen()


class AboutScreen(Screen):
    """ttyping 소개 화면 (Enter/Esc로 닫기)."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="escape", action="go_back", description="Back"),
        Binding(key="enter", action="go_back", description="Back"),
    ]

    def compose(self) -> ComposeResult:
        about_text = [
            "# ttyping",
            "",
            "A minimal, monkeytype-inspired terminal typing test.",
            "",
            "Practice layouts, track WPM/accuracy, and",
            "target specific finger muscle memory.",
            "",
            "Built with Python & Textual.",
            "",
            "---",
            "Apache License 2.0",
        ]
        with Center():
            with Vertical(id="menu-container"):
                yield Static("About ttyping", id="menu-title")
                yield Static("\n".join(about_text), classes="about-text")

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WordCountInputScreen(Screen):
    """기본 단어 수(1~1000)를 입력받는 화면."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="submit", description="Save"),
        Binding(key="escape", action="go_back", description="Cancel"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Set Word Count", id="menu-title")
                yield Input(
                    value=str(app._word_count),
                    placeholder="Number of words (e.g. 25)",
                    id="words-input",
                    type="integer",
                    max_length=4,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """입력 중에는 이전 오류 안내(border_title)를 즉시 지운다."""
        self.query_one("#words-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """값 검증 후 앱 상태와 설정 파일에 저장한다."""
        from ttyping.storage import load_config, save_config

        value = event.value.strip()
        try:
            count = int(value)
            if not 1 <= count <= 1000:
                raise ValueError
        except ValueError:
            self.query_one(
                "#words-input", Input
            ).border_title = "⚠ Enter a number from 1 to 1000"
            return

        app = cast("TypingApp", self.app)
        app._word_count = count
        cfg = load_config()
        cfg["word_count"] = count
        save_config(cfg)
        app.notify(f"Words set to {count}", title="Saved", timeout=2)
        app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class TimeMenu(_SubMenuScreen):
    """자주 쓰는 시간 제한 프리셋을 고르는 메뉴."""

    PRESETS: list[tuple[str, int | None]] = [
        ("Off (Free Practice)", 0),
        ("15 seconds", 15),
        ("30 seconds", 30),
        ("60 seconds", 60),
        ("120 seconds", 120),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = "Off" if app._duration is None else f"{app._duration}s"
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Time Limit", id="menu-title")
                yield Static(escape(f"Current: {current}"), classes="about-text")
                options = [
                    Option(label, id=f"time:{value}") for label, value in self.PRESETS
                ]
                yield OptionList(
                    *options,
                    Option("Custom…", id="time:custom"),
                    id="menu-options",
                )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """프리셋 선택을 앱 상태와 설정 파일에 반영한다.

        ID 형식이 "time:<초>"이며 "0"은 제한 없음(None)으로 해석한다.
        """
        from ttyping.storage import load_config, save_config

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)

        if opt_id == "time:custom":
            app.push_screen(TimeLimitInputScreen())
            return
        if not opt_id.startswith("time:"):
            return

        raw = opt_id.split(":", 1)[1]
        duration: int | None = None if raw == "0" else int(raw)

        app._duration = duration
        cfg = load_config()
        cfg["duration"] = duration
        save_config(cfg)
        msg = "Time limit cleared" if duration is None else f"Time set to {duration}s"
        app.notify(msg, title="Saved", timeout=2)
        app.pop_screen()


class TimeLimitInputScreen(Screen):
    """시간 제한(초, 1~3600)을 직접 입력받는 화면. 빈 값이면 제한 해제."""

    DEFAULT_CSS = MenuScreen.DEFAULT_CSS

    BINDINGS = [
        Binding(key="enter", action="submit", description="Save"),
        Binding(key="escape", action="go_back", description="Cancel"),
    ]

    def compose(self) -> ComposeResult:
        app = cast("TypingApp", self.app)
        current = str(app._duration) if app._duration else ""
        with Center():
            with Vertical(id="menu-container"):
                yield Static("Set Time Limit", id="menu-title")
                yield Input(
                    value=current,
                    placeholder="Seconds (leave blank for no limit)",
                    id="time-input",
                    type="integer",
                    max_length=4,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """입력 중에는 이전 오류 안내(border_title)를 즉시 지운다."""
        self.query_one("#time-input", Input).border_title = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """값 검증 후 앱 상태와 설정 파일에 저장한다 (빈 값 = 제한 해제)."""
        from ttyping.storage import load_config, save_config

        value = event.value.strip()

        if not value:
            duration: int | None = None
        else:
            try:
                duration = int(value)
                if not 1 <= duration <= 3600:
                    raise ValueError
            except ValueError:
                self.query_one(
                    "#time-input", Input
                ).border_title = "⚠ Enter a number from 1 to 3600"
                return

        app = cast("TypingApp", self.app)
        app._duration = duration
        cfg = load_config()
        cfg["duration"] = duration
        save_config(cfg)
        msg = "Time limit cleared" if duration is None else f"Time set to {duration}s"
        app.notify(msg, title="Saved", timeout=2)
        app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WeaknessScreen(_SubMenuScreen):
    """약점 키 분석 화면 — 누적 오류 통계와 손가락별 집중 연습 메뉴.

    데이터 흐름:
    1. load_error_stats()로 지금까지 가장 많이 틀린 글자 상위 10개를 모은다.
    2. 그 글자들을 손가락별로 분류해 오류 수 기준 정렬한다.
    3. 가장 약한 손가락 3개에 대한 집중 드릴 시작 옵션을 제공한다.
    """

    DEFAULT_CSS = """
    WeaknessScreen {
        align: center middle;
    }

    #weakness-container {
        width: 95%;
        max-width: 70;
        height: auto;
        align: center middle;
        padding: 1 2;
    }

    #weakness-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .weakness-section {
        width: 100%;
        text-align: center;
        margin-top: 1;
    }

    #weakness-table {
        width: 100%;
        height: auto;
        max-height: 12;
        margin-top: 0;
    }

    #weakness-options {
        width: 100%;
        margin-top: 1;
        border: none;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        """오류 통계 표와 손가락별 연습 옵션을 구성한다."""
        from ttyping.words import (
            FINGER_LABELS,
            FINGER_LABELS_KO,
            chars_to_finger,
        )

        stats = load_error_stats()
        app = cast("TypingApp", self.app)
        layout = app._lang
        # 한글 레이아웃이면 손가락 라벨도 한글로 표시
        is_ko = layout.startswith("ko")
        labels = FINGER_LABELS_KO if is_ko else FINGER_LABELS
        with Center():
            with Vertical(id="weakness-container"):
                yield Static("Weakness Analysis", id="weakness-title")
                if not stats:
                    yield Static(
                        "Complete more typing tests to build analysis.",
                        classes="weakness-section",
                    )
                else:
                    # 누적 오류 수 기준 상위 10개 글자
                    sorted_chars = sorted(
                        stats.items(), key=lambda x: x[1], reverse=True
                    )[:10]
                    top_chars_str = "".join(c for c, _ in sorted_chars)

                    # 글자를 소속 손가락으로 분류하고 손가락별 오류 합계 산출
                    finger_map = chars_to_finger(layout, top_chars_str)
                    finger_totals: dict[str, int] = {
                        f: sum(stats.get(c, 0) for c in cs)
                        for f, cs in finger_map.items()
                    }

                    sorted_fingers = sorted(
                        finger_totals.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )

                    # 연습 시작 옵션 (전체 + 가장 약한 손가락 3개)
                    options: list[Option] = [
                        Option("Practice All Weak Keys ▶", id="drill:all"),
                    ]
                    for finger, total in sorted_fingers[:3]:
                        finger_chars = "".join(finger_map.get(finger, []))
                        if finger_chars:
                            label = labels.get(finger, finger)
                            options.append(
                                Option(
                                    # 보안: 기록 파일에서 온 문자열은 신뢰할 수 없다.
                                    # escape()로 Rich 마크업 주입(크래시)을 방지한다.
                                    escape(f"Practice {label} ({total} err) ▶"),
                                    id=f"drill:{finger}",
                                )
                            )
                    options.append(Option("← Back", id="back"))

                    yield OptionList(*options, id="menu-options")

                    # ── 손가락별 오류 분포 표 ──
                    yield Static("▸ Errors by Finger", classes="weakness-section")
                    table: DataTable[str] = DataTable(id="weakness-table")
                    table.add_columns("Finger", "Weak Keys", "Errors")
                    for finger, total in sorted_fingers:
                        chars_list = finger_map.get(finger, [])
                        chars_display = " ".join(chars_list[:8])
                        label = labels.get(finger, finger)
                        table.add_row(escape(label), escape(chars_display), str(total))
                    yield table

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """선택한 드릴(전체 또는 특정 손가락) 연습을 시작한다."""
        from ttyping.words import chars_to_finger

        opt_id = str(event.option_id)
        app = cast("TypingApp", self.app)
        layout = app._lang
        stats = load_error_stats()

        if opt_id == "back":
            app.pop_screen()
            return

        sorted_chars = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]
        top_chars_str = "".join(c for c, _ in sorted_chars)

        if opt_id == "drill:all":
            app.start_weak_drill(layout, top_chars_str)
        elif opt_id.startswith("drill:"):
            finger = opt_id[len("drill:") :]
            finger_map = chars_to_finger(layout, top_chars_str)
            weak_chars = "".join(finger_map.get(finger, []))
            if weak_chars:
                app.start_weak_drill(layout, weak_chars)

    def action_go_back(self) -> None:
        self.app.pop_screen()
