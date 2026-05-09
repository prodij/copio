import pytest

from copio_api.agent.tools.base import ToolContext
from copio_api.agent.tools.math import MATH_TOOLS
from copio_api.config import get_settings


def _ctx() -> ToolContext:
    return ToolContext(tenant_id="test-tenant", settings=get_settings(), spapi_client=None)


def _by_name(name: str):
    return next(t for t in MATH_TOOLS if t.name == name)


@pytest.mark.asyncio
async def test_summary_stats_normal_case() -> None:
    tool = _by_name("summary_stats")
    result = await tool.handler(_ctx(), {"values": [1, 2, 3, 4, 5]})
    assert result.content["n"] == 5
    assert result.content["mean"] == 3.0
    assert result.content["median"] == 3
    assert result.content["min"] == 1
    assert result.content["max"] == 5


@pytest.mark.asyncio
async def test_summary_stats_empty() -> None:
    tool = _by_name("summary_stats")
    result = await tool.handler(_ctx(), {"values": []})
    assert "error" in result.content


@pytest.mark.asyncio
async def test_pct_change_normal() -> None:
    tool = _by_name("pct_change")
    result = await tool.handler(_ctx(), {"baseline": 100, "current": 108})
    assert result.content["pct_change"] == 8.0
    assert result.content["abs_delta"] == 8


@pytest.mark.asyncio
async def test_pct_change_zero_baseline() -> None:
    tool = _by_name("pct_change")
    result = await tool.handler(_ctx(), {"baseline": 0, "current": 5})
    assert result.content["error"] == "baseline_zero"


@pytest.mark.asyncio
async def test_z_score_anomaly() -> None:
    tool = _by_name("z_score")
    result = await tool.handler(
        _ctx(),
        {"baseline_values": [10, 11, 9, 10, 12, 8, 11], "point": 25},
    )
    assert result.content["anomaly"] is True
    assert result.content["z"] > 2.0


@pytest.mark.asyncio
async def test_z_score_normal() -> None:
    tool = _by_name("z_score")
    result = await tool.handler(
        _ctx(),
        {"baseline_values": [10, 11, 9, 10, 12, 8, 11], "point": 11},
    )
    assert result.content["anomaly"] is False
