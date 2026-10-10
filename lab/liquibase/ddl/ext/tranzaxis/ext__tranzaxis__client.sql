--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.client;

create readable external table ext__tranzaxis.client
(
    client_id          bigint,
    core_customer_code char(8),
    pinfl              char(14),
    full_name          text,
    birth_date         date,
    phone              text,
    risk_level         text,
    created_at         timestamptz
)
location ('pxf://tx.client?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.client
    owner to gpadmin;
