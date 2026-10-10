--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.mcc;

create readable external table ext__tranzaxis.mcc
(
    mcc            char(4),
    description    text,
    category_group text,
    is_cash_like   boolean,
    is_high_risk   boolean
)
location ('pxf://tx.mcc?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.mcc
    owner to gpadmin;
