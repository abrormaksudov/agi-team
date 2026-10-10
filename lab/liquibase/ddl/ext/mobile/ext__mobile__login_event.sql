--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__mobile.login_event;

create readable external table ext__mobile.login_event
(
    event_id    bigint,
    user_id     text,
    device_id   text,
    session_id  text,
    event_type  text,
    auth_result text,
    ip_address  text,
    app_version text,
    occurred_at timestamptz
)
location ('pxf://users.login_event?profile=jdbc&server=mobile')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__mobile.login_event
    owner to gpadmin;
