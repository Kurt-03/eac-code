"""Formatting utilities (H.5/H.8) — markdown tables, sizes, durations."""

from __future__ import annotations


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GitHub-flavored markdown table from headers + rows.

    Cells are escaped (pipes → ``\\|``); all rows are padded to the
    header width so the model sees a clean grid.
    """
    if not headers:
        return ""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    lines = [
        "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |",
    ]
    for row in rows:
        cells = [
            (row[i] if i < len(row) else "").ljust(widths[i]).replace("|", "\\|")
            for i in range(len(headers))
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def sizefmt(n: int) -> str:
    """Bytes → human readable (B/KB/MB/GB, one decimal)."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def timefmt(seconds: float) -> str:
    """Seconds → human readable (45s / 3m 12s / 1h 05m)."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"
