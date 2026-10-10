--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.deposit_contract;

create readable external table ext__iabs.deposit_contract
(
    deposit_id       bigint,
    contract_number  text,
    customer_code    char(8),
    deposit_type     text,
    currency_code    char(3),
    amount           bigint,
    interest_rate    numeric(5, 2),
    start_date       date,
    planned_end_date date,
    account_number   char(20),
    actual_end_date  date,
    state            text
)
location ('pxf://core.deposit_contract?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.deposit_contract
    owner to gpadmin;
