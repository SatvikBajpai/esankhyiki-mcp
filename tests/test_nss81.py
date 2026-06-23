"""NSS81 health-check - exercises all four MCP tools, chaining each step.

get_data filters are built from get_metadata's api_params at runtime, so this
works for any dataset shape (base_year, frequency_code, survey) with no hardcoding.

Run in-process:    pytest tests/test_nss81.py -v
Against a server:  MCP_SERVER_URL=https://mcp.mospi.gov.in/mcp pytest tests/test_nss81.py -v
"""
import json
import os

import pytest
from fastmcp import Client

TARGET = os.environ.get("MCP_SERVER_URL", "mospi_server.py")
DATASET = "NSS81"
REQUIRES_INDICATOR = True

# Sensible values for params that are required but carry no default/enum.
FILTER_FALLBACKS = {"frequency_code": 1}


async def call(tool: str, args: dict) -> dict:
    async with Client(TARGET) as client:
        res = await client.call_tool(tool, args)
    text = res.content[0].text if res.content else "{}"
    return json.loads(text)


def first_indicator_code(obj):
    """First indicator_code found anywhere in a get_indicators response."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "indicator_code":
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
            found = first_indicator_code(val)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = first_indicator_code(item)
            if found is not None:
                return found
    return None


def build_filters(indicator_code, metadata):
    """Build a valid get_data filter set from the metadata's api_params."""
    filters = {"limit": 5}
    if indicator_code is not None:
        filters["indicator_code"] = indicator_code
    for param in (metadata.get("api_params") or []):
        name = param.get("name")
        if not param.get("required") or name in ("indicator_code", "limit", "Format"):
            continue
        schema = param.get("schema") or {}
        value = schema.get("default")
        if value is None and schema.get("enum"):
            value = schema["enum"][0]
        if value is None:
            value = FILTER_FALLBACKS.get(name)
        if value is not None:
            filters[name] = value
    return filters


async def _metadata():
    """Shared chain: pick a real indicator, then fetch its metadata."""
    indicators = await call("get_indicators", {"dataset": DATASET})
    ic = first_indicator_code(indicators)
    args = {"dataset": DATASET}
    if REQUIRES_INDICATOR:
        args["indicator_code"] = ic if ic is not None else 1
    return ic, await call("get_metadata", args)


@pytest.mark.asyncio
async def test_listed():
    data = await call("list_datasets", {})
    assert DATASET in data["datasets"], "NSS81 missing from list_datasets"


@pytest.mark.asyncio
async def test_get_indicators():
    data = await call("get_indicators", {"dataset": DATASET})
    assert "error" not in data, data


@pytest.mark.asyncio
async def test_get_metadata():
    _, metadata = await _metadata()
    assert "error" not in metadata, metadata


@pytest.mark.asyncio
async def test_get_data():
    ic, metadata = await _metadata()
    filters = build_filters(ic, metadata)
    data = await call("get_data", {"dataset": DATASET, "filters": filters})
    assert "error" not in data, data
    assert "data" in data, data
