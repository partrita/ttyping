## 2024-05-24 - Unnecessary Sub-directory permissions vulnerability in Storage
**Vulnerability:** Weak permissions for .ttyping/ configuration storage
**Learning:** `storage.py` set directory permissions with 0o700, but Python's `Path.mkdir(parents=True)` without additional handling only applies mode to the *last* created directory. Intermediate directories are created with default umask permissions, which could be less restrictive.
**Prevention:** In this application, `.ttyping` is created in the user's home directory. Intermediate directories aren't created (since `~` already exists), but when doing directory permission operations, ensure the permissions on any implicitly created intermediate directories are also correct or handled, or just use `exist_ok=True` without relying on parents=True where possible, or use explicit modes.

## 2024-05-24 - `os.umask(0o077)` is not thread safe
**Vulnerability:** Modifying the global process umask with `os.umask(0o077)` during initialization can lead to race conditions where other threads might create files with unintended permissions during that tiny window.
**Learning:** Even with try-finally, changing process state like umask is unsafe in a multithreaded application.
**Prevention:** Where possible, use the `mode` parameter of `open()` or `os.open()` with `os.O_CREAT | os.O_EXCL` rather than modifying the process `umask`, or set the umask once at application startup.

## 2024-05-25 - TOCTOU Symlink vulnerability in storage permissions
**Vulnerability:** Changing permissions on directories or files without checking if they are symlinks first.
**Learning:** `storage.py` used `chmod(0o700)` and `chmod(0o600)` on the config directory and files if the existing permissions were incorrect. If a malicious user or script replaced these with symlinks to sensitive files (like `/etc/passwd` or another user's files), `chmod` would follow the symlink and inadvertently change the permissions of the target file. It also breaks legitimate use-cases where users symlink their config to a `.dotfiles` repository.
**Prevention:** Always verify `not path.is_symlink()` before applying `chmod` to ensure the operation only affects regular files/directories as intended, and safely skips symlinks.