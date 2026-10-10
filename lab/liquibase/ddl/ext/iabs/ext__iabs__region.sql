--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.region;

create readable external table ext__iabs.region
(
    region_code char(4),
    region_name text
)
location ('pxf://core.region?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.region
    owner to gpadmin;
