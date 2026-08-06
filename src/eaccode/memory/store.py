"""Auto-memory store (Task 6.3) — JSONL per project, FIFO cap.

The agent learns facts during work; they are injected into the system
prompt on the next session start. Facts only — rules stay user-only.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


class MemoryStore:
    def __init__(self, memory_dir: Path, max_entries: int = 50) -> None:
        self.memory_dir = memory_dir
        self.max_entries = max_entries
        memory_dir.mkdir(parents=True, exist_ok=True)

    def _file(self, project_hash: str) -> Path:
        return self.memory_dir / f"{project_hash}.jsonl"

    @staticmethod
    def project_hash(workdir: Path) -> str:
        """Stable hash per project root (git root or directory)."""
        cur = workdir.resolve()
        while not (cur / ".git").exists() and cur.parent != cur:
            cur = cur.parent
        return hashlib.sha256(str(cur).encode()).hexdigest()[:16]

    async def remember(self, project_hash: str, text: str, source: str = "agent") -> None:
        entry = {"text": text, "source": source, "created_at": datetime.now().isoformat()}
        path = self._file(project_hash)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._trim(path)

    async def recall(self, project_hash: str) -> list[str]:
        path = self._file(project_hash)
        if not path.exists():
            return []
        texts: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                texts.append(json.loads(line)["text"])
            except Exception:
                continue
        return texts

    async def forget(self, project_hash: str, text: str) -> None:
        path = self._file(project_hash)
        if not path.exists():
            return
        kept = [ln for ln in path.read_text(encoding="utf-8").splitlines() if text not in ln]
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    def _trim(self, path: Path) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > self.max_entries:
            path.write_text("\n".join(lines[-self.max_entries :]) + "\n", encoding="utf-8")
