## 2024-05-24 - Unnecessary Sub-directory permissions vulnerability in Storage
**Vulnerability:** Weak permissions for .ttyping/ configuration storage
**Learning:** `storage.py` set directory permissions with 0o700, but Python's `Path.mkdir(parents=True)` without additional handling only applies mode to the *last* created directory. Intermediate directories are created with default umask permissions, which could be less restrictive.
**Prevention:** In this application, `.ttyping` is created in the user's home directory. Intermediate directories aren't created (since `~` already exists), but when doing directory permission operations, ensure the permissions on any implicitly created intermediate directories are also correct or handled, or just use `exist_ok=True` without relying on parents=True where possible, or use explicit modes.

## 2024-05-24 - `os.umask(0o077)` is not thread safe
**Vulnerability:** Modifying the global process umask with `os.umask(0o077)` during initialization can lead to race conditions where other threads might create files with unintended permissions during that tiny window.
**Learning:** Even with try-finally, changing process state like umask is unsafe in a multithreaded application.
**Prevention:** Where possible, use the `mode` parameter of `open()` or `os.open()` with `os.O_CREAT | os.O_EXCL` rather than modifying the process `umask`, or set the umask once at application startup.

## 2024-10-27 - TOCTOU symlink vulnerability in os.chmod
**Vulnerability:** Calling `os.chmod` (or `Path.chmod`) on a file without checking if it's a symlink allows a Time-of-Check to Time-of-Use (TOCTOU) symlink attack. An attacker can replace a configuration file with a symlink to another file they don't own, causing the application to unknowingly change the permissions of the target file.
**Learning:** `os.chmod` has a `follow_symlinks=False` argument, but it is not implemented on all platforms (like Linux and Windows) and will throw a `NotImplementedError`. Thus, checking `if not path.is_symlink():` before `chmod` is necessary for cross-platform security.
**Prevention:** Always check `if not path.is_symlink():` before changing file permissions in directories where an attacker might be able to create symlinks, especially when `follow_symlinks=False` is unavailable.
