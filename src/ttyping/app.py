"""ttyping 메인 Textual 애플리케이션.

TypingApp은 화면(screen) 스택과 앱 전역 상태를 관리한다:
- 언어/단어 수/시간 제한 등 세션 설정 (CLI 인자 > 저장된 설정 > 기본값 우선순위)
- 타이핑 화면 ↔ 결과 화면 ↔ 기록 화면 사이의 이동
- 목표 정확도 미달 시 같은 단어로 재시작하는 세션 관리

화면 위젯 자체는 screens.py에 구현되어 있다.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from ttyping.screens import HistoryScreen, TypingScreen
from ttyping.storage import TypingResult
from ttyping.words import get_weak_drill, get_words, words_from_file, words_from_url

# ── 설정 파일 방어적 파싱 헬퍼 ──────────────────────────────────────
# config.json은 사용자가 직접 수정할 수 있어 값의 타입을 신뢰할 수 없다.
# 잘못된 값(문자열 숫자, null, 객체 등)이 있어도 앱이 크래시하지 않도록
# 모든 필드를 아래 헬퍼로 명시적으로 변환한다.


def _cfg_str(raw: object) -> str | None:
    """값이 문자열일 때만 그대로 반환하고, 그 외엔 None을 돌려준다."""
    return raw if isinstance(raw, str) else None


def _cfg_int(raw: object, fallback: int | None) -> int | None:
    """값을 int로 변환한다. None이거나 변환 불가면 *fallback*을 반환한다."""
    if raw is None:
        return fallback
    try:
        return int(raw)
    except (ValueError, TypeError):
        return fallback


def _cfg_float(raw: object, fallback: float | None) -> float | None:
    """값을 float로 변환한다. None이거나 변환 불가면 *fallback*을 반환한다."""
    if raw is None:
        return fallback
    try:
        return float(raw)
    except (ValueError, TypeError):
        return fallback


class TypingApp(App):
    """ttyping 최상위 앱. 화면 스택과 세션 상태를 관리한다."""

    TITLE = "ttyping"

    BINDINGS = [
        Binding(key="ctrl+q", action="quit", description="Quit", show=True),
    ]

    # ── 듀얼 테마 CSS ───────────────────────────────────────────────────
    # 라이트 모드(Serika): bg #e1e1e3, 서브배경 #d1d0c5, 글자 #323437, 강조 #e2b714
    # 다크 모드(Serika Dark): bg #323437, 서브배경 #2c2e31, 글자 #d1d0c5, 강조 #e2b714
    # `.-dark-mode` 클래스가 붙으면 다크 팔레트 규칙이 적용된다.
    CSS = """
    /* ── Base ───────────────────────────────────────── */
    Screen               { background: #e1e1e3; color: #323437; }
    .-dark-mode Screen { background: #323437; color: #d1d0c5; }

    /* ── Scrollbars ─────────────────────────────────── */
    ScrollBar {
        background: #e1e1e3;
        color: #646669;
    }
    ScrollBar .scrollbar--thumb {
        background: #646669 50%;
        color: #e2b714;
    }
    ScrollBar .scrollbar--thumb:hover {
        background: #e2b714;
    }
    .-dark-mode ScrollBar {
        background: #323437;
        color: #646669;
    }
    .-dark-mode ScrollBar .scrollbar--thumb {
        background: #646669 50%;
        color: #e2b714;
    }
    .-dark-mode ScrollBar .scrollbar--thumb:hover {
        background: #e2b714;
    }

    /* ── OptionList & Selection ─────────────────────── */
    OptionList {
        border: none;
    }
    OptionList:focus > .option-list--option-highlighted {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }
    OptionList > .option-list--option-highlighted {
        background: #e2b714 30%;
        color: #323437;
    }
    .-dark-mode OptionList:focus > .option-list--option-highlighted {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }
    .-dark-mode OptionList > .option-list--option-highlighted {
        background: #e2b714 30%;
        color: #d1d0c5;
    }

    /* ── Input (All inputs in modals/menus) ─────────── */
    Input {
        border: round #646669;
        background: #e1e1e3;
        color: #323437;
    }
    Input:focus {
        border: round #e2b714;
    }
    .-dark-mode Input {
        border: round #646669;
        background: #323437;
        color: #d1d0c5;
    }
    .-dark-mode Input:focus {
        border: round #e2b714;
    }

    /* ── ProgressBar ────────────────────────────────── */
    ProgressBar .bar--bar {
        color: #e2b714;
        background: #646669 40%;
    }
    ProgressBar .bar--complete {
        color: #e2b714;
    }
    .-dark-mode ProgressBar .bar--bar {
        color: #e2b714;
        background: #646669 40%;
    }
    .-dark-mode ProgressBar .bar--complete {
        color: #e2b714;
    }

    /* ── DataTable ──────────────────────────────────── */
    DataTable {
        border: round #646669;
    }
    .-dark-mode DataTable {
        border: round #646669;
    }
    DataTable:focus {
        border: round #e2b714;
    }
    .-dark-mode DataTable:focus {
        border: round #e2b714;
    }
    DataTable > .datatable--cursor {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }
    .-dark-mode DataTable > .datatable--cursor {
        background: #e2b714;
        color: #323437;
        text-style: bold;
    }

    /* ── Typing screen ──────────────────────────────── */
    #stats               { color: #e2b714; }
    .-dark-mode #stats { color: #e2b714; }

    #input-area {
        border: round #646669;
        background: #d1d0c5;
        color: #323437;
    }
    .-dark-mode #input-area {
        border: round #646669;
        background: #2c2e31;
        color: #d1d0c5;
    }
    #input-area:focus          { border: round #e2b714; }
    .-dark-mode #input-area:focus { border: round #e2b714; }

    #hints               { color: #646669; }
    .-dark-mode #hints { color: #646669; }

    /* ── Result screen ──────────────────────────────── */
    .result-detail       { color: #646669; }
    .result-title        { color: #646669; }
    #result-hints        { color: #646669; }
    .-dark-mode .result-detail { color: #646669; }
    .-dark-mode .result-title  { color: #646669; }
    .-dark-mode #result-hints  { color: #646669; }
    .-dark-mode #speed-map     { background: #2c2e31; }

    /* ── History screen ─────────────────────────────── */
    #history-title { color: #e2b714; }
    .-dark-mode #history-title { color: #e2b714; }

    #history-stats  { color: #646669; }
    #history-hints  { color: #646669; }
    .-dark-mode #history-stats { color: #646669; }
    .-dark-mode #history-hints { color: #646669; }

    #history-table  { background: #d1d0c5; }
    .-dark-mode #history-table {
        background: #2c2e31;
        scrollbar-background: #2c2e31;
    }

    #history-empty  { color: #646669; }
    .-dark-mode #history-empty { color: #646669; }

    /* ── Menu / sub-menu containers ─────────────────── */
    #menu-container {
        border: round #e2b714;
        background: #d1d0c5;
    }
    .-dark-mode #menu-container {
        border: round #e2b714;
        background: #2c2e31;
    }

    #menu-title { color: #e2b714; }
    .-dark-mode #menu-title { color: #e2b714; }

    #menu-hints  { display: none; }

    #menu-options { background: #d1d0c5; }
    .-dark-mode #menu-options { background: #2c2e31; }

    /* ── Confirm delete modal ────────────────────────── */
    #confirm-box {
        background: #d1d0c5;
        border: round #ca4754;
    }
    .-dark-mode #confirm-box {
        background: #2c2e31;
        border: round #ca4754;
    }
    #confirm-title  { color: #ca4754; }
    #confirm-body   { color: #323437; }
    #confirm-hints  { color: #646669; }
    .-dark-mode #confirm-body  { color: #d1d0c5; }
    .-dark-mode #confirm-hints { color: #646669; }

    /* ── Weakness screen ─────────────────────────────── */
    #weakness-container {
        border: round #e2b714;
        background: #d1d0c5;
    }
    .-dark-mode #weakness-container {
        border: round #e2b714;
        background: #2c2e31;
    }
    #weakness-title   { color: #e2b714; }
    .-dark-mode #weakness-title { color: #e2b714; }

    .weakness-section { color: #646669; }
    .-dark-mode .weakness-section { color: #646669; }

    #weakness-options { background: #d1d0c5; }
    .-dark-mode #weakness-options { background: #2c2e31; }

    #weakness-hints  { color: #646669; }
    .-dark-mode #weakness-hints { color: #646669; }

    /* ── About screen ────────────────────────────────── */
    .about-text  { color: #646669; }
    .-dark-mode .about-text { color: #646669; }

    /* ── DataTable global ────────────────────────────── */
    DataTable {
        background: #d1d0c5;
        color: #323437;
        scrollbar-background: #d1d0c5;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    .-dark-mode DataTable {
        background: #2c2e31;
        color: #d1d0c5;
        scrollbar-background: #2c2e31;
        scrollbar-color: #646669;
        scrollbar-color-hover: #e2b714;
        scrollbar-color-active: #e2b714;
    }
    """

    def __init__(
        self,
        lang: str | None = None,
        file_path: str | None = None,
        word_count: int | None = None,
        duration: int | None = None,
        target_accuracy: float | None = None,
        show_history: bool = False,
        url: str | None = None,
    ) -> None:
        super().__init__()

        # 설정 파일은 앱 초기화 시점에만 읽으므로(콜드 패스) 지연 임포트 사용
        from ttyping.storage import load_config

        config = load_config()

        # ── CLI 인자 > 저장된 설정 > 기본값 순서로 세션 설정을 결정한다 ──
        # config.json은 임의로 수정 가능하므로 모든 값에 방어적 타입 검사를 적용.

        self._lang: str = _cfg_str(lang) or _cfg_str(config.get("lang")) or "en_qwerty"
        self._file_path: str | None = _cfg_str(file_path) or _cfg_str(
            config.get("file_path")
        )
        self._url: str | None = url

        # 단어 수: 1~1000으로 제한 (과도한 메모리 할당 방지)
        wc = (
            word_count
            if word_count is not None
            else _cfg_int(config.get("word_count", 25), 25)
        )
        self._word_count: int = max(1, min(int(wc), 1000))

        # 시간 제한(초): 1~3600으로 제한. 미설정(None)이면 단어 수 기반 테스트.
        dur = (
            duration if duration is not None else _cfg_int(config.get("duration"), None)
        )
        self._duration: int | None = max(1, min(dur, 3600)) if dur is not None else None

        # 목표 정확도(%): 0~100으로 제한. 이 값 아래로 떨어지면 자동 재시작.
        acc = (
            target_accuracy
            if target_accuracy is not None
            else _cfg_float(config.get("target_accuracy"), None)
        )
        self._target_accuracy: float | None = (
            max(0.0, min(acc, 100.0)) if acc is not None else None
        )

        # 목표 WPM: 1~500으로 제한. 기록 화면의 진행 바에 사용된다.
        target_wpm = _cfg_int(config.get("target_wpm"), None)
        self._target_wpm: int | None = (
            max(1, min(target_wpm, 500)) if target_wpm is not None else None
        )

        self._show_history: bool = show_history
        self._session_attempts: list[TypingResult] = []
        # 현재 세션에서 재사용할 단어 목록 (목표 정확도 재시작 시 같은 단어 유지용)
        self._current_session_words: list[str] | None = None

        # 저장된 테마 적용 (기본은 다크; 타입이 잘못된 값도 다크로 처리)
        is_dark = (_cfg_str(config.get("theme")) or "dark") == "dark"
        self.theme = "textual-dark" if is_dark else "textual-light"

    def on_mount(self) -> None:
        """앱 시작 직후 첫 화면을 띄운다."""
        if self._show_history:
            self.push_screen(HistoryScreen())
        else:
            # 순환 임포트 회피를 위해 함수 안에서 임포트
            from ttyping.screens import MenuScreen

            self.push_screen(MenuScreen())

    def _start_typing(self, keep_words: bool = False) -> None:
        """타이핑 테스트 화면을 연다.

        Args:
            keep_words: True면 이전 세션의 같은 단어를 재사용하고,
                False(기본값)면 새 문제를 만든다.
        """
        # 현재 설정을 다음 실행을 위한 기본값으로 저장
        from ttyping.storage import load_config, save_config

        config = load_config()
        config.update(
            {
                "lang": self._lang,
                "file_path": self._file_path,
                "word_count": self._word_count,
                "duration": self._duration,
                "target_accuracy": self._target_accuracy,
            }
        )
        save_config(config)

        if not keep_words:
            self._current_session_words = None

        words = self._get_words()
        self.push_screen(
            TypingScreen(
                words,
                lang=self._lang,
                duration=self._duration,
                target_accuracy=self._target_accuracy,
            )
        )

    def _get_words(self) -> list[str]:
        """세션 단어 목록을 반환 (필요 시 새로 생성).

        우선순위: 재사용 대기 중인 단어 > 파일 > URL > 내장 단어장.
        시간 제한 모드는 단어가 먼저 끝나지 않도록 넉넉히 500개를 준비한다.
        """
        if self._current_session_words:
            return self._current_session_words

        count = self._word_count
        if self._duration:
            count = 500

        words: list[str]
        if self._file_path:
            words = words_from_file(self._file_path, count)
        elif self._url:
            words = words_from_url(self._url, count)
        else:
            words = get_words(self._lang, count)

        self._current_session_words = words
        return words

    def _clear_typing_screens(self) -> None:
        """스택 위에 쌓인 타이핑/결과 화면을 모두 치운다."""
        while len(self.screen_stack) > 1 and self.screen.__class__.__name__ in (
            "TypingScreen",
            "ResultScreen",
        ):
            self.pop_screen()

    def restart(self) -> None:
        """현재 화면들을 치우고 **새 단어**로 타자 테스트를 시작한다. (Tab 키)"""
        self._clear_typing_screens()
        self._start_typing(keep_words=False)

    def reset_session_attempt(self, stats: TypingResult) -> None:
        """실패한 시도(목표 정확도 미달)를 기록하고 **같은 단어**로 재시작한다."""
        self._session_attempts.append(stats)
        self._clear_typing_screens()
        self._start_typing(keep_words=True)

    def show_result(self, result: TypingResult) -> None:
        """테스트 종료 후 타이핑 화면을 결과 화면으로 교체한다."""
        from ttyping.screens import ResultScreen

        self.switch_screen(
            ResultScreen(result, session_attempts=self._session_attempts)
        )

    def start_custom_test(self, lang: str, words: int, duration: int | None) -> None:
        """사용자가 고른 파라미터로 새 테스트를 시작하고 세션 상태를 초기화한다."""
        self._lang = lang
        self._word_count = words
        self._duration = duration
        self._file_path = None
        self._url = None
        self._session_attempts = []
        self._current_session_words = None
        self._start_typing(keep_words=False)

    def start_weak_drill(self, layout: str, weak_chars: str) -> None:
        """약한 글자(*weak_chars*) 집중 연습 드릴을 시작한다."""
        self._session_attempts = []
        drill_words = get_weak_drill(layout, weak_chars, count=30)
        self._current_session_words = drill_words
        self._lang = layout
        self._duration = None
        self.push_screen(
            TypingScreen(
                drill_words,
                lang=layout,
                duration=None,
                target_accuracy=self._target_accuracy,
            )
        )
