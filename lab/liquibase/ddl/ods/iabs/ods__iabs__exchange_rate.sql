--liquibase formatted sql

--changeset abror:1
create table ods__iabs.exchange_rate
(
    currency_numeric char(3),
    currency_code    char(3),
    rate_date        date,
    rate             numeric(14, 4),
    nominal          integer,
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (currency_code);

alter table ods__iabs.exchange_rate
    owner to gpadmin;
