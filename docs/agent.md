# Agent and chat panel

How the catalog's AI agent works. Ground rules: metadata only, propose-then-apply, keyword search, the user's own token.

## Shape

- **Panel** (`product/openmetadata/proxy/static/chat.js` + `chat.css`): plain JS that Caddy injects into every OM page, like `catalog.js`. A gradient "✦ Ask AI" launcher opens a 460 px drawer on the right; the catalog stays usable beside it. Its left edge drags to any width (double-click resets; remembered in the browser); answers stay in an 860 px column when it is wide. Code blocks get a Copy button and highlighting (SQL keywords and functions; strings, numbers, comments in any language), escaped like all model output. The empty state offers the four demo questions; the transcript survives page changes and reloads (sessionStorage, per tab); "New chat" starts a fresh conversation. A proposal card appears above the answer text.
- **Search box entry** (same script): OM's `#searchBox` (navbar on every page, the big box on the home page) gets a first suggestion row "✦ Ask AI: <text>". Enter asks the AI when the text reads as a question (ends with "?", starts with a question or task word, or has five or more words; the row is highlighted then), otherwise OM's keyword search runs; Ctrl/⌘+Enter or a click always asks the AI. Sending clears the box and opens the drawer on the current page. The row sits inside OM's antd popover card (`.global-search-overlay` / `.customise-search-overlay` → `.ant-popover-inner-content`), re-inserted by a MutationObserver; when Enter asks the AI, OM's own "Press Enter to find data assets…" line is hidden. Enter is intercepted in the capture phase so OM's React handler never sees it.
- **Home and table pages** (`catalog.js`, through `window.agiAsk` / `window.agiOpen` that `chat.js` exposes): the home banner adds a one-line promise, three question chips and four cards (ask, trace a figure, document a table, the report's lineage); the search box placeholder offers the AI; a table page gets "✦ Ask about this table" and "✦ Document with AI" next to its name. A shortcut that needs another page first opens it with `?agi-ask=<question>`, which `catalog.js` asks once the page has rendered. On phones (≤ 768 px) OM's sidebar is hidden and the banner stacks.
- **Backend** (`product/agent/`, Compose service `agent` in `product/openmetadata/compose.yaml`, port 8000, `127.0.0.1:8600` on the host): FastAPI. Caddy routes `/agent/*` on the catalog's own origin to it (public site and `proxy-local`), unbuffered and uncompressed for streaming.
- **Model:** Claude Haiku 5.5 (`AGENT_MODEL` overrides), adaptive thinking at effort `low` (`AGENT_EFFORT`), prompt caching on, at most 10 LLM calls per question. Key: `ANTHROPIC_API_KEY` in `product/agent/.env`.

## Who the agent is

- The panel sends the user's OM session token: first the one OM's own API calls carry (it captures `Authorization` on OM's XHRs), else IndexedDB `AppDataStore` / `keyValueStore` / `app_state` → `primary`, where OM's service worker keeps it. It never refreshes the token itself (OM rotates the refresh token).
- The backend asks OM who the token belongs to (`/api/v1/users/loggedInUser`, cached 5 min) and forwards the token as `Authorization: Bearer` on every MCP call, so OM's own permissions apply; writes are recorded as the user, impersonated by `McpApplicationBot`.

## Tools the model sees

- From OM's MCP server (`POST /mcp`, stateless JSON-RPC): `search_metadata`, `get_entity_details`, `get_entity_lineage`, `root_cause_analysis`, `get_test_definitions`, `get_user_context`. Off: semantic search and Context Center tools (keyword search only), `create_*`, `patch_entity` (writes go through Apply).
- `propose_change` (ours): table and column descriptions as a proposal. Nothing is written; the panel shows a card with Apply / Discard. Apply looks up column indexes in OM and calls `patch_entity` with JSON Patch `add` ops under the user's token.
- OM fits every reply into its own 100,000-char budget with paging markers, but a batch over it comes back as a bare "withheld" envelope. The backend slims every `get_entity_details` reply (drops the compiled SQL copy — `rawSql` keeps dbt's `config` —, the markdown `context`, joins, ids and empty fields: a table read goes from ~20K to ~8K chars) and re-reads a withheld batch one entity at a time in parallel. It cuts above 120,000 chars as a backstop only.

## API

- `POST /agent/chat` `{conversation_id, message, page}` → server-sent events: `text` (answer chunks), `tool` (status line), `proposal` (card), `error`, `done` (LLM calls, tool calls, tokens, cost, seconds). `page` is the OM path; `/table/<fqn>` and similar become a hint ("the user is viewing …") so "document this table" works.
- `POST /agent/proposals` `{proposal_id, action: apply|discard}`; only the proposal's owner may decide, once.
- `GET /agent/health`.
- `GET /agent/demo-login` → `{email, password}` for the sign-in page's "✦ Sign in as jury" button (`catalog.js`: shows the login under the form, fills it and submits on one tap). Compose passes `DEMO_LOGIN_EMAIL` (`jury@agi.uz`) and `DEMO_LOGIN_PASSWORD` (from `OM_JURY_PASSWORD` in the catalog's `.env`); 404 when the password is unset, which hides the button.
- Conversations live in the agent's memory per (user, conversation); a restart forgets them. A failed or abandoned turn is rolled back, so history never holds a tool call without its result. Apply / Discard outcomes are passed to the model on the next turn.

## Journal

`/data/journal.jsonl` (volume `agent-data`): one line per question (user, conversation, page, question, answer, tool calls with sizes and times, tokens, cost, seconds) and per Apply / Discard. Never the token. It is the audit trail and the input for the evaluation.

## Prompt

`product/agent/src/agi_agent/prompts/system.md`: role, ground rules, catalog map (layers, glossary, metrics, articles, PII tag, contract), playbooks for the four demo questions, SQL drafting rules (Greenplum, marts, units, no `PII.Sensitive` columns unless needed), answer style (short answer first, fully qualified names in backticks — the panel links tables and glossary terms).

## Measured

`product/agent/eval/`: `cases.json` (question, page, regexes the answer must and must not contain, proposal expected) and `run.py` (signs in as jury on the local catalog, runs each case through the live API, prints pass/fail, LLM calls, seconds, cost; results in `eval/results/`, gitignored). Run: `cd product/agent && uv run python eval/run.py --base http://localhost:8590 --runs 2`.

Latest (container through `proxy-local`, 10k data, Haiku 5.5, effort `low`): 7/7 passed, median 9.1 s, slowest 19.6 s (document this table), mean $0.0045 per question.

| Case                      | LLM calls | Seconds | Cost    |
| ------------------------- | --------- | ------- | ------- |
| q1 how is overdue decided | 2         | 9       | $0.006  |
| q2 91–180 figure, checks  | 3         | 12      | $0.006  |
| q3 PINFL, may I use it    | 3         | 14      | $0.006  |
| q4 document this table    | 4         | 18–20   | $0.007  |
| owner of the report       | 2         | 3       | $0.0004 |
| NPL 90+ ratio with SQL    | 3         | 8       | $0.004  |
| a figure it cannot see    | 2         | 6       | $0.002  |

## Tests

`cd product/agent && uv run pytest -q`: offline unit tests (tool set, page hints, identity check, proposals → JSON Patch, MCP client framing and errors). End to end: the four demo questions through `proxy-local` (<http://localhost:8590>).
