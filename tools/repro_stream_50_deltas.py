"""tools/repro_stream_50_deltas.py — manual streaming reproducer.

Run from the repo root:

    .venv/Scripts/python.exe tools/repro_stream_50_deltas.py

This script:
1. Uses the ``StreamingMarkdownRenderer`` directly (no full TUI boot).
2. Feeds 50 synthetic deltas through the renderer.
3. Records the timestamps of every output fragment and the feed sizes.
4. Saves the report to ``logs/stream_50_deltas.log`` so the user can
   inspect what landed in the transcript.

The script does NOT assert anything — it's a manual probe to confirm
the user's "i-was flackert / i-was doppelt" bug is gone.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eaccode.tui.streaming_md import StreamingMarkdownRenderer  # noqa: E402


def _synthetic_deltas(n: int = 50, chunk_size: int = 4) -> list[str]:
    full = (
        "Hello **world** — this is a synthetic stream of text used to "
        "verify Hermes-style in-place updates. Each call appends a bit "
        "more content; the UI must render without full re-parse."
    )
    full = (full * 5)[: n * chunk_size]
    return [full[i : i + chunk_size] for i in range(0, len(full), chunk_size)]


def run() -> None:
    renderer = StreamingMarkdownRenderer()
    records: list[tuple[float, int, int, int]] = []
    transcript: list[str] = []
    start = time.monotonic()
    for i, chunk in enumerate(_synthetic_deltas(50)):
        fragment = renderer.feed(chunk)
        if fragment:
            transcript.append(fragment)
        records.append(
            (
                time.monotonic() - start,
                i,
                renderer.last_feed_size,
                len(fragment or ""),
            )
        )
    tail = renderer.finalize()
    if tail:
        transcript.append(tail)

    out_dir = REPO_ROOT / "logs"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "stream_50_deltas.log"
    feed_sizes = [r[2] for r in records]
    fragment_sizes = [r[3] for r in records]
    lines = [
        "v0.0.1 — 50-delta streaming reproducer",
        "=" * 40,
        f"deltas:                   {len(records)}",
        f"transcript fragments:     {len(transcript)}",
        f"max renderer feed size:   {max(feed_sizes)}",
        f"max fragment size:        {max(fragment_sizes)}",
        f"avg renderer feed size:   {sum(feed_sizes) / len(feed_sizes):.1f}",
        f"final renderer state:     {'clean' if renderer._buffer == '' else 'has-buffer'}",
        "",
        "per-delta timings (first 10):",
    ]
    for t, idx, size, frag in records[:10]:
        lines.append(f"  [{idx:>2}] t={t:.3f}s  feed={size:>3}  fragment={frag:>3}")
    lines.append("")
    lines.append("transcript content (first 600 chars):")
    lines.append("".join(transcript)[:600])
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    print(f"  deltas: {len(records)}")
    print(f"  max feed size: {max(feed_sizes)}")
    print(f"  transcript fragments: {len(transcript)}")


if __name__ == "__main__":
    run()
