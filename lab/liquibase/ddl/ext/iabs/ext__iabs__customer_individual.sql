--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.customer_individual;

create readable external table ext__iabs.customer_individual
(
    customer_code   char(8),
    pinfl           char(14),
    last_name       text,
    first_name      text,
    middle_name     text,
    birth_date      date,
    gender          char(1),
    passport_series char(2),
    passport_number char(7),
    passport_issued date,
    district_code   char(7),
    address         text,
    phone           text,
    monthly_income  bigint
)
location ('pxf://core.customer_individual?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.customer_individual
    owner to gpadmin;
