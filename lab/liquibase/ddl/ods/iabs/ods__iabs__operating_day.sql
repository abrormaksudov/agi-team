--liquibase formatted sql

--changeset abror:1
create table ods__iabs.operating_day
(
    oper_day       date,
    prev_oper_day  date,
    next_oper_day  date,
    is_holiday     boolean,
    is_weekend     boolean,
    day_status     text,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (oper_day);

alter table ods__iabs.operating_day
    owner to gpadmin;
