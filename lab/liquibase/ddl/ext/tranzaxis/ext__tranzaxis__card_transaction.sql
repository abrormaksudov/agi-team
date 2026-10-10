--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.card_transaction;

create readable external table ext__tranzaxis.card_transaction
(
    transaction_id   bigint,
    card_id          bigint,
    contract_id      bigint,
    oper_day         date,
    registered_at    timestamptz,
    transaction_kind text,
    channel          text,
    mcc              char(4),
    amount           bigint,
    currency_code    char(3),
    amount_uzs       bigint,
    status           text,
    decline_reason   text,
    rrn              char(12)
)
location ('pxf://tx.card_transaction?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.card_transaction
    owner to gpadmin;
