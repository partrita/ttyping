"""타자 연습 결과·설정을 위한 로컬 JSON 저장소.

저장 구조:
- ``~/.ttyping/results.json`` : 타자 결과 목록. **JSON Lines**(줄당 JSON 1개) 형식.
  과거의 단일 JSON 배열 형식은 읽을 때 자동으로 JSONL로 마이그레이션한다.
- ``~/.ttyping/config.json``  : 언어/단어 수/테마 등 사용자 설정.

캐싱 전략 (성능):
- 결과/설정은 최초 디스크 읽기 후 모듈 전역 캐시(`_RESULTS_CACHE`,
  `_CONFIG_CACHE`)에 보관되며, 이후 조회는 O(1)이다.
- 쓰기(append/delete/clear)는 **디스크 쓰기가 성공한 뒤에만** 캐시를
  갱신한다. I/O 실패 시 메모리와 디스크 상태 불일치(데이터 오염)를 막기 위함.

보안 조치:
- 모든 파일 접근은 심볼릭 링크 거부 + ``O_NOFOLLOW`` 플래그로 TOCTOU
  (검사-사용 사이 경로 교체) 공격을 차단한다.
- 파일은 0o600, 디렉터리는 0o700 권한으로 강제해 다른 사용자의 읽기를 막는다.
- 읽기/쓰기 대상은 fstat으로 일반 파일임을 확인하며(FIFO/디바이스 거부),
  10MB 용량 제한으로 메모리 고갈을 방지한다.
"""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from stat import S_ISREG
from typing import Any

# ── 저장 위치 상수 ──────────────────────────────────────────────────
STORAGE_DIR = Path.home() / ".ttyping"
RESULTS_FILE = STORAGE_DIR / "results.json"
CONFIG_FILE = STORAGE_DIR / "config.json"
EXPORT_CSV_FILE = STORAGE_DIR / "results_export.csv"
EXPORT_JSON_FILE = STORAGE_DIR / "results_export.json"

# 모듈 전역 캐시. None이면 "아직 디스크에서 읽지 않음"을 뜻한다.
_STORAGE_ENSURED: bool = False
_CONFIG_CACHE: dict[str, Any] | None = None
_RESULTS_CACHE: list[TypingResult] | None = None


def _parse_top_char_errors(raw: object) -> list[tuple[str, int]]:
    """저장된 자주 틀린 글자 목록을 방어적으로 파싱한다.

    각 항목은 ``[글자, 개수]`` 형태의 길이 2 시퀀스여야 하며,
    형태가 다르거나 형변환이 불가능한 항목은 조용히 건너뛴다.
    (손상된 results.json이 앱 크래시를 유발하지 않도록)
    """
    if not isinstance(raw, list):
        return []
    parsed: list[tuple[str, int]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                parsed.append((str(item[0]), int(item[1])))
            except (ValueError, TypeError):
                pass
    return parsed


def _parse_char_timings(raw: object) -> list[dict[str, Any]]:
    """저장된 글자별 타이핑 시각 기록을 방어적으로 파싱한다.

    각 항목은 ``{"char": ..., "time": ...}`` 딕셔너리여야 하며
    내부 값(time은 float, char는 str)까지 형변환해 검증한다.
    변환에 실패한 항목은 건너뛴다.
    """
    if not isinstance(raw, list):
        return []
    parsed: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and "time" in item and "char" in item:
            try:
                item["time"] = float(item["time"])
                item["char"] = str(item["char"])
                parsed.append(item)
            except (ValueError, TypeError):
                pass
    return parsed


@dataclass
class TypingResult:
    """타자 연습 1회의 결과 레코드.

    주요 필드:
    - wpm / gross_wpm : 순 WPM(오타 감안), 총 WPM
    - accuracy        : 글자 단위 정확도(%)
    - top_char_errors : 가장 많이 틀린 글자 [(글자, 횟수)]
    - char_timings    : 글자별 입력 시각/정오표 (속도 지도·일관성 계산용)
    - text            : 연습한 전체 문장
    """

    wpm: float
    accuracy: float
    time: float
    lang: str
    words: int
    correct: int
    keystrokes: int
    errors: int
    gross_wpm: float = 0.0
    consistency: float = 0.0
    top_char_errors: list[tuple[str, int]] = field(default_factory=list)
    char_timings: list[dict[str, Any]] = field(default_factory=list)
    text: str = ""
    date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON 저장용 딕셔너리로 변환."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TypingResult:
        """딕셔너리에서 결과 객체를 복원한다 (방어적 역직렬화).

        사용자가 results.json을 임의로 수정했을 수 있으므로 모든 필드를
        명시적으로 형변환하며, 실패 시 기본값으로 폴백해 앱 크래시를 막는다.
        오래된 기록 일부 필드가 누락된 경우도 .get() 기본값으로 처리한다.
        """
        try:
            val = data.get("date")
            return cls(
                wpm=float(data.get("wpm", 0)),
                accuracy=float(data.get("accuracy", 0)),
                time=float(data.get("time", 0)),
                lang=str(data.get("lang", "en")),
                words=int(data.get("words", 0)),
                correct=int(data.get("correct", 0)),
                keystrokes=int(data.get("keystrokes", 0)),
                errors=int(data.get("errors", 0)),
                gross_wpm=float(data.get("gross_wpm", 0)),
                consistency=float(data.get("consistency", 0)),
                top_char_errors=_parse_top_char_errors(data.get("top_char_errors", [])),
                char_timings=_parse_char_timings(data.get("char_timings", [])),
                text=str(data.get("text", "")),
                date=str(val) if val is not None else None,
            )
        except (ValueError, TypeError):
            # 치명적으로 손상된 레코드는 0값 레코드로 대체해 로드가 계속되게 한다
            return cls(
                wpm=0.0,
                accuracy=0.0,
                time=0.0,
                lang="en",
                words=0,
                correct=0,
                keystrokes=0,
                errors=0,
                gross_wpm=0.0,
                top_char_errors=[],
                char_timings=[],
                text="",
                date=None,
            )


# ── 안전한 저수준 파일 접근 헬퍼 ────────────────────────────────────


def _open_fd_safely(file_path: Path, flags: int, create_mode: int | None) -> int:
    """TOCTOU 방지 플래그를 덧붙여 fd를 열고 블로킹 모드로 복원.

    - ``O_NOFOLLOW``: 경로 마지막 성분이 심볼릭 링크면 open 자체가 실패.
      "is_symlink 검사 → 실제 open" 사이에 공격자가 링크로 바꿔치기하는
      TOCTOU 경쟁 상태를 커널 수준에서 차단한다.
    - 플랫폼에 따라 open을 O_NONBLOCK으로 해야 FIFO이 걸리지 않으므로
      열린 직후 원래대로 블로킹 모드를 되돌린다.
    - *create_mode*는 O_CREAT 시 적용될 초기 권한(예: 0o600).
    """
    flags |= getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd = (
        os.open(file_path, flags, create_mode)
        if create_mode is not None
        else os.open(file_path, flags)
    )
    try:
        if getattr(os, "O_NONBLOCK", 0):
            os.set_blocking(fd, True)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _ensure_regular_file(fd: int, file_path: Path) -> None:
    """열린 fd가 일반 파일인지 확인(FIFO/디바이스 등 거부)."""
    st = os.fstat(fd)
    if not S_ISREG(st.st_mode):
        raise OSError(f"Not a regular file: {file_path}")


def _force_private_mode(fd: int) -> None:
    """열린 fd의 권한을 소유자 전용(rw-------)으로 강제."""
    if hasattr(os, "fchmod"):
        st = os.fstat(fd)
        if (st.st_mode & 0o777) != 0o600:
            os.fchmod(fd, 0o600)


def _fchmod_safe(file_path: Path, mode: int = 0o600, is_dir: bool = False) -> None:
    """fd 기반으로 권한을 안전하게 설정한다 (TOCTOU 방지).

    Path.chmod()는 "검사 후 chmod" 사이 경로가 심볼릭 링크로 바뀌면
    의도치 않은 대상에 적용될 수 있다. 그래서 가능한 플랫폼(macOS/Linux)
    에서는 O_NOFOLLOW로 연 fd에 fchmod를 적용한다.
    fchmod/fstat이 없는 플랫폼(Windows 등)에서만 Path 기반 폴백을 쓴다.
    """
    from stat import S_ISDIR

    if hasattr(os, "fchmod") and hasattr(os, "fstat"):
        try:
            fd = _open_fd_safely(file_path, os.O_RDONLY, None)
            try:
                st = os.fstat(fd)
                # 대상 종류가 기대와 다르면(디렉터리↔파일) 건드리지 않음
                if is_dir and not S_ISDIR(st.st_mode):
                    return
                if not is_dir and not S_ISREG(st.st_mode):
                    return
                if (st.st_mode & 0o777) != mode:
                    os.fchmod(fd, mode)
                return
            finally:
                os.close(fd)
        except OSError:
            # 파일이 삭제되었거나 O_NOFOLLOW로 심볼릭 링크가 차단된 경우
            return

    # fchmod/fstat 미지원 플랫폼(Windows 등) 폴백
    if file_path.is_symlink():
        return
    try:
        st = file_path.stat()
        if is_dir and not S_ISDIR(st.st_mode):
            return
        if not is_dir and not S_ISREG(st.st_mode):
            return
        if (st.st_mode & 0o777) != mode:
            file_path.chmod(mode)
    except OSError:
        pass


def _secure_append(file_path: Path, content: str) -> None:
    """파일 끝에 내용을 추가한다. 생성 시 0o600 권한 보장.

    결과 저장(save_result)에서 매번 전체 파일을 다시 쓰지 않고
    한 줄(JSONL)만 붙이기 위해 사용한다 — O(1) append.
    """
    if file_path.is_symlink():
        raise OSError(f"Refusing to write to symlink: {file_path}")

    fd = _open_fd_safely(file_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        _ensure_regular_file(fd, file_path)
        _force_private_mode(fd)
        f = os.fdopen(fd, "a", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        f.write(content)
    # 이미 존재하던 파일일 때도 권한이 올바른지 최종 확인
    _fchmod_safe(file_path)


def _secure_write(file_path: Path, content: str) -> None:
    """파일에 내용을 통째로 덮어쓴다. 생성 시 0o600 권한 보장."""
    # 보안: TOCTOU 심볼릭 링크 취약점 사전 차단
    if file_path.is_symlink():
        raise OSError(f"Refusing to write to symlink: {file_path}")

    # os.open으로 생성과 권한(0o600) 설정을 원자적으로 수행하고,
    # 기존 파일이면 잘라쓴다(truncate).
    fd = _open_fd_safely(file_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        _ensure_regular_file(fd, file_path)
        _force_private_mode(fd)
        f = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        f.write(content)
    # 기존 파일이었던 경우를 위해 권한 재확인
    _fchmod_safe(file_path)


def _secure_read(file_path: Path) -> str:
    """파일을 안전하게 읽는다. 일반 파일 확인 + 심볼릭 링크 거부 + 10MB 제한."""
    if file_path.is_symlink():
        raise OSError(f"Refusing to read from symlink: {file_path}")

    fd = _open_fd_safely(file_path, os.O_RDONLY, None)
    try:
        _ensure_regular_file(fd, file_path)

        # 메모리 고갈 방지를 위한 크기 제한
        st = os.fstat(fd)
        if st.st_size > 10_000_000:
            raise OSError(f"'{file_path}' is too large (max 10MB)")

        f = os.fdopen(fd, "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with f:
        return f.read()


def _ensure_storage() -> None:
    """저장 디렉터리와 기본 파일이 올바른 권한으로 존재함을 보장.

    프로세스당 1회만 실행되며(`_STORAGE_ENSURED` 플래그),
    이후 호출은 즉시 반환되므로 호출 비용이 없다.

    권한 정책: 디렉터리 0o700(rwx------), 파일 0o600(rw-------).
    """
    global _STORAGE_ENSURED
    if _STORAGE_ENSURED:
        return

    # 중간 디렉터리는 기본 권한으로 만들고, 저장 디렉터리만 명시적으로
    # 0o700을 적용한다 (공유 상위 디렉터리를 함부로 제한하지 않기 위함).
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    _fchmod_safe(STORAGE_DIR, mode=0o700, is_dir=True)

    for file_path, default_content in [
        (RESULTS_FILE, ""),  # 빈 JSONL
        (CONFIG_FILE, "{}"),  # 빈 JSON 객체
    ]:
        if not file_path.exists():
            try:
                # 보안: 생성 전에도 심볼릭 링크 여부를 확인
                if file_path.is_symlink():
                    raise OSError(f"Refusing to write to symlink: {file_path}")

                # 보안: os.open + O_EXCL 로 "없을 때만 생성"을 원자적으로 보장.
                # exists() 검사와 생성 사이 다른 프로세스가 만들어도 안전.
                fd = _open_fd_safely(
                    file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                try:
                    # 보안: 열린 fd에 직접 권한 적용 (TOCTOU 방지)
                    if hasattr(os, "fchmod") and hasattr(os, "fstat"):
                        st = os.fstat(fd)
                        if (st.st_mode & 0o777) != 0o600:
                            os.fchmod(fd, 0o600)
                    f = os.fdopen(fd, "w", encoding="utf-8")
                except BaseException:
                    os.close(fd)
                    raise
                with f:
                    f.write(default_content)
            except FileExistsError:
                # exists() 검사와 os.open 사이에 파일이 생긴 경우 — 무시
                pass

        # 기존 파일이었던 경우에도 권한이 올바른지 확인
        _fchmod_safe(file_path)

    _STORAGE_ENSURED = True


# ── 결과(CRUD) 공개 API ─────────────────────────────────────────────


def save_result(result: TypingResult) -> None:
    """결과 1건을 로컬 저장소에 추가한다.

    성능: 전체 파일 재작성 대신 JSONL 한 줄만 append 하므로 O(1).
    안전: 디스크 쓰기가 **성공한 후에** 메모리 캐시를 갱신한다.
    """
    global _RESULTS_CACHE
    _ensure_storage()
    results = load_results().copy()
    if not result.date:
        result.date = datetime.now(timezone.utc).isoformat()

    # O(1) append; 쓰기가 성공한 뒤에만 캐시를 갱신한다
    jsonl_line = json.dumps(result.to_dict(), ensure_ascii=False) + "\n"
    _secure_append(RESULTS_FILE, jsonl_line)

    results.append(result)
    _RESULTS_CACHE = results


def load_results() -> list[TypingResult]:
    """저장된 모든 타자 결과를 반환한다 (최초 1회만 디스크에서 읽음).

    - 이후 호출은 전역 캐시를 그대로 돌려주므로 O(1)이다.
    - 구버전 JSON 배열 형식이 발견되면 읽는 즉시 JSONL로 변환해 저장한다.
    - 손상된 줄은 건너뛰고 읽을 수 있는 것만 반환한다.
    """
    global _RESULTS_CACHE
    if _RESULTS_CACHE is not None:
        return _RESULTS_CACHE

    _ensure_storage()
    try:
        text = _secure_read(RESULTS_FILE).strip()
        if not text:
            _RESULTS_CACHE = []
            return _RESULTS_CACHE

        # ── 구버전(JSON 배열) 형식 마이그레이션 ──
        if text.startswith("[") and text.endswith("]"):
            try:
                data = json.loads(text)
                if not isinstance(data, list):
                    _RESULTS_CACHE = []
                    return _RESULTS_CACHE
                _RESULTS_CACHE = [
                    TypingResult.from_dict(r) for r in data if isinstance(r, dict)
                ]
                # 즉시 JSONL 형식으로 변환해 다시 저장한다
                jsonl_data = "\n".join(
                    json.dumps(r.to_dict(), ensure_ascii=False) for r in _RESULTS_CACHE
                )
                _secure_write(RESULTS_FILE, jsonl_data + "\n" if jsonl_data else "")
                return _RESULTS_CACHE
            except (json.JSONDecodeError, ValueError, TypeError):
                _RESULTS_CACHE = []
                return _RESULTS_CACHE

        # ── 현재 형식: JSON Lines (줄당 결과 1개) ──
        results = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    results.append(TypingResult.from_dict(data))
            except (json.JSONDecodeError, ValueError, TypeError):
                # 손상된 한 줄은 무시하고 계속 (다른 기록은 살려야 함)
                continue

        _RESULTS_CACHE = results
        return _RESULTS_CACHE
    except OSError:
        # 파일이 없거나 읽기 실패 시 빈 목록으로 시작 (앱 크래시 방지)
        _RESULTS_CACHE = []
        return _RESULTS_CACHE


def clear_results() -> None:
    """저장된 모든 타자 결과를 삭제한다."""
    global _RESULTS_CACHE
    _ensure_storage()
    try:
        _secure_write(RESULTS_FILE, "")
        _RESULTS_CACHE = []
    except OSError:
        pass


def delete_result_by_index(index: int) -> None:
    """저장 목록에서 *index* 위치의 결과 1건을 삭제한다.

    안전: 복사본에서 삭제 후 디스크에 먼저 반영하고,
    쓰기가 성공했을 때만 전역 캐시를 교체한다.
    (쓰기 실패가 일어나도 메모리 상태가 디스크와 어긋나지 않음)
    """
    global _RESULTS_CACHE
    results = load_results().copy()
    if 0 <= index < len(results):
        results.pop(index)
        jsonl_data = "\n".join(
            json.dumps(r.to_dict(), ensure_ascii=False) for r in results
        )
        _secure_write(RESULTS_FILE, jsonl_data + "\n" if jsonl_data else "")
        _RESULTS_CACHE = results


# ── 설정 공개 API ───────────────────────────────────────────────────


def save_config(config: dict[str, Any]) -> None:
    """사용자 설정을 로컬 저장소에 저장한다."""
    global _CONFIG_CACHE
    _ensure_storage()
    _secure_write(CONFIG_FILE, json.dumps(config, indent=2, ensure_ascii=False))
    _CONFIG_CACHE = config


def load_config() -> dict[str, Any]:
    """사용자 설정을 읽어온다 (최초 1회 디스크 접근, 이후 캐시)."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    _ensure_storage()
    try:
        text = _secure_read(CONFIG_FILE)
        data = json.loads(text)
        if not isinstance(data, dict):
            _CONFIG_CACHE = {}
            return {}
        _CONFIG_CACHE = data
        return _CONFIG_CACHE
    except (json.JSONDecodeError, OSError):
        _CONFIG_CACHE = {}
        return {}


# ── 통계/내보내기 유틸리티 ──────────────────────────────────────────


def load_error_stats() -> dict[str, int]:
    """모든 기록에 걸쳐 글자별 누적 오류 횟수를 집계해 반환.

    Returns a dict mapping char -> total error count across all sessions.
    취약점 분석 화면(WeaknessScreen)의 데이터 소스로 쓰인다.
    """
    results = load_results()
    totals: dict[str, int] = {}
    for result in results:
        for char, count in result.top_char_errors:
            totals[char] = totals.get(char, 0) + count
    return totals


def get_personal_best(lang: str, exclude_date: str | None = None) -> float:
    """특정 언어에서 기록한 최고 WPM을 반환한다.

    *exclude_date*와 timestamp가 정확히 같은 기록은 제외한다.
    방금 끝낸 세션을 과거 기록과 비교할 때 자기 자신이 최고 기록으로
    잡히지 않도록 하는 용도다.
    """
    best = 0.0
    for r in load_results():
        if r.lang != lang:
            continue
        if exclude_date is not None and r.date == exclude_date:
            continue
        best = max(best, r.wpm)
    return best


def export_results_csv(path: Path) -> int:
    """모든 결과를 CSV 파일로 내보낸다. 기록한 행 수를 반환."""
    results = load_results()
    if not results:
        return 0

    buf = io.StringIO()
    fieldnames = list(TypingResult.__dataclass_fields__)
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for result in results:
        row = result.to_dict()
        # 리스트/딕셔너리 셀은 CSV에 넣을 수 있으므로 압축 JSON 문자열로 직렬화
        for key, value in row.items():
            if isinstance(value, (list, dict)):
                row[key] = json.dumps(value, ensure_ascii=False)
        writer.writerow(row)

    _ensure_storage()
    _secure_write(path, buf.getvalue())
    return len(results)


def export_results_json(path: Path) -> int:
    """모든 결과를 JSON 배열 파일로 내보낸다. 내보낸 항목 수를 반환."""
    results = load_results()
    if not results:
        return 0

    text = json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)
    _ensure_storage()
    _secure_write(path, text)
    return len(results)
