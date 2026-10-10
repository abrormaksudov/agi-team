--liquibase formatted sql

--changeset abror:1
create table ods__mobile.user_device
(
    user_device_id   bigint,
    user_id          uuid,
    device_id        uuid,
    is_trusted       boolean,
    is_blocked       boolean,
    is_rooted        boolean,
    malware_detected boolean,
    malware_scan_at  timestamptz,
    first_linked_at  timestamptz,
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (user_device_id);

alter table ods__mobile.user_device
    owner to gpadmin;
