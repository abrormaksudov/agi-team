-- iabs: core banking (customer master, accounts, core ledger). Runs only in database "iabs".
-- Amounts are in tiyin (1/100 UZS) or minor units of the account currency.
SELECT current_database() <> 'iabs' AS skip \gset
\if :skip
\quit
\endif

CREATE SCHEMA core;

CREATE TABLE core.region (region_code char(4) PRIMARY KEY, region_name text NOT NULL);
COMMENT ON TABLE core.region IS 'Regions of Uzbekistan (reference data)';
CREATE TABLE core.district (
    district_code char(7) PRIMARY KEY,
    region_code char(4) NOT NULL,
    district_name text NOT NULL,
    is_city boolean NOT NULL
);
COMMENT ON TABLE core.district IS 'Districts within regions (reference data)';
CREATE TABLE core.branch (branch_code char(5) PRIMARY KEY, branch_name text NOT NULL, region_code char(4) NOT NULL);
COMMENT ON TABLE core.branch IS 'Bank branches: a regional office per region plus the digital head office';
CREATE TABLE core.currency (
    currency_numeric char(3) PRIMARY KEY,
    currency_code char(3) NOT NULL,
    currency_name text NOT NULL,
    minor_units smallint NOT NULL
);
COMMENT ON TABLE core.currency IS 'Currencies with ISO 4217 codes and minor units (reference data)';
CREATE TABLE core.balance_account (
    code char(5) PRIMARY KEY,
    name text NOT NULL,
    account_class text NOT NULL,
    section text NOT NULL,
    side text NOT NULL,
    is_contra boolean NOT NULL
);
COMMENT ON TABLE core.balance_account IS 'Chart of balance accounts (5-digit codes, CBU style)';

CREATE TABLE core.operating_day (
    oper_day date PRIMARY KEY,
    prev_oper_day date NOT NULL,
    next_oper_day date NOT NULL,
    is_holiday boolean NOT NULL,
    is_weekend boolean NOT NULL,
    day_status text NOT NULL
);
COMMENT ON TABLE core.operating_day IS 'Operating days of the bank: open, closed, previous and next day';
CREATE TABLE core.exchange_rate (
    currency_numeric char(3) NOT NULL,
    currency_code char(3) NOT NULL,
    rate_date date NOT NULL,
    rate numeric(14, 4) NOT NULL,
    nominal integer NOT NULL,
    PRIMARY KEY (currency_code, rate_date)
);
COMMENT ON TABLE core.exchange_rate IS 'Official CBU rate in UZS per nominal units of the currency';

CREATE TABLE core.customer (
    customer_id bigint PRIMARY KEY,
    customer_code char(8) NOT NULL UNIQUE,
    customer_type text NOT NULL,
    tax_id char(9),
    branch_code char(5) NOT NULL,
    status text NOT NULL,
    open_date date NOT NULL,
    close_date date,
    updated_at timestamptz NOT NULL
);
COMMENT ON TABLE core.customer IS 'Customer master: individuals and legal entities';
COMMENT ON COLUMN core.customer.tax_id IS 'Taxpayer identification number (INN)';

CREATE TABLE core.customer_individual (
    customer_code char(8) PRIMARY KEY,
    pinfl char(14) NOT NULL,
    last_name text NOT NULL,
    first_name text NOT NULL,
    middle_name text,
    birth_date date NOT NULL,
    gender char(1) NOT NULL,
    passport_series char(2) NOT NULL,
    passport_number char(7) NOT NULL,
    passport_issued date NOT NULL,
    district_code char(7) NOT NULL,
    address text NOT NULL,
    phone text NOT NULL,
    monthly_income bigint
);
COMMENT ON TABLE core.customer_individual IS 'Personal data of individual customers';
COMMENT ON COLUMN core.customer_individual.pinfl IS 'Personal identification number of an individual (14 digits)';

CREATE TABLE core.customer_company (
    customer_code char(8) PRIMARY KEY,
    company_name text NOT NULL,
    registration_date date NOT NULL,
    oked_code char(5) NOT NULL,
    legal_form text NOT NULL,
    director_name text NOT NULL,
    director_pinfl char(14) NOT NULL
);
COMMENT ON TABLE core.customer_company IS 'Legal-entity customers (1:1 with customer): registration, OKED sector, legal form, director';

CREATE TABLE core.account (
    account_id bigint PRIMARY KEY,
    account_number char(20) NOT NULL UNIQUE,
    balance_account char(5) NOT NULL,
    currency_code char(3) NOT NULL,
    customer_code char(8) NOT NULL,
    account_type text NOT NULL,
    status text NOT NULL,
    open_date date NOT NULL,
    close_date date
);
COMMENT ON TABLE core.account IS 'Customer accounts, current state; the 20-digit number encodes balance account, currency, check digit, customer code and sequence';
COMMENT ON COLUMN core.account.account_number IS 'Balance account (5) + currency (3, 000 for UZS) + check digit (1) + customer code (8) + sequence (3)';

CREATE TABLE core.account_balance (
    account_id bigint NOT NULL,
    oper_day date NOT NULL,
    opening_balance bigint NOT NULL,
    debit_turnover bigint NOT NULL,
    credit_turnover bigint NOT NULL,
    closing_balance bigint NOT NULL,
    closing_balance_eqv bigint NOT NULL,
    PRIMARY KEY (account_id, oper_day)
);
COMMENT ON TABLE core.account_balance IS 'Daily balance and turnover, only on days with movement; the balance on a quiet day is the latest row before it';

CREATE TABLE core.payment_document (
    document_id bigint PRIMARY KEY,
    document_date date NOT NULL,
    oper_day date NOT NULL,
    payer_account char(20) NOT NULL,
    payer_bank_code char(5) NOT NULL,
    payer_name text NOT NULL,
    payee_account char(20) NOT NULL,
    payee_bank_code char(5) NOT NULL,
    payee_name text NOT NULL,
    amount bigint NOT NULL,
    currency_code char(3) NOT NULL,
    purpose text NOT NULL,
    state text NOT NULL,
    created_at timestamptz NOT NULL
);
COMMENT ON TABLE core.payment_document IS 'Payment documents (interbank and internal transfers) with payer, payee, amount and state';

CREATE TABLE core.deposit_contract (
    deposit_id bigint PRIMARY KEY,
    contract_number text NOT NULL,
    customer_code char(8) NOT NULL,
    deposit_type text NOT NULL,
    currency_code char(3) NOT NULL,
    amount bigint NOT NULL,
    interest_rate numeric(5, 2) NOT NULL,
    start_date date NOT NULL,
    planned_end_date date NOT NULL,
    account_number char(20) NOT NULL,
    actual_end_date date,
    state text NOT NULL
);
COMMENT ON TABLE core.deposit_contract IS 'Term deposit contracts of individuals: type, currency, amount, rate, start, planned and actual end';
