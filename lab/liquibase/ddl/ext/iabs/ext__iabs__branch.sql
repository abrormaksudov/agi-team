--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.branch;

create readable external table ext__iabs.branch
(
    branch_code char(5),
    branch_name text,
    region_code char(4)
)
location ('pxf://core.branch?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.branch
    owner to gpadmin;
