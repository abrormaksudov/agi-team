--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.account;

create readable external table ext__iabs.account
(
    account_id      bigint,
    account_number  char(20),
    balance_account char(5),
    currency_code   char(3),
    customer_code   char(8),
    account_type    text,
    status          text,
    open_date       date,
    close_date      date
)
location ('pxf://core.account?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.account
    owner to gpadmin;
