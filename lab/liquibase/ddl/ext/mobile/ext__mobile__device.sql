--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__mobile.device;

create readable external table ext__mobile.device
(
    device_id          text,
    device_fingerprint text,
    platform           text,
    device_model       text,
    os_version         text,
    app_version        text,
    first_seen_at      timestamptz
)
location ('pxf://devices.device?profile=jdbc&server=mobile')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__mobile.device
    owner to gpadmin;
