--liquibase formatted sql

--changeset abror:1
create table datamart.metrics_daily
(
    report_date    date,
    metric_key     text,
    dimension      text,
    period         text,
    value          numeric(24, 4),
    unit           text,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (metric_key);

alter table datamart.metrics_daily
    owner to gpadmin;
