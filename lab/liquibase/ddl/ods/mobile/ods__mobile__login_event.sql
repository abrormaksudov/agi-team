--liquibase formatted sql

--changeset abror:1
create table ods__mobile.login_event
(
    event_id       bigint,
    user_id        uuid,
    device_id      uuid,
    session_id     uuid,
    event_type     text,
    auth_result    text,
    ip_address     inet,
    app_version    text,
    occurred_at    timestamptz,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (event_id);

alter table ods__mobile.login_event
    owner to gpadmin;
