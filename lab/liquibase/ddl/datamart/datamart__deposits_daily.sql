--liquibase formatted sql

--changeset abror:1
create table datamart.deposits_daily
(
    report_date      date,
    deposit_id       bigint,
    contract_number  text,
    customer_code    char(8),
    deposit_type     text,
    currency_code    char(3),
    contract_amount  bigint,
    interest_rate    numeric(5, 2),
    start_date       date,
    planned_end_date date,
    days_to_maturity integer,
    balance          bigint,
    balance_uzs      bigint,
    accrued_interest bigint,
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (deposit_id);

alter table datamart.deposits_daily
    owner to gpadmin;
