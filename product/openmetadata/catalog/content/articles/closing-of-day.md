# Closing of the operating day

The closing of day turns one operating day in the source systems into checked warehouse data and refreshed catalog metadata. Every mart, metric and Central Bank report is as of the end of an operating day.

## Operating day vs calendar day

- **`oper_day`** is the bank's business date. It travels explicitly, in the trigger conf and then as the dbt var `oper_day`, and is never derived from the Airflow run's logical date. Per-day tables stamp it as `oper_day` or `report_date`.
- **Time zone: Asia/Tashkent (UZT, UTC+5).** A timestamp belongs to the operating day of its UZT date. Event loads use a whole-UZT-day window, `load_from_datetime ≤ ts < load_to_datetime`: for 2026-09-30, from 2026-09-29 19:00 UTC to 2026-09-30 19:00 UTC. Bucket timestamps the same way, `(ts at time zone 'Asia/Tashkent')::date` as in `datamart.kyc_funnel_daily`, never by the UTC date.
- **Calendar:** `ods__iabs.operating_day` (previous and next day, `is_weekend`, `is_holiday`, `day_status`). Days are closed one by one, weekends and holidays included; the classification's previous day is the calendar day before.
- **History day 2026-07-31:** the first closed day. Its files carry all earlier history, so day-sliced models load everything up to it.

## How a day flows

1. **Sources deliver the day.** The core systems' closing-of-day event loads the day into iABS, mobile and TranzAxis; here it is the DAG `sim__operating_day`, kept out of the catalog. It upserts the day's files by primary key, one transaction per source, then triggers `dbt__cod` with run id `oper_day__<day>` and waits.
1. **`dbt__cod` builds the warehouse** (Airflow, unscheduled, one run at a time): one task per dbt model, named after the model, in `ref()` dependency order. Each task runs `dbt build --select <model>` for the day: load, then the model's tests. Results go to `dbt_test__audit.dq_test_log`; every row written carries the run id in `dwh_job_id`.
1. **Final tasks** run even when a model failed (trigger rule `all_done`): `compile_for_catalog` compiles every model so the catalog can parse column-level lineage; `test_all` runs all tests once more into a single results file.
1. **The catalog picks it up** through its ingestion pipelines: `greenplum_dbt` hourly at :15 (descriptions, owners, lineage, test results), `lab_airflow_metadata` hourly at :45 (DAG, tasks, run statuses of the last 7 days), `greenplum_metadata` daily (tables, columns), source usage daily.

## Load strategies

| Strategy | Tables | On replay |
| --- | --- | --- |
| Full reload, `truncate+insert` | current state: reference data, customers, accounts, contracts, schedules, statements, app users, devices, KYC attempts; `datamart.clients_id_xref`; dictionaries | holds the sources' current state, no history |
| Daily facts, `delete+insert` by day | `ods__iabs.account_balance`, `ods__iabs.payment_document`, `ods__tranzaxis.account_turnover`, `ods__tranzaxis.card_transaction`, `ods__tranzaxis.delinquency_history`; `ods__mobile.login_event` by `event_id` within the UZT window | the day's rows replaced |
| Per-day marts, `delete+insert` on `report_date` / `oper_day` | classification, portfolio, deposits, card operations, KYC funnel, metrics, `datamart.tx_turnover`, the Central Bank report | the day's rows replaced |

ODS full reloads are checked with `equal_row_count` against the source. Day filters compare the raw source column, so PXF pushes them down to the source. Liquibase owns every table's DDL and dbt only fills it (`on_schema_change = fail`).

## Replaying a day

- Trigger `sim__operating_day` with conf `{"oper_day": "<day>"}`: it reloads the sources and resets the `dbt__cod` run `oper_day__<day>`. Rows are replaced, never duplicated.
- To rerun only the warehouse, clear the failed task and its downstream tasks in that `dbt__cod` run.
- `datamart.contract_classification_daily` reads its own previous day: after replaying a day, replay every later day in order. Runs queue one at a time.

## When a check fails

- **Severity `error`** (most tests): the model's task fails, its downstream models do not run that day (`upstream_failed`), `test_all` fails on the same check, and the `dbt__cod` run ends failed, and with it `sim__operating_day`.
- **Severity `warn`** (for example `datamart__contract_classification_daily__dpd_matches_tranzaxis_state`): logged, the day continues.

What to do:

1. **Find it:** the table's data-quality tab in the catalog; Airflow `dbt__cod`, run `oper_day__<day>`, the red task (named after the model) and its log; or `dbt_test__audit.dq_test_log` rows whose `status` is not `pass`.
1. **Trace upstream** with column-level lineage to the first table whose checks fail or whose data changed: that is the root cause.
1. **Fix** the source data or the model, then replay from that day forward.
1. **Hold** the day's figures, the Central Bank report included, until its checks pass.
