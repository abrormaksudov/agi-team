--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.contract;

create readable external table ext__tranzaxis.contract
(
    contract_id        bigint,
    client_id          bigint,
    contract_type      text,
    product_code       text,
    status             text,
    currency_code      char(3),
    credit_limit       bigint,
    interest_rate      numeric(5, 2),
    term_months        smallint,
    principal_amount   bigint,
    settlement_account char(20),
    open_date          date,
    close_date         date
)
location ('pxf://tx.contract?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.contract
    owner to gpadmin;
