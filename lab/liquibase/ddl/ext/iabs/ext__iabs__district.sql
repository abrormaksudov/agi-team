--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.district;

create readable external table ext__iabs.district
(
    district_code char(7),
    region_code   char(4),
    district_name text,
    is_city       boolean
)
location ('pxf://core.district?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.district
    owner to gpadmin;
