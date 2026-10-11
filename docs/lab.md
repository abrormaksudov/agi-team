# Lab

Design of the fictional bank in `lab/`: services, users and pipes, plus the source tables, data and mapping described in `story.md`.

## Landscape

```text
iabs (core banking)   mobile (app backend)   tranzaxis (card processing)
        └──────────── PXF ──────┴────────── PXF ──────────┘
                               ▼
              Greenplum DWH ── dbt (ods → marts) ── Airflow
                               ▼
                    CB regulatory reports
                               ▼
                       OpenMetadata catalog
```

## Source systems

One PostgreSQL 17 container per system, defined once in `lab/compose.yaml` (project `agi-lab`) through the `x-source-db` anchor; all share the init folder `lab/sources/init/`.

| Service / DB | System                                            | Port (127.0.0.1) |
| ------------ | ------------------------------------------------- | ---------------- |
| `iabs`       | iABS (Fido-Biznes), core banking                  | 5434             |
| `mobile`     | in-house mobile banking backend                   | 5435             |
| `tranzaxis`  | TranzAxis (Compass Plus), retail credit and cards | 5436             |

Users, identical on every system (lab-only passwords, committed in the init scripts):

| User           | Who               | Rights                                  |
| -------------- | ----------------- | --------------------------------------- |
| `admin`        | DDL, init         | superuser                               |
| `loader`       | CSV loader DAG    | `pg_read_all_data`, `pg_write_all_data` |
| `pxf`          | Greenplum via PXF | `pg_read_all_data`                      |
| `openmetadata` | catalog ingestion | `pg_read_all_data`, `pg_read_all_stats` |

Built-in roles cover schemas created later, so story tables need no grants. `pg_stat_statements` is preloaded and installed in each system's database for OM query usage. Story schemas (tables in `story.md`) come from `10_mobile.sql` (`users`, `devices`, `kyc`), `11_iabs.sql` (`core`) and `12_tranzaxis.sql` (`tx`); each skips itself (`\if`) in the other databases, so all three share one init folder.

Init runs only on an empty volume: to change users or schemas, remove the source volumes and start again.

**Data:** `lab/generator/` writes `lab/data/<source>/<oper_day>/<schema>.<table>.csv` (gitignored; seeded, so a fresh clone regenerates it): `uv run --group generator python lab/generator/generate.py --scale 10000`. Day 0 (2026-07-31) carries all history; 2026-08-01 … 2026-09-30 carry each day's new and changed rows. Design in `story.md`.

## Warehouse

Greenplum 6.29 single node (`greenplum`, database `dwh`, 127.0.0.1:5433), built from `lab/greenplum/Dockerfile` on `woblerr/opengpdb`. Conventions of a typical bank DWH (Greenplum + dbt + Airflow + Liquibase): layering, naming, DDL and access model.

**PXF.** Greenplum reads sources through PXF: an external table holds no data, only an address (`pxf://core.account?profile=jdbc&server=iabs`); every `select` queries the source live over JDBC. One PXF server per source system (`lab/greenplum/pxf/servers/<source>/jdbc-site.xml`, user `pxf`). The image's init hook, run once on first start after PXF is up, installs the servers and the pgJDBC jar (PXF 6.10 ships none) and restarts PXF; a marker file gates the healthcheck. It also trusts `gpadmin` from `samehost` above the image's catch-all md5 rules: gpinitsystem trusts only the container's first IP, so a restart with a new IP made the image's `pxf cluster start` fail and the container restart-loop.

**Layers.** `ext__<source>` (PXF external tables) → `ods__<source>` → `datamart`, `dictionary`, `datamart_regtech` (CB reports). No `stg`: it is for pushed data (Kafka, files), and all three sources are pulled through PXF, so dbt sources point straight at `ext__<source>`.

**DDL: Liquibase 5.0.** `lab/liquibase/ddl/`, one changelog per file; the one-shot `liquibase` service (`deploy.sh`) builds a master changelog including every file in byte order and applies it in one run on every `up` (seconds; a run per file took minutes); journal in schema `liquibase`.

- `_init/_core.sql` — global reader roles and login users; `_init/<source>.sql` — the source's level role and its `ext__`/`ods__` schemas, each `create schema` with its `grant usage`; `_init/<schema>.sql` for shared schemas. `_` sorts first, so `_init` runs before table DDL.
- `ext/<source>/ext__<source>__<table>.sql` — external tables, `drop` + `create`, `runAlways:true`.
- Every object owned by `gpadmin`; Liquibase and dbt connect as `gpadmin`.

**Access.** Schema `usage` through core roles: `read__prod` (`ods__*`, `datamart`, `dictionary`), `read__prod_tech` (`ext__*`). Table `select` only through level roles (`l2__<source>__bs`), issued by dbt `grants` config, never in DDL. Login `openmetadata` is a member of the core roles and every level role. Greenplum 6 is PostgreSQL 9.4: no `pg_read_all_data`.

**Source → `ext__` lineage.** dbt gives OM every edge from `ext__<source>` onward, column level included. The one hop it cannot know is source system → `ext__<source>` table: OM reads an external table as a plain Greenplum table. It is computable from each external table's `location`: `pg_exttable.urilocation` gives `server=<source>` and `pxf://<schema>.<table>`; a script pushes those edges, column level by name, through the OM lineage API after both services are ingested (`catalog.md`).

## Transformations

dbt Core 1.12.5 + dbt-postgres 1.11.0, project `lab/dbt/dwh`, profile `lab/dbt/profiles.yml` (target `lab`, `gpadmin`, default schema `dbt`; `DBT_HOST`/`DBT_PORT` override the in-network host for runs from the host). Python deps in the root `pyproject.toml`, group `dbt`. From the host: `DBT_HOST=127.0.0.1 DBT_PORT=5433 DBT_PROFILES_DIR=.. uv run --group dbt dbt build` in `lab/dbt/dwh`.

- **Liquibase creates every table, dbt only fills it.** ODS/datamart DDL lives in `lab/liquibase/ddl/<layer>/<source>/`; models are `incremental` with an explicit strategy (`truncate+insert`, `delete+insert` with `unique_key`, `append`) and `on_schema_change="fail"`, so the DDL is the contract. No `is_incremental()` guards.
- **Layout.** `sources/<source>.yml` (schema `ext__<source>`); `models/ods/<source>/ods__<source>__<table>.sql` + `.yaml`, one model per file, `alias` and `schema` explicit.
- **ODS load strategy per table.** Current-state tables (reference data, customers, accounts, contracts, schedules, statements — anything a later day rewrites without a change stamp) reload in full every day (`truncate+insert`, tested with `equal_row_count` against the source). Daily facts (`account_balance`, `payment_document`, `account_turnover`, `card_transaction`, `delinquency_history`, `login_event`) load the day being closed (`delete+insert` by the day column, or by `event_id`): macros `day_filter(col)` and `ts_window_filter(ts)` compare the raw column so PXF pushes the filter to the source. On var `history_day` (2026-07-31, the snapshot whose files carry all history) they load everything up to that day.
- **PXF types.** uuid and inet are text in the external table and cast back in the ODS model; every other type (incl. timestamptz) reads natively.
- **Marts** (`models/datamart/`, `models/dictionary/`, `models/datamart_regtech/`): per-day marts are `delete+insert` on `report_date` and compute the state as of `oper_day`; level roles `l3__datamart__bs`, `l3__dictionary__bs`, `l3__datamart_regtech__bs`. Cross-model checks are singular tests in `tests/`.
- **Model shape.** Config order `tags` → `meta` → `materialized` → `incremental_strategy` → `unique_key` → `on_schema_change` → `alias` → `schema` → `distributed_by` → `pre_hook` → `grants`; `grants={ "select": [ "l2__<source>__bs" ] }`; last two columns `dwh_job_id` (from `var`) and `dwh_created_at` (`now()`). `meta.owner` required on `datamart*`.
- **Tests** in YAML under `data_tests:`, dict form with explicit `name` (`<model>__<test>_<col>`, table-level `<model>__<descriptive>`); `equal_row_count` only on full-reload models. Results go to `dbt_test__audit.dq_test_log` (written by the Airflow runner).
- **Macros:** `create_table_as`, `storage_parameters`, `distribution`, `get_delete_insert_merge_sql`, `get_incremental_truncate_insert_sql`, `smart_analyze` (global post-hook), `uzt`, `generate_schema_name`, `get_grant_sql`, `get_revoke_sql`. Packages `dbt_utils`, `dbt_expectations`, `dbt_date`. Not included: `automate_dv`, `dbt_project_evaluator` (its models would land in the catalog), a `ci` target, CDC, `microbatch_load`, snapshots.
- Vars `dwh_job_id`, `load_from_datetime`, `load_to_datetime`, `oper_day`; tags name the schedule (`daily`, `hourly`, `cod`) and pick the `dbt__<tag>` DAG.

## Orchestration

Airflow 3.3.2, LocalExecutor, services per the official compose minus Celery: `airflow-db` (own Postgres, not in the catalog), one-shot `airflow-init` (DB migrate, FAB `admin` user, `dbt deps` + `dbt parse` into the shared `dbt-state` volume so the manifest exists before DAG parsing), `airflow-apiserver` (127.0.0.1:8081, REST API for OM), `airflow-scheduler`, `airflow-dag-processor`. Image `lab/airflow/Dockerfile`, built from the repo root: the official image plus dbt in its own venv from the `dbt` dependency group, JSON dbt logs. Connections `greenplum`, `iabs`, `mobile`, `tranzaxis` as `AIRFLOW_CONN_*` in compose. Deployment-level `catchup` off, `max_active_runs` 1, timezone Asia/Tashkent.

- **`dbt__<tag>` factory** (`_dbt__common_dag` / `_dbt.py`): tags in `_dbt__common_dag.yml`; one task per model, `task_id` = model name, order from the manifest's `ref()` graph; each task runs `dbt build --select <model>` with `dwh_job_id` = run id and the operating day as `oper_day` plus a whole-UZT-day `load_from_datetime`/`load_to_datetime`; test results go to `dbt_test__audit.dq_test_log`, flushed even when the build fails. After the models, for the catalog (both run even after a failure): `compile_for_catalog` writes a manifest with every model's compiled SQL to `dbt-state/catalog/` (OM parses it for column-level lineage; `dbt parse` and the per-model builds leave compiled SQL empty), then `test_all` runs every test into one `dbt-state/target/run_results.json` (OM's test results). The only leaf, `watcher` (`one_failed`), fails the run when any task failed. One tag, `cod`, unscheduled and triggered per day. A parent model under another tag fails DAG parsing: a cross-DAG sensor would have to read Airflow's metadata DB, which Airflow 3 forbids, and one daily flow does not need it.
- **`sim__operating_day`** (scenery, excluded from OM ingestion): unscheduled, `oper_day` in the trigger conf. Streams each file of `lab/data/<source>/<oper_day>/` into a temp table (`copy … csv header`) and upserts it into the source by the table's primary key, read from the catalog (new rows inserted, changed rows replace their earlier version; one transaction per source and day), then closes the day: triggers `dbt__cod` with run id `oper_day__<day>` and waits. Stands in for the closing-of-day event (core system → coordinator → `dbt__cod`) without Kafka. Sources come from `sim__operating_day.yml`. Replaying a day replaces its rows everywhere.

Play days in order (runs queue, one at a time):

```bash
docker compose exec airflow-scheduler airflow dags trigger sim__operating_day --run-id sim__2026-10-01 --conf '{"oper_day": "2026-10-01"}'
```

After changing dbt models, refresh the manifest: `docker compose run --rm airflow-init`.

**Ops scripts** (`lab/ops/`, run on the host of the stack): `gpsql` (psql into `dwh`), `labdbt DAY <dbt args>` (dbt for one operating day with the DAG's vars, seconds — the development loop), `labbackfill FROM TO [selector]` (fast catch-up: per day the sim loader + one `dbt run`, ~20 s a day at 10k; leave the last days to `sim__operating_day` so Airflow has run history), `labday DAY` (state of a day's `dbt__cod` run).
