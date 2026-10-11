# Catalog

Design of the OpenMetadata deployment in `product/openmetadata/`. Stock OpenMetadata 2.0.5 images, no fork; everything we add sits beside it (agent, chat panel) or on top of an official image (one backported fix).

## Stack

`product/openmetadata/compose.yaml`, project `agi-catalog`, based on the official 2.0.5 `docker-compose-postgres.yml`.

| Service               | Image (`openmetadata/…` unless noted)   | Role                                                    |
| --------------------- | --------------------------------------- | ------------------------------------------------------- |
| `postgresql`          | `postgresql:2.0.5`                      | catalog DB `openmetadata_db`, ingestion's `airflow_db`  |
| `elasticsearch`       | `elasticsearch:9.3.0` (Elastic)         | search indexes                                          |
| `keys`                | `postgresql:2.0.5` (for its `openssl`)  | one-shot: JWT RSA key pair into volume `jwt-keys`       |
| `execute-migrate-all` | `server:2.0.5`                          | one-shot: schema migration, exits 0                     |
| `openmetadata-server` | `server:2.0.5`                          | API + UI, `127.0.0.1:8585`                              |
| `ingestion`           | `agi-catalog/ingestion:2.0.5-pr32031`   | OM's Airflow running ingestion, `127.0.0.1:8080`        |

Differences from upstream:

- **Env holds only what differs from the image's `conf/openmetadata.yaml` defaults** (anchor `x-om-env`, shared by migrate and server): Postgres instead of MySQL, in-network hosts, our secrets, self-signup off. Upstream's ~130 variables restate defaults. Ingestion needs only its Airflow DB location; executor, `load_examples` and the DAG config path are image defaults.
- **Own secrets instead of the public defaults.** Upstream signs JWTs with `conf/private_key.der` from the public repo and ships a fixed Fernet key, so anyone could mint admin tokens for a public URL. The `keys` service generates a fresh RSA pair on first start (skips if present; files owned by the server's uid 1000, private key `400`); `OM_FERNET_KEY` and `OM_ADMIN_PASSWORD` come from the gitignored `.env` (names in `.env.example`). The admin password goes in as `AUTHORIZER_ADMIN_PRINCIPALS=[admin:<password>]`, which the server applies only when it first creates the admin; later changes go through the UI. Internal DB passwords stay upstream's: those ports are never published.
- **Ingestion image** = official image + backport of open-metadata/OpenMetadata#32031 (issue #32030): usage ingestion looked Queries up by bare hash while their FQN is `service.hash`, so a repeated query was re-created and lost its links to earlier tables. Merged to `main`, not in 2.0.x. `ingestion/backport_32031.py` replaces the exact 2.0.5 text and fails the build if upstream changed it; drop it with the first 2.0.x release containing the fix. The image also deletes upstream's six sample-data DAGs.
- **Ports:** only `127.0.0.1:8585` (UI/API, stock OM), `127.0.0.1:8590` (`proxy-local`: the same UI with the proxy's injection, as the jury sees it) and `127.0.0.1:8080` (ingestion Airflow, debugging). Postgres and Elasticsearch are not published.
- **Lab access:** only `ingestion` joins `agi-lab_default` (external): start the lab first. The server never talks to the lab.
- Named volumes, no `container_name`, no fixed subnet; `restart: unless-stopped`.

Run (from `product/openmetadata/`, after `cp .env.example .env` and generating each value):

```bash
docker compose up -d --build --wait
```

Log in at <http://localhost:8585> as `admin@open-metadata.org` with `OM_ADMIN_PASSWORD`.

## Catalog as code

Teams, services, their ingestion pipelines and the catalog's content are declared in the repo, not clicked in the UI: `product/openmetadata/catalog/` holds `teams.json`, `users.json` (the shared demo account `demo@agi.uz`, role Data Steward, password `OM_DEMO_PASSWORD` from `.env`, set only when the user is first created), one JSON file per service in `services/` and the content in `content/`, applied by `apply.py` + `content.py` (standard library only), which log in as admin and create or update everything through the API (PUT and minimal JSON patches, so a rerun changes nothing) and deploy the pipelines to `ingestion`. Every deploy runs `apply.py`; `--run` also triggers the pipelines stage by stage and waits: 1 metadata, 2 dbt (needs the tables), 3 usage and Airflow, then the source → `ext__` lineage and the content, then 4 profiler. The catalog stores no sample data: `apply.py` deletes any it finds and removes pipelines no longer declared. `--trigger <pipeline>…` runs only the named pipelines, `--content` only the content. Pipelines show and run in OM's own UI on their schedules.

```bash
python3 product/openmetadata/catalog/apply.py --run   # on the server; --url for another endpoint
```

- **Teams and owners.** `data_platform` (DWH, marts, catalog; owner of every dbt model via `meta.owner`: marts in their config, ODS in `dbt_project.yml`), `regulatory_reporting` (CB report mart), and one team per source system that owns its service and databases: `core_banking` (iabs), `cards_and_lending` (tranzaxis), `digital_banking` (mobile). OM inherits a database's owner down to schemas and tables that name none, so `ext__*` tables show Data Platform and source tables their system's team.
- Database services `iabs`, `mobile`, `tranzaxis` (PostgreSQL, user `openmetadata`, story schemas only): metadata, usage (`pg_stat_statements`), profiler. Source tables are documented in their own DDL (`COMMENT ON`, `lab/sources/init/`); `tools/deploy/deploy.sh` replays those comments on every deploy, since init scripts run only on an empty volume.
- `greenplum` (database `dwh`, user `openmetadata`, schemas `ext__*`, `ods__*`, `datamart*`, `dictionary`): metadata, dbt, profiler (`ods__*`, marts, dictionaries; never `ext__*`, which would read the sources live). OM's Greenplum connector has no usage or query-lineage support; warehouse lineage comes from dbt. The dbt pipeline reads `catalog/manifest.json` (compiled SQL: OM parses each model's `create table … as <compiled SQL>` into **column-level lineage**) and `target/run_results.json` (test results) from the lab's `dbt-state` volume, mounted read-only into `ingestion` at `/opt/lab/dbt-state`; both are written by the last tasks of `dbt__cod` (`lab.md`, Orchestration). Descriptions and owners from dbt overwrite the catalog's (`dbtUpdateDescriptions`, `dbtUpdateOwners`).
- Pipeline service `lab_airflow` (Airflow REST API at `airflow-apiserver:8080`, basic auth), excluding `sim__*`.
- **Descriptions are written in dbt YAML and pulled by OM** from the manifest; OM takes column types from Greenplum itself, so no `catalog.json` is needed. `content.py` carries an ODS column's description up the 1:1 column lineage to its `ext__` table and the source column when those have none (never overwrites).

**Content** (`content/`, applied after the services):

| File | What it creates |
| --- | --- |
| `domains.json` | 6 domains (Lending, Deposits, Cards & Payments, Customers, Core Ledger, Regulatory Reporting) and their tables across source, `ext__`, ODS and marts |
| `governance.json` | tiers (Tier1: the CB report, the classification hub, metrics, the PII hub; Tier2 other marts; Tier3 ODS) and `PII.Sensitive`: declared on the source columns, then followed down the column lineage to every column the value reaches unchanged (same name or a declared rename), labelled `Propagated` |
| `glossary.json` | glossary `banking`, 23 terms, linked to tables and columns |
| `metrics.json` | 15 metrics, one per `metric_key` of `datamart.metrics_daily`, with SQL, unit, related metrics and a lineage edge from `metrics_daily` |
| `articles.json`, `articles/*.md` | 4 Context Center articles (`/v1/contextCenter/pages`): contract classification, Overdue Loans Report, closing of day, customer identity |
| `contracts.json` | data contract on `datamart.clients_id_xref`: personal-data terms of use, SLA, its PINFL tests as quality expectations |

`datamart.customer_segments` stays without description, tier, domain and glossary links on purpose (demo question 4); its PINFL still gets `PII.Sensitive` from lineage.

## Public entry

Service `proxy` (Caddy 2.10, Compose profile `public`: started only by `tools/deploy/deploy.sh` on `agi-demo`, so a plain `up` elsewhere leaves it out) publishes 80/443 and terminates HTTPS for `157-22-137-126.sslip.io` (sslip.io resolves the name to the server's IP; Let's Encrypt certificate, obtained and renewed automatically, state in volume `proxy-data`), proxying to `openmetadata-server:8585`. Self-signup stays off; the jury signs in with the shared jury account.

The proxy also injects `proxy/static/` (served at `/_agi/`, config in `proxy/catalog.caddy`) into OM's HTML, through the `replace-response` module of a Caddy build pinned in `proxy/Dockerfile`, so OM's UI stays stock: the sign-in video panel is hidden. `catalog.js` marks the first-visit prompts (welcome screen, what's-new alert, GitHub star card) seen for whichever user and version the API returns (`/users/loggedInUser`, `/system/version`), so they stay hidden for any account, including ones created later. Service `proxy-local` (`proxy/Caddyfile.local`, plain HTTP on `127.0.0.1:8590`) serves the same injection without certificates.

## Source → DWH lineage

A script pushes source table → `ext__<source>` edges, column level by name, through the OM lineage API, computed from `pg_exttable.urilocation` (`lab.md`, Warehouse). `apply.py --run` runs it after the metadata, dbt, usage and Airflow pipelines have been ingested.
