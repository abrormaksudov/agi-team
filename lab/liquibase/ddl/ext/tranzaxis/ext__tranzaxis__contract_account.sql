--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.contract_account;

create readable external table ext__tranzaxis.contract_account
(
    account_id      bigint,
    contract_id     bigint,
    account_number  char(20),
    account_role    text,
    balance_account char(5),
    currency_code   char(3),
    status          text,
    open_date       date,
    close_date      date
)
location ('pxf://tx.contract_account?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.contract_account
    owner to gpadmin;
