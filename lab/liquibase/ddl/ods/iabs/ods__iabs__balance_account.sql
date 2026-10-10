--liquibase formatted sql

--changeset abror:1
create table ods__iabs.balance_account
(
    code           char(5),
    name           text,
    account_class  text,
    section        text,
    side           text,
    is_contra      boolean,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (code);

alter table ods__iabs.balance_account
    owner to gpadmin;
