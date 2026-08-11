---
name: code-review
description: Use when reviewing changes — security, quality, tests
triggers: [review, pr, pull-request, audit]
---

# Code Review Checklist

## Steps
1. **Security** — secrets, path traversal, shell injection, denied paths.
2. **Correctness** — does it fix the class of bug, not one site?
3. **Tests** — is there a failing-then-passing test for the change?
4. **Maintainability** — file size caps (200–400 LoC, hard 600), naming.

## Pitfalls
- Review the diff, not the intent — verify claims against the code.
- Flag silent failure swallowing without a comment.
