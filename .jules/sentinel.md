## 2024-05-24 - Unnecessary Sub-directory permissions vulnerability in Storage
**Vulnerability:** Weak permissions for .ttyping/ configuration storage
**Learning:** `storage.py` set directory permissions with 0o700, but Python's `Path.mkdir(parents=True)` without additional handling only applies mode to the *last* created directory. Intermediate directories are created with default umask permissions, which could be less restrictive.
**Prevention:** In this application, `.ttyping` is created in the user's home directory. Intermediate directories aren't created (since `~` already exists), but when doing directory permission operations, ensure the permissions on any implicitly created intermediate directories are also correct or handled, or just use `exist_ok=True` without relying on parents=True where possible, or use explicit modes.

## 2024-05-24 - `os.umask(0o077)` is not thread safe
**Vulnerability:** Modifying the global process umask with `os.umask(0o077)` during initialization can lead to race conditions where other threads might create files with unintended permissions during that tiny window.
**Learning:** Even with try-finally, changing process state like umask is unsafe in a multithreaded application.
**Prevention:** Where possible, use the `mode` parameter of `open()` or `os.open()` with `os.O_CREAT | os.O_EXCL` rather than modifying the process `umask`, or set the umask once at application startup.

## 2024-05-24 - TOCTOU vulnerability via Symlinks in `chmod`
**Vulnerability:** `_ensure_storage` in `src/ttyping/storage.py` used `chmod` to enforce restrictive permissions on config and result files without first verifying if the paths were symlinks.
**Learning:** `chmod` inherently follows symlinks on Linux/Unix systems. If an attacker replaces a file with a symlink before the application calls `chmod`, the target of the symlink (e.g., an important system file) will have its permissions changed unexpectedly. This is a classic Time-of-Check to Time-of-Use (TOCTOU) vulnerability. Since `os.chmod(..., follow_symlinks=False)` is not supported on all platforms (like Linux), the application must manually check for symlinks.
**Prevention:** Always verify `if not Path.is_symlink():` before applying `chmod` to ensure that you are only altering the permissions of the actual file you intend to protect, and not inadvertently following an attacker-controlled symlink.
