--liquibase formatted sql

--changeset abror:1
create table ods__iabs.district
(
    district_code  char(7),
    region_code    char(4),
    district_name  text,
    is_city        boolean,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (district_code);

alter table ods__iabs.district
    owner to gpadmin;
