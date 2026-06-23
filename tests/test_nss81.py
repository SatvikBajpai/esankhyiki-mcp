import os
import json
import asyncio
import pytest
from fastmcp import Client

TARGET = os.environ.get("MCP_SERVER_URL", "mospi_server.py")
THROTTLE = 0.1


def parse_tool_result(result) -> dict:
    """Extract and parse the JSON text from a CallToolResult."""
    assert result.content, "Tool returned empty content"
    text = result.content[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"raw": text}


async def call(mcp_target, tool_name: str, arguments: dict, retries: int = 2) -> dict:
    """Open a Client, call a tool, parse and return the result dict.

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
    assert data["count"] > 0


async def test_get_metadata():
    """get_metadata: Returns filters for NSS81 indicator 1."""
    data = await call(TARGET, "get_metadata", {"dataset": "NSS81", "indicator_code": "1"})
    assert isinstance(data, dict)
    assert "error" not in data
    assert "api_params" in data


async def test_get_data():
    """get_data: Returns data for NSS81 indicator 1."""
    data = await call(TARGET, "get_data", {"dataset": "NSS81", "indicator_code": "1", "limit": "1"})
    assert isinstance(data, dict)
    assert "error" not in data
    assert "data" in data
