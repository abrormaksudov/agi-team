--liquibase formatted sql

--changeset abror:1
create table ods__mobile.device
(
    device_id          uuid,
    device_fingerprint text,
    platform           text,
    device_model       text,
    os_version         text,
    app_version        text,
    first_seen_at      timestamptz,
    dwh_job_id         text,
    dwh_created_at     timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (device_id);

alter table ods__mobile.device
    owner to gpadmin;
