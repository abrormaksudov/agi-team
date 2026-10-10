--liquibase formatted sql

--changeset abror:1
create table ods__iabs.branch
(
    branch_code    char(5),
    branch_name    text,
    region_code    char(4),
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (branch_code);

alter table ods__iabs.branch
    owner to gpadmin;
