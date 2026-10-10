--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.exchange_rate;

create readable external table ext__iabs.exchange_rate
(
    currency_numeric char(3),
    currency_code    char(3),
    rate_date        date,
    rate             numeric(14, 4),
    nominal          integer
)
location ('pxf://core.exchange_rate?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.exchange_rate
    owner to gpadmin;
