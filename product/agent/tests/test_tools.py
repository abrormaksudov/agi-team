import json

from agi_agent.tools import (
    MAX_DESCRIPTION_CHARS,
    MAX_RESULT_CHARS,
    MCP_TOOLS,
    clip_result,
    is_withheld,
    model_tools,
    slim_details,
    status_label,
)


def mcp_tool(name, description="A tool.", schema=None):
    return {"name": name, "description": description, "inputSchema": schema or {"type": "object"}}


def test_model_tools_keeps_curated_tools_in_fixed_order_and_appends_propose_change():
    listed = [mcp_tool("create_entity"), *(mcp_tool(n) for n in reversed(MCP_TOOLS))]

    tools = model_tools(listed)

    assert [t["name"] for t in tools] == [*MCP_TOOLS, "propose_change"]


def test_model_tools_skips_curated_tools_that_om_does_not_list():
    tools = model_tools([mcp_tool("search_metadata")])

    assert [t["name"] for t in tools] == ["search_metadata", "propose_change"]


def test_model_tools_truncates_description_and_renames_input_schema():
    schema = {"type": "object", "properties": {"fqn": {"type": "string"}}}
    long = "x" * (MAX_DESCRIPTION_CHARS + 50)

    tool = model_tools([mcp_tool("search_metadata", long, schema)])[0]

    assert tool["description"] == "x" * MAX_DESCRIPTION_CHARS
    assert tool["input_schema"] == schema
    assert "inputSchema" not in tool


def test_clip_result_leaves_short_text_alone():
    at_limit = "x" * MAX_RESULT_CHARS

    assert clip_result("hello") == "hello"
    assert clip_result(at_limit) == at_limit


def test_clip_result_cuts_long_text_and_says_so():
    text = "y" * (MAX_RESULT_CHARS + 10)

    out = clip_result(text)

    kept, note = out.split("\n", 1)
    assert kept == text[:MAX_RESULT_CHARS]
    assert f"cut by the agent at {MAX_RESULT_CHARS} of {len(text)} chars" in note


def test_status_label_search_with_query():
    assert status_label("search_metadata", {"query": "orders"}) == "Searching the catalog: orders"


def test_status_label_search_without_query():
    assert status_label("search_metadata", {}) == "Searching the catalog"


def test_status_label_entity_details_for_one_fqn():
    assert status_label("get_entity_details", {"fqn": "table:greenplum.dwh.x"}) == "Reading greenplum.dwh.x"


def test_status_label_entity_details_for_five_entities_shows_three_and_count():
    entities = [f"table:db.s.t{i}" for i in range(5)]

    label = status_label("get_entity_details", {"entities": entities})

    assert label == "Reading db.s.t0, db.s.t1, db.s.t2 and 2 more"


def test_status_label_lineage_uses_fqn():
    assert status_label("get_entity_lineage", {"fqn": "greenplum.dwh.x"}) == "Tracing lineage of greenplum.dwh.x"


def test_slim_details_drops_duplicates_and_keeps_raw_sql():
    entity = {"name": "t", "id": "x", "context": "# markdown copy", "joins": {"a": 1},
              "service": {"name": "greenplum", "fullyQualifiedName": "greenplum", "id": "s"},
              "dataModel": {"rawSql": "{{ config(materialized='incremental') }} select 1", "sql": "select 1",
                            "columns": [{"name": "a"}]},
              "columns": [{"name": "a", "constraint": "NULL", "children": [], "description": "A", "tags": []}]}

    slim = json.loads(slim_details(json.dumps(entity)))

    assert slim == {"name": "t", "service": "greenplum",
                    "dataModel": {"rawSql": "{{ config(materialized='incremental') }} select 1"},
                    "columns": [{"name": "a", "description": "A"}]}


def test_slim_details_passes_envelopes_and_non_json_through():
    envelope = '{"tool":"get_entity_details","truncated":true,"responseSizeChars":105085,"maxResponseChars":100000}'

    assert slim_details(envelope) == envelope
    assert is_withheld(envelope)
    assert slim_details("not json") == "not json"
    assert not is_withheld('{"name": "t"}')
