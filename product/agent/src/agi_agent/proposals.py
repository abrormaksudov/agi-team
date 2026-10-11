"""Changes the agent proposes; written to the catalog only when the user clicks Apply."""

import json
import secrets
from urllib.parse import quote

import httpx

from .om_mcp import OM_URL, OmMcp


class Proposals:
    def __init__(self):
        self._items: dict[str, dict] = {}

    def add(self, owner: tuple[str, str], args: dict) -> dict:
        p = {"id": f"P-{secrets.token_hex(3)}", "owner": owner, "status": "proposed",
             "entityType": args.get("entityType", ""), "fqn": args.get("fqn", ""),
             "summary": args.get("summary", ""), "changes": list(args.get("changes") or [])}
        self._items[p["id"]] = p
        return p

    def get(self, user: str, pid: str) -> dict | None:
        p = self._items.get(pid)
        return p if p and p["owner"][0] == user else None

    @staticmethod
    def public(p: dict) -> dict:
        return {k: p[k] for k in ("id", "status", "entityType", "fqn", "summary", "changes")}

    async def apply(self, p: dict, mcp: OmMcp, http: httpx.AsyncClient, token: str) -> tuple[bool, str]:
        try:
            ops = await _patch_ops(p, http, token)
        except ValueError as e:
            p["status"] = "failed"
            return False, str(e)
        text, is_error = await mcp.call_tool("patch_entity", {
            "entityType": p["entityType"], "fqn": p["fqn"], "patch": json.dumps(ops, ensure_ascii=False)})
        p["status"] = "failed" if is_error else "applied"
        return not is_error, text[:500] if is_error else f"Applied {len(ops)} change(s) to {p['fqn']}."


async def _patch_ops(p: dict, http: httpx.AsyncClient, token: str) -> list[dict]:
    """JSON Patch with `add` (it also replaces an existing value); column indexes are looked up, not guessed."""
    index: dict[str, int] = {}
    if any(c.get("column") for c in p["changes"]):
        if p["entityType"] != "table":
            raise ValueError("Column descriptions can only be proposed for tables.")
        r = await http.get(f"{OM_URL}/api/v1/tables/name/{quote(p['fqn'], safe='')}", params={"fields": "columns"},
                           headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code != 200:
            raise ValueError(f"Could not read {p['fqn']} (HTTP {r.status_code}).")
        index = {c["name"]: i for i, c in enumerate(r.json().get("columns") or [])}
    ops = []
    for c in p["changes"]:
        col = c.get("column")
        if col and col not in index:
            raise ValueError(f"{p['fqn']} has no column {col!r}; nothing was changed.")
        path = f"/columns/{index[col]}/description" if col else "/description"
        ops.append({"op": "add", "path": path, "value": c["description"]})
    if not ops:
        raise ValueError("The proposal contains no changes.")
    return ops
