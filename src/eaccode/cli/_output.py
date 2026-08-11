"""CLI output helpers (P0.18) — one place for consistent info/warn/error.

Every ``commands_*.py`` prints through these instead of raw
``click.echo`` so severity is visible at a glance (yellow warnings, red
errors) and the stream convention is uniform: errors → stderr, the rest
→ stdout. In non-TTY contexts (tests, pipes) click strips the colors, so
output stays machine-friendly.
"""

from __future__ import annotations

from collections.abc import Iterable

import click


def print_info(message: str = "") -> None:
    """Plain informational output (stdout)."""
    click.echo(message)


def print_success(message: str) -> None:
    """Confirmation output (stdout, green)."""
    click.secho(message, fg="green")


def print_warn(message: str) -> None:
    """Warning output (stdout, yellow)."""
    click.secho(message, fg="yellow")


def print_error(message: str) -> None:
    """Error output (stderr, red)."""
    click.secho(message, fg="red", err=True)


def print_table(rows: Iterable[tuple[str, ...]],
                headers: tuple[str, ...] = ()) -> None:
    """Minimal aligned table (stdout). Empty rows print nothing."""
    all_rows = [tuple(str(c) for c in r) for r in rows]
    if headers:
        all_rows = [tuple(headers), *all_rows]
    if not all_rows:
        return
    widths = [
        max(len(r[i]) for r in all_rows)
        for i in range(len(all_rows[0]))
    ]
    for row in all_rows:
        print_info("  " + "  ".join(
            c.ljust(w) for c, w in zip(row, widths, strict=False)
        ))
