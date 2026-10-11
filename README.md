# AGI — data catalog with a built-in AI agent

A data catalog for banks with an AI agent built in, running inside the bank's perimeter. Anyone who takes data from the warehouse (analysts, risk, regulatory reporting, developers) asks in plain language where a figure comes from, how it is computed, which checks it passed and whether a column may be used, and gets an answer grounded in the catalog, with links. The agent can also document an undocumented table; a person reviews the proposal and applies it, and the catalog records who changed what.

WIUT Hackathon 2026 · FinTech / AI in Finance · team AGI (ref. 70630E22)

## Try it

- Live: <https://157-22-137-126.sslip.io>
- Sign in as `jury@agi.uz`, password in the defence deck and the submission message (Data Steward: can read everything and edit descriptions, cannot delete or reconfigure).
- Click **✦ Ask AI** (or type a question into the search box and press Enter), e.g.:
  - How is a contract classified as overdue, and how are days past due counted?
  - Where does the 91–180 days figure in the overdue loans report come from, and which checks did it pass?
  - Where is the customer's PINFL stored, and may I use it?
  - On an undocumented table (`customer_segments`): "Document this table" → review the proposal → Apply.

## How it works

```text
 source systems (Postgres: iabs, mobile, tranzaxis)
        │  PXF external tables
        ▼
 Greenplum DWH ── Liquibase DDL ── dbt (ODS → marts → CB overdue loans report, tests) ── Airflow
        │  metadata, dbt, lineage, usage, profiler, test results
        ▼
 OpenMetadata 2.0.5 (stock images) + catalog as code (owners, domains, glossary, metrics, PII tags, contracts, articles)
        ▲  MCP tools under the user's own token
        │
 agent (FastAPI, Claude Haiku 5.5) ◄── chat panel injected into the catalog UI by Caddy
```

- **The fictional bank** (`lab/`): three source systems, a Greenplum warehouse with ODS, marts and a central-bank overdue loans report, 324 dbt tests, Airflow running one operating day at a time. All data is synthetic, from a seeded generator. Details: [docs/lab.md](docs/lab.md), [docs/story.md](docs/story.md).
- **The catalog** (`product/openmetadata/`): stock OpenMetadata, configured entirely from the repo: column-level lineage from the sources to the report, PII tags following lineage, a data contract, glossary, metrics and articles. Details: [docs/catalog.md](docs/catalog.md).
- **The agent** (`product/agent/`): uses OpenMetadata's own MCP tools under the asking user's token, so the catalog's permissions apply. Metadata only: it never queries the warehouse. Changes are proposed, never written until a person clicks Apply. Every question is journaled (tokens, cost, time, tool calls). Details: [docs/agent.md](docs/agent.md).
- **Perimeter:** everything runs on the bank's own servers except the model API. The model is swappable for a self-hosted one; the prototype uses the Anthropic API.

## Evaluation

`product/agent/eval/`: 7 cases with must and must-not checks on the answer, run against the live catalog.

| Result    | Value                        |
| --------- | ---------------------------- |
| Passed    | 7 / 7                        |
| Median    | 9 s                          |
| Slowest   | 19.6 s (document this table) |
| Mean cost | $0.0045 per question         |

Unit tests: `cd product/agent && uv run pytest -q`.

## Run it locally

Needs Docker with at least 12 GB of memory and [uv](https://docs.astral.sh/uv/). Images build for amd64 and arm64.

1. `uv sync --all-groups`
1. Generate the data: `uv run --group generator python lab/generator/generate.py --scale 10000`
1. Start the bank: `cd lab && docker compose up -d --build --wait` (Greenplum's first start takes minutes), then play the operating days: `lab/ops/labbackfill 2026-08-01 2026-09-30` ([docs/lab.md](docs/lab.md)).
1. Secrets: `cp product/openmetadata/.env.example product/openmetadata/.env` and `cp product/agent/.env.example product/agent/.env`, then fill in the values (each file says how).
1. Start the catalog: `cd product/openmetadata && docker compose up -d --build --wait`, then `python3 product/openmetadata/catalog/apply.py --run` (~10 min).
1. Open <http://localhost:8590> (the catalog with the chat panel) and sign in with the jury account.

Deployment to the demo server runs from GitHub Actions on demand: [product/README.md](product/README.md).

## Data sources

- All bank data is **synthetic**, produced by `lab/generator/` (seeded, reproducible). No real customer or bank data is used.
- Reference lists in `lab/generator/reference/` (regions and districts, currencies, public holidays, card merchant category codes, mobile operator prefixes, Uzbek first names and surnames, a chart of balance accounts) were generated with an LLM (Claude) as synthetic lists from general public knowledge; frequencies and weights are invented.

## Built with

| Component | Licence |
| ---------------------------------- | ----------- |
| OpenMetadata 2.0.5 (images; compose based on upstream's; one upstream fix backported, open-metadata/OpenMetadata#32031) | Apache-2.0 |
| Greenplum (`woblerr/opengpdb` image), PXF, PostgreSQL JDBC | Apache-2.0, BSD-2-Clause |
| PostgreSQL | PostgreSQL License |
| dbt Core, dbt-postgres; dbt_utils, dbt_expectations, dbt_date | Apache-2.0 |
| Apache Airflow | Apache-2.0 |
| Liquibase | FSL-1.1-ALv2 |
| Caddy, replace-response | Apache-2.0 |
| FastAPI, httpx, uvicorn, numpy, polars | MIT, BSD-3-Clause |
| Anthropic Python SDK; Claude Haiku 5.5 via the Anthropic API (paid, in the cost model) | MIT; commercial API |

## Licence

Apache-2.0 ([LICENSE](LICENSE)).
