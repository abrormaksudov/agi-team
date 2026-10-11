"""Client for OpenMetadata's MCP server (POST /mcp, stateless JSON-RPC), acting as the asking user."""

import json
import os

import httpx

OM_URL = os.environ.get("OM_URL", "http://localhost:8585")
PROTOCOL_VERSION = "2025-06-18"


class McpError(Exception):
    """JSON-RPC level failure (the tool itself failing comes back as a result with isError)."""


class Unauthorized(McpError):
    """OM rejected the user's token: expired or signed out."""


class OmMcp:
    def __init__(self, token: str, http: httpx.AsyncClient):
        self._http = http
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        self._id = 0

    async def _post(self, body: dict) -> httpx.Response:
        r = await self._http.post(f"{OM_URL}/mcp", headers=self._headers, json=body, timeout=60)
        if r.status_code == 401:
            raise Unauthorized("OpenMetadata rejected the session token")
        r.raise_for_status()
        return r

    async def _rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        r = await self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        text = r.text
        # JSON for Accept: application/json; tolerate an SSE-framed reply all the same
        if not text.lstrip().startswith("{"):
            text = next((line[5:] for line in text.splitlines() if line.startswith("data:")), "")
            if not text:
                raise McpError(f"unexpected reply from OM: {r.text[:200]!r}")
        msg = json.loads(text)
        if "error" in msg:
            raise McpError(msg["error"])
        return msg["result"]

    async def initialize(self) -> None:
        await self._rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                                       "clientInfo": {"name": "agi-agent", "version": "0.1"}})
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    async def list_tools(self) -> list[dict]:
        return (await self._rpc("tools/list", {}))["tools"]

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Returns (result text, is_error)."""
        res = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return text, bool(res.get("isError"))
