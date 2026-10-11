import asyncio
import json

import httpx
import pytest
from agi_agent import om_mcp
from agi_agent.om_mcp import McpError, OmMcp, Unauthorized


def with_mcp(handler, action):
    """Runs `action(OmMcp)` against a fake OM server (`handler`); returns the action's result."""
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await action(OmMcp("tok", http))

    return asyncio.run(run())


def rpc_reply(request, result):
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": json.loads(request.content)["id"], "result": result})


def test_call_tool_joins_text_parts_and_reports_is_error():
    def handler(request):
        body = json.loads(request.content)
        assert body["method"] == "tools/call"
        assert body["params"] == {"name": "search_metadata", "arguments": {"query": "x"}}
        return rpc_reply(request, {"content": [{"type": "text", "text": "Found "},
                                               {"type": "image", "data": "..."},
                                               {"type": "text", "text": "2 tables"}],
                                   "isError": True})

    text, is_error = with_mcp(handler, lambda m: m.call_tool("search_metadata", {"query": "x"}))

    assert text == "Found 2 tables"
    assert is_error is True


def test_sse_framed_reply_is_parsed():
    def handler(request):
        payload = {"jsonrpc": "2.0", "id": json.loads(request.content)["id"],
                   "result": {"tools": [{"name": "search_metadata"}]}}
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                              text=f"event: message\ndata: {json.dumps(payload)}\n\n")

    tools = with_mcp(handler, lambda m: m.list_tools())

    assert tools == [{"name": "search_metadata"}]


def test_http_401_raises_unauthorized():
    with pytest.raises(Unauthorized):
        with_mcp(lambda request: httpx.Response(401, text="expired"), lambda m: m.list_tools())


def test_json_rpc_error_raises_mcp_error():
    def handler(request):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1,
                                         "error": {"code": -32601, "message": "Method not found"}})

    with pytest.raises(McpError) as err:
        with_mcp(handler, lambda m: m.list_tools())

    assert err.value.args[0]["code"] == -32601


def test_initialize_sends_initialize_then_notification_without_id():
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.append(body)
        assert request.headers["Authorization"] == "Bearer tok"
        if body["method"] == "initialize":
            return rpc_reply(request, {"protocolVersion": om_mcp.PROTOCOL_VERSION, "capabilities": {}})
        return httpx.Response(202)

    with_mcp(handler, lambda m: m.initialize())

    assert [b["method"] for b in sent] == ["initialize", "notifications/initialized"]
    assert "id" in sent[0]
    assert "id" not in sent[1]
