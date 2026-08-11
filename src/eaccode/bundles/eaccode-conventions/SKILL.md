---
name: eaccode-conventions
description: Use when changing eaccode — LoC caps, tests, commit rules
triggers: [eaccode, convention, refactor]
---

# eaccode Project Conventions

## Rules
- New files 200–400 LoC, hard cap 600; split growing files immediately.
- Tests per feature in `tests/unit/test_<module>.py`; run with
  `-p no:cacheprovider` (browser/cua tests are flaky otherwise).
- Commit per feature: `feat|fix|refactor|chore(<scope>): <desc>`.
- Code, comments, docstrings and CLI strings in English.
- No new Python deps unless approved; no cloud services with keys.
