## 2024-05-24 - Unnecessary Sub-directory permissions vulnerability in Storage
**Vulnerability:** Weak permissions for .ttyping/ configuration storage
**Learning:** `storage.py` set directory permissions with 0o700, but Python's `Path.mkdir(parents=True)` without additional handling only applies mode to the *last* created directory. Intermediate directories are created with default umask permissions, which could be less restrictive.
**Prevention:** In this application, `.ttyping` is created in the user's home directory. Intermediate directories aren't created (since `~` already exists), but when doing directory permission operations, ensure the permissions on any implicitly created intermediate directories are also correct or handled, or just use `exist_ok=True` without relying on parents=True where possible, or use explicit modes.

## 2024-05-24 - `os.umask(0o077)` is not thread safe
**Vulnerability:** Modifying the global process umask with `os.umask(0o077)` during initialization can lead to race conditions where other threads might create files with unintended permissions during that tiny window.
**Learning:** Even with try-finally, changing process state like umask is unsafe in a multithreaded application.
**Prevention:** Where possible, use the `mode` parameter of `open()` or `os.open()` with `os.O_CREAT | os.O_EXCL` rather than modifying the process `umask`, or set the umask once at application startup.

## 2023-10-27 - [TOCTOU Symlink Attack]
**Vulnerability:** Symlink attack allowing arbitrary file permission changes due to TOCTOU vulnerability in `chmod` usage.
**Learning:** Checking for file existence and then calling `chmod` allows an attacker to swap the file with a symlink between the two calls, causing the `chmod` operation to be applied to the symlink's target instead. This occurs because `os.chmod` follows symlinks by default.
**Prevention:** Verify `if not file_path.is_symlink():` before calling `chmod`. Alternatively, when creating files, atomic file creation using `os.open` with `os.O_CREAT | os.O_EXCL` and explicit mode is preferred.
