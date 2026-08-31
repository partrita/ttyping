# Project Instructions (for AI Agents)

## Language Rule — Always Use ASD-STE100
- Always write all agent-facing text in ASD-STE100 Simplified Technical English.
- Use short sentences. Use approved words. Avoid ambiguity.
- Do not use idioms. Do not use long nouns. Do not use passive voice unless needed.
- Apply this rule to: comments, commit messages, pull request descriptions, documentation, and chat replies.


## Project Overview

`ttyping` provides a clean and focused typing practice environment directly in the terminal. It tracks speed (WPM) and accuracy, saving results locally for history viewing. A minimal, monkeytype-inspired terminal typing test for English and Korean, built with Python and Textual.

### Tech Stack
- Language: Python 3.10+
- TUI Framework: [Textual](https://github.com/Textualize/textual)
- Styling/Formatting: [Rich](https://github.com/Textualize/rich)
- Dependency Management: [uv](https://github.com/astral-sh/uv)
- Build System: Hatchling

### Core Architecture
- `src/ttyping/__main__.py`: CLI entry point. Handles argument parsing (`argparse`).
- `src/ttyping/app.py`: The main `TypingApp` class. Manages the screen stack and application-level state.
- `src/ttyping/screens.py`: Contains the UI logic:
    - `MenuScreen`: Main menu to select typing modes (English/Korean/Weak Analysis) and options.
    - `TypingScreen`: The interactive typing test.
    - `ResultScreen`: Summary shown after a test completes.
    - `HistoryScreen`: A table view of past results.
- `src/ttyping/storage.py`: Handles persistent storage of results in `~/.ttyping/results.json`.
- `src/ttyping/words.py`: Provides internal word lists (English/Korean) and file reading capabilities.

## Building and Running

### Development Commands
- Run the app: `uv run ttyping`
- Run with specific options:
    - Korean: `uv run ttyping --lang ko`
    - Custom word count: `uv run ttyping --words 50`
    - Practice from file: `uv run ttyping --file path/to/text.txt`
    - View history: `uv run ttyping history`

### Installation
- Local editable install: `uv pip install -e .`
- Install as a tool: `uv tool install .`

## Development Conventions

### Coding Style
- Uses modern Python features (type hints, `from __future__ import annotations`).
- UI styling is defined via Textual's CSS-like `DEFAULT_CSS` in screen classes or `TypingApp.CSS`.
- Monkeytype-inspired color palette is defined as constants in `screens.py`.

## Design Philosophy: Minimalist Typing Experience (미니멀 타자 연습)

`ttyping`의 핵심 정체성은 **터미널 환경에서의 미니멀하고 몰입감 있는 타자 연습 경험(Minimalist & Focused Typing Experience)** 입니다. Monkeytype의 철학을 계승하여 불필요한 UI 장식과 복잡성을 배제하고 타이핑 본연의 집중과 반응성에 초점을 맞춥니다.

- **극도의 집중 (Distraction-Free UI)**: 화면을 복잡하게 만드는 불필요한 테두리, 지나치게 화려한 애니메이션, 복잡한 메뉴 계층을 지양하고 타이핑할 텍스트와 핵심 피드백(WPM, 정확도, 오타 표시)에만 시각적 무게를 둡니다. 특히 타이핑 도중 실시간 그래프/차트가 노출되는 것은 미니멀한 몰입을 방해하므로 엄격히 금지합니다.
- **키보드 중심 인터랙션 (Keyboard-First Flow)**: 마우스 조작 없이 모든 내비게이션(단일 키 숏컷 `e`, `k`, `p`, `w`, `z`, `d`, `h`, `o`, `q` 및 한글 2벌식 매핑), 재시작(`Tab`), 단어 삭제(`Ctrl+W`), 뒤로 가기(`Esc`)를 손가락의 자연스러운 흐름 안에서 완결합니다.
- **빠른 피드백 & 경량성 (Instant Feedback & Low Latency)**: 입력 지연 없는 타건감, 뷰포트 기반 O(N) 렌더링 최적화로 가볍고 빠른 반응 속도를 유지합니다.
- **로컬 우선 & 개인정보 보호 (Local-First)**: 외부 서버 연동이나 로그인 없이 로컬 파일(`~/.ttyping/results.json`)을 기반으로 동작하여 오프라인에서도 즉시 실행 가능합니다.

### UI/UX Rules
- **미니멀 타이핑 화면 원칙 (No Live Graphs During Typing)**: 타이핑 진행 화면(`TypingScreen`)에는 오직 상단 핵심 텍스트 통계(WPM/정확도/진행도), 텍스트 디스플레이, 입력 필드만 유지하며 실시간 그래프 등 시각적 노이즈를 유발하는 위젯을 추가하지 않습니다.
- **미니멀 히스토리 화면 레이아웃 원칙 (Clean History View & Centered 3-Tier Layout)**: 
  - 기록 화면(`HistoryScreen`)에서 부정확하고 불필요한 WPM/Accuracy 트렌드 그래프 위젯과 잉여 텍스트 통계(Tests 수, Avg WPM)를 배제합니다.
  - 화면 중앙에 위에서부터 아래로 다음 3개 요소를 차례대로 정렬합니다:
    1. **목표 WPM 프로그레스 바 (`ProgressBar`)**: 가운데 맞춤(`align: center middle`, `max-width: 60`), 평균 WPM 달성율 표시.
    2. **조작 안내 텍스트 (`Static`)**: `Press d to delete selected record · D to delete all · Esc to back` (표 위에 중앙 정렬).
    3. **상세 데이터 테이블 (`DataTable`)**: 최근 50회 기록 상세 표.
- **미니멀 취약점 분석 화면 원칙 (Clean Weakness View & No Graphs/Heatmaps)**: 취약점 분석 화면(`WeaknessScreen`)에서 불필요한 막대 차트(`Top Missed Keys`)와 키보드 히트맵(`Keyboard Heatmap`)을 배제하고, 손가락별 취약점 연습 메뉴(`OptionList`) 및 직관적인 오류 통계 표(`DataTable`)에만 집중합니다.
- **기본 테마 & 컬러 팔레트 원칙 (Strict Serika & Serika Dark Color Palette)**: 
  - Monkeytype의 시그니처 테마를 표준으로 채택하며, Textual 기본의 푸른빛 틴트 및 파란색 위젯 스타일을 전면 배제합니다.
  - **다크 모드 (`Serika Dark`)**: Background `#323437`, Sub-Background `#2c2e31`, Text `#d1d0c5`, Dim/Sub `#646669`, Accent `#e2b714`, Error `#ca4754`.
  - **라이트 모드 (`Serika`)**: Background `#e1e1e3`, Sub-Background `#d1d0c5`, Text `#323437`, Dim/Sub `#646669`, Accent `#e2b714`, Error `#ca4754`.
  - **위젯 악센트 & 스크롤바 일관성**:
    - 모든 `OptionList` 선택/하이라이트, `DataTable` 커서, `ProgressBar`, `Input` 포커스 테두리는 `#e2b714` (Serika Yellow)로 통일합니다.
    - 모든 컨테이너/입력창/테이블의 기본 테두리는 차분한 `#646669`를 사용합니다.
    - 스크롤바(`ScrollBar`, `DataTable` 스크롤바)는 배경을 테마 서브 컬러로, 썸(Thumb)을 `#646669`, 호버 및 활성 색상을 `#e2b714`로 지정하여 푸른색 잔재를 허용하지 않습니다.
- **미니멀 결과 화면 원칙 (Clean Result View)**: 결과 화면(`ResultScreen`)에서 `top missed characters`, 불필요한 PB(Personal Best) 팝업/뱃지, 일관성(`cons`) 등의 과도한 통계 노이즈를 노출하지 않고 WPM, 정확도, 소요 시간, 타자 단어 수, 언어 등 핵심 지표만 간결하게 표시합니다.
- **미니멀 모드 원칙 (No Zen/Daily/Endless Mode Overload)**: 불필요한 무한 스트리밍 Zen 모드 및 부가적인 데일리 챌린지 모드를 배제하고, 언어/단어 수/시간 기반의 표준 연습 세션에 집중합니다.
- **미니멀 설정 원칙 (No Sound & Custom Keybinding Overload)**: 청각적 노이즈를 유발하는 사운드/벨 옵션 및 불필요한 단축키 매핑 변경 기능을 제공하지 않으며, 직관적이고 표준적인 기본 키바인딩(`Tab`, `Esc`, `Space`, `Ctrl+W`)만을 제공합니다.
- **미니멀 메뉴 원칙 (No Redundant Quit Option in Menu)**: 메인 메뉴의 `OptionList`에 별도의 `Quit [q]` 항목을 두지 않습니다. 프로그램 종료는 전역 키보드 단축키(`Esc`, `q`, `ㅂ`)를 통해 직관적으로 처리합니다.
- **미니멀 UI 푸터 원칙 (No Textual Footer Widget)**: 화면 하단에 고정된 Textual `Footer` 위젯을 일절 사용하지 않습니다. 하단 푸터 바는 시각적 집중을 분산시키므로, 모든 필수 단축키 안내는 메뉴 항목 내 인라인 태그(`[dim][key][/dim]`) 또는 화면 내 안내 텍스트로만 제공합니다.
- Main Menu Shortcuts: `e` (English), `k` (Korean), `p` (Code), `w` (Weak Analysis), `h` (History), `o` (Options), `Esc`/`q` (Quit) and their 2-set Korean equivalents (`ㄷ`, `ㅏ`, `ㅔ`, `ㅈ`, `ㅗ`, `ㅐ`, `ㅂ`).
- Tab: Restart the test.
- Esc: Quit the application / go back to the previous screen.
- Space: Proceed to the next word.
- Results are calculated based on characters per minute (CPM / 5) for WPM and character-level accuracy.

### Data Storage
- Data is stored in JSON format at `~/.ttyping/results.json`.
- Each result entry includes `wpm`, `accuracy`, `lang`, `word_count`, and an ISO-formatted `date`.

## Bolt

### 2026-03-07 - O(N) Render Optimization in Textual App
**Learning:** Generating Textual/Rich `Text` objects for ALL words on every keystroke causes significant overhead in UI rendering.
**Action:** When rendering a viewport of text, compute line wraps via string lengths/indices first, and ONLY generate `Text` objects for the lines actually visible on screen.

### Performance Optimization (ttyping/screens.py)
**What**: Cached `#stats` Static widget (`self._stats_widget`) on `TypingScreen.on_mount` instead of calling `self.query_one("#stats", Static)` directly on every invocation of `_update_stats`.
**Why**: `_update_stats` is called very frequently (both via a fast 0.5s timer and repeatedly on every keystroke/completion). The Textual `query_one` method searches the DOM, adding overhead. Storing the reference locally allows bypassing this DOM traversal completely.
**Measured Improvement**: Baseline `_update_stats` benchmark processed 1k calls in ~0.0136s. Using a cached widget processed 1k calls in ~0.0122s, a roughly 1.11x speedup. While small in absolute terms per call, this is a hot path for key interactions, saving CPU cycles and garbage collection overhead during tight loops.

#### Mocking module imports

When mocking imports, it's important to understand how they were imported in the source file. If a file `src/my_module/utils.py` does:

```python
from importlib import resources

def load_file():
    resources.files("my_module.data")
```

The correct target to patch is `"my_module.utils.resources.files"` not `"my_module.utils.files"`. Patching `"importlib.resources.files"` also wouldn't affect the specific `resources.files` reference initialized within the scope of the file executing.

## Palette

### 2026-03-07 - Add Keyboard Shortcuts to Main Menu
**Learning:** Terminal TUIs with arrow-key-only navigation can be tedious. Users benefit immensely from single-key shortcuts (`E`, `K`, `W`, `H`, `O`, `Q`) combined with clear label hints.
**Action:** Always consider `BINDINGS` for main OptionLists in Textual to provide immediate, accessible navigation.

### 2026-03-09 - Terminal Input Validation UX
**Learning:** Input fields in TUI frameworks often suffer from persistent error states if not actively cleared. Using native constraints like `type="integer"` with active `on_input_changed` error-clearing prevents users from seeing stale error messages while correcting input.
**Action:** When implementing numeric inputs in TUIs, use strict typing (`type="integer"`) and clear validation errors immediately on subsequent keystrokes (`on_input_changed`).

### 2026-03-14 - Textual OptionList Keyboard Shortcuts
**Learning:** In Textual UI, assigning `BINDINGS` with `show=False` prevents shortcut discoverability. Aligning `[dim][key][/dim]` tags directly inside `OptionList` items via Rich markup is an accessible, elegant pattern to reveal them without cluttering the bottom Footer widget.
**Action:** Use `Text.from_markup` with `[dim]` tags to neatly inline key hints for all Textual `OptionList`s.

### 2026-03-21 - Destructive Action Keyboard Hints
**Learning:** For destructive actions (like deleting all history), users often hesitate when they don't see clear, immediate instructions on how to confirm or abort the action. Visual hints reinforce confidence.
**Action:** In Textual TUIs, explicitly display keyboard hints for destructive or critical actions (e.g., pressing 'y' or 'n' to confirm deletion) using visual text elements like `Static` with Rich markup to prevent user hesitation and ensure accessibility.

### 2024-05-23 - Inline Keybindings for Discoverability
**Learning:** Hidden keybindings in TUIs are often missed by users because they aren't visible in the footer or the UI.
**Action:** Inline keyboard shortcuts directly into option labels using rich markup (e.g., `[dim]\[key][/dim]`) to improve discoverability while keeping the UI clean.

## Sentinel

### 2025-02-26 - Prevent Application Crash from Malformed Int Casts during Initialization
**Vulnerability:** Similar to the target_accuracy casting vulnerability, `word_count` and `duration` fields in `config.json` were cast or evaluated unsafely during initialization. If a malicious or corrupted `config.json` provided string values like `"not an int"` for these numeric fields, accessing `_get_words()` or running the app would trigger a `TypeError` due to math operations or type mismatches (e.g., trying to interpret a string as an integer size for random sampling), leading to an immediate crash (Local DoS). More importantly, there was no range enforcement for these inputs from `config.json`, allowing a malicious file to set `word_count = 1000000`, causing immediate Memory Exhaustion/Local DoS when `random.choices` generates the practice set.
**Learning:** Type enforcement must be rigorous across all dynamic properties read from user configuration. Relying on default fallbacks via `dict.get("key", default)` does not protect against explicitly provided but incorrectly typed values (e.g. `{"word_count": "invalid"}`). Validating the type is insufficient; applications must also clamp integers to safe limits.
**Prevention:** Explicitly cast numerical config fields (`word_count`, `duration`) with `int()` inside a `try...except (ValueError, TypeError):` block, and fall back to safe default values when casting fails. Finally, clamp the values to sensible bounds (e.g., `max(1, min(val, 1000))`) before storing them as instance properties.

### 2025-02-26 - Prevent App Crash from Malformed Results JSON Data
**Vulnerability:** In `src/ttyping/storage.py`, `TypingResult.from_dict` parsed data directly without handling explicit type casting errors on nested json items (e.g. `ValueError` on `int("abc")` or `TypeError` on `float(None)` if users tampered with `.ttyping/results.json`). This crash behavior would break application loading resulting in DoS.
**Learning:** Similarly to the configuration file, parsing stored data fields requires defensive type casting using `try...except (ValueError, TypeError):` in order to gracefully handle malformed data rather than propagating exceptions up and crashing the entire application.
**Prevention:** Wrap type casting in `from_dict` with `try...except` and provide a fallback default or ignore the malformed item.

### 2025-02-26 - Prevent Application Crash from Malformed Nested JSON Data
**Vulnerability:** Similar to other missing type/shape checks when parsing `results.json`, `TypingResult.from_dict` extracted nested list properties (`top_char_errors` and `char_timings`) without verifying that the contained items actually matched the expected shapes (e.g. nested lists of size 2, or dicts). If a user tampered with `results.json` and inserted objects like `["a", "not_an_int"]` into `top_char_errors`, it would silently pass deserialization but cause a hard `TypeError` crash later when properties like `count` were accessed or used in math operations inside features like `load_error_stats()`. This results in a Local Denial of Service.
**Learning:** Defensive deserialization requires not just shallow type casting of primitives, but also deep structural validation of nested collections. If a complex object is expected, the code must actively verify its structure (e.g. `isinstance(item, (list, tuple)) and len(item) == 2`) and types before storing it in application memory.
**Prevention:** In `from_dict` methods, iterate over incoming collections. Wrap element unpacking and type-casting inside `try...except (ValueError, TypeError):` blocks and drop or skip malformed elements, ensuring only valid structured data propagates into the application.

### 2025-02-26 - Prevent App Crash from Malformed Nested char_timings Items
**Vulnerability:** The application was vulnerable to Local DoS because `TypingResult.from_dict` extracted the `char_timings` list from stored JSON and verified elements were dictionaries, but did not type cast or validate the inner dictionary values (like `time`). A tampered `results.json` containing string values for `time` passed deserialization but crashed the app with a `TypeError` when `ResultScreen._render_speed_map` attempted subtraction operations on the strings.
**Learning:** Deep structural validation of nested collections is insufficient if the inner dictionary values are not explicitly type-cast and validated. It is essential to proactively cast items nested inside dictionaries before using them in numeric contexts.
**Prevention:** Iterate through collections of dictionaries and wrap value casting inside `try...except (ValueError, TypeError):` blocks, skipping elements whose internal values cannot be safely cast to the expected type.

### 2025-02-26 - Prevent Application Crash from Rich Markup Injection
**Vulnerability:** In `src/ttyping/screens.py`, `ResultScreen` took `top_char_errors` directly from `results.json` and rendered it into a `Static` widget by calling `Static(str(err_dict))`. If a malicious or tampered `results.json` file contained specific bracket tags like `[/]`, the Rich text engine attempted to parse it as formatting markup. Since it wasn't valid or matched markup, the underlying `rich.markup` parser threw a `MarkupError`, crashing the entire UI and resulting in a Local Denial of Service.
**Learning:** Any dynamic string (especially those read from local storage or user configuration) passed to Rich or Textual rendering widgets must be treated as untrusted input. The default behavior of these widgets is to interpret bracketed strings as markup.
**Prevention:** Always sanitize dynamically loaded or untrusted display strings by explicitly escaping them using `rich.markup.escape()` before rendering them in Textual UI components (e.g. `Static(escape(str(err_dict)))`).

### 2025-02-27 - Remove Security Theater (secrets vs random)
**Vulnerability:** The application was using `secrets.SystemRandom()` to shuffle and sample words for typing practice. While this is cryptographically secure, it is significantly slower than the standard `random` module. Using cryptographic primitives for non-security tasks (like typing test words) is "security theater" and introduces unnecessary performance regressions.
**Learning:** Only use `secrets` or cryptographically secure pseudorandom number generators (CSPRNG) for actual security purposes (e.g., tokens, passwords, cryptography). For general-purpose shuffling or non-security sampling, standard PRNGs like `random` are preferred for their speed.
**Prevention:** Replaced `secrets.SystemRandom()` with `random` in `src/ttyping/words.py` where word sampling and shuffling occurs.

### 2025-02-27 - Prevent Path Traversal in words_from_file
**Vulnerability:** The application read words from a file path provided by the user using `--file` without restricting access to the current directory. This could allow for path traversal attacks, where a user could read sensitive files on the system outside the application directory.
**Learning:** It is crucial to restrict file reading to specific allowed directories, particularly when user input specifies the file path. The application requires only reading words from files in the current working directory.
**Prevention:** In `src/ttyping/words.py`, `words_from_file` restricts file reading to the current working directory by taking the `os.path.basename` of the provided file path, enforcing path traversal prevention.

### 2025-02-27 - Prevent Application Crash from Rich Markup Injection
**Vulnerability:** In `src/ttyping/screens.py`, `WordCountMenu` instantiated the menu title by taking `config["lang"]` directly from `config.json` and rendered it into a `Static` widget by calling `Static(f"{self.layout_id.upper()}")`. If a malicious or tampered `config.json` file contained specific bracket tags like `[red]`, the Rich text engine attempted to parse it as formatting markup. Since it wasn't valid or matched markup, the underlying `rich.markup` parser threw a `MarkupError`, crashing the entire UI and resulting in a Local Denial of Service.
**Learning:** Any dynamic string (especially those read from local storage or user configuration) passed to Rich or Textual rendering widgets must be treated as untrusted input. The default behavior of these widgets is to interpret bracketed strings as markup.
**Prevention:** Always sanitize dynamically loaded or untrusted display strings by explicitly escaping them using `rich.markup.escape()` before rendering them in Textual UI components (e.g. `Static(escape(str(err_dict)))`).

### 2025-02-27 - Prevent Application Crash from Rich Markup Injection in OptionList
**Vulnerability:** In `src/ttyping/screens.py`, `WeaknessScreen` rendered untrusted user input directly into an `OptionList` without escaping. A malformed history file (`results.json`) containing Rich markup tags like `[/]` would cause the `rich.markup` parser to throw a `MarkupError` when rendering the `Option` label, resulting in a Local DoS.
**Learning:** Untrusted dynamic strings must be escaped in all Textual components that render text, not just `Static` or `DataTable` widgets. `OptionList` labels are also parsed by the Rich markup engine and are vulnerable to injection.
**Prevention:** Added `escape()` calls around the formatted strings inside the `Option()` constructor in `WeaknessScreen.compose()`.

### 2025-02-27 - Prevent Application Crash from Rich Markup Injection in Practice Menu
**Vulnerability:** In src/ttyping/screens.py, PracticeMenu rendered the menu title into a Static widget without escaping. Although the titles are currently hardcoded strings, failing to escape them poses a risk if they were to become dynamic or include markup-like sequences (e.g., [/]), which would cause the Rich markup parser to throw a MarkupError and crash the UI.
**Learning:** Any dynamic string (especially those based on configuration or layout IDs) passed to Rich or Textual rendering widgets must be treated as untrusted input. The default behavior of these widgets is to interpret bracketed strings as markup.
**Prevention:** Always sanitize dynamically loaded or untrusted display strings by explicitly escaping them using `rich.markup.escape()` before rendering them in Textual UI components (e.g. `Static(escape(title))`).

### 2024-05-12 - Prevent Application Crash from Rich Markup Injection in OptionsScreen and Static Menus
**Vulnerability:** In `src/ttyping/screens.py`, `OptionsScreen`, `TargetAccuracyMenu`, and `ThemeScreen` rendered untrusted or potentially malformed user input directly into an `OptionList` or `Static` widget without escaping. A malformed configuration file (`config.json`) containing Rich markup tags like `[/]` in fields like `lang` or numbers could cause the `rich.markup` parser to throw a `MarkupError` when rendering the UI, resulting in a Local DoS.
**Learning:** Any dynamic string (especially those read from local storage or user configuration) passed to Rich or Textual rendering widgets must be treated as untrusted input. The default behavior of these widgets is to interpret bracketed strings as markup.
**Prevention:** Always sanitize dynamically loaded or untrusted display strings by explicitly escaping them using `rich.markup.escape()` before rendering them in Textual UI components (e.g. `Static(escape(title))` or `Option(escape(label))`).

### 2025-02-27 - Prevent Application Crash from Malformed Config Strings
**Vulnerability:** In `src/ttyping/app.py`, `TypingApp.__init__` assigned string properties like `self._lang` and `self._file_path` directly from `config.json` without verifying the value's type. If a user manually tampered with `.ttyping/config.json` and inserted an integer (e.g., `"lang": 123`), the application loaded the config but crashed with an `AttributeError` during `TypingScreen` initialization when string methods like `.startswith()` were called. This resulted in a Local Denial of Service.
**Learning:** Defensive deserialization must extend beyond numbers and complex objects to simple string configuration fields. Code cannot assume that values retrieved from untrusted JSON storage are implicitly of the expected string type.
**Prevention:** Cast extracted simple configuration values to `str()` inside a `try...except (ValueError, TypeError)` block. Explicitly check `isinstance(saved_val, str)` to prevent complex structures (like dicts or lists) from silently bypassing the validation by being cast to their string representations.

### 2025-02-27 - Prevent Unexpected Behavior from Malformed Theme Config Type
**Vulnerability:** The application read the `"theme"` value from `config.json` without verifying its type before performing string operations (specifically `== "dark"`). While not an exploitable vulnerability, if a user manually tampered with the config file to set the theme to an integer or complex object (e.g., `123`), the equality check would evaluate to `False` and incorrectly apply the light theme fallback rather than preserving default behavior, indicating weak defensive parsing.
**Learning:** Defensive deserialization must validate the type of *every* untrusted configuration value, including simple string fields like "theme", before performing string comparisons or operations, to avoid logic errors or unintentional behavior.
**Prevention:** Cast extracted simple configuration values to `str()` or explicitly check `isinstance(saved_val, str)` to ensure the expected fallback behavior when untrusted config fields contain incorrect types.

### 2024-05-24 - Strict Validation of Nested JSON Collections
**Vulnerability:** Malformed `char_timings` entries from local storage without required keys (`time`, `char`) were blindly loaded, leading to `KeyError` crashes (Local DoS) when the UI accessed those missing keys.
**Learning:** During JSON deserialization, partial validation (checking type or a single key) isn't enough. All accessed properties must be verified or explicitly try/except handled to ensure data safety.
**Prevention:** Strictly enforce required keys (`in` checks) and type-cast dynamically loaded properties within a protective `try...except` block, discarding malformed objects.

### 2025-02-27 - Prevent Data Corruption on File Write Failure
**Vulnerability:** The application was modifying the global `_RESULTS_CACHE` in-place using `.pop(index)` in `delete_result_by_index` before executing the `_secure_write` operation. If `_secure_write` failed (e.g., due to an `OSError` such as disk full or permissions change), the in-memory state remained out of sync with the physical disk storage. This leads to data inconsistency and corruption within the session.
**Learning:** Operations that modify persistent storage must only update in-memory caching *after* the I/O operation is confirmed successful, or perform the operation on a decoupled copy.
**Prevention:** Modified `delete_result_by_index` to operate on `load_results().copy()`. This creates a temporary working list that is modified and serialized. The global `_RESULTS_CACHE` is only updated *after* the `_secure_write` completes successfully, maintaining data integrity.
