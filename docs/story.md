# Story

What the fictional bank in `lab/` contains, so the catalog looks like a bank's and the demo questions have concrete answers. The stack it runs on is in `lab.md`, the catalog in `catalog.md`.

Structures are generalised from the usual shape of iABS / TranzAxis / mobile-backend data (English names, our own logic); values are synthetic, with no actual figures, internal product codes, code lists or cut-over dates.

## Demo questions

1. *How do we decide a contract is overdue, and how are its days past due counted?* → `datamart__contract_classification_daily`, metric, glossary, article.
1. *Where does the 91–180 days figure in September's Overdue Loans Report come from, and did it pass its checks?* → lineage report → classification → TranzAxis / iABS, dbt test results, Airflow run.
1. *I need customers' PINFL with their overdue status — where is it, and may I use it?* → PINFL in `mobile`, KYC and `iabs`, PII tags, downstream lineage, data contract.
1. *Document this table.* → the agent writes descriptions of the one deliberately undocumented mart into OM.

The agent answers from marts and metrics first, then drills into a column's SQL and upstream lineage on follow-up.

## Source systems

### mobile — in-house mobile banking backend

- `app_user` — app account: user_id, phone_number\*, email\*, names\*, date_of_birth\*, pinfl\*, account_status, verification_level, core_customer_id
- `device` — device: device_id, device_fingerprint\*, platform, device_model, os_version, app_version, first/last_seen_at
- `user_device` — user × device: is_trusted, is_blocked, is_rooted, malware_detected, malware_scan_at, last_used_at
- `kyc_attempt` — identity-check attempt: purpose (onboarding, new device, password reset, …), mode, status (new → in progress → hold/fail/success/refuse), last_step, face_match_score, face_photo_ref\*, aml_result
- `login_event` — login / logout / register: user_id, device_id, session_id, event_type, auth_result, ip_address\*, occurred_at

### iabs — core banking (customer master, core ledger)

- `customer` — customer: customer_id, customer_code (8 digits), customer_type, tax_id\*, branch_code, status, open/close date
- `customer_individual` — individual (1:1): customer_code, pinfl\*, names\*, birth_date\*, passport series/number\*, address\*, phone\*
- `customer_company` — legal entity (1:1): customer_code, registration date, sector (OKED), legal form, director\*
- `account` — account: account_id, account_number (20 digits = balance account 5 + currency 3 + check 1 + customer 8 + seq 3), balance_account, currency, customer_code, status, open date
- `balance_account_chart` — balance account (5 digits): code, name, asset/liability, section, active from/to
- `account_balance` — account × day with movement: oper_day, opening/closing balance, debit/credit turnover, UZS equivalents (tiyin)
- `payment_document` — payment: document_id, payer/payee account, payer/payee tax id\*, amount, currency, purpose, state
- `deposit_contract` — term deposit: customer_code, type, currency, amount, rate, start / planned end / actual end, state
- `exchange_rate` — currency × day: currency, rate to UZS, nominal
- `operating_day` — operating day: oper_day, previous / next, status

### tranzaxis — retail credit and card engine

- `contract` — contract (current state): contract_id, client_id, contract_type (credit line, microloan), status, currency, open/close date
- `contract_account` — contract × account role: account_id, account_number (20), role (principal, interest, overdue principal, overdue interest, penalty, write-off, limit), linked account
- `account_turnover` — account × day with movement: opening/closing balance, debit/credit turnover, UZS equivalents
- `credit_line_cycle` — contract × statement cycle: statement date, cycle start, due date, grace end, used limit, overdue start, last payment
- `payment_schedule` — contract × revision × debt kind × due date: scheduled, paid, unpaid amounts, repayment transaction
- `delinquency_history` — contract × state change: state, previous state, days past due, recorded_at
- `card` — card / sticker / virtual card: contract_id, product type, network (Humo, Uzcard), status, issued/expiry, masked_pan, pan_hash\*
- `card_transaction` — authorisation / clearing / reversal: card_id, oper_day, kind, channel (POS, e-com, ATM, contactless), mcc, amount, currency, status
- `mcc` — merchant category: code, description, group, is_cash_like, is_high_risk

`*` = personal data, tagged PII in the catalog. Identity bridge: PINFL (`mobile.app_user` ↔ `iabs.customer_individual` ↔ TranzAxis client), plus `app_user.core_customer_id`. TranzAxis accounts mirror into the iABS ledger, reconciled at closing of day.

## Warehouse (answer layer)

Every source table gets `ext__<source>__<table>` and `ods__<source>__<table>` (conventions in `lab.md`). Marts, each with full column descriptions:

- `datamart__clients_id_xref` — one row per person: app user, iABS customer, TranzAxis client, by PINFL. The PII hub.
- `datamart__tx_turnover` — TranzAxis account × day, UZS equivalents.
- `datamart__contract_classification_tech` — contract × day: balances by account role, the FIFO overdue clock (oldest unpaid slice of overdue principal / interest), last drawdown and repayment, latest statement, first due date.
- `datamart__contract_classification_daily` — **the hub**: contract × day class by first-match cascade (overdue → written off → repaying carried balance → interest only → principal only → dormant → microloan first period → performing), previous class, FIFO and consecutive-day clocks, day band, first-grace flag. Stateful: reads its own previous day.
- `datamart__portfolio_daily` — borrower × day credit exposure, overdue, worst class, NPL flag.
- `datamart__deposits_daily` — deposit × day balance and accrued interest.
- `datamart__card_operations_daily` — card activity by day, network, channel, MCC group, transaction kind.
- `datamart__kyc_funnel_daily` — registrations → onboarding KYC (started, passed, failed, refused, on hold) → first product, per day.
- `datamart__metrics_daily` — long table (report_date, metric_key, dimension, period, value, unit): the metrics below, computed from the marts.
- `datamart_regtech__overdue_loans_report` — monthly CB overdue-loans report: borrower categories × overdue bands (1–30 … 730+), principal and interest, thousand UZS; template rows from `dictionary__overdue_report_rows`.
- `dictionary__overdue_report_rows`, `dictionary__overdue_bands` — the report's template rows and band columns.
- Checks (dbt tests, results ingested into OM): bands sum to each row's total; the report's overdue principal reconciles to the TranzAxis ledger's overdue-principal balance accounts 16400 / 16410 (the generator does not mirror loan accounts into iABS); one class per contract-day; our FIFO days past due match TranzAxis's own delinquency states; balance roll-forward holds.
- `datamart__customer_segments` is left **undocumented** on purpose (demo question 4).

## Metrics (OM Metric entities)

Each has a definition, SQL expression against a mart, type, unit, granularity, related metrics and linked tables: gross loan portfolio; overdue portfolio by band; NPL 90+ ratio; write-offs; microloan disbursements (volume, count); credit-line utilisation; term-deposit balance; active depositors; deposit interest expense; commission income; card payment volume; card decline rate; cards issued; KYC pass rate; active customers; ARPU. Pitfalls stated in descriptions: tiyin vs UZS, CBU-rate FX on the day, stock (level) vs flow (period change), operating vs calendar days, zero vs missing.

## Catalog content

- Glossary (~20 terms, English): PINFL, operating day, closing of day, balance account / chart of accounts, account number structure, days past due, FIFO overdue ageing, NPL, asset quality classes, provisions, write-off, statement cycle, grace period, microloan, credit line, CBU rate, tiyin, Humo / Uzcard, MCC, KYC, NIBBD.
- Articles (Context Center pages): contract classification; overdue loans report; closing of the operating day; customer identity across systems.
- Domains: Lending, Deposits, Cards & Payments, Customers, Regulatory Reporting. Owners per mart. Data contract on `datamart__clients_id_xref` (terms of use for personal data).

## Generator

`lab/generator/` (Python, numpy/polars, deps pinned in `pyproject.toml`), seeded and reproducible; output is gitignored, a fresh clone regenerates it.

- **Agent-based:** each person has a profile (region, age, income band, behaviour type: good payer, sometimes late, defaulter, dormant, written off) and a life story — register → KYC (fails, retries) → customer → accounts, card → spending by MCC → credit line or microloan → each cycle pays per behaviour. Every table is a by-product of the same story.
- **Opening snapshot + daily detail:** day 0 carries contracts opened up to ~18 months earlier with balances and overdue start dates, so every overdue band is populated; then ~60 operating days are simulated in detail, one file set per day for `sim__operating_day`.
- **Invariants asserted by the generator:** opening + turnovers = closing; schedules sum to the principal; days past due follow payments; ledger mirrors TranzAxis.
- **Uzbek realism:** Latin-script Uzbek names, 14 regions, structured synthetic PINFL / passport / +998 phones, Humo and Uzcard (masked PAN + hash only), tiyin amounts, a daily USD/UZS rate, salary-day and weekend seasonality, holidays.
- **Deliberate flaws:** duplicate app accounts sharing a PINFL, one late-arriving file, one failing check traceable upstream.
- **Scale parameter:** `--scale` persons; 10,000 for development and the demo; balances stored only on days with movement.
