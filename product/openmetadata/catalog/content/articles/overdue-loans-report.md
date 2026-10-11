# Overdue Loans Report

Monthly report to the Central Bank of Uzbekistan on overdue retail loans: borrower categories (rows) × overdue bands (columns), with the number of overdue contracts and their overdue principal and interest. Table `datamart_regtech.overdue_loans_report`, owned by Regulatory Reporting.

## As-of date, grain, units

- **As of** the end of the last calendar day of the month (`report_date`). The model runs at every closing of day but writes rows only on a month end: the September report is `report_date = 2026-09-30`, written by the `dbt__cod` run `oper_day__2026-09-30`.
- **Grain:** `report_date` × `row_code` × `band_code`. Every template cell is present, zeros included: 4 rows × 8 columns = 32 cells.
- **Units:** thousand UZS, `numeric(20,5)`. The ledger is in tiyin and 1 thousand UZS = 100,000 tiyin, so every cell is exact to the tiyin, without rounding.
- Replaying the month-end day replaces the report (`delete+insert` on `report_date`).

## Template

Rows, `dictionary.overdue_report_rows`:

| row_code | Row | Contracts counted |
| --- | --- | --- |
| 0100 | Loans to individuals, total | all overdue credit lines and microloans |
| 0110 | of which: microloans | `contract_type = 'microloan'` |
| 0120 | of which: credit lines on cards | `contract_type = 'credit_line'` |
| 0200 | Loans to legal entities and individual entrepreneurs | none: every TranzAxis retail loan is an individual's, so the row is zero |

Columns, `dictionary.overdue_bands`: `1_30` (up to 30 days, from 0), `31_60`, `61_90`, `91_180`, `181_360`, `361_730` (361 days to 2 years), `730_plus` (over 2 years), `total`.

## How a cell is computed

1. Take the rows of `datamart.contract_classification_daily` for `report_date` with `classification = 'overdue'`.
1. Assign each contract to every row with `borrower_type = 'individual'` whose `contract_type` is empty or equals the contract's: row 0100, plus 0110 or 0120.
1. The column is the contract's `overdue_band`, set by its FIFO days past due on the report date.
1. Per row × band: `contracts_count` = number of contracts; `overdue_principal_thousand_uzs` = Σ `overdue_principal_balance` / 100,000; `overdue_interest_thousand_uzs` = Σ `overdue_interest_balance` / 100,000; `overdue_total_thousand_uzs` = principal + interest.
1. Column `total` = the sum of the seven bands.

Not in the report: penalties, principal and interest not yet due, written-off contracts.

So "the 91–180 days figure in September" is row 0100 (or 0110 / 0120), `band_code = '91_180'`, `report_date = 2026-09-30`: contracts whose oldest unpaid due was 91 to 180 days old on 30 September.

## Lineage

1. **TranzAxis**, the retail credit engine (schema `tx`): `contract`, `contract_account`, `account_turnover`, `credit_line_cycle`, `payment_schedule`.
1. **PXF external tables** `ext__tranzaxis.*` in Greenplum: they hold no data and read TranzAxis live over JDBC at load time.
1. **ODS** `ods__tranzaxis.*`: contracts, contract accounts, statements and schedules reloaded in full each day; `account_turnover` loads the day's movements.
1. **`datamart.tx_turnover`**, the TranzAxis ledger: account × day movement with contract, account role and 5-digit balance account.
1. **`datamart.contract_classification_tech`**: balances by account role and the FIFO clock per contract.
1. **`datamart.contract_classification_daily`**: class and overdue band.
1. **`datamart_regtech.overdue_loans_report`**, with the two dictionaries.

No iABS table feeds the report: retail loan accounts live in the TranzAxis ledger. TranzAxis's `delinquency_history` only cross-checks the days past due. Every model is a task named after it in the Airflow DAG `dbt__cod`; the catalog shows the chain at column level.

## Checks

| Test | Proves |
| --- | --- |
| `datamart_regtech__overdue_loans_report__bands_sum_to_total` | in every row the seven bands add up to `total`: contracts, principal, interest |
| `datamart_regtech__overdue_loans_report__reconciles_to_ledger` | row 0100 total overdue principal equals the closing balance of balance accounts 16400 (credit lines) and 16410 (microloans) in `datamart.tx_turnover` on the report date |
| `datamart_regtech__overdue_loans_report__one_cell_per_row_band` | one cell per `report_date` × `row_code` × `band_code` |
| `…__relationships_row_code`, `…__relationships_band_code`, `…__not_null_report_date` | only template rows and columns; the date is set |
| `datamart__contract_classification_daily__dpd_matches_tranzaxis_state` (severity warn) | our FIFO days past due agree with TranzAxis's delinquency states |
| `datamart__contract_classification_daily__band_iff_overdue`, `…__one_class_per_contract_day` | a band exactly for overdue contracts; one class per contract and day |
| `datamart__tx_turnover__balance_roll_forward`, `ods__tranzaxis__account_turnover__balance_roll_forward` | opening + debits − credits = closing in the ledger |
| `ods__tranzaxis__contract__equal_row_count` and the other full-reload counts | the ODS holds every source row |

Submit only when every check for the report date is green. Results: each table's data-quality tab in the catalog, the `dbt__cod` run of the day, or `dbt_test__audit.dq_test_log`.
