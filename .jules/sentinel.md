## 2024-05-14 - Intermediate Directory Permissions Vulnerability & Shared Path Architecture
**Vulnerability:** A vulnerability was identified during the execution of `STORAGE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)`. The `.mkdir()` function in `pathlib` only applies the specified mode to the *last* (leaf) directory created. If intermediate directories were also implicitly created, they would inherit the system's default umask permissions (often overly permissive like `0o755` or `0o777`), potentially exposing sensitive files in the application's configuration path structure.

## 2024-05-24 - `os.umask(0o077)` is not thread safe
**Vulnerability:** Modifying the global process umask with `os.umask(0o077)` during initialization can lead to race conditions where other threads might create files with unintended permissions during that tiny window.
**Learning:** Even with try-finally, changing process state like umask is unsafe in a multithreaded application.
**Prevention:** Where possible, use the `mode` parameter of `open()` or `os.open()` with `os.O_CREAT | os.O_EXCL` rather than modifying the process `umask`, or set the umask once at application startup.
## 2025-02-26 - Prevent Privilege Escalation via Symlink
**Vulnerability:** The application enforced restrictive permissions (chmod 0o700/0o600) on its config/results files without checking if the files were symlinks.
**Learning:** Calling `chmod` on a `Path` object follows symlinks on Linux by default. An attacker could replace `.ttyping/results.json` with a symlink to another user's file, tricking the application into modifying the target file's permissions, enabling a TOCTOU (Time-of-check to time-of-use) privilege escalation.
**Prevention:** Always verify `not path.is_symlink()` prior to invoking `.chmod()` to ensure modifications only apply to real files.
## 2025-02-26 - Unsafe File Creation Permissions via write_text
**Vulnerability:** The application was using `Path.write_text()` to write sensitive typing results and configurations to disk. If these files were deleted while the application was running, `write_text()` would recreate them with default umask permissions (e.g., `0o644`), bypassing the strict `0o600` permissions established at startup by `_ensure_storage()`.
**Learning:** `Path.write_text()` simply calls `open()` and inherits the user's default umask for new file creation. The initial permission setup using `chmod` is not sticky and does not apply to recreation events.
**Prevention:** Avoid `Path.write_text()` when writing files that require strict permissions. Use atomic file creation via `os.open` with explicit flags (`os.O_WRONLY | os.O_CREAT | os.O_TRUNC`) and the desired permission mode (e.g., `0o600`), then convert the file descriptor to a file object using `os.fdopen()`.
## 2025-02-26 - Prevent TOCTOU Symlink Vulnerability on File Creation
**Vulnerability:** The application used `os.open()` with `os.O_CREAT | os.O_TRUNC` to save result files. However, this does not prevent a Time-of-Check to Time-of-Use (TOCTOU) vulnerability where an attacker replaces the file with a symlink. When writing, it would follow the symlink and overwrite the target file.
**Learning:** `O_CREAT` combined with `O_TRUNC` follows symlinks. You must include `os.O_NOFOLLOW` in the flags for `os.open` (if available on the platform) to ensure the operation fails if the destination is a symlink. Additionally, a preemptive `.is_symlink()` check helps on platforms that don't support `O_NOFOLLOW`.
**Prevention:** Always use `os.O_NOFOLLOW` when securely opening or creating files, and add `if path.is_symlink(): raise OSError(...)` prior to `os.open()` for cross-platform robustness against symlink-based arbitrary file writes.

## 2025-05-14 - Fix TOCTOU vulnerability in file chmod
**Vulnerability:** TOCTOU (Time-of-Check Time-of-Use) in file permission setting.
**Learning:** Using path-based  after a file check or creation creates a race condition window where an attacker can replace the target with a symlink. The secure way to handle this on Unix-like systems is to use  and  on an open file descriptor.
**Prevention:** Always prefer descriptor-based operations (, ) over path-based ones when the file is already open. Use `os.O_NOFOLLOW` when opening existing files to prevent following symlinks.

## 2025-05-14 - Fix TOCTOU vulnerability in file chmod
**Vulnerability:** TOCTOU (Time-of-Check Time-of-Use) in file permission setting.
**Learning:** Using path-based `chmod` after a file check or creation creates a race condition window where an attacker can replace the target with a symlink. The secure way to handle this on Unix-like systems is to use `os.fchmod` and `os.fstat` on an open file descriptor.
**Prevention:** Always prefer descriptor-based operations (`fchmod`, `fstat`) over path-based ones when the file is already open. Use `os.O_NOFOLLOW` when opening existing files to prevent following symlinks.
