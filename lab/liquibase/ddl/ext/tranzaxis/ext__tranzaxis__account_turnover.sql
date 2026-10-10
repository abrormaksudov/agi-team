--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.account_turnover;

create readable external table ext__tranzaxis.account_turnover
(
    account_id      bigint,
    oper_day        date,
    opening_balance bigint,
    debit_turnover  bigint,
    credit_turnover bigint,
    closing_balance bigint
)
location ('pxf://tx.account_turnover?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.account_turnover
    owner to gpadmin;
