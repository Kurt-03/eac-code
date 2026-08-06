# Example project config — copy to EACCODE.md or use `eaccode config init`
# This file is auto-loaded when eaccode runs in this directory
# (parent walk up to the git root).

## Build
- Run tests with: pytest tests/ -q
- Lint with: ruff check src tests
- Install: pip install -e ".[all]"

## Conventions
- Code and comments in English
- TDD: write the failing test first
- Keep functions small and single-purpose

## Project-specific skills
# Put .md skill files in .eaccode/skills/ — the agent loads them automatically
# when the task matches their description.
