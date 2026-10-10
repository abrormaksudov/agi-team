--liquibase formatted sql

--changeset abror:1
create table ods__iabs.account
(
    account_id      bigint,
    account_number  char(20),
    balance_account char(5),
    currency_code   char(3),
    customer_code   char(8),
    account_type    text,
    status          text,
    open_date       date,
    close_date      date,
    dwh_job_id      text,
    dwh_created_at  timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (account_id);

alter table ods__iabs.account
    owner to gpadmin;
