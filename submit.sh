#!/bin/bash
git checkout -b security-fix-negative-words
git add src/ttyping/__main__.py tests/test_main.py tests/test_security_config.py
git commit -m "🔒 Fix negative word count vulnerability

🎯 **What:** The application failed to validate negative word counts, potentially leading to anomalous behavior. Fixed this by adding proper bounds checking with max(1, min(args.words, 1000)) in the CLI entrypoint. Added a unit test, and also fixed an existing linting issue in a test file.
⚠️ **Risk:** A negative word count might be used to circumvent expected flow and perform out-of-bounds operations.
🛡️ **Solution:** Properly limit the parameter with boundary checks immediately after parsing."
