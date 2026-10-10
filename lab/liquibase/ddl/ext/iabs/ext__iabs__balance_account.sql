--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.balance_account;

create readable external table ext__iabs.balance_account
(
    code          char(5),
    name          text,
    account_class text,
    section       text,
    side          text,
    is_contra     boolean
)
location ('pxf://core.balance_account?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.balance_account
    owner to gpadmin;
