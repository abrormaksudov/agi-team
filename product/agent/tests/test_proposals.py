import asyncio
import re

import httpx
import pytest
from agi_agent.om_mcp import OM_URL
from agi_agent.proposals import Proposals, _patch_ops

FQN = "greenplum.dwh.datamart.x"
TABLE_URL = f"{OM_URL}/api/v1/tables/name/{FQN}"


def proposal(entity_type="table", changes=()):
    return {"entityType": entity_type, "fqn": FQN, "changes": list(changes)}


def patch_ops(p, columns=("a", "b")):
    """Runs _patch_ops against a fake OM; returns (ops, requests seen)."""
    seen = []

    def handler(request):
        seen.append(request)
        body = {"columns": [{"name": c} for c in columns]}
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await _patch_ops(p, http, "tok")

    return asyncio.run(run()), seen


def test_ids_are_random_and_get_is_scoped_to_the_owner():
    ps = Proposals()
    first = ps.add(("jury", "c1"), {"entityType": "table", "fqn": FQN, "summary": "s", "changes": []})
    second = ps.add(("jury", "c1"), {"entityType": "table", "fqn": FQN, "summary": "s", "changes": []})

    assert first["id"] != second["id"]
    assert re.fullmatch(r"P-[0-9a-f]{6}", first["id"])
    assert ps.get("jury", first["id"]) is first
    assert ps.get("someone-else", first["id"]) is None
    assert ps.get("jury", "P-000000") is None


def test_public_view_hides_owner():
    ps = Proposals()
    p = ps.add(("jury", "c1"), {"entityType": "table", "fqn": FQN, "summary": "s",
                                "changes": [{"description": "T"}]})

    assert Proposals.public(p) == {"id": p["id"], "status": "proposed", "entityType": "table", "fqn": FQN,
                                   "summary": "s", "changes": [{"description": "T"}]}


def test_table_and_column_changes_become_json_patch_with_looked_up_index():
    ops, seen = patch_ops(proposal(changes=[{"description": "T"}, {"column": "b", "description": "B"}]))

    assert ops == [{"op": "add", "path": "/description", "value": "T"},
                   {"op": "add", "path": "/columns/1/description", "value": "B"}]
    assert len(seen) == 1
    assert seen[0].url.path == f"/api/v1/tables/name/{FQN}"
    assert seen[0].url.params["fields"] == "columns"
    assert seen[0].headers["Authorization"] == "Bearer tok"


def test_unknown_column_raises_value_error():
    with pytest.raises(ValueError, match="no column 'zzz'"):
        patch_ops(proposal(changes=[{"column": "zzz", "description": "x"}]))


def test_column_change_on_non_table_raises_value_error_without_calling_om():
    with pytest.raises(ValueError, match="only be proposed for tables"):
        patch_ops(proposal(entity_type="dashboard", changes=[{"column": "a", "description": "x"}]))


def test_empty_changes_raise_value_error():
    with pytest.raises(ValueError, match="no changes"):
        patch_ops(proposal(changes=[]))


def test_entity_only_change_makes_no_http_call():
    ops, seen = patch_ops(proposal(changes=[{"description": "T"}]))

    assert ops == [{"op": "add", "path": "/description", "value": "T"}]
    assert seen == []
