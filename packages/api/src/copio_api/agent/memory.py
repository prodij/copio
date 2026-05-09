"""Phase 1.0 file-backed memory.

Per the CEO plan: "Tool palette: structured SP-API tool calls, math/stat tools,
**simple file-based memory**."

The pgvector schema exists for Phase 1.1 graduation, but Phase 1.0 keeps the
runtime memory in flat JSON files keyed by tenant_id so it works on a single
laptop with no embedding pipeline yet.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from copio_api.config import get_settings


@dataclass
class MemoryEntry:
    kind: str  # 'preference' | 'fact' | 'decision' | 'note'
    body: str
    created_at: str


class MemoryStore:
    """Append-only JSONL memory per tenant."""

    def __init__(self, *, tenant_id: str, root: Path | None = None) -> None:
        settings = get_settings()
        self.tenant_id = tenant_id
        self.root = root or settings.memory_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{tenant_id}.jsonl"
        self._lock = asyncio.Lock()

    async def list(self, limit: int = 200) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        loop = asyncio.get_running_loop()
        lines = await loop.run_in_executor(None, self._read_lines)
        entries = [MemoryEntry(**json.loads(line)) for line in lines[-limit:]]
        return entries

    def _read_lines(self) -> list[str]:
        with self.path.open() as f:
            return [line for line in f.read().splitlines() if line.strip()]

    async def append(self, *, kind: str, body: str) -> MemoryEntry:
        entry = MemoryEntry(
            kind=kind,
            body=body,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        async with self._lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._append_line, entry)
        return entry

    def _append_line(self, entry: MemoryEntry) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    async def snapshot(self, *, limit: int = 50) -> str:
        """Return a stable text snapshot for inclusion in the prompt cache.

        Phase 1.0 intentionally keeps this as plain text rather than embeddings,
        so it can be the 4th cache breakpoint without a vector lookup hop. Phase
        1.1 graduates this to RAG over the pgvector store.
        """
        entries = await self.list(limit=limit)
        if not entries:
            return "MEMORY: (no prior context — first session)"
        lines = ["MEMORY (most recent last):"]
        for e in entries:
            lines.append(f"- [{e.kind}] {e.body}")
        return "\n".join(lines)
