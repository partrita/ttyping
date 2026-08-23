"""ttyping CLI 진입점.

명령줄 인자를 파싱해 TypingApp을 실행한다:
- ``ttyping``                    : 메인 메뉴로 시작
- ``ttyping --lang ko_2set``     : 언어/레이아웃 지정
- ``ttyping --words 50``         : 단어 수 지정
- ``ttyping --time 60``          : 시간 제한 모드
- ``ttyping --file a.txt``       : 파일 연습
- ``ttyping history``            : 기록 보기
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

# --lang 옵션에서 선택 가능한 언어/레이아웃/문장 모드 식별자들.
# (내장 단어장 키와 1:1 대응 — ttyping/words.py의 LAYOUT_TO_WORDS 참고)
LANG_CHOICES: list[str] = [
    "en_qwerty",
    "en_dvorak",
    "en_colemak",
    "ko_2set",
    "ko_3set",
    "en",
    "ko",
    "python",
    "rust",
    "r",
    "javascript",
    "julia",
    "typst",
    "markdown",
    "go",
    "c",
    "typescript",
    "en_sentences",
    "ko_sentences",
    "en_lorem_ipsum",
    "ko_lorem_ipsum",
    "en_quotes",
    "ko_quotes",
]


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """명령줄 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        prog="ttyping",
        description="A minimal terminal typing test",
    )
    parser.add_argument(
        "--lang",
        choices=LANG_CHOICES,
        help="language for random words",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="path to a text file for typing practice",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="URL of a remote text file for typing practice",
    )
    parser.add_argument(
        "--words",
        type=int,
        help="number of words to type (max: 1000)",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=int,
        help="duration of the test in seconds (overrides --words)",
    )
    parser.add_argument(
        "--target-accuracy",
        "-a",
        type=float,
        help="target accuracy percentage (0-100); restart on drop",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["history"],
        help="subcommand (history: view past results)",
    )

    return parser.parse_args(args)


def main() -> None:
    """CLI 인자를 해석해 앱을 실행한다."""
    args = parse_args()

    # 보안: 단어 수 상한(1000) 강제 — 과도한 메모리 할당 방지
    if args.words is not None:
        args.words = max(1, min(args.words, 1000))

    # TUI 프레임워크(Textual) 임포트는 실제 실행 직전으로 미뤄
    # `--help` 같은 가벼운 호출의 시작 시간을 줄인다.
    from ttyping.app import TypingApp

    try:
        app = TypingApp(
            lang=args.lang,
            file_path=args.file,
            word_count=args.words,
            duration=args.time,
            target_accuracy=args.target_accuracy,
            show_history=args.command == "history",
            url=args.url,
        )
        app.run()
    except Exception as e:
        # TUI 초기화 실패 등 치명적 오류는 stderr로 알리고 비정상 종료
        import sys

        print(f"Sentinel: Application error encountered: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
