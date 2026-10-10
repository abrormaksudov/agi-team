--liquibase formatted sql

--changeset abror:1
create table ods__iabs.region
(
    region_code    char(4),
    region_name    text,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (region_code);

alter table ods__iabs.region
    owner to gpadmin;
