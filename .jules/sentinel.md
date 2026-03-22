## 2024-05-24 - Unnecessary Sub-directory permissions vulnerability in Storage
**Vulnerability:** Weak permissions for .ttyping/ configuration storage
**Learning:** `storage.py` set directory permissions with 0o700, but Python's `Path.mkdir(parents=True)` without additional handling only applies mode to the *last* created directory. Intermediate directories are created with default umask permissions, which could be less restrictive.
**Prevention:** In this application, `.ttyping` is created in the user's home directory. Intermediate directories aren't created (since `~` already exists), but when doing directory permission operations, ensure the permissions on any implicitly created intermediate directories are also correct or handled, or just use `exist_ok=True` without relying on parents=True where possible, or use explicit modes.

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
