-- tranzaxis: retail credit and card engine. Runs only in database "tranzaxis". Amounts in tiyin.
SELECT current_database() <> 'tranzaxis' AS skip \gset
\if :skip
\quit
\endif

CREATE SCHEMA tx;

CREATE TABLE tx.client (
    client_id bigint PRIMARY KEY,
    core_customer_code char(8) NOT NULL,
    pinfl char(14) NOT NULL,
    full_name text NOT NULL,
    birth_date date NOT NULL,
    phone text NOT NULL,
    risk_level text NOT NULL,
    created_at timestamptz NOT NULL
);
COMMENT ON TABLE tx.client IS 'Retail client of the credit and card engine, linked to the iABS customer by core_customer_code';

CREATE TABLE tx.contract (
    contract_id bigint PRIMARY KEY,
    client_id bigint NOT NULL,
    contract_type text NOT NULL,
    product_code text NOT NULL,
    status text NOT NULL,
    currency_code char(3) NOT NULL,
    credit_limit bigint,
    interest_rate numeric(5, 2),
    term_months smallint,
    principal_amount bigint,
    settlement_account char(20),
    open_date date NOT NULL,
    close_date date
);
COMMENT ON TABLE tx.contract IS 'Product contract, current state: debit_card, credit_line, microloan';
COMMENT ON COLUMN tx.contract.settlement_account IS 'iABS card account of a debit-card contract';

CREATE TABLE tx.contract_account (
    account_id bigint PRIMARY KEY,
    contract_id bigint NOT NULL,
    account_number char(20) NOT NULL,
    account_role text NOT NULL,
    balance_account char(5) NOT NULL,
    currency_code char(3) NOT NULL,
    status text NOT NULL,
    open_date date NOT NULL,
    close_date date
);
COMMENT ON TABLE tx.contract_account IS 'Accounts of a contract by role (principal, interest, overdue, penalty, write-off, limit, settlement), mirrored into the iABS ledger';
COMMENT ON COLUMN tx.contract_account.account_role IS 'principal, interest, overdue_principal, overdue_interest, penalty, write_off, write_off_interest, limit, settlement';

CREATE TABLE tx.account_turnover (
    account_id bigint NOT NULL,
    oper_day date NOT NULL,
    opening_balance bigint NOT NULL,
    debit_turnover bigint NOT NULL,
    credit_turnover bigint NOT NULL,
    closing_balance bigint NOT NULL,
    PRIMARY KEY (account_id, oper_day)
);
COMMENT ON TABLE tx.account_turnover IS 'Daily turnover of contract accounts, only on days with movement';

CREATE TABLE tx.credit_line_cycle (
    contract_id bigint NOT NULL,
    statement_date date NOT NULL,
    cycle_start_date date NOT NULL,
    due_date date NOT NULL,
    grace_end_date date NOT NULL,
    statement_balance bigint NOT NULL,
    min_payment bigint NOT NULL,
    used_limit bigint NOT NULL,
    paid_amount bigint NOT NULL,
    overdue_start_date date,
    last_payment_date date,
    PRIMARY KEY (contract_id, statement_date)
);
COMMENT ON TABLE tx.credit_line_cycle IS 'Monthly statement cycle of a credit line: statement and due dates, grace end, minimum payment, overdue start';

CREATE TABLE tx.payment_schedule (
    schedule_line_id bigint PRIMARY KEY,
    contract_id bigint NOT NULL,
    schedule_revision smallint NOT NULL,
    debt_kind text NOT NULL,
    due_date date NOT NULL,
    scheduled_amount bigint NOT NULL,
    paid_amount bigint NOT NULL,
    unpaid_amount bigint NOT NULL,
    last_paid_date date
);
COMMENT ON TABLE tx.payment_schedule IS 'Repayment schedule of a contract per revision, debt kind and due date: scheduled, paid and unpaid amounts';

CREATE TABLE tx.delinquency_history (
    contract_id bigint NOT NULL,
    effective_date date NOT NULL,
    state text NOT NULL,
    previous_state text NOT NULL,
    days_past_due integer NOT NULL,
    recorded_at timestamptz NOT NULL,
    PRIMARY KEY (contract_id, effective_date)
);
COMMENT ON TABLE tx.delinquency_history IS 'Delinquency state changes of a contract with days past due as TranzAxis counts them';

CREATE TABLE tx.card (
    card_id bigint PRIMARY KEY,
    contract_id bigint NOT NULL,
    client_id bigint NOT NULL,
    product_type text NOT NULL,
    network text NOT NULL,
    status text NOT NULL,
    masked_pan text NOT NULL,
    issued_at timestamptz NOT NULL,
    expiry_date date NOT NULL,
    pan_hash char(64) NOT NULL
);
COMMENT ON TABLE tx.card IS 'Cards (plastic, virtual, sticker) of the Humo and Uzcard networks; only the masked PAN and a hash are stored';
COMMENT ON COLUMN tx.card.pan_hash IS 'SHA-256 of the full card number; the number itself is never stored here';

CREATE TABLE tx.card_transaction (
    transaction_id bigint PRIMARY KEY,
    card_id bigint NOT NULL,
    contract_id bigint NOT NULL,
    oper_day date NOT NULL,
    registered_at timestamptz NOT NULL,
    transaction_kind text NOT NULL,
    channel text NOT NULL,
    mcc char(4) NOT NULL,
    amount bigint NOT NULL,
    currency_code char(3) NOT NULL,
    amount_uzs bigint NOT NULL,
    status text NOT NULL,
    decline_reason text,
    rrn char(12) NOT NULL
);
COMMENT ON TABLE tx.card_transaction IS 'Card authorisations, clearings and reversals by channel and MCC, in transaction currency and UZS';

CREATE TABLE tx.mcc (
    mcc char(4) PRIMARY KEY,
    description text NOT NULL,
    category_group text NOT NULL,
    is_cash_like boolean NOT NULL,
    is_high_risk boolean NOT NULL
);
COMMENT ON TABLE tx.mcc IS 'Merchant category codes with reporting group and cash-like / high-risk flags (reference data)';
