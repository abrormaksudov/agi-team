--liquibase formatted sql

--changeset abror:1
create table dictionary.overdue_bands
(
    band_code      text,
    band_name      text,
    min_days       integer,
    max_days       integer,
    sort_order     smallint,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed replicated;

alter table dictionary.overdue_bands
    owner to gpadmin;
