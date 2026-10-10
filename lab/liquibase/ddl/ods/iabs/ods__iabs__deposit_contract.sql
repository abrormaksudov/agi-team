--liquibase formatted sql

--changeset abror:1
create table ods__iabs.deposit_contract
(
    deposit_id       bigint,
    contract_number  text,
    customer_code    char(8),
    deposit_type     text,
    currency_code    char(3),
    amount           bigint,
    interest_rate    numeric(5, 2),
    start_date       date,
    planned_end_date date,
    account_number   char(20),
    actual_end_date  date,
    state            text,
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (deposit_id);

alter table ods__iabs.deposit_contract
    owner to gpadmin;
