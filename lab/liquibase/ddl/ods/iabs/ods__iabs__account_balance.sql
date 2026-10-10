--liquibase formatted sql

--changeset abror:1
create table ods__iabs.account_balance
(
    account_id          bigint,
    oper_day            date,
    opening_balance     bigint,
    debit_turnover      bigint,
    credit_turnover     bigint,
    closing_balance     bigint,
    closing_balance_eqv bigint,
    dwh_job_id          text,
    dwh_created_at      timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (account_id);

alter table ods__iabs.account_balance
    owner to gpadmin;
