# Agent

AI chat backend for the catalog: Claude Haiku 5.5 + OpenMetadata's MCP tools under the asking user's token, streamed to the chat panel (`../openmetadata/proxy/static/chat.js`). Design: [docs/agent.md](../../docs/agent.md).

- Runs as Compose service `agent` in `../openmetadata/compose.yaml`; Caddy routes `/agent/*` to it. Key: `ANTHROPIC_API_KEY` in `.env`.
- Rebuild after a code change: `docker compose -f product/openmetadata/compose.yaml up -d --build agent` (from the repo root).
- Tests: `uv run pytest -q` (offline).
- Dev server against the local catalog: `OM_URL=http://localhost:8585 uv run --env-file .env uvicorn agi_agent.app:app --port 8601`.
- Journal: `docker exec agi-catalog-agent-1 tail -f /data/journal.jsonl`.
