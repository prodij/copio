from pathlib import Path

import pytest

from copio_api.agent.memory import MemoryStore


@pytest.mark.asyncio
async def test_memory_append_and_recall(tmp_path: Path) -> None:
    store = MemoryStore(tenant_id="test", root=tmp_path)
    await store.append(kind="preference", body="user does not want Walmart suggestions")
    await store.append(kind="decision", body="held price on B0CABCD123 in March")

    entries = await store.list()
    assert len(entries) == 2
    assert entries[0].kind == "preference"
    assert entries[1].kind == "decision"


@pytest.mark.asyncio
async def test_memory_snapshot_empty(tmp_path: Path) -> None:
    store = MemoryStore(tenant_id="t1", root=tmp_path)
    snapshot = await store.snapshot()
    assert "no prior context" in snapshot.lower()


@pytest.mark.asyncio
async def test_memory_snapshot_with_entries(tmp_path: Path) -> None:
    store = MemoryStore(tenant_id="t2", root=tmp_path)
    await store.append(kind="fact", body="Nutragroup runs 12 active ASINs as of May 2026")
    snapshot = await store.snapshot()
    assert "Nutragroup runs 12 active ASINs" in snapshot
    assert "[fact]" in snapshot


@pytest.mark.asyncio
async def test_memory_isolated_per_tenant(tmp_path: Path) -> None:
    a = MemoryStore(tenant_id="a", root=tmp_path)
    b = MemoryStore(tenant_id="b", root=tmp_path)
    await a.append(kind="fact", body="alpha entry")
    await b.append(kind="fact", body="beta entry")

    a_entries = await a.list()
    b_entries = await b.list()
    assert len(a_entries) == 1
    assert len(b_entries) == 1
    assert a_entries[0].body == "alpha entry"
    assert b_entries[0].body == "beta entry"
