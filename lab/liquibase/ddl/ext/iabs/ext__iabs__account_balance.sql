--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.account_balance;

create readable external table ext__iabs.account_balance
(
    account_id          bigint,
    oper_day            date,
    opening_balance     bigint,
    debit_turnover      bigint,
    credit_turnover     bigint,
    closing_balance     bigint,
    closing_balance_eqv bigint
)
location ('pxf://core.account_balance?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.account_balance
    owner to gpadmin;
