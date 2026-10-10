--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__mobile.user_device;

create readable external table ext__mobile.user_device
(
    user_device_id   bigint,
    user_id          text,
    device_id        text,
    is_trusted       boolean,
    is_blocked       boolean,
    is_rooted        boolean,
    malware_detected boolean,
    malware_scan_at  timestamptz,
    first_linked_at  timestamptz
)
location ('pxf://devices.user_device?profile=jdbc&server=mobile')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__mobile.user_device
    owner to gpadmin;
