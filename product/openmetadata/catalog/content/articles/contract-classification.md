# Contract classification

Every operating day the bank gives each open credit contract exactly one class. The classification is the hub the Central Bank overdue-loans report, the borrower portfolio and the credit-risk metrics are built from.

## Where it lives

| Table | Grain | Holds |
| --- | --- | --- |
| `datamart.contract_classification_tech` | contract × operating day | balances by account role, the FIFO overdue clock, last drawdown and repayment, latest credit-line statement, first due date |
| `datamart.contract_classification_daily` | contract × operating day | class, previous class, both overdue clocks, overdue band, first-grace flag |

- **Scope:** TranzAxis contracts (`ods__tranzaxis.contract`) of type `credit_line` or `microloan`, status not `closed`, opened on or before the day. Written-off contracts stay in scope.
- **Balances:** per account role, the closing balance of its latest movement on or before the day in `datamart.tx_turnover`, the TranzAxis ledger. Amounts in tiyin.
- **Load:** `report_date` = the operating day; `delete+insert` on `report_date`, so replaying a day replaces it. Owner: Data Platform.

## The cascade: first match wins

| # | Class | Rule on the day |
| --- | --- | --- |
| 1 | `overdue` | `overdue_principal_balance + overdue_interest_balance > 0` |
| 2 | `written_off` | `written_off_principal + written_off_interest > 0` (off-balance write-off accounts) |
| 3 | `repaying_carried_balance` | credit line, `principal_balance > 0` and `interest_balance > 0`: a balance carried past a statement accrues interest |
| 4 | `interest_only` | `principal_balance = 0` and `interest_balance > 0`, either product |
| 5 | `principal_only` | credit line, `principal_balance > 0`, no interest: drawn within the grace period |
| 6 | `dormant` | credit line, no balance, nothing drawn for over 90 days: `coalesce(last_draw_date, open_date) < report_date - 90` |
| 7 | `microloan_first_period` | microloan, `report_date <= first_due_date` |
| 8 | `performing` | everything else |

Any overdue principal or interest makes a contract `overdue`, whatever else holds. A penalty balance alone does not.

## Two clocks

**FIFO days past due** (`days_past_due`, both tables). Every debit to an overdue-principal or overdue-interest account is a slice dated by its posting day; TranzAxis moves an unpaid due there on its due date. Repayments clear the oldest slice first, so the oldest unpaid slice is the first debit whose running total exceeds everything credited to that account. `days_past_due_principal` and `days_past_due_interest` count calendar days from `oldest_unpaid_principal_date` and `oldest_unpaid_interest_date`; `days_past_due` counts from the earlier of the two and is 0 when nothing is overdue. It drives the overdue band and the NPL flag (`datamart.portfolio_daily.is_npl`: over 90).

**Consecutive overdue days** (`consecutive_overdue_days`, daily table only): days overdue without a break, today included; 0 when not overdue. Overdue yesterday: yesterday's value + 1. Another class yesterday: 1. No row yesterday: `days_past_due + 1`. Partial repayments do not move it back.

Example: the dues of 10 Aug and 10 Sep are unpaid; on 20 Sep the borrower repays the 10 Aug due. FIFO days past due drop from 41 to 10; consecutive overdue days keep counting (42).

## Overdue bands

`overdue_band` is set only for class `overdue`, from `days_past_due`. Codes match `dictionary.overdue_bands`:

| Band       | Days past due                  |
| ---------- | ------------------------------ |
| `1_30`     | 0–30 (0 = the due date itself) |
| `31_60`    | 31–60                          |
| `61_90`    | 61–90                          |
| `91_180`   | 91–180                         |
| `181_360`  | 181–360                        |
| `361_730`  | 361–730                        |
| `730_plus` | 731 and more                   |

TranzAxis writes a contract off at 361 days past due, so the last two bands normally stay empty.

## Stateful

`datamart.contract_classification_daily` reads its own row for `report_date - 1` to carry `previous_classification`, `days_in_classification` and `consecutive_overdue_days`. Therefore:

- days are closed in order; a missing previous day restarts the clocks as if every contract were new;
- after replaying a day, replay every later day too.

`is_first_grace_period` is true for a credit line before the due date of its first statement.

## Checks

| Test | Guards |
| --- | --- |
| `datamart__contract_classification_daily__one_class_per_contract_day` | one row per `report_date` × `contract_id` |
| `datamart__contract_classification_daily__accepted_values_classification`, `…__not_null_classification` | always one of the eight classes |
| `datamart__contract_classification_daily__band_iff_overdue` | a band if and only if the class is `overdue` |
| `datamart__contract_classification_daily__dpd_matches_tranzaxis_state` (severity warn) | our days past due, bucketed like TranzAxis, equal TranzAxis's latest state in `ods__tranzaxis.delinquency_history` |
| `datamart__contract_classification_tech__unique_report_date_contract_id`, `…__days_past_due_not_negative` | grain; the clock never negative |
| `datamart__tx_turnover__balance_roll_forward`, `datamart__tx_turnover__unique_account_id_oper_day` | the ledger underneath: opening + debits − credits = closing |

Results are logged to `dbt_test__audit.dq_test_log` and shown on each table's data-quality tab in the catalog.
