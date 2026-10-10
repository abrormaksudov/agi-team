--liquibase formatted sql

--changeset abror:1
create table ods__iabs.currency
(
    currency_numeric char(3),
    currency_code    char(3),
    currency_name    text,
    minor_units      smallint,
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (currency_numeric);

alter table ods__iabs.currency
    owner to gpadmin;
