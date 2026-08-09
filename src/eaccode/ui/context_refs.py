"""@-reference expansion (Phase H.3) — resolve @file:/@folder:/@git:/@url:
into actual content BEFORE the LLM call.

Ported from Hermes' ``agent/context_references.py``. The input
completion (Phase F.4) suggests the tokens; this module expands them
into real context blocks with metadata + code fences, so the model sees
the referenced content instead of a bare token.
"""

from __future__ import annotations

import re
from pathlib import Path

_REF_RE = re.compile(r"@(file|folder|git|url):([^\s]+)")

_MAX_FILE_CHARS = 8_000
_MAX_FOLDER_ENTRIES = 200


def parse_context_references(message: str) -> list[tuple[str, str]]:
    """Extract (kind, value) pairs from an @-reference message."""
    return [(m.group(1), m.group(2)) for m in _REF_RE.finditer(message)]


def preprocess_context_references(message: str, cwd: Path | None = None) -> str:
    """Replace every @-reference with its expanded content block.

    Unknown or failing references are left as-is (the model sees the
    token and can react). References resolve relative to *cwd*.
    """
    cwd = Path(cwd or Path.cwd()).resolve()

    def _replace(match: re.Match) -> str:
        kind, value = match.group(1), match.group(2)
        expanded = _expand(kind, value, cwd)
        return expanded if expanded is not None else match.group(0)

    return _REF_RE.sub(_replace, message)


def _expand(kind: str, value: str, cwd: Path) -> str | None:
    if kind == "file":
        return _expand_file_reference(value, cwd)
    if kind == "folder":
        return _expand_folder_reference(value, cwd)
    if kind == "git":
        return _expand_git_reference(value, cwd)
    if kind == "url":
        return _expand_url_reference(value)
    return None


def _resolve_path(cwd: Path, target: str) -> Path | None:
    path = Path(target).expanduser()
    if not path.is_absolute():
        path = cwd / path
    try:
        return path.resolve()
    except OSError:
        return None


def _code_fence_language(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {
        "py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
        "jsx": "javascript", "md": "markdown", "json": "json", "yaml": "yaml",
        "yml": "yaml", "toml": "toml", "sh": "bash", "bash": "bash", "rs": "rust",
        "go": "go", "java": "java", "c": "c", "h": "c", "cpp": "cpp", "hpp": "cpp",
        "html": "html", "css": "css", "sql": "sql",
    }.get(suffix, "")


def _expand_file_reference(value: str, cwd: Path) -> str | None:
    path = _resolve_path(cwd, value)
    if path is None or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(text) > _MAX_FILE_CHARS:
        text = text[:_MAX_FILE_CHARS] + "\n[...truncated...]"
    lang = _code_fence_language(path)
    fence = f"```{lang}" if lang else "```"
    return (f"[Reference: {path}]\n"
            f"Size: {path.stat().st_size} bytes\n"
            f"{fence}\n{text}\n```")


def _expand_folder_reference(value: str, cwd: Path) -> str | None:
    path = _resolve_path(cwd, value)
    if path is None or not path.is_dir():
        return None
    entries: list[str] = []
    try:
        for child in sorted(path.iterdir()):
            if child.name.startswith("."):
                continue
            entries.append(child.name + ("/" if child.is_dir() else ""))
            if len(entries) >= _MAX_FOLDER_ENTRIES:
                entries.append(f"... ({len(entries)} entries capped)")
                break
    except OSError:
        return None
    return f"[Folder listing: {path}]\n" + "\n".join(entries)


def _expand_git_reference(value: str, cwd: Path) -> str | None:
    """@git:N → last N commits with diffs (default 5)."""
    from eaccode._subprocess_compat import bounded_git_probe

    try:
        n = max(1, min(int(value or "5"), 20))
    except ValueError:
        n = 5
    log = bounded_git_probe(["git", "-C", str(cwd), "log", f"-{n}", "--stat"], timeout=15)
    if not log:
        return None
    return f"[Git log (last {n} commits)]\n{log}"


def _expand_url_reference(value: str) -> str | None:
    """@url: → fetch the page (bounded). Returns None on failure."""
    try:
        import httpx

        resp = httpx.get(value, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "eaccode/0.1"})
        resp.raise_for_status()
        text = resp.text[:_MAX_FILE_CHARS]
        return f"[Fetched URL: {value}]\n{text}"
    except Exception:
        return None
