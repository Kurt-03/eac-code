"""Pending approval registry (B.4) — resolve ASKs by id.

Every permission ASK gets an id; the REPL renders it in the modal and
the registry remembers the future. ``/approve <id>`` / ``/deny <id>``
resolve a still-pending future — useful when the modal cannot be
answered directly (headless bridge, tests) or the user wants to decide
after the fact. Double resolution is safe (the future is already done).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingApproval:
    id: int
    tool: str
    arguments: dict
    question: str
    future: Any  # asyncio.Future[PermissionChoice]
    done: bool = field(default=False)


class ApprovalRegistry:
    def __init__(self) -> None:
        self._pending: dict[int, PendingApproval] = {}
        self._next_id = 1

    def register(self, tool: str, arguments: dict, question: str,
                 future: Any) -> int:
        approval_id = self._next_id
        self._next_id += 1
        self._pending[approval_id] = PendingApproval(
            approval_id, tool, arguments, question, future
        )
        future.add_done_callback(lambda _f: self._mark_done(approval_id))
        return approval_id

    def _mark_done(self, approval_id: int) -> None:
        entry = self._pending.get(approval_id)
        if entry is not None:
            entry.done = True

    def resolve(self, approval_id: int, choice: Any) -> bool:
        """Resolve a pending approval; True when it was still pending."""
        entry = self._pending.get(approval_id)
        if entry is None or entry.done:
            return False
        try:
            entry.future.set_result(choice)
        except Exception:
            return False
        entry.done = True
        return True

    def pending(self) -> list[PendingApproval]:
        return [e for e in self._pending.values() if not e.done]

    def __len__(self) -> int:
        return len(self.pending())
