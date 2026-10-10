--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.contract_account
(
    account_id      bigint,
    contract_id     bigint,
    account_number  char(20),
    account_role    text,
    balance_account char(5),
    currency_code   char(3),
    status          text,
    open_date       date,
    close_date      date,
    dwh_job_id      text,
    dwh_created_at  timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (account_id);

alter table ods__tranzaxis.contract_account
    owner to gpadmin;
