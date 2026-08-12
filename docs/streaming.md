# v0.0.1 — Streaming Architecture

The LLM stream is a sequence of small `Delta` chunks (4-32 chars
each). The naive renderer calls `render_markdown(accumulated_text)`
on every delta, which is O(N²) and visibly stutters on 50 deltas.
v0.0.1 introduces `StreamingMarkdownRenderer` to fix this.

## The renderer

```
user input → agent loop → stream(chunk) → on_text(chunk)
                                          ↓
                                  StreamingMarkdownRenderer.feed(chunk)
                                          ↓
                                  fragment string (Rich markup)
                                          ↓
                                  log.write(fragment)
```

The renderer is **stateful** but **single-direction** (no rewinding,
no recomputation). It holds:

- `_buffer: str` — the partial marker at the end of the last delta.
- `_state: _State` — the per-renderer mutable fields (last feed size).

The public API:

```python
renderer = StreamingMarkdownRenderer()
fragment = renderer.feed(delta)   # returns the new fragment
# ...
tail = renderer.finalize()         # at turn end, flush any buffer
renderer.reset()                    # at the next turn, clear state
```

## How the renderer handles a delta

1. **Concat** the buffer with the delta.
2. **Walk** the combined text char-by-char.
3. For each char, check if it starts a marker (`**`, `*`, `` ` ``, ` ``` `).
4. **If the marker is complete** (closing marker found in the safe
   section), emit the span with the right Rich markup.
5. **If the marker is incomplete** (closing marker NOT in the safe
   section), defer everything from the open marker to the next feed.
6. The safe section is bounded by `_safe_end`, which scans backward
   for any partial marker at the end of the text.

The safe section is what keeps the renderer incremental. Without it,
the renderer would have to buffer ALL of the delta (in case a marker
opens near the end) — that defeats the purpose.

## Performance

The repro script shows:

```
$ python tools/repro_stream_50_deltas.py
deltas: 50
max feed size: 4
transcript fragments: 47
```

- `max feed size: 4` — the renderer fed at most 4 bytes per delta
  (the delta size). With a naive re-render, this would be 200
  bytes (the accumulated text size).
- `transcript fragments: 47` — out of 50 deltas, 47 produced
  non-empty fragments. 3 deltas were absorbed by the buffer (they
  ended on a partial marker).

The savings on a 200-char answer is ~50× less work per delta.

## Failure modes

What if the LLM emits a malformed sequence?

- `**bold` (no closing) — held in the buffer, never emitted. On
  `finalize()`, the partial marker is dropped but the text is kept.
- `**bold** more` (closing and then more) — the bold span is emitted
  immediately, the rest is processed in the same delta.
- `*italic *` (closing in the middle of a word) — the renderer emits
  `italic` for the chars between `*` and `*`. The trailing `*` is
  not a marker (no open italic).
- Code-blocks that aren't closed — held in the buffer; on
  `finalize()`, the renderer closes the syntax-highlight span and
  drops the partial content.

## Verification

The behavior is locked in by:

- `tests/integration/test_stream_50_deltas.py::test_streaming_renderer_does_not_reparse_full_text_per_delta`
- `tests/integration/test_stream_50_deltas.py::test_streaming_renderer_buffers_unclosed_markdown`
- `tests/integration/test_stream_50_deltas.py::test_stream_50_deltas_writes_to_transcript_not_separate_static`
- `tests/integration/test_stream_50_deltas.py::test_stream_50_deltas_does_not_call_full_reparse`
- `tests/integration/test_stream_50_deltas.py::test_stream_final_text_is_not_written_twice`

The repro script (`tools/repro_stream_50_deltas.py`) is a manual
probe for the user to confirm the behavior in their environment.
