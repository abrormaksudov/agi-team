--liquibase formatted sql

--changeset abror:1
create table datamart.tx_turnover
(
    oper_day        date,
    account_id      bigint,
    account_number  char(20),
    contract_id     bigint,
    contract_type   text,
    account_role    text,
    balance_account char(5),
    currency_code   char(3),
    opening_balance bigint,
    debit_turnover  bigint,
    credit_turnover bigint,
    closing_balance bigint,
    dwh_job_id      text,
    dwh_created_at  timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (contract_id);

alter table datamart.tx_turnover
    owner to gpadmin;
