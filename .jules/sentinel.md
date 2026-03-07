## 2026-03-07 - Stack Trace Leakage Fix
**Vulnerability:** Unhandled exceptions at the CLI entry point leaked raw Python stack traces directly to the user's terminal.
**Learning:** Terminal UI applications can crash on setup before capturing `sys.stderr`, meaning it's still necessary to wrap the highest level entry points directly to prevent exposing sensitive internal state.
**Prevention:** Always wrap application start loops in broad `try...except Exception` blocks to gracefully log errors and exit securely, instead of letting Python dump the stack trace.
