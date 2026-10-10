--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.currency;

create readable external table ext__iabs.currency
(
    currency_numeric char(3),
    currency_code    char(3),
    currency_name    text,
    minor_units      smallint
)
location ('pxf://core.currency?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.currency
    owner to gpadmin;
