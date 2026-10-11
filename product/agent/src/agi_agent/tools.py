"""The tools the model sees: a curated subset of OM's MCP tools with safe defaults, plus propose_change."""

import json

# Read tools only: writes go through propose_change and the user's Apply. Semantic search and Context Center tools
# stay off (keyword search only); create_* are out of scope.
MCP_TOOLS = ["search_metadata", "get_entity_details", "get_entity_lineage", "root_cause_analysis",
             "get_test_definitions", "get_user_context"]

# OM fits columns, hits and lineage edges into its own 100,000-char budget with paging markers; this cut is a backstop.
MAX_RESULT_CHARS = 120_000
MAX_DESCRIPTION_CHARS = 4_000

PROPOSE_CHANGE = {
    "name": "propose_change",
    "description": (
        "Propose a change to one catalog entity (for example descriptions for an undocumented table and its "
        "columns). The change is NOT applied: the user sees it as a card with Apply / Discard, and only Apply "
        "writes it to the catalog under their own account. Call get_entity_details first so column names are "
        "exact. After calling it, tell the user the proposal is waiting for their Apply; never say it is applied."),
    "input_schema": {
        "type": "object",
        "properties": {
            "entityType": {"type": "string", "description": "Entity type, e.g. table"},
            "fqn": {"type": "string", "description": "Fully qualified name of the entity"},
            "summary": {"type": "string", "description": "One sentence: what the change does"},
            "changes": {
                "type": "array",
                "description": "Descriptions to set. Omit column for the entity's own description.",
                "items": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string", "description": "Column name, or omit for the entity"},
                        "description": {"type": "string", "description": "New description (markdown)"},
                    },
                    "required": ["description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["entityType", "fqn", "summary", "changes"],
        "additionalProperties": False,
    },
}


def model_tools(mcp_tools: list[dict]) -> list[dict]:
    """Anthropic tool definitions, in a fixed order so the prompt cache prefix stays stable."""
    by_name = {t["name"]: t for t in mcp_tools}
    out = []
    for name in MCP_TOOLS:
        t = by_name.get(name)
        if t is None:
            continue
        out.append({
            "name": name,
            "description": (t.get("description") or "")[:MAX_DESCRIPTION_CHARS],
            "input_schema": t.get("inputSchema") or {"type": "object", "properties": {}},
        })
    return out + [PROPOSE_CHANGE]


# Parts of an OM entity the model never needs: the compiled SQL repeats rawSql (which keeps dbt's config block),
# `context` re-renders the columns as markdown, and joins/usage are query-log statistics.
DROP_KEYS = {"context", "joins", "usageSummary", "customMetrics", "children", "dataLength", "ordinalPosition",
             "href", "id", "serviceType", "deleted", "entityStatus"}
REF_KEYS = {"service", "database", "databaseSchema"}


def _prune(value):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in DROP_KEYS:
                continue
            if k in REF_KEYS and isinstance(v, dict):
                v = v.get("fullyQualifiedName") or v.get("name")
            v = _prune(v)
            if v in (None, "", [], {}) or (k == "constraint" and v == "NULL"):
                continue
            out[k] = v
        return out
    if isinstance(value, list):
        return [_prune(v) for v in value]
    return value


def slim_entity(entity: dict) -> dict:
    entity = dict(entity)
    model = entity.get("dataModel")
    if isinstance(model, dict) and model.get("rawSql"):
        entity["dataModel"] = {k: v for k, v in model.items() if k not in ("sql", "columns")}
    return _prune(entity)


def slim_details(text: str) -> str:
    """get_entity_details result, slimmed; text that is not entity JSON (errors, envelopes) passes through."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if not isinstance(data, dict) or data.get("truncated"):
        return text
    if isinstance(data.get("entities"), list):
        data["entities"] = [slim_entity(e) if isinstance(e, dict) else e for e in data["entities"]]
    else:
        data = slim_entity(data)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def is_withheld(text: str) -> bool:
    """OM's envelope for a reply over its size budget: nothing of the content comes back."""
    return text.startswith("{") and '"truncated":true' in text[:200] and '"responseSizeChars"' in text[:300]


def clip_result(text: str) -> str:
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return (text[:MAX_RESULT_CHARS] + f"\n[cut by the agent at {MAX_RESULT_CHARS} of {len(text)} chars; "
            "ask for fewer entities at once]")


def status_label(name: str, args: dict) -> str:
    """One line for the panel while a tool runs."""
    fqn = args.get("fqn") or ""
    if name == "search_metadata":
        q = args.get("query") or args.get("entityType") or ""
        return f"Searching the catalog: {q}".rstrip(": ")
    if name == "get_entity_details":
        names = args.get("entities") or ([fqn] if fqn else [])
        shown = ", ".join(str(n).split(":", 1)[-1] for n in names[:3])
        return f"Reading {shown}" + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    if name == "get_entity_lineage":
        return f"Tracing lineage of {fqn}"
    if name == "root_cause_analysis":
        return f"Checking data quality upstream of {fqn}"
    if name == "get_test_definitions":
        return "Reading test definitions"
    if name == "get_user_context":
        return "Looking up your assets"
    if name == "propose_change":
        return f"Drafting a change to {fqn}"
    return name


def preview(args: dict) -> str:
    return json.dumps(args, ensure_ascii=False)[:300]
