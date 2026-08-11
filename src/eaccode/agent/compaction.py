"""Smart context compaction (P0.2) — soft-tail demotion, ghost-skill defense,
feasibility skip, small-window floor, session-boundary redaction.

Replaces the plain drop-everything compaction:

- **Soft tail** — the middle is *demoted* into a compact per-role digest
  instead of being dropped: every message keeps a one-line residue, so
  the model still sees the shape of the earlier conversation.
- **Ghost-skill defense** — when skill sections have to leave the system
  prompt, a ``[SKILL_PRUNED: <name>]`` marker stays behind so the model
  knows the skill existed and can reload it (Hermes' ghost pattern).
- **Feasibility skip** — an LLM summary of the middle only runs when the
  middle is substantial (>= 10% of the compaction threshold); tiny
  middles are demoted locally without burning a model call.
- **Small-window floor** — models with < 512K context compact at most at
  50% of the window, so small-window models never run to the brim.
- **Session-boundary redaction** — demoted tool payloads from earlier
  turns are scrubbed (names kept, arguments/paths replaced) instead of
  being carried forward verbatim.
"""

from __future__ import annotations

from collections.abc import Callable

from eaccode.llm.models import Message
from eaccode.llm.tokens import count_message_tokens, model_context_window

SMALL_WINDOW = 512_000  # below this the 50% floor applies
SMALL_WINDOW_FLOOR = 0.5
FEASIBILITY_RATIO = 0.10  # middle must be >= 10% of the threshold budget
GHOST_MARKER = "[SKILL_PRUNED]"
_DEMOTE_CHARS = 160  # per-message residue length in the soft tail
_MAX_SYSTEM_RATIO = 0.25  # system prompt budget of the window


def effective_threshold(model: str, threshold: float) -> float:
    """Small-context-window floor: <512K models compact at max 50%."""
    if model_context_window(model) < SMALL_WINDOW:
        return min(threshold, SMALL_WINDOW_FLOOR)
    return threshold


def should_compact(messages: list[Message], model: str, threshold: float) -> bool:
    window = model_context_window(model)
    used = count_message_tokens(messages, model)
    return used > window * effective_threshold(model, threshold)


def _message_text(msg: Message) -> str:
    """Concatenated text of a message's content blocks."""
    return " ".join(
        b.text for b in msg.content if getattr(b, "type", "") == "text"
    )


def _message_image_count(msg: Message) -> int:
    return sum(1 for b in msg.content if getattr(b, "type", "") != "text")


def _demote_message(msg: Message, redact: bool) -> str:
    """One-line residue of a message (soft tail)."""
    role = msg.role.value
    text = _message_text(msg)
    text = text[:_DEMOTE_CHARS] if redact else text[:_DEMOTE_CHARS * 4]
    line = f"[{role}] {text}".rstrip()
    if msg.tool_calls:
        names = ", ".join(tc.name for tc in msg.tool_calls)
        line += f" → tools: {names}"
        if redact:
            line += " (args redacted)"
    images = _message_image_count(msg)
    if images:
        line += f" ({images} image(s))"
    return line


def _demoted_summary(middle: list[Message], redact: bool) -> str:
    """Soft tail: one residue line per earlier message."""
    if not middle:
        return "(nothing to compact)"
    lines = [_demote_message(m, redact) for m in middle]
    # Cap the residue block so a huge middle can't re-bloat the context.
    cap = 80
    if len(lines) > cap:
        lines = [*lines[:cap], f"… {len(lines) - cap} more messages"]
    return "\n".join(lines)


def _ghost_skill_defense(system: Message, model: str) -> Message:
    """Drop skill sections beyond the system budget, leaving markers.

    Returns the (possibly trimmed) system message. The section header
    ``## <name>`` is replaced by ``[SKILL_PRUNED: <name>]`` so the model
    knows the skill existed and can reload it with skill_view.
    """
    budget = int(model_context_window(model) * _MAX_SYSTEM_RATIO)
    if count_message_tokens([system], model) <= budget:
        return system
    text = system.text
    sections = text.split("\n## ")
    kept: list[str] = []
    ghosts: list[str] = []
    for i, section in enumerate(sections):
        header = section.splitlines()[0] if section else ""
        name = header.strip()
        candidate = [*kept, section]
        size = count_message_tokens([Message.system("\n## ".join(candidate))], model)
        if i > 0 and size > budget:
            ghosts.append(f"{GHOST_MARKER}: {name}")
        else:
            kept.append(section)
    trimmed = "\n## ".join(kept)
    if ghosts:
        trimmed = f"{trimmed}\n\nGhost skills (reload with skill_view):\n" \
                  + "\n".join(ghosts)
    return Message.system(trimmed)


def compact_messages(
    messages: list[Message],
    keep_recent: int = 5,
    *,
    model: str = "anthropic/claude-sonnet-4-6",
    threshold: float = 0.7,
    summarize: Callable[[list[Message]], str] | None = None,
    redact: bool = True,
) -> list[Message]:
    """Smart compaction with soft tail, ghost defense, feasibility skip.

    ``summarize`` is an optional callable(middle) -> str (e.g. an LLM
    summary); it only runs when the middle is substantial enough that the
    call pays off (feasibility skip). ``redact`` scrubs tool payloads of
    the demoted middle (session-boundary redaction, default on).
    """
    if len(messages) <= keep_recent + 1:
        return messages
    middle = messages[:-keep_recent]
    tail = messages[-keep_recent:]

    summary_text = _demoted_summary(middle, redact)

    if summarize is not None:
        window = model_context_window(model)
        used = count_message_tokens(middle, model)
        budget = window * effective_threshold(model, threshold)
        if used >= budget * FEASIBILITY_RATIO:  # pre-LLM feasibility skip
            try:
                llm_text = summarize(middle)
                if llm_text and llm_text.strip():
                    summary_text = llm_text
            except Exception:
                pass  # fall back to the demoted soft tail

    # Keep the system prompt (with ghost-skill defense) ahead of the summary.
    head: list[Message] = []
    if messages and messages[0].role.value == "system":
        head = [_ghost_skill_defense(messages[0], model)]

    summary = Message.system(
        "[Earlier conversation compacted — residues below (or LLM summary).]\n"
        f"{summary_text}"
    )
    return [*head, summary, *tail]
