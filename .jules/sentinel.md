## 2024-05-24 - Unnecessary Sub-directory permissions vulnerability in Storage
**Vulnerability:** Weak permissions for .ttyping/ configuration storage
**Learning:** `storage.py` set directory permissions with 0o700, but Python's `Path.mkdir(parents=True)` without additional handling only applies mode to the *last* created directory. Intermediate directories are created with default umask permissions, which could be less restrictive.
**Prevention:** In this application, `.ttyping` is created in the user's home directory. Intermediate directories aren't created (since `~` already exists), but when doing directory permission operations, ensure the permissions on any implicitly created intermediate directories are also correct or handled, or just use `exist_ok=True` without relying on parents=True where possible, or use explicit modes.

## 2024-05-24 - `os.umask(0o077)` is not thread safe
**Vulnerability:** Modifying the global process umask with `os.umask(0o077)` during initialization can lead to race conditions where other threads might create files with unintended permissions during that tiny window.
**Learning:** Even with try-finally, changing process state like umask is unsafe in a multithreaded application.
**Prevention:** Where possible, use the `mode` parameter of `open()` or `os.open()` with `os.O_CREAT | os.O_EXCL` rather than modifying the process `umask`, or set the umask once at application startup.

## 2024-05-24 - Prevent `chmod` from changing symlink targets
**Vulnerability:** Symlink attack via TOCTOU (Time-of-Check to Time-of-Use) leading to arbitrary file permission changes.
**Learning:** `os.chmod` on Linux will follow symlinks by default (and `follow_symlinks=False` raises `NotImplementedError` on many systems), meaning changing permissions on an implicitly created file could be hijacked to modify sensitive files elsewhere in the system if the file is replaced with a symlink before `chmod` is called.
**Prevention:** Always ensure a file or directory is not a symlink by checking `not path.is_symlink()` before performing `chmod` operations to lock down file access permissions.
