import os
import json
import asyncio
import pytest
from fastmcp import Client

TARGET = os.environ.get("MCP_SERVER_URL", "mospi_server.py")
THROTTLE = 0.5


def parse_tool_result(result) -> dict:
    """Extract and parse the JSON text from a CallToolResult."""
    assert result.content, "Tool returned empty content"
    text = result.content[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"raw": text}


async def call(mcp_target, tool_name: str, arguments: dict, retries: int = 2) -> dict:
    """Open a Client, call the tool, parse and return the result dict.

    Retries on transient backend errors (MoSPI 500s from rate-limiting).
    """
    for attempt in range(1, retries + 2):
        await asyncio.sleep(THROTTLE)
        async with Client(mcp_target) as c:
            result = await c.call_tool(tool_name, arguments)
        data = parse_tool_result(result)
        if "error" not in data or attempt > retries:
            return data
        # Back off before retry
        await asyncio.sleep(THROTTLE * attempt)
    return data


async def test_list_datasets():
    """list_datasets: API overview returns all datasets including NSS81."""
    data = await call(TARGET, "list_datasets", {})
    assert isinstance(data, dict)
    assert "datasets" in data
    assert "NSS81" in data["datasets"]
    assert "error" not in data


async def test_get_indicators():
    """get_indicators: Returns NSS81 indicators."""
    data = await call(TARGET, "get_indicators", {"dataset": "NSS81"})
    assert isinstance(data, dict)
    assert "error" not in data
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0
    # Check that indicator codes are in expected range
    codes = [ind.get("code") or ind.get("indicator_code") for ind in data["data"]]
    for code in codes:
        assert 1 <= code <= 29, f"Indicator code {code} out of range 1-29"


async def test_get_metadata():
    """get_metadata: Returns filters for a valid NSS81 indicator."""
    data = await call(TARGET, "get_metadata", {"dataset": "NSS81", "indicator": "1"})
    assert isinstance(data, dict)
    assert "error" not in data
    assert "api_params" in data
    assert "parameter_notes" in data
    assert "next_step" in data


async def test_get_data():
    """get_data: Returns data for a valid NSS81 indicator."""
    data = await call(TARGET, "get_data", {"dataset": "NSS81", "indicator_code": "1", "limit": "1"})
    assert isinstance(data, dict)
    assert "error" not in data
    assert "data" in data
    assert isinstance(data["data"], list)
    # Should return at most 1 record due to limit
    assert len(data["data"]) <= 1
